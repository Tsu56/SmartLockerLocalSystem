from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
import serial
import threading
import time
import requests

router = APIRouter(prefix="/api/device/door", tags=["Device Communication"])

# ==========================================
# ⚙️ ตั้งค่าระบบฮาร์ดแวร์
# ==========================================
PORT = "/dev/ttyUSB0"
BAUDRATE = 38400
active_transaction_slot = None
active_transaction_id = "UNKNOWN"
DEVICE_ADDRESSES = ['S1', 'S2', 'S3', 'S4']
CAMERA_SERVICE_URL = "http://localhost:8002/api/camera" 

serial_lock = threading.Lock()
try:
    ser = serial.Serial(PORT, BAUDRATE, timeout=0.5)
    print(f"✅ Connected to RS485 at {PORT}")
except Exception as e:
    ser = None
    print(f"❌ Failed to connect to RS485: {e}")

door_states = {addr: "UNKNOWN" for addr in DEVICE_ADDRESSES}

class DoorCommandRequest(BaseModel):
    address: str
    transaction_id: str = "TXN_UNKNOWN"

# ==========================================
# 🔌 ฟังก์ชันสื่อสาร RS485 (อัปเกรด Auto-Retry)
# ==========================================
def calculate_checksum(data_str: str) -> str:
    checksum = 0
    for char in data_str:
        checksum ^= ord(char)
    return f"{checksum:02X}"

def send_and_read(address: str, command: str, max_retries: int = 3):
    if not ser:
        return {"status": "error", "message": "Serial port is not connected"}
    
    full_cmd = f"{address}:{command}"
    
    for attempt in range(1, max_retries + 1):
        with serial_lock: 
            try:
                time.sleep(0.05)
                ser.reset_input_buffer()
                ser.reset_output_buffer()
                
                ser.write((full_cmd + "\n").encode())
                ser.flush()
                
                raw_line = ser.readline().decode(errors="ignore").strip()
                time.sleep(0.05)

                if not raw_line:
                    raise ValueError("Timeout") 

                if "|" in raw_line:
                    data_part, recv_cs = raw_line.rsplit("|", 1)
                    if recv_cs == calculate_checksum(data_part):
                        return {"status": "success", "reply": data_part}
                    else:
                        raise ValueError(f"Checksum Mismatch")
                
                return {"status": "success", "reply": raw_line}
                
            except Exception as e:
                if attempt >= 2:
                    print(f"⚠️ [RS485] ตู้ {address} สื่อสารล้มเหลว (รอบ {attempt}/{max_retries}): {e} -> กำลังลองใหม่...")
        
        if attempt < max_retries:
            time.sleep(0.2)
            
    return {"status": "error", "message": f"ขาดการเชื่อมต่อกับตู้ {address} (ล้มเหลว {max_retries} ครั้งรวด)"}

# ==========================================
# 🔄 Loop เช็คสถานะฮาร์ดแวร์
# ==========================================
def hardware_polling_loop():
    print("🚀 Hardware Polling Loop Started...")
    time.sleep(2)
    
    while True:
        for addr in DEVICE_ADDRESSES:
            result = send_and_read(addr, "GETDATA")
            
            if result["status"] == "success":
                reply = result["reply"]
                is_door_open = "DOOR:OPEN" in reply.upper()
                
                current_state = "OPEN" if is_door_open else "CLOSED"
                previous_state = door_states[addr]
                
                if current_state != previous_state and previous_state != "UNKNOWN":
                    if current_state == "OPEN":
                        print(f"🚪 ตู้ {addr} ถูกเปิดออกแล้ว!")
                        send_and_read(addr, "DOORLOCKOFF")
                            
                    elif current_state == "CLOSED":
                        print(f"🚪 ตู้ {addr} ถูกปิด! 🛑 สั่งกล้องหยุดถ่าย...")
                        try:
                            # สั่งปิดกล้อง (ฝั่งกล้องจะถ่าย After, สั่ง YOLO แล้วยิงกลับมาปิด Relay เอง)
                            requests.post(f"{CAMERA_SERVICE_URL}/stop", json={"slot_id": addr, "transaction_id": active_transaction_id}, timeout=2)
                        except:
                            pass
                
                door_states[addr] = current_state

            time.sleep(0.3)

# ==========================================
# 🌐 API Endpoints
# ==========================================
@router.post("/open")
def open_door(req: DoorCommandRequest, background_tasks: BackgroundTasks):
    global active_transaction_slot, active_transaction_id

    # 🚨 เช็คก่อนเลยว่ามีตู้ไหนใช้งานอยู่ไหม!
    if active_transaction_slot is not None and active_transaction_slot != req.address:
        raise HTTPException(
            status_code=423, 
            detail=f"ไม่สามารถเปิดตู้ {req.address} ได้ เนื่องจากตู้ {active_transaction_slot} กำลังทำรายการอยู่"
        )
        
    # ถ้าว่าง ล็อกคิวให้ตู้ปัจจุบันเลย
    active_transaction_slot = req.address
    active_transaction_id = req.transaction_id

    print(f"⚡ [Transaction] เริ่มกระบวนการเปิดตู้ {req.address}...")
    
    # 🔌 1. จ่ายไฟเลี้ยงกล้อง (Cold Boot)
    result_power = send_and_read(req.address, "CAMERAPOWERON")
    if result_power["status"] == "error":
        raise HTTPException(status_code=500, detail="ไม่สามารถจ่ายไฟให้กล้องได้")
    time.sleep(0.3) # ให้เวลากระแสไฟไหลเข้าวงจรนิ่งๆ

    # 📹 2. สลับสัญญาณภาพเข้า Capture Card
    result_camera_on = send_and_read(req.address, "CAMERAON")
    if result_camera_on["status"] == "error":
        raise HTTPException(status_code=500, detail="ไม่สามารถสลับสัญญาณภาพได้")
    
    print(f"⏳ รอ 2 วินาทีให้สัญญาณ Analog วิ่งเข้า Capture Card จนภาพเสถียร...")
    time.sleep(2.0)

    # 📸 3. ยิง API ให้ Camera Service เริ่มทำงาน
    # (ฝั่งโน้นมีลูปดึงภาพทิ้ง 40 เฟรมเพื่อรอแสงสว่างอยู่แล้ว จึงไม่ต้องหน่วงเวลาฝั่งนี้เยอะ)
    try:
        print(f"📸 กำลังสั่งกล้องถ่ายรูป Before...")
        requests.post(
            f"{CAMERA_SERVICE_URL}/start", 
            json={"slot_id": req.address, "transaction_id": active_transaction_id}, 
            timeout=15 
        )
    except Exception as e:
        print(f"⚠️ Error ยิง API กล้องไม่สำเร็จ: {e}")

    print(f"🟢 เปิดไฟสถานะสีเขียวตู้ {req.address}")
    send_and_read(req.address, "STATUSON")
    time.sleep(0.1)
    
    # 🔓 4. สั่งปลดล็อกกลอนประตู (ทำหลังจากกล้องถ่าย Before เสร็จแล้ว)
    print(f"🔓 สั่งปลดล็อกประตู {req.address}")
    result_door = send_and_read(req.address, "DOORLOCKON")

    time.sleep(0.3)

    if result_door["status"] == "error":
        raise HTTPException(status_code=500, detail="ไม่สามารถปลดล็อกประตูได้")

    return {"message": "Success", "hardware_reply": result_door["reply"]}

@router.post("/close")
def close_door(req: DoorCommandRequest):
    result = send_and_read(req.address, "DOORLOCKOFF")
    time.sleep(0.3)
    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result["message"])
    return {"message": "Success", "hardware_reply": result["reply"]}

@router.post("/status-light/on")
def status_light_on(req: DoorCommandRequest):
    result = send_and_read(req.address, "STATUSON") 
    return {"message": "Status light is ON", "reply": result.get("reply")}

@router.post("/status-light/off")
def status_light_off(req: DoorCommandRequest):
    result = send_and_read(req.address, "STATUSOFF")
    return {"message": "Status light is OFF", "reply": result.get("reply")}

@router.post("/camera/off")
def turn_off_camera(req: DoorCommandRequest):
    global active_transaction_slot

    """ฟังก์ชันนี้ถูกเรียกโดย Camera Service หลังจากที่ถ่ายรูป After เสร็จสิ้น"""
    print(f"🔌 ได้รับคำสั่งปิดระบบกล้องตู้ {req.address}")
    
    # 1. 🚫 สั่งตัดสัญญาณภาพ (Multiplexer)
    res_cam = send_and_read(req.address, "CAMERAOFF")
    time.sleep(0.1)
    
    # 2. 🔌 สั่งตัดไฟเลี้ยงกล้อง (Power)
    res_power = send_and_read(req.address, "CAMERAPOWEROFF")

    if res_cam["status"] == "error" or res_power["status"] == "error":
        print(f"❌ [RS485 Error] ตู้ {req.address} ปิดระบบกล้องไม่สมบูรณ์")
        raise HTTPException(status_code=500, detail="ปิดระบบกล้องไม่สมบูรณ์")
        
    if active_transaction_slot == req.address:
        active_transaction_slot = None
        print(f"🔓 คืนสถานะว่างให้ระบบ (พร้อมรับรายการตู้ต่อไป)")
        
    return {"message": "Camera signal and power turned OFF successfully"}

@router.get("/status/{address}")
def get_door_status(address: str):
    """ส่งคืนสถานะล่าสุดของประตู (OPEN/CLOSED) จาก Polling Loop"""
    if address not in door_states:
        raise HTTPException(status_code=404, detail="ไม่พบข้อมูลตู้")
        
    return {"status": door_states[address]}