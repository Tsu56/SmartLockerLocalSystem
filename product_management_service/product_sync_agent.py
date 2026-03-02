import os
import time
import threading
import requests
from sqlmodel import Session, select, func
from datetime import datetime, timezone
from dotenv import load_dotenv

# นำเข้าองค์ประกอบภายใน Service
from database import engine, models
from getkey import get_internal_shared_secret

load_dotenv()

CLOUD_SERVER_URL = os.getenv("SERVER_URL", "http://localhost:3000/api")
IDENTITY_SERVICE_URL = "http://device-identity-service:8000/device/internal/auth-headers"
INTERNAL_SECRET = get_internal_shared_secret()

def get_cloud_auth_headers():
    """ดึง Auth Headers จาก Identity Service"""
    try:
        headers = {"X-Internal-Secret": INTERNAL_SECRET}
        response = requests.get(IDENTITY_SERVICE_URL, headers=headers, timeout=5)
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        print(f"📡 [Product Sync] Identity Service Connection Error: {e}")
        return None

def perform_product_sync():
    """
    Incremental Sync Logic: ดึงเฉพาะข้อมูลสินค้าที่มีการเปลี่ยนแปลงหลังจากเวลา Sync ล่าสุด
    """
    print(f"🔄 [Product Sync] Checking for updates at {datetime.now(timezone.utc)}")
    
    auth_headers = get_cloud_auth_headers()
    if not auth_headers:
        return {"status": "error", "message": "Auth headers unavailable"}

    try:
        with Session(engine) as session:
            # 1. หาเวลา Sync ล่าสุดจากตาราง Product (Incremental Logic)
            last_sync_time = "1970-01-01T00:00:00Z"
            
            # ค้นหา Timestamp ที่ใหม่ที่สุดจากทุกฟิลด์เวลา
            p_max = session.exec(select(
                func.max(models.Product.created_at),
                func.max(models.Product.updated_at),
                func.max(models.Product.deleted_at)
            )).first()
            
            all_ts = [ts for ts in list(p_max or []) if ts is not None]
            if all_ts:
                # จัดรูปแบบเป็น ISO String เพื่อส่งไปที่ Server
                last_sync_time = max(all_ts).replace(tzinfo=timezone.utc).isoformat()

            # 2. ยิงไปที่ Cloud Server พร้อมพารามิเตอร์ last_sync
            sync_url = f"{CLOUD_SERVER_URL}/product/sync/products" # เปลี่ยนเป็น Endpoint สำหรับ Sync
            params = {"last_sync": last_sync_time}
            
            response = requests.get(sync_url, headers=auth_headers, params=params, timeout=15)
            
            if response.status_code == 200:
                sync_res = response.json()
                # รองรับรูปแบบข้อมูล {"data": [...]} หรือ [...]
                cloud_products = sync_res.get("data", []) if isinstance(sync_res, dict) else sync_res
                
                updated_count = 0
                inserted_count = 0
                
                if cloud_products:
                    for cp in cloud_products:
                        product_id = cp.get("product_id")
                        if not product_id:
                            continue
                            
                        db_product = session.get(models.Product, product_id)
                        
                        if db_product:
                            # มีอยู่แล้ว -> Update
                            db_product.product_name = cp.get("product_name")
                            db_product.product_detail = cp.get("product_detail")
                            # จัดการ Soft Delete ถ้า Server ส่ง deleted_at มา
                            if cp.get("deleted_at"):
                                db_product.deleted_at = datetime.fromisoformat(cp["deleted_at"].replace("Z", "+00:00"))
                            
                            db_product.updated_at = datetime.now(timezone.utc)
                            session.add(db_product)
                            updated_count += 1
                        else:
                            # ยังไม่มี -> Insert
                            new_product = models.Product(
                                product_id=product_id,
                                product_name=cp.get("product_name"),
                                product_detail=cp.get("product_detail"),
                                created_at=datetime.now(timezone.utc)
                            )
                            session.add(new_product)
                            inserted_count += 1
                            
                    session.commit()
                    msg = f"Synced {len(cloud_products)} items. (Added: {inserted_count}, Updated: {updated_count})"
                    print(f"✅ [Product Sync] {msg}")
                    return {"status": "success", "message": msg, "data_count": len(cloud_products)}
                else:
                    return {"status": "success", "message": "Already up to date", "data_count": 0}
            
            else:
                error_msg = f"Cloud API Error {response.status_code}: {response.text}"
                print(f"⚠️ [Product Sync] {error_msg}")
                return {"status": "error", "message": error_msg}

    except Exception as e:
        error_msg = f"Unexpected sync error: {str(e)}"
        print(f"❌ [Product Sync] {error_msg}")
        return {"status": "error", "message": error_msg}

def sync_products_loop():
    """รอบการทำงานเบื้องหลัง"""
    print("🚀 Product Sync Agent Loop Started...")
    time.sleep(10) # รอให้ระบบอื่นๆ พร้อม
    
    while True:
        perform_product_sync()
        time.sleep(300) # Sync ทุกๆ 5 นาที (สอดคล้องกับ User Sync)

def start_product_sync_agent():
    """เริ่มต้น Agent ใน Background Thread"""
    agent_thread = threading.Thread(target=sync_products_loop, daemon=True)
    agent_thread.start()