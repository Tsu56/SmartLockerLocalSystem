from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel
import cv2
import threading
import time
import os
from datetime import datetime
from ultralytics import YOLO
import requests

# 🗄️ Import สำหรับเชื่อมต่อฐานข้อมูล (SQLModel)
from database.database import engine
from database.models import SyncQueue
from sqlmodel import Session

# 👉 เปลี่ยนจาก FastAPI() เป็น APIRouter
router = APIRouter(tags=["Camera Management"])

# ==========================================
# ⚙️ ตั้งค่าระบบ
# ==========================================
VIDEO_INDEX = 0
SAVE_DIR = "captures"
MODEL_PATH = "models/best_ncnn_model"
DEVICE_COMM_URL = "http://localhost:8003/api/device/door"

# 🧠 โหลดโมเดล YOLO ไว้ล่วงหน้า 
print("⏳ Loading YOLO Model into Memory...")
model = YOLO(MODEL_PATH, task='detect')
print("✅ YOLO Model Loaded Successfully!")

# ตัวแปรควบคุมสถานะ (State)
is_capturing = False
capture_thread = None
cap = None
session_dir = ""
before_image_path = ""

os.makedirs(SAVE_DIR, exist_ok=True)

class CameraCommandRequest(BaseModel):
    slot_id: str
    transaction_id: str = "AUTO_TXN"

# ==========================================
# 📸 ฟังก์ชันลูปแอบถ่ายรูประหว่างทำรายการ
# ==========================================
def capture_loop():
    global is_capturing, cap, session_dir
    last_save_time = time.time()
    try:
        while is_capturing:
            if cap and cap.isOpened():
                ret, frame = cap.read() 
                
                if ret:
                    current_time = time.time()
                    
                    if current_time - last_save_time >= 1.0:
                        filename_time = datetime.now().strftime("%H%M%S_%f")[:9]
                        filepath = os.path.join(session_dir, f"log_{filename_time}.jpg")
                        cv2.imwrite(filepath, frame)
                        last_save_time = current_time

            time.sleep(0.01) 
    finally:
        print("🛑 Background capture loop stopped.")

# ==========================================
# 🧠 ฟังก์ชัน YOLO (ทำงานเบื้องหลัง)
# ==========================================
# 👉 เพิ่มตัวแปร session_dir เพื่อให้ DB รู้ตำแหน่งโฟลเดอร์ของรอบนี้
def process_yolo_task(slot_id: str, txn_id: str, before_path: str, after_path: str, session_dir_path: str):
    print(f"\n🔍 [YOLO] เริ่มวิเคราะห์ภาพตู้ {slot_id} เบื้องหลัง...")
    
    # ส่งภาพให้โมเดลประมวลผล
    before_result = model(before_path, verbose=False)
    after_result = model(after_path, verbose=False)
    
    # วาดกรอบและบันทึกภาพผลลัพธ์
    before_annotated_path = before_path.replace(".jpg", "_yolo.jpg")
    after_annotated_path = after_path.replace(".jpg", "_yolo.jpg")

    before_result[0].save(filename=before_annotated_path)
    after_result[0].save(filename=after_annotated_path)
    
    print(f"🎨 บันทึกภาพผลลัพธ์ Before: {before_annotated_path}")
    print(f"🎨 บันทึกภาพผลลัพธ์ After : {after_annotated_path}")
    
    # นับจำนวนกล่องที่พบ
    before_count = len(before_result[0].boxes)
    after_count = len(after_result[0].boxes)
    
    # คำนวณส่วนต่าง (Diff)
    diff = after_count - before_count
    
    action_type = ""
    amount = 0
    
    if diff > 0:
        action_type = "RESTOCK (เติมของ)"
        amount = diff
    elif diff < 0:
        action_type = "WITHDRAW (หยิบออก)"
        amount = abs(diff)
    else:
        action_type = "NO_CHANGE (ไม่มีการเปลี่ยนแปลง)"
        amount = 0
        
    print("========================================")
    print(f"📊 [YOLO Result] ตู้ {slot_id} (TXN: {txn_id})")
    print(f"   - ก่อนทำรายการ (Before): {before_count} ชิ้น")
    print(f"   - หลังปิดตู้ (After)  : {after_count} ชิ้น")
    print(f"   - สถานะการทำรายการ    : {action_type}")
    print(f"   - จำนวนชิ้นที่ทำรายการ   : {amount} ชิ้น")
    print("========================================\n")
    
    # -------------------------------------------------------------
    # 🚀 บันทึกข้อมูลลงฐานข้อมูล Camera Queue (SQLModel)
    # -------------------------------------------------------------
    try:
        with Session(engine) as session:
            new_queue = SyncQueue(
                transaction_id=txn_id,
                slot_id=slot_id,
                session_dir=session_dir_path,
                before_image_local=before_annotated_path,
                after_image_local=after_annotated_path,
                before_count=before_count,
                after_count=after_count,
                camera_amount=amount,
                action_type=action_type,
                sync_status="PENDING"
            )
            session.add(new_queue)
            session.commit()
            print("💾 บันทึกข้อมูลลงตาราง SyncQueue สำเร็จ! (สถานะ: PENDING)")
    except Exception as e:
        print(f"❌ Error บันทึกข้อมูลลงฐานข้อมูล: {e}")

# ==========================================
# 🌐 API Endpoints
# ==========================================
@router.post("/api/camera/start")
def start_camera(req: CameraCommandRequest, background_tasks: BackgroundTasks):
    global is_capturing, capture_thread, cap, session_dir, before_image_path
    
    if is_capturing:
        return {"status": "error", "message": "Camera is already capturing"}

    # สร้างโฟลเดอร์สำหรับเก็บภาพ
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    session_dir = os.path.join(SAVE_DIR, f"{req.slot_id}_{req.transaction_id}_{timestamp}")
    os.makedirs(session_dir, exist_ok=True)
    before_image_path = os.path.join(session_dir, "1_before.jpg")

    # เปิดการเชื่อมต่อกล้อง
    cap = cv2.VideoCapture(VIDEO_INDEX, cv2.CAP_V4L2)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    
    # ---------------------------------------------------------
    # 🔄 การปรับแสงแบบ Adaptive (รอจนกว่าแสงจะนิ่ง)
    # ---------------------------------------------------------
    print(f"[{req.slot_id}] ⏳ รอระบบภาพเสถียร...")
    
    # ดึงเฟรมแรกๆ ทิ้งไปก่อนนิดหน่อย (ให้ Capture Card จูนคลื่น)
    for _ in range(10):
        cap.read()
        
    is_ready = False
    max_attempts = 100        # รอบการพยายามสูงสุด (ป้องกันลูปค้าง)
    min_brightness = 20.0     # ค่าความสว่างขั้นต่ำ (ป้องกันเฟรมดำ)
    stable_frames_needed = 5  # ต้องการให้ภาพสว่างคงที่ติดกัน 5 เฟรม
    stable_count = 0
    prev_brightness = -1
    tolerance = 2.0           # ยอมให้ความสว่างต่างกันได้ 2.0 
    
    for attempt in range(max_attempts):
        ret, frame = cap.read()
        if ret:
            # คำนวณความสว่างเฉลี่ยของภาพ
            brightness = frame.mean()
            
            # ตรวจสอบ 2 เงื่อนไข: สว่างพอ และ สว่างคงที่
            if brightness > min_brightness:
                # ถ้าความสว่างใกล้เคียงกับเฟรมที่แล้ว
                if prev_brightness != -1 and abs(brightness - prev_brightness) < tolerance:
                    stable_count += 1
                else:
                    stable_count = 0 # รีเซ็ตถ้าความสว่างแกว่ง
                    
                prev_brightness = brightness
                
                # ถ้าภาพสว่างและนิ่งติดต่อกันครบตามที่ตั้งไว้ = พร้อม!
                if stable_count >= stable_frames_needed:
                    print(f"✨ กล้องพร้อม! แสงเสถียรที่เฟรม {attempt+1} (ความสว่าง: {brightness:.1f})")
                    is_ready = True
                    break
            else:
                # ถ้ายังมืดอยู่ ให้รีเซ็ตค่า
                stable_count = 0
                prev_brightness = -1
                
        time.sleep(0.05) # หน่วงนิดนึงให้ภาพมีเวลาอัปเดต
        
    if not is_ready:
        print("⚠️ คำเตือน: ระบบภาพไม่เสถียร หรือหลอดไฟตู้ไม่ทำงานในเวลาที่กำหนด (อาจได้ภาพมืด)")
        
    # ---------------------------------------------------------
    
    # ถ่ายรูป Before ทันทีที่แสงพร้อม
    ret, frame = cap.read()
    if ret:
        cv2.imwrite(before_image_path, frame)
        print(f"✅ บันทึกภาพ Before: {before_image_path}")

    # เริ่มลูปถ่าย Background (เพื่อให้กล้องไม่ถูกปล่อย)
    is_capturing = True
    capture_thread = threading.Thread(target=capture_loop, daemon=True)
    capture_thread.start()

    return {"status": "success", "message": "Camera started", "session_dir": session_dir}

@router.post("/api/camera/stop")
def stop_camera(req: CameraCommandRequest, background_tasks: BackgroundTasks):
    global is_capturing, cap, before_image_path, session_dir, capture_thread
    
    if not is_capturing:
         return {"status": "success", "message": "Camera was not running."}
         
    is_capturing = False
    if capture_thread and capture_thread.is_alive():
        capture_thread.join(timeout=0.5) 

    after_image_path = os.path.join(session_dir, "2_after.jpg")
    if cap and cap.isOpened():
        
        for _ in range(30):
            cap.read()
            
        ret, frame = cap.read()
        if ret:
            cv2.imwrite(after_image_path, frame)
            print(f"✅ บันทึกภาพ After สำเร็จ: {after_image_path}")
        else:
            print("❌ Error: ถ่ายภาพ After ไม่สำเร็จ (เฟรมภาพมีปัญหา)")
    
    if cap:
        cap.release()
        cap = None
        print("🛑 Camera released.")

    try:
        print(f"🔌 ถ่ายรูปเสร็จแล้ว กำลังส่งคำสั่งปิดไฟกล้องที่ตู้ {req.slot_id}...")
        res = requests.post(f"{DEVICE_COMM_URL}/camera/off", json={
            "address": req.slot_id
        }, timeout=2)
        print(f"✅ ปิด Relay สำเร็จ (Status: {res.status_code})")
    except Exception as e:
        print(f"⚠️ Error: ไม่สามารถเชื่อมต่อเพื่อปิด Relay ได้: {e}")

    if os.path.exists(before_image_path) and os.path.exists(after_image_path):
        # 👉 ส่งตัวแปร session_dir เข้าไปด้วย เพื่อให้บันทึกในฐานข้อมูลได้ถูกต้อง
        background_tasks.add_task(process_yolo_task, req.slot_id, req.transaction_id, before_image_path, after_image_path, session_dir)
    else:
        print("⚠️ ข้ามการรัน YOLO เพราะรูป Before หรือ After ไม่สมบูรณ์")

    return {"status": "success", "message": "Stopped capturing, turned off relay, and YOLO is running."}