import cv2

# เปลี่ยนเลข 0 เป็น Index ของกล้องที่หาได้จากขั้นตอนที่ 2
video_index = 0 
cap = cv2.VideoCapture(video_index)

# ตรวจสอบว่าสามารถเปิดกล้องได้หรือไม่
if not cap.isOpened():
    print(f"Error: ไม่สามารถเปิดกล้องหมายเลข {video_index} ได้ ลองเปลี่ยนหมายเลขดูนะครับ")
    exit()

print("กดปุ่ม 'q' เพื่อปิดหน้าต่าง")

while True:
    # อ่านเฟรมภาพจากกล้อง
    ret, frame = cap.read()

    # ถ้าอ่านภาพไม่ได้ (เช่น สายหลุด)
    if not ret:
        print("Error: ไม่สามารถรับภาพจากกล้องได้ (อาจจะไม่มีไฟเลี้ยงกล้อง หรือสายสัญญาณหลวม)")
        break

    # แสดงผลภาพ
    cv2.imshow('AV Camera Feed', frame)

    # รอรับคำสั่งคีย์บอร์ด ถ้ากด 'q' ให้ออกจากลูป
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# คืนทรัพยากรและปิดหน้าต่าง
cap.release()
cv2.destroyAllWindows()