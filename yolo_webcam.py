import cv2
from ultralytics import YOLO
import time

def run_yolo_webcam():
    # 1. โหลดโมเดล YOLO11 Nano สำเร็จรูป
    # เมื่อรันครั้งแรก มันจะดาวน์โหลดไฟล์ 'yolo11n.pt' มาให้โดยอัตโนมัติ
    try:
        model = YOLO("yolo11n.pt")
    except Exception as e:
        print(f"เกิดข้อผิดพลาดในการโหลดโมเดล: {e}")
        return

    # 2. เริ่มต้นเปิดกล้องเว็บแคม (ปกติกล้องหลักโน้ตบุ๊กคือ index 0)
    cap = cv2.VideoCapture(0)

    # ตรวจสอบว่ากล้องเปิดได้หรือไม่
    if not cap.isOpened():
        print("ไม่สามารถเปิดกล้องเว็บแคมได้")
        return

    print("--- เริ่มการตรวจจับแบบ Real-time (กด 'q' เพื่อเลิก) ---")
    
    # ตัวแปรสำหรับคำนวณ FPS
    prev_time = 0

    while True:
        # A. อ่านเฟรมจากกล้อง
        success, frame = cap.read()
        
        if not success:
            print("ไม่สามารถอ่านข้อมูลจากกล้องได้")
            break

        # B. ประมวลผลรูปภาพด้วย YOLO11
        # stream=True ช่วยให้ประมวลผลแบบ Real-time ได้เร็วขึ้น
        # conf=0.5 คือค่าความมั่นใจขั้นต่ำ 50% ถึงจะแสดงผล
        results = model.predict(frame, stream=True, conf=0.5, classes=[39])

        # C. วาดกล่องและชื่อวัตถุลงบนเฟรม (ใช้ OpenCV)
        # วิธีที่ง่ายที่สุดคือใช้ method plot() ที่มากับ results
        # แต่ผลลัพธ์จาก stream=True เป็น Generator ต้องวนลูปดึงทีละ frame
        processed_frame = frame.copy() # สร้าง copy เพื่อไม่ให้แก้ไข frame ต้นฉบับ
        for r in results:
            processed_frame = r.plot() # plot กล่อง, ชื่อ, และ conf ลงบน frame
            break # เนื่องจาก model.predict(..., stream=True) ส่งคืนผลลัพธ์ทีละเฟรมใน Loop นี้

        # D. คำนวณและแสดงผล FPS
        curr_time = time.time()
        fps = 1 / (curr_time - prev_time)
        prev_time = curr_time
        
        # วาดข้อความ FPS ลงบนภาพ
        cv2.putText(processed_frame, f"FPS: {int(fps)}", (10, 30), 
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

        # E. แสดงผลภาพที่ประมวลผลแล้ว
        cv2.imshow("YOLO11 Real-time Detection (Press 'q' to Quit)", processed_frame)

        # F. หยุดการทำงานเมื่อกดปุ่ม 'q' (ที่หน้าต่างแสดงผล)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    # G. คืนทรัพยากร
    cap.release()
    cv2.destroyAllWindows()
    print("--- จบการทำงาน ---")

if __name__ == "__main__":
    run_yolo_webcam()