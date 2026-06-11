import time
from mfrc522 import SimpleMFRC522
import RPi.GPIO as GPIO

reader = SimpleMFRC522()

print("ระบบพร้อม! กรุณานำบัตรมาแตะที่เครื่องอ่าน (กด Ctrl+C เพื่อออก)...")

try:
    while True:
        # ใช้ read_id() แทนการใช้ read() เพื่อข้ามการอ่าน Data Block
        id = reader.read_id()
        
        print(f"✅ อ่านบัตรสำเร็จ! ID บัตรของคุณคือ: {id}")
        time.sleep(1) # หน่วงเวลา 1 วินาทีเพื่อไม่ให้อ่านรหัสซ้ำรัวๆ
        
except KeyboardInterrupt:
    print("\nออกจากโปรแกรม")
finally:
    GPIO.cleanup() # ล้างค่า GPIO ให้ปลอดภัย