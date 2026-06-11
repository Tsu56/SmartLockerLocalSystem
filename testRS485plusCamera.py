import tkinter as tk
from tkinter import ttk, scrolledtext
import serial
import time
import threading
import queue
import cv2
from PIL import Image, ImageTk

PORT = "/dev/ttyUSB0"  # เปลี่ยนตามเครื่องของคุณ
BAUDRATE = 38400
device_addresses = ['S1', 'S2', 'S3', 'S4']
VIDEO_INDEX = 0

# คำสั่งที่ใช้บ่อยสำหรับใส่ใน Dropdown
COMMON_COMMANDS = [
    "GETDATA",
    "DOORLOCKON", "DOORLOCKOFF",
    "CAMERAON", "CAMERAOFF",
    "STATUSON", "STATUSOFF",
    "CAMERAPOWERON", "CAMERAPOWEROFF"
]

class SmartLockerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Smart Locker Control Panel (Camera + RS485)")
        self.root.geometry("1100x600") # ขยายหน้าต่างให้กว้างขึ้นเพื่อรองรับกล้อง
        
        self.ser = None
        self.serial_lock = threading.Lock()
        self.running = True
        self.auto_polling = False
        self.log_queue = queue.Queue()

        self.setup_ui()
        self.connect_serial()
        
        # --- เริ่มระบบกล้อง ---
        self.cap = cv2.VideoCapture(VIDEO_INDEX)
        if not self.cap.isOpened():
            self.log(f"❌ Error: ไม่สามารถเปิดกล้องหมายเลข {VIDEO_INDEX} ได้")
        else:
            self.log(f"✅ Camera initialized (Index: {VIDEO_INDEX})")
            self.update_camera_frame() # เริ่มลูปดึงภาพ

        # เริ่มอัปเดต UI จาก Queue
        self.root.after(100, self.process_log_queue)

        # เริ่ม Thread สำหรับ Auto-loop
        self.thread_auto = threading.Thread(target=self.auto_loop, daemon=True)
        self.thread_auto.start()

    def setup_ui(self):
        # สร้าง Frame หลักแบ่งซ้าย-ขวา
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # ================= ฝั่งซ้าย: กล้องวงจรปิด =================
        frame_left = ttk.LabelFrame(main_frame, text="AV Camera Feed", padding=10)
        frame_left.pack(side="left", fill="both", expand=True, padx=(0, 5))

        self.video_label = ttk.Label(frame_left, text="กำลังโหลดกล้อง หรือ ไม่พบกล้อง...")
        self.video_label.pack(fill="both", expand=True)

        # ================= ฝั่งขวา: ควบคุม RS485 =================
        frame_right = ttk.Frame(main_frame)
        frame_right.pack(side="right", fill="both", expand=True, padx=(5, 0))

        # --- Frame บน: ควบคุม Auto Polling ---
        frame_top = ttk.LabelFrame(frame_right, text="Auto Polling (GETDATA)", padding=10)
        frame_top.pack(fill="x", pady=(0, 5))

        self.btn_toggle_poll = ttk.Button(frame_top, text="▶ Start Auto-Polling", command=self.toggle_polling)
        self.btn_toggle_poll.pack(side="left", padx=5)

        self.lbl_status = ttk.Label(frame_top, text="Status: Stopped", foreground="red")
        self.lbl_status.pack(side="left", padx=10)

        # --- Frame กลาง: ส่งคำสั่ง Manual ---
        frame_mid = ttk.LabelFrame(frame_right, text="Manual Command", padding=10)
        frame_mid.pack(fill="x", pady=5)

        ttk.Label(frame_mid, text="Address:").grid(row=0, column=0, padx=5, pady=5)
        self.cb_address = ttk.Combobox(frame_mid, values=device_addresses, width=5, state="readonly")
        self.cb_address.current(1) # ค่าเริ่มต้น S2
        self.cb_address.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(frame_mid, text="Command:").grid(row=0, column=2, padx=5, pady=5)
        self.cb_command = ttk.Combobox(frame_mid, values=COMMON_COMMANDS, width=15)
        self.cb_command.current(1) # ค่าเริ่มต้น DOORLOCKON
        self.cb_command.grid(row=0, column=3, padx=5, pady=5)

        self.btn_send = ttk.Button(frame_mid, text="Send Command", command=self.on_send_manual)
        self.btn_send.grid(row=1, column=0, columnspan=4, pady=10)

        # --- Frame ล่าง: Log แสดงผล ---
        frame_bottom = ttk.LabelFrame(frame_right, text="Communication Log", padding=10)
        frame_bottom.pack(fill="both", expand=True, pady=(5, 0))

        self.txt_log = scrolledtext.ScrolledText(frame_bottom, wrap=tk.WORD, height=10)
        self.txt_log.pack(fill="both", expand=True)
        
        btn_clear = ttk.Button(frame_bottom, text="Clear Log", command=lambda: self.txt_log.delete(1.0, tk.END))
        btn_clear.pack(side="right", pady=5)

    # ================= ฟังก์ชันระบบกล้อง =================
    def update_camera_frame(self):
        if self.cap.isOpened() and self.running:
            ret, frame = self.cap.read()
            if ret:
                # แปลงสีจาก BGR (OpenCV) เป็น RGB (Pillow/Tkinter)
                cv_img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                # ปรับขนาดภาพให้พอดีกับ UI (ปรับขนาดได้ตามต้องการ)
                cv_img = cv2.resize(cv_img, (640, 480)) 
                
                # แปลงเป็น Image ของ Tkinter
                pil_img = Image.fromarray(cv_img)
                imgtk = ImageTk.PhotoImage(image=pil_img)
                
                # อัปเดตภาพลงบน Label
                self.video_label.imgtk = imgtk
                self.video_label.configure(image=imgtk, text="")
            else:
                self.video_label.configure(text="สัญญาณภาพขาดหาย (No Signal)")

            # วนลูปเรียกฟังก์ชันนี้ซ้ำทุกๆ 30 มิลลิวินาที (~33 FPS)
            self.root.after(30, self.update_camera_frame)

    # ================= ฟังก์ชันระบบ RS485 (คงเดิม) =================
    def connect_serial(self):
        try:
            self.ser = serial.Serial(PORT, BAUDRATE, timeout=0.5)
            self.log(f"✅ Connected to {PORT} at {BAUDRATE} bps")
        except Exception as e:
            self.log(f"❌ Failed to connect to {PORT}: {e}")
            self.ser = None

    def log(self, message):
        self.log_queue.put(message)

    def process_log_queue(self):
        while not self.log_queue.empty():
            msg = self.log_queue.get()
            self.txt_log.insert(tk.END, msg + "\n")
            self.txt_log.see(tk.END)
        if self.running:
            self.root.after(100, self.process_log_queue)

    def calculate_checksum(self, data_str):
        checksum = 0
        for char in data_str:
            checksum ^= ord(char)
        return f"{checksum:02X}"

    def send_command(self, address, command):
        if not self.ser:
            self.log("⚠️ Serial not connected!")
            return None

        full_cmd = f"{address}:{command}"
        with self.serial_lock:
            try:
                self.ser.reset_input_buffer()
                self.ser.reset_output_buffer()
                self.ser.write((full_cmd + "\n").encode())
                self.ser.flush()
            except Exception as e:
                self.log(f"❌ Send Error: {e}")
        return full_cmd

    def read_response(self):
        if not self.ser: return None
        
        with self.serial_lock:
            try:
                raw_line = self.ser.readline().decode(errors="ignore").strip()
            except Exception as e:
                return None
        
        if not raw_line:
            return None
        
        if "|" in raw_line:
            data_part, recv_cs = raw_line.rsplit("|", 1)
            calc_cs = self.calculate_checksum(data_part)

            if recv_cs == calc_cs:
                return data_part
            else:
                self.log(f"[ERROR] Checksum Mismatch! Recv: {recv_cs}, Calc: {calc_cs}")
                return None
        else:
            return raw_line

    def auto_loop(self):
        while self.running:
            if self.auto_polling:
                for addr in device_addresses:
                    if not self.auto_polling or not self.running: break

                    self.send_command(addr, "GETDATA")
                    response = self.read_response()

                    if response:
                        self.log(f"🔄 [AUTO {addr}] {response}")
                    else:
                        self.log(f"⚠️ [TIMEOUT] {addr} did not respond.")
                    
                    time.sleep(0.1)
                time.sleep(1)
            else:
                time.sleep(0.5)

    def toggle_polling(self):
        self.auto_polling = not self.auto_polling
        if self.auto_polling:
            self.btn_toggle_poll.config(text="⏹ Stop Auto-Polling")
            self.lbl_status.config(text="Status: Polling...", foreground="green")
            self.log("▶ Started Auto-Polling")
        else:
            self.btn_toggle_poll.config(text="▶ Start Auto-Polling")
            self.lbl_status.config(text="Status: Stopped", foreground="red")
            self.log("⏹ Stopped Auto-Polling")

    def on_send_manual(self):
        addr = self.cb_address.get()
        cmd = self.cb_command.get().strip()
        
        if not cmd:
            self.log("⚠️ Please enter a command.")
            return

        self.log(f"➡️ Manual Sent: {addr}:{cmd}")
        self.send_command(addr, cmd)
        
        res = self.read_response()
        if res:
            self.log(f"⬅️ Reply: {res}")
        else:
            self.log("❌ No reply.")

    def on_closing(self):
        self.running = False
        # คืนทรัพยากรกล้องให้ระบบ
        if hasattr(self, 'cap') and self.cap.isOpened():
            self.cap.release()
        if self.ser:
            self.ser.close()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = SmartLockerApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()