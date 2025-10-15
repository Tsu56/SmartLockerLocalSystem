import secrets
import base64

# สร้าง key สำหรับ AES-256 (32 bytes)
key = secrets.token_bytes(32)
print("Raw Key:", key)

# เก็บเป็น Base64
key_b64 = base64.urlsafe_b64encode(key).decode('utf-8')
print("Base64 Key:", key_b64)
