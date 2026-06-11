import os
import time
import requests
import shutil
import glob
import cloudinary
import cloudinary.uploader
from dotenv import load_dotenv
from sqlmodel import Session, select

# 🗄️ Import ฐานข้อมูลของ Camera Service
from database.database import engine
from database.models import SyncQueue

# 🔑 Import ฟังก์ชันดึง Secret
from getkey import get_internal_shared_secret

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) 
env_path = os.path.join(base_dir, '.env')


load_dotenv(env_path) 
load_dotenv()

CLOUD_SERVER_URL = os.getenv("SERVER_URL", "http://192.168.X.X:3000") 

# ดึง Secret จาก getkey.py
INTERNAL_SHARED_SECRET = get_internal_shared_secret()

DEVICE_SERVICE_URL = os.getenv("DEVICE_SERVICE_URL", "http://localhost:5001") 
PRODUCT_SERVICE_URL = os.getenv("PRODUCT_SERVICE_URL", "http://localhost:5003")

# ==========================================
# ☁️ 1. ตั้งค่า Cloudinary (ใช้ .env ตามเดิม)
# ==========================================
cloudinary.config( 
  cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME"), 
  api_key = os.getenv("CLOUDINARY_API_KEY"), 
  api_secret = os.getenv("CLOUDINARY_API_SECRET") 
)

def get_cloud_auth_headers():
    """ดึง Auth Headers จาก Device Identity Service"""
    try:
        headers = {"X-Internal-Secret": INTERNAL_SHARED_SECRET}
        response = requests.get(
            f"{DEVICE_SERVICE_URL}/device/internal/auth-headers",
            headers=headers,
            timeout=5
        )
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        print(f"📡 [Camera Sync] Device Service Connection Error: {e}")
        return None

def upload_session_to_cloud(session_dir: str, locker_id: str, slot_id: str, txn_id: str):
    """กวาดรูปทั้งหมดไปอัปโหลดขึ้น Cloudinary แบบสร้างโฟลเดอร์แยก"""
    uploaded_urls = {"before_url": None, "after_url": None, "log_urls": []}
    
    if not os.path.exists(session_dir):
        return uploaded_urls

    cloud_folder_name = f"SmartLocker/{locker_id}/Txn_{txn_id}/Slot_{slot_id}"
    print(f"☁️ เตรียมอัปโหลดภาพไปที่โฟลเดอร์: {cloud_folder_name}")

    all_images = glob.glob(os.path.join(session_dir, "*.jpg"))
    for img_path in all_images:
        filename = os.path.basename(img_path)
        try:
            response = cloudinary.uploader.upload(
                img_path,
                folder=cloud_folder_name,
                public_id=filename.replace(".jpg", "") 
            )
            secure_url = response.get("secure_url")
            print(f"✅ อัปโหลดสำเร็จ: {filename}")
            
            if "1_before_yolo" in filename:
                uploaded_urls["before_url"] = secure_url
            elif "2_after_yolo" in filename:
                uploaded_urls["after_url"] = secure_url
            elif "log_" in filename:
                uploaded_urls["log_urls"].append(secure_url)
                
        except Exception as e:
            print(f"❌ อัปโหลด {filename} ล้มเหลว: {e}")

    return uploaded_urls

# ==========================================
# 🤖 2. ฟังก์ชัน Worker คอยจัดการคิว
# ==========================================
def process_pending_queues():
    with Session(engine) as session:
        statement = select(SyncQueue).where(SyncQueue.sync_status == "PENDING")
        pending_tasks = session.exec(statement).all()
        
        if not pending_tasks:
            return 
            
        print(f"\n🔄 พบข้อมูลกล้องค้างส่ง {len(pending_tasks)} รายการ กำลังเริ่มจัดการ...")
        
        # 🔑 ขอ Auth Headers ก่อนเริ่มส่งข้อมูล
        auth_headers = get_cloud_auth_headers()
        if not auth_headers:
            print("❌ ไม่สามารถดึง Auth Headers ได้ ข้ามการส่งรอบนี้")
            return
        
        locker_id = auth_headers.get("locker_id", "UnknownLocker")

        slot_mapping = {}

        try:
            # ดึงข้อมูลจาก Endpoint ที่มีอยู่แล้ว
            slot_res = requests.get(f"{DEVICE_SERVICE_URL}/device/internal/slots", headers=auth_headers, timeout=5)
            if slot_res.status_code == 200:
                slots_data = slot_res.json()
                for s in slots_data:
                    # สร้าง Key เป็น "S1", "S2" ... และ Value เป็น Integer ID
                    # อ้างอิงจากโค้ด UI คุณใช้ s["slot_id"] มาต่อกับ "S"
                    hw_address = f"S{s['id']}"  
                    slot_mapping[hw_address] = s["slot_id"] 
                print(f"📋 โหลดข้อมูล Slot Mapping สำเร็จ: {slot_mapping}")
        except Exception as e:
            print(f"⚠️ ดึงข้อมูล Slots จาก Device Service ไม่สำเร็จ: {e}")

        for task in pending_tasks:
            server_txn_id = None

            print(f"📦 จัดการคิวกล้อง ID: {task.id} (ตู้ {task.slot_id} | TXN: {task.transaction_id})")

            try:
                # ยิง API ไปถามหา Transaction ID นี้
                res = requests.get(f"{PRODUCT_SERVICE_URL}/locker/transactions/{task.transaction_id}", timeout=5)
                if res.status_code == 200:
                    txn_data = res.json()
                    server_txn_id = txn_data.get("server_transaction_id")
            except Exception as e:
                print(f"⚠️ ไม่สามารถเชื่อมต่อ Product Service ได้: {e}")
                
            # ⏳ ถ้ายังเป็น None แปลว่า Kivy/Product Service ยัง Sync ไม่เสร็จ ให้ "ข้าม" ไปก่อน!
            if not server_txn_id:
                print(f"⏳ ตู้ {task.slot_id} (TXN: {task.transaction_id}) รอ Server Transaction ID... ข้ามไปรอบถัดไป")
                continue
            
            try:
                # 1. อัปโหลดรูปขึ้น Cloud
                upload_session_to_cloud(task.session_dir, locker_id, task.slot_id, server_txn_id)
                
                # 2. เตรียมข้อมูล 
                cloud_folder_path = f"SmartLocker/{locker_id}/{server_txn_id}/Slot_{task.slot_id}"

                real_slot_id = slot_mapping.get(task.slot_id)
                
                if real_slot_id is None:
                    try:
                        real_slot_id = int(task.slot_id.replace("S", ""))
                    except ValueError:
                        real_slot_id = 0

                sync_url = f"{CLOUD_SERVER_URL}/camera/sync-snapshot" 
                
                payload = {
                    "transaction_id": server_txn_id,
                    "slot_id": real_slot_id,
                    "camera_amount": task.camera_amount,
                    "action_type": task.action_type,
                    "image_path": cloud_folder_path 
                }
                
                # 3. ยิง API ส่ง Main Server
                print(f"🌐 ส่งข้อมูลไปที่ {sync_url} พร้อม Slot ID: {real_slot_id} ...")
                response = requests.post(sync_url, json=payload, headers=auth_headers, timeout=15)
                
                if response.status_code in (200, 201):
                    print(f"✅ Main Server รับข้อมูลสำเร็จ!")
                    task.sync_status = "COMPLETED"
                    session.add(task)
                    session.commit()
                    
                    if os.path.exists(task.session_dir):
                        shutil.rmtree(task.session_dir)
                        print(f"🗑️ ลบไฟล์รูป Local ทิ้งสำเร็จ")
                else:
                    print(f"⚠️ Main Server Error: {response.status_code} - {response.text}")
                    
            except Exception as e:
                print(f"❌ Error ประมวลผลคิว {task.id}: {e}")

def start_worker():
    print("🤖 เริ่มต้น Camera Sync Agent...")
    while True:
        try:
            process_pending_queues()
        except Exception as e:
            print(f"🔥 Error ใน Worker Loop: {e}")
        time.sleep(5) 

if __name__ == "__main__":
    start_worker()