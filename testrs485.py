import serial
import time
import threading

PORT = "COM3"  # เปลี่ยนตามเครื่องของคุณ
BAUDRATE = 38400

ser = serial.Serial(PORT, BAUDRATE, timeout=1)
time.sleep(2)

device_addresses = ['S1', 'S2', 'S3', 'S4', 'S5', 'S6']
running = True  # flag สำหรับหยุดลูป

def auto_loop():
    """ส่งคำสั่ง GETDATA ไปยังทุกช่อง S1–S6 แบบวนลูป"""
    global running
    while running:
        for addr in device_addresses:
            if not running:
                break
            command = f"{addr}:GETDATA"
            ser.write((command + "\n").encode())
            ser.flush()
            print(f"[AUTO] Send: {command}")

            time.sleep(0.1)  # เว้นช่วงเล็กน้อย

            response = ser.readline().decode(errors="ignore").strip()
            if response:
                print(f"[AUTO] Arduino replied: {response}")
            else:
                print("[AUTO] (no response)")

        time.sleep(2)  # เว้นระยะก่อนลูปใหม่ (ปรับได้ตามต้องการ)


def manual_input():
    """รับคำสั่งจากผู้ใช้"""
    global running
    while running:
        msg = input("Send manual command (or type 'exit' to stop): ").strip()
        if msg.lower() == "exit":
            running = False
            print("Stopping auto loop...")
            break
        elif msg == "":
            continue  # ถ้าไม่พิมพ์อะไร ข้ามไป

        # ส่งคำสั่งที่ผู้ใช้พิมพ์เอง
        ser.write((msg + "\n").encode())
        ser.flush()
        print("Send:", msg)

        time.sleep(0.1)
        response = ser.readline().decode(errors="ignore").strip()
        if response:
            print("Arduino replied:", response)
        else:
            print("(no response)")


# เริ่ม Thread สำหรับ auto loop และ manual input พร้อมกัน
thread_auto = threading.Thread(target=auto_loop, daemon=True)
thread_auto.start()

manual_input()

# ปิดพอร์ตเมื่อออกจากโปรแกรม
ser.close()
print("Serial port closed. Program ended.")