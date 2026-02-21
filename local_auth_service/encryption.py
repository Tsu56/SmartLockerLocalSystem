"""
โมดูลสำหรับเข้ารหัสและถอดรหัสข้อมูลที่เป็นความลับ
แก้ไขเพื่อให้รองรับ Fernet Key ในรูปแบบ Base64 ได้ถูกต้อง
"""
import os
import base64
import hashlib
import binascii
from cryptography.fernet import Fernet
from getkey import get_encryption_key, get_secret_key


def _get_encryption_key() -> bytes:
    """
    ดึง encryption key จาก environment variable ENCRYPTION_KEY
    ถ้าไม่มี จะสร้าง key จาก SECRET_KEY
    """
    raw_key = get_encryption_key()
    
    if raw_key:
        # [FIXED]: ล้างช่องว่างและเครื่องหมายคำพูด แต่ "ไม่ต้อง" decode
        # เพราะ Fernet() ต้องการกุญแจที่ยังเป็น Base64 อยู่
        cleaned_key = raw_key.strip().strip("'").strip('"')
        
        # ตรวจสอบเบื้องต้นว่ารูปแบบพอจะใช้ได้ไหม (ต้องยาวประมาณ 44 ตัวอักษร)
        try:
            # ลองตรวจสอบว่ามันเป็น base64 ที่ถูกต้องและได้ 32 bytes จริงไหม
            # (ทำเพื่อตรวจสอบความถูกต้องเฉยๆ แต่เราจะส่งค่าที่ยัง encoded อยู่กลับไป)
            test_decode = base64.urlsafe_b64decode(cleaned_key)
            if len(test_decode) == 32:
                return cleaned_key.encode()
            else:
                print(f"⚠️ Warning: ENCRYPTION_KEY length is {len(test_decode)} bytes, not 32. Re-hashing...")
        except Exception:
            print("⚠️ Warning: ENCRYPTION_KEY format is invalid. Re-hashing...")

    # Fallback: สร้าง key ใหม่ที่ถูกต้องจาก SECRET_KEY หรือค่าพื้นฐาน
    secret = get_secret_key()
    
    # Hash ให้มี 32 bytes (Raw)
    key_bytes = hashlib.sha256(secret.encode()).digest()
    # แปลงเป็น Base64 (ตามที่ Fernet ต้องการ)
    return base64.urlsafe_b64encode(key_bytes)

# สร้าง cipher suite ด้วยกุญแจที่เป็น Base64 (Bytes หรือ String)
try:
    _cipher_suite = Fernet(_get_encryption_key())
except Exception as e:
    print(f"❌ Initialization Error: {e}")
    # ในกรณีวิกฤต สร้างกุญแจสุ่มเพื่อให้ระบบทำงานต่อได้ (แต่จะถอดข้อมูลเก่าไม่ได้)
    _cipher_suite = Fernet(Fernet.generate_key())

def encrypt_data(data: str) -> str:
    """เข้ารหัสข้อมูล"""
    if not data:
        return ""
    try:
        encrypted = _cipher_suite.encrypt(data.encode())
        return encrypted.decode()
    except Exception as e:
        print(f"❌ Encryption Error: {e}")
        return ""

def decrypt_data(encrypted_data: str) -> str:
    """ถอดรหัสข้อมูล"""
    if not encrypted_data:
        return ""
    
    try:
        decrypted = _cipher_suite.decrypt(encrypted_data.encode())
        return decrypted.decode()
    except Exception as e:
        # แสดง Error ที่เข้าใจง่ายขึ้น
        print(f"❌ Decryption Error: {e}")
        return ""