import requests
from dotenv import load_dotenv
import os
import threading
import time
from fastapi import APIRouter, HTTPException, status, Header, BackgroundTasks
from sqlmodel import select, delete
from datetime import datetime, timezone
from typing import List

from database import SessionDep, engine, Session
from database.models import DeviceInfo, Slot
from database.schema import (
    DeviceInfoCreate, 
    DeviceInfoPublic, 
    DeviceInfoUpdate, 
    DeviceActivationRequest,
    SlotPublic
)
from encryption import encrypt_data, decrypt_data
from getkey import get_internal_shared_secret
from slot_sync_agent import run_slot_sync_logic

router = APIRouter(prefix="/device", tags=["Device Identification"])

load_dotenv()

CLOUD_SERVER_URL = os.getenv("SERVER_URL", "")

INTERNAL_SHARED_SECRET = get_internal_shared_secret()

# --- Internal API for other services ---
@router.get("/internal/auth-headers")
def get_internal_auth_headers(x_internal_secret: str = Header(None, alias="X-Internal-Secret")):
    """
    Endpoint สำหรับให้ Service ภายในตู้มาขอ Header 
    เพิ่มความปลอดภัยด้วยการเช็ค Shared Secret ก่อนคืนค่าข้อมูลลับ
    """
    # 1. ตรวจสอบรหัสลับภายใน (ป้องกันการเรียกจากบุคคลภายนอก)
    if not x_internal_secret or x_internal_secret != INTERNAL_SHARED_SECRET:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Access Denied: Invalid internal secret"
        )

    with Session(engine) as session:
        device = session.exec(select(DeviceInfo)).first()
        if not device or not device.api_token_encrypted:
            raise HTTPException(status_code=404, detail="Device not activated")
        
        try:
            # ถอดรหัสเพื่อส่งให้ Service ภายในนำไปใช้งาน
            decrypted_token = decrypt_data(device.api_token_encrypted)
            return {
                "locker_id": device.locker_id,
                "api_token": f"Bearer {decrypted_token}"
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail="Decryption failed")

@router.get("/internal/slots", response_model=List[dict])
def get_all_slots(x_internal_secret: str = Header(None, alias="X-Internal-Secret")):
    """
    Endpoint สำหรับให้ Service ภายในตู้ (เช่น product_management_service) 
    มาดึงข้อมูลช่อง (Slot) ทั้งหมด
    """
    # 1. ตรวจสอบรหัสลับภายใน
    if not x_internal_secret or x_internal_secret != INTERNAL_SHARED_SECRET:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Access Denied: Invalid internal secret"
        )

    with Session(engine) as session:
        # คืนเฉพาะ slot ที่ยังไม่ถูก soft-delete
        slots = session.exec(
            select(Slot).where(Slot.deleted_at.is_(None))
        ).all()
        return [
            {
                "slot_id": slot.slot_id,
                "locker_id": slot.locker_id,
                "slot_status": slot.slot_status,
                "capacity": slot.capacity,
                "id": slot.id,
                "created_at": slot.created_at,
                "updated_at": slot.updated_at,
                "deleted_at": slot.deleted_at,
            }
            for slot in slots
        ]

def perform_local_revoke():
    """ลบข้อมูลตัวตนในเครื่องทิ้ง เมื่อ Server สั่ง Revoke"""
    with Session(engine) as session:
        session.exec(delete(DeviceInfo))
        session.exec(delete(Slot))
        session.commit()
    print("⚠️  CRITICAL: Device Identity has been revoked and wiped locally.")

# --- Heartbeat Agent Logic ---
def run_heartbeat_agent():
    try:
        with Session(engine) as session:
            device = session.exec(select(DeviceInfo)).first()
            
            if device and device.api_token_encrypted:
                # ถอดรหัส api_token ก่อนส่งไป
                decrypted_token = decrypt_data(device.api_token_encrypted)
                # เตรียมข้อมูลส่งไปเช็คสถานะที่ Cloud Server
                headers = {
                    "locker_id": device.locker_id,
                    "api_token": f"Bearer {decrypted_token}"
                }
                
                # ยิงไปที่ Endpoint สำหรับเช็คสถานะ (ที่ฝั่ง Express.js เตรียมไว้)
                response = requests.post(
                    f"{CLOUD_SERVER_URL}/locker/heartbeat",
                    headers=headers,
                    timeout=15
                )

                print(f"📡 Sending heartbeat to: {CLOUD_SERVER_URL}/locker/heartbeat")

                print(f"📡 [HEARTBEAT RESPONSE] Status: {response.status_code}")
                # ถ้า Server ตอบกลับว่า 403 (Forbidden) หรือ 401 (Unauthorized)
                # แสดงว่าตู้ถูกถอดสิทธิ์ หรือ Token ไม่ถูกต้องแล้ว
                if response.status_code in [401, 403]:
                    print(f"❌ Revoke detected (Status: {response.status_code})")
                    print(f"Response: {response.text}")
                    perform_local_revoke()
                
                elif response.status_code == 200:
                    # อัปเดตเวลาที่ Sync ล่าสุดลงฐานข้อมูลตัวเอง
                    device.last_sync = datetime.now(timezone.utc)
                    session.add(device)
                    session.commit()
                    # print(f"✅ Heartbeat OK: {device.device_id}")
            else:
                pass

    except requests.exceptions.ConnectionError as ce:
        print(f"📡 Heartbeat Connection Error: Cannot connect to {CLOUD_SERVER_URL}")

    except Exception as e:
        print(f"📡 Heartbeat Agent Error: {e}")
            
def heartbeat_agent():
    """
    Agent ทำงานเบื้องหลัง คอยตรวจสอบสถานะกับ Server
    จะถูกเรียกทำงานเพียงครั้งเดียวเมื่อ Service เริ่มต้น
    """
    print("🚀 Heartbeat Agent Started...")

    time.sleep(5)

    session_http = requests.Session()

    while True:
        try:
            with Session(engine) as session:
                device = session.exec(select(DeviceInfo)).first()
                
                if device and device.api_token_encrypted:
                    # ถอดรหัส api_token ก่อนส่งไป
                    decrypted_token = decrypt_data(device.api_token_encrypted)
                    # เตรียมข้อมูลส่งไปเช็คสถานะที่ Cloud Server
                    headers = {
                        "locker_id": device.locker_id,
                        "api_token": f"Bearer {decrypted_token}"
                    }
                    
                    # ยิงไปที่ Endpoint สำหรับเช็คสถานะ (ที่ฝั่ง Express.js เตรียมไว้)
                    response = requests.post(
                        f"{CLOUD_SERVER_URL}/locker/heartbeat",
                        headers=headers,
                        timeout=15
                    )

                    # ถ้า Server ตอบกลับว่า 403 (Forbidden) หรือ 401 (Unauthorized)
                    # แสดงว่าตู้ถูกถอดสิทธิ์ หรือ Token ไม่ถูกต้องแล้ว
                    if response.status_code in [401, 403]:
                        print(f"❌ Revoke detected (Status: {response.status_code})")
                        print(f"Response: {response.text}")
                        perform_local_revoke()
                    
                    elif response.status_code == 200:
                        # อัปเดตเวลาที่ Sync ล่าสุดลงฐานข้อมูลตัวเอง
                        device.last_sync = datetime.now(timezone.utc)
                        session.add(device)
                        session.commit()
                        # print(f"✅ Heartbeat OK: {device.device_id}")
                else:
                    pass

        except Exception as e:
            print(f"📡 Heartbeat Agent Error: {e}")

        # รอ 60 วินาทีก่อนเช็คครั้งถัดไป (ปรับจูนความเร็วได้ที่นี่)
        time.sleep(60)

# --- API Endpoints ---
@router.post("/heartbeat/trigger")
async def trigger_heartbeat(background_tasks: BackgroundTasks):
    """
    Endpoint สำหรับสั่งยิง Heartbeat ทันที (Manual Trigger)
    เรียกผ่าน Gateway: POST /api/identity/device/heartbeat/trigger
    """
    background_tasks.add_task(run_heartbeat_agent)
    return {"message": "Heartbeat trigger initiated in background"}

@router.post("/activate", response_model=DeviceInfoPublic)
def activate_device(activation_data: DeviceActivationRequest, session: SessionDep):
    try:
        endpoint = f"{CLOUD_SERVER_URL}/lockerProvision/getProvisionByCode/{activation_data.provision_code}"
        response = requests.get(
            endpoint,  
            timeout=10
        )

        response.raise_for_status()
        cloud_data = response.json() 
    
    except requests.exceptions.RequestException as e:
        detail = "Connection to server failed"
        if response_err := getattr(e, 'response', None):
            try:
                detail = response_err.json().get("detail", detail)
            except:
                pass
        raise HTTPException(status_code=503, detail=detail)
    
    existing_device = session.exec(select(DeviceInfo)).first()
    
    # เข้ารหัส api_token ก่อนบันทึกลงฐานข้อมูล
    encrypted_token = encrypt_data(cloud_data["data"]["api_token"])

    if existing_device:
        existing_device.locker_id = cloud_data["data"]["locker_id"]
        existing_device.api_token_encrypted = encrypted_token
        existing_device.locker_location_detail = cloud_data["data"]["locker_location_detail"]
        existing_device.last_sync = datetime.now(timezone.utc)
        session.add(existing_device)
        session.commit()
        session.refresh(existing_device)
        return existing_device
    else:
        new_device = DeviceInfo(
            locker_id=cloud_data["data"]["locker_id"],
            api_token_encrypted=encrypted_token,
            locker_location_detail=cloud_data["data"]["locker_location_detail"],
            is_active=True
        )
        session.add(new_device)
        session.commit()
        session.refresh(new_device)
        return new_device
    
@router.get("/info", response_model=DeviceInfoPublic)
def get_device_info(session: SessionDep):
    """ดึงข้อมูลสถานะปัจจุบันของตู้"""
    device = session.exec(select(DeviceInfo)).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not activated yet")
    
    # ถอดรหัส api_token ก่อนส่ง
    if device.api_token_encrypted:
        device.api_token_encrypted = decrypt_data(device.api_token_encrypted)
    
    return device

@router.post("/sync/slots/trigger")
async def trigger_slot_sync(background_tasks: BackgroundTasks):
    """
    Endpoint สำหรับสั่งให้ตู้ทำการ Sync ข้อมูล Slot ทันที (Manual Trigger)
    เหมาะสำหรับการทดสอบ หรือสั่งการจาก UI
    """
    background_tasks.add_task(run_slot_sync_logic)
    return {"message": "Slot sync process triggered in background"}

heartbeat_thread = threading.Thread(target=heartbeat_agent, daemon=True)
heartbeat_thread.start()