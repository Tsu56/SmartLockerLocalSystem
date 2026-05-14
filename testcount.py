import cv2
import numpy as np
import matplotlib.pyplot as plt

def resize_image(image, max_width=800):
    """ย่อภาพให้มีความกว้างมาตรฐาน เพื่อให้การคำนวณพื้นที่ (Area) นิ่งขึ้น"""
    h, w = image.shape[:2]
    if w > max_width:
        scale = max_width / float(w)
        dim = (max_width, int(h * scale))
        return cv2.resize(image, dim, interpolation=cv2.INTER_AREA)
    return image

def align_images(img_before, img_after):
    """
    🌟 ฟังก์ชันใหม่: จัดตำแหน่งภาพ After ให้ซ้อนทับกับ Before เป๊ะๆ 
    (แก้ปัญหากล้องสั่น/ขยับมุมเวลาถ่ายด้วยมือถือ)
    """
    gray1 = cv2.cvtColor(img_before, cv2.COLOR_BGR2GRAY)
    gray2 = cv2.cvtColor(img_after, cv2.COLOR_BGR2GRAY)
    
    # 1. ใช้ ORB หาจุดเด่นของภาพ (Keypoints)
    orb = cv2.ORB_create(5000)
    kp1, des1 = orb.detectAndCompute(gray1, None)
    kp2, des2 = orb.detectAndCompute(gray2, None)
    
    # 2. จับคู่จุดเด่น
    matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
    matches = matcher.match(des1, des2)
    matches = sorted(matches, key=lambda x: x.distance)
    
    # 3. คัดเฉพาะจุดที่เหมือนกันมากๆ เพื่อความแม่นยำ
    good_matches = matches[:int(len(matches) * 0.15)]
    
    if len(good_matches) < 4:
        print("⚠️ ภาพต่างกันเกินไป ไม่สามารถจัดตำแหน่งอ้างอิงได้")
        return img_after

    # 4. คำนวณเมทริกซ์การบิดเบือน (Homography)
    points1 = np.zeros((len(good_matches), 2), dtype=np.float32)
    points2 = np.zeros((len(good_matches), 2), dtype=np.float32)
    
    for i, match in enumerate(good_matches):
        points1[i, :] = kp1[match.queryIdx].pt
        points2[i, :] = kp2[match.trainIdx].pt
        
    h, mask = cv2.findHomography(points2, points1, cv2.RANSAC)
    
    # 5. ดัดภาพ img_after ให้มุมตรงกับ img_before
    height, width, _ = img_before.shape
    img_after_aligned = cv2.warpPerspective(img_after, h, (width, height))
    
    return img_after_aligned

def test_smart_locker_change(img_before_path, img_after_path):
    """
    ทดสอบการตรวจจับและ 'ประมาณการจำนวน' สิ่งของที่หายไป/เพิ่มมา
    """
    # 1. โหลดภาพ
    img_before = cv2.imread(img_before_path)
    img_after = cv2.imread(img_after_path)

    if img_before is None or img_after is None:
        print("❌ ไม่พบไฟล์รูปภาพ")
        return

    # 2. ย่อภาพให้เท่ากัน
    img_before = resize_image(img_before)
    img_after = resize_image(img_after)

    # 3. จัดภาพให้ตรงกันก่อนเปรียบเทียบ (กำจัด Noise จากกล้องมือถือสั่น)
    print("🔄 กำลังประมวลผลจัดตำแหน่งมุมกล้อง (Image Registration)...")
    img_after_aligned = align_images(img_before, img_after)

    # 4. แปลงสีและทำ Blur
    gray_before = cv2.cvtColor(img_before, cv2.COLOR_BGR2GRAY)
    gray_after = cv2.cvtColor(img_after_aligned, cv2.COLOR_BGR2GRAY)
    
    gray_before = cv2.GaussianBlur(gray_before, (15, 15), 0)
    gray_after = cv2.GaussianBlur(gray_after, (15, 15), 0)

    # 5. หาผลต่าง
    diff = cv2.absdiff(gray_before, gray_after)

    # 6. Threshold (ตั้งให้แข็งขึ้นนิดหน่อยเพื่อตัดแสงสะท้อน)
    _, thresh = cv2.threshold(diff, 60, 255, cv2.THRESH_BINARY)

    # 7. Morphological Operations (ลบจุดรบกวนเล็กๆ)
    # [FIXED] ลดขนาดของ Kernel ลงจาก 11 เหลือ 5 เพื่อไม่ให้มันไปถม "ช่องว่างระหว่างเหรียญ" จนบวมเกินจริง
    kernel = np.ones((5, 5), np.uint8)
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel) 
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel) 

    # 8. หา Contours
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # ==========================================
    # 🌟 CORE LOGIC: ตั้งค่าพื้นที่ของเหรียญในรูปของคุณ
    # ==========================================
    # [FIXED] ปรับเพิ่มขึ้นจาก 25,000 เป็น 28,000 
    # เพื่อให้เป็นค่าเฉลี่ยที่ทนทานต่อการบวมของพื้นที่เมื่อของ 2 ชิ้นวางติดกัน
    EXPECTED_ITEM_AREA = 28000  
    MIN_AREA_THRESHOLD = 5000 # เล็กกว่านี้ตัดทิ้ง
    
    estimated_items_changed = 0
    img_result = img_after.copy()

    for cnt in contours:
        area = cv2.contourArea(cnt)
        
        if area > MIN_AREA_THRESHOLD:
            # นำพื้นที่มาคำนวณจำนวนชิ้น
            items_in_contour = int(round(area / EXPECTED_ITEM_AREA))
            
            if items_in_contour == 0:
                items_in_contour = 1
                
            estimated_items_changed += items_in_contour

            # วาดกรอบและแสดงข้อมูลบนรูป
            x, y, w, h = cv2.boundingRect(cnt)
            cv2.rectangle(img_result, (x, y), (x + w, y + h), (0, 0, 255), 3)
            
            label = f"Area: {int(area)} | Est: {items_in_contour}"
            cv2.putText(img_result, label, (x, y - 10), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

    # 9. แสดงผลลัพธ์ผ่าน Matplotlib
    plt.figure(figsize=(14, 8))
    
    titles = ['Before', 'After (Aligned)', 'Diff Map', 'Threshold', 'Result']
    images = [img_before, img_after_aligned, diff, thresh, img_result]

    for i in range(5):
        plt.subplot(2, 3, i+1)
        if len(images[i].shape) == 2:
            plt.imshow(images[i], cmap='gray')
        else:
            plt.imshow(cv2.cvtColor(images[i], cv2.COLOR_BGR2RGB))
        plt.title(titles[i])
        plt.axis('off')

    plt.tight_layout()
    print("-" * 40)
    print(f"✅ ประมาณการสิ่งของที่เปลี่ยนแปลง (หายไป/เพิ่มมา): {estimated_items_changed} ชิ้น")
    print("-" * 40)
    plt.show()

if __name__ == "__main__":
    # รันโค้ดด้วยรูปของคุณ
    test_smart_locker_change("before.jpeg", "after.jpeg")