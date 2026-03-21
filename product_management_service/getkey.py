import os
import json

def get_all_secrets() -> dict:
    """
    ดึงข้อมูลความลับทั้งหมดจากไฟล์ secrets.json เพียงไฟล์เดียว
    ตำแหน่งไฟล์จะอยู่ที่ /app/shared_configs/secrets.json (ภายใน Container)
    """
    base_path = "/product_management_service/secret"
    file_path = os.path.join(base_path, "secrets.json")
    
    secrets = {}

    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                file_data = json.load(f)
                secrets.update(file_data)
        except Exception as e:
            print(f"⚠️ Error reading secrets.json: {e}")
            
    return secrets

def get_encryption_key():
    """
    ดึงกุญแจสำหรับการเข้ารหัสข้อมูล (Fernet Key)
    """
    secrets = get_all_secrets()
    return secrets.get("ENCRYPTION_KEY")

def get_internal_shared_secret():
    """
    ดึงค่า Secret สำหรับการยืนยันตัวตนระหว่าง Service ภายในตู้
    """
    secrets = get_all_secrets()
    return secrets.get("INTERNAL_SHARED_SECRET")

def get_search_hash_salt():
    """
    ดึงค่า Salt สำหรับการทำ Blind Index (Search Hash)
    """
    secrets = get_all_secrets()
    return secrets.get("SEARCH_HASH_SALT")

def get_secret_key():
    """
    ดึงค่า Secret Key สำหรับการสร้างกุญแจเข้ารหัส (ถ้าไม่มี ENCRYPTION_KEY)
    """
    secrets = get_all_secrets()
    return secrets.get("SECRET_KEY")


def get_mqtt_config() -> dict:
    """ดึงค่าคอนฟิก MQTT จาก mqtt_config.json"""
    base_path = "/product_management_service/secret"
    file_path = os.path.join(base_path, "mqtt_config.json")

    if not os.path.exists(file_path):
        return {}

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
    except Exception as e:
        print(f"⚠️ Error reading mqtt_config.json: {e}")

    return {}