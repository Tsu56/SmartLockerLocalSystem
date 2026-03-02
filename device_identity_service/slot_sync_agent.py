"""
Slot Sync Agent
ดึงข้อมูล Slot จาก Cloud Server มาเก็บใน device_identity_service
"""
import requests
import time
from datetime import datetime, timezone
from sqlmodel import select, func
from database import Session, engine
from database.models import Slot, DeviceInfo
from getkey import get_internal_shared_secret
import os
from dotenv import load_dotenv

load_dotenv()

CLOUD_SERVER_URL = os.getenv("SERVER_URL", "")
INTERNAL_SECRET = get_internal_shared_secret()


def get_auth_headers():
    """ดึง authentication headers จาก device_identity_service's own data"""
    try:
        with Session(engine) as session:
            device = session.exec(select(DeviceInfo)).first()
            if not device or not device.api_token_encrypted:
                return None
            
            from encryption import decrypt_data
            decrypted_token = decrypt_data(device.api_token_encrypted)
            return {
                "locker_id": device.locker_id,
                "api_token": f"Bearer {decrypted_token}"
            }
    except Exception as e:
        print(f"❌ Failed to get auth headers: {e}")
        return None


def process_slot_sync(session, slot_data):
    """
    จัดการข้อมูล Slot แบบ Upsert
    - Insert ถ้ายังไม่มี
    - Update ถ้ามีอยู่แล้ว
    """
    slot_id = slot_data.get("slot_id")
    
    # ค้นหา Slot ที่มีอยู่
    slot = session.exec(select(Slot).where(Slot.slot_id == slot_id)).first()
    
    server_now_str = slot_data.get("updated_at") or datetime.now(timezone.utc).isoformat()
    server_now = datetime.fromisoformat(server_now_str.replace('Z', '+00:00'))
    
    if not slot:
        # สร้าง Slot ใหม่
        slot = Slot(slot_id=slot_id)
        if slot_data.get("created_at"):
            slot.created_at = datetime.fromisoformat(slot_data["created_at"].replace('Z', '+00:00'))
        print(f"🆕 Sync: Preparing New Slot {slot_id}")
    
    # Mapping Slot Data
    slot.locker_id = slot_data.get("locker_id")
    slot.slot_status = slot_data.get("slot_status", "active")
    slot.capacity = slot_data.get("capacity", 0)
    slot.updated_at = server_now
    
    # จัดการ Soft Delete
    delete_ts = slot_data.get("deleted_at")
    if delete_ts:
        slot.deleted_at = datetime.fromisoformat(delete_ts.replace('Z', '+00:00'))
    else:
        slot.deleted_at = None
    
    session.add(slot)


def run_slot_sync_logic():
    """
    Logic หลักในการดึงข้อมูล Slot จาก Server มาลงเครื่อง
    แยกออกมาเพื่อให้เรียกใช้ได้จากทั้ง Agent และ Manual Trigger
    
    Returns:
        dict: สถานะการ sync พร้อมจำนวนข้อมูลที่อัปเดต
    """
    try:
        # 1. ขอ Auth Headers
        cloud_headers = get_auth_headers()
        if not cloud_headers:
            return {
                "status": "error",
                "message": "Device not activated or missing auth headers",
                "synced_count": 0
            }
        
        with Session(engine) as session:
            # 2. หาเวลาที่ Sync ล่าสุดจากตาราง Slot
            last_sync_time = "1970-01-01T00:00:00Z"
            
            slot_max = session.exec(select(
                func.max(Slot.created_at),
                func.max(Slot.updated_at),
                func.max(Slot.deleted_at)
            )).first()
            
            all_ts = [ts for ts in (slot_max or []) if ts is not None]
            
            if all_ts:
                last_sync_time = max(all_ts).replace(tzinfo=timezone.utc).isoformat()
            
            # 3. ยิงไปที่ Server
            sync_url = f"{CLOUD_SERVER_URL}/slot/sync/slots"
            params = {"last_sync": last_sync_time}
            
            print(f"📡 Syncing slots from: {sync_url}")
            print(f"   Last sync: {last_sync_time}")
            
            response = requests.get(sync_url, headers=cloud_headers, params=params, timeout=15)
            
            if response.status_code == 200:
                sync_data = response.json()
                slots_to_sync = sync_data.get("data", [])
                
                if slots_to_sync:
                    print(f"🔄 Sync: Received {len(slots_to_sync)} slot updates")
                    for slot_data in slots_to_sync:
                        process_slot_sync(session, slot_data)
                    session.commit()
                    print(f"✅ Synced {len(slots_to_sync)} slots successfully")
                    return {
                        "status": "success",
                        "message": f"Synced {len(slots_to_sync)} slots",
                        "synced_count": len(slots_to_sync)
                    }
                else:
                    print("✅ No new slot updates from server")
                    return {
                        "status": "success",
                        "message": "No new updates",
                        "synced_count": 0
                    }
            else:
                error_msg = f"Server responded with status {response.status_code}"
                print(f"❌ Sync Error: {error_msg}")
                return {
                    "status": "error",
                    "message": error_msg,
                    "synced_count": 0
                }
                
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Slot Sync Error: {error_msg}")
        return {
            "status": "error",
            "message": error_msg,
            "synced_count": 0
        }


def slot_sync_agent():
    """
    Agent ทำงานเบื้องหลัง คอยดึงข้อมูล Slot จาก Server มาอัปเดตลงตู้
    ทำงานทุก 5 นาที
    """
    print("🚀 Slot Sync Agent Started...")
    time.sleep(10)  # รอให้ app เริ่มต้นเสร็จก่อน
    
    while True:
        try:
            result = run_slot_sync_logic()
            if result["status"] == "success":
                print(f"📊 Slot Sync: {result['synced_count']} records updated")
        except Exception as e:
            print(f"📡 Slot Sync Agent Error: {e}")
        
        # รอ 5 นาทีก่อน sync ครั้งต่อไป
        time.sleep(300)


def start_slot_sync_agent():
    """เริ่มต้น Slot Sync Agent ใน background thread"""
    import threading
    sync_thread = threading.Thread(target=slot_sync_agent, daemon=True)
    sync_thread.start()
    print("✅ Slot Sync Agent thread started")
