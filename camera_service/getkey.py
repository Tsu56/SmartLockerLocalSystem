import os
import json

def get_all_secrets() -> dict:
    """
    ดึงข้อมูลความลับจากไฟล์ secrets.json
    รองรับทั้งรันใน Docker Container และรัน Local นอก Docker
    """
    # 1. Path สำหรับรันใน Docker (อิงตามท่าของ docker-compose)
    docker_path = "/camera_service/secret/secrets.json"
    
    # 2. Path สำหรับรัน Local ตรงๆ ระหว่างเทสต์ (ถอยกลับไป 1 โฟลเดอร์)
    local_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "secret", "secrets.json"))
    
    file_path = docker_path if os.path.exists(docker_path) else local_path
    
    secrets = {}
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                file_data = json.load(f)
                secrets.update(file_data)
        except Exception as e:
            print(f"⚠️ Error reading secrets.json: {e}")
            
    return secrets

def get_internal_shared_secret():
    secrets = get_all_secrets()
    return secrets.get("INTERNAL_SHARED_SECRET")