from kivymd.uix.screen import MDScreen
from kivy.clock import Clock
from kivymd.app import MDApp

try:
    from mfrc522 import SimpleMFRC522
    HAS_RFID = True
except ImportError:
    print("⚠️ ไม่พบไลบรารี mfrc522 ในระบบ")
    HAS_RFID = False

class RFIDLoginScreen(MDScreen):
    rfid_event = None
    reader = None

    def on_enter(self):
        """ทำงานเมื่อเปิดเข้ามาหน้านี้"""
        # เปิดเครื่องอ่าน
        if HAS_RFID and self.reader is None:
            self.reader = SimpleMFRC522()
        
        # เริ่มตั้งเวลาแอบเช็คเครื่องอ่านทุกๆ 0.5 วินาที
        if HAS_RFID:
            self.rfid_event = Clock.schedule_interval(self._poll_reader, 0.5)

    def on_leave(self):
        """ทำงานเมื่อกดปิด หรือย้ายไปหน้าอื่น"""
        self._stop_reading()

    def _poll_reader(self, dt):
        print("🔍 กำลังเช็คบัตร RFID...")
        
        """ฟังก์ชันแอบเช็คแบบไม่บล็อกหน้าจอ"""
        if not self.reader:
            return
            
        # ใช้ no_block เพื่อให้หน้าจอยังลื่นไหล
        card_id = self.reader.read_id_no_block()
        
        if card_id:
            print(f"💳 RFID Login Detected: {card_id}")
            self._stop_reading() # หยุดอ่านทันทีกันมันเบิ้ลรัวๆ
            self.process_rfid_login(str(card_id))

    def _stop_reading(self):
        """ยกเลิกตัวจับเวลา"""
        if self.rfid_event:
            self.rfid_event.cancel()
            self.rfid_event = None

    def process_rfid_login(self, card_uid):
        """ส่งเลข UID ไปให้แอปหลักจัดการต่อ"""
        app = MDApp.get_running_app()
        app.show_toast("อ่านบัตรสำเร็จ! กำลังเข้าสู่ระบบ...")
        app.process_rfid_login_request(card_uid)