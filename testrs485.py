import serial
import time
import threading

PORT = "COM3"  # เปลี่ยนตามเครื่องของคุณ
BAUDRATE = 38400
device_addresses = ['S1', 'S2']

ser = serial.Serial(PORT, BAUDRATE, timeout=0.5)
serial_lock = threading.Lock()
running = True

def calculate_checksum(data_str):
    checksum = 0
    for char in data_str:
        checksum ^= ord(char)
    return f"{checksum:02X}"

def send_command(address, command):
    full_cmd = f"{address}:{command}"
    with serial_lock:
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        ser.write((full_cmd + "\n").encode())
        ser.flush()

    return full_cmd

def read_response():
    with serial_lock:
        try:
            raw_line = ser.readline().decode(errors="ignore").strip()
        except:
            return None
    
    if not raw_line:
        return None
    
    if "|" in raw_line:
        data_part, recv_cs = raw_line.rsplit("|", 1)
        calc_cs = calculate_checksum(data_part)

        if recv_cs == calc_cs:
            return data_part
        else:
            print(f"[ERROR] Checksum Mismatch! Recv: {recv_cs}, Calc: {calc_cs}")
            return None
    else:
        return raw_line

def auto_loop():
    """ส่งคำสั่ง GETDATA ไปยังทุกช่อง S1–S6 แบบวนลูป"""
    global running
    print(f"Starting Auto-Plling loop for: {device_addresses}")
    time.sleep(2)

    while running:
        for addr in device_addresses:
            if not running: break

            cmd = "GETDATA"
            send_command(addr, cmd)
            response = read_response()

            if response:
                print(f"[SUCCESS] {addr} => {response}")
            else:
                print(f"[TIMEOUT] {addr} did not respond or data corrupted.")
            
            time.sleep(0.1)

        time.sleep(1)

def manual_input():
    """รับคำสั่งจากผู้ใช้"""
    global running
    print("Manual mode ready. Type 'S1:DOORLOCKON' etc.")
    while running:
        msg = input().strip()
        if msg.lower() == "exit":
            running = False
            print("Stopping auto loop...")
            break
        elif msg == "":
            continue

        parts = msg.split(':')
        if len(parts) == 2:
            send_command(parts[0], parts[1])
            print(f"Manual Sent: {msg}")
            res = read_response()
            if res:
                print(f"Reply: {res}")
            else:
                print("No reply.")
        else:
            print("Invalid format. Use ADDR:CMD")


# เริ่ม Thread สำหรับ auto loop และ manual input พร้อมกัน
thread_auto = threading.Thread(target=auto_loop, daemon=True)
thread_auto.start()

try:
    manual_input()
except KeyboardInterrupt:
    running = False

# ปิดพอร์ตเมื่อออกจากโปรแกรม
ser.close()
print("Serial port closed. Program ended.")