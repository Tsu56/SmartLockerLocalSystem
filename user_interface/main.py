import os
from kivymd.app import MDApp
from kivy.lang import Builder
from kivymd.toast import toast
from kivy.properties import StringProperty, ColorProperty, NumericProperty
from kivy.core.window import Window
from kivymd.uix.button import MDRaisedButton, MDTextButton
from kivymd.uix.textfield import MDTextField
from controller.id_card_controller import IDCardController, Clock
import json
from controller.restock_controller import RestockScreen, CartItemWidget, MDScreen, MDDataTable, MDBoxLayout
from controller.dispense_controller import DispenseScreen
from kivy.network.urlrequest import UrlRequest

Window.size = (1024, 600)

GATEWAY_URL = "http://localhost:5000/api"

AUTH_CARD_URL = f"{GATEWAY_URL}/auth/auth/login/smartcard"
AUTH_PWD_URL = f"{GATEWAY_URL}/auth/auth/login/password"

KV_FILES = [
    "screen/main_screen.kv",
    "screen/id_card_login.kv",
    "screen/rfid_staff_tag.kv",
    "screen/qr_scan_screen.kv",
    "screen/user_pass_login.kv",
    "screen/home_screen.kv",
    "screen/dispense_screen.kv",
    "screen/restock_screen.kv",
    "screen/provision_screen.kv",
]

screen_helper = """
MDScreenManager:
    id: screen_manager
    MainScreen:
    IDCardLoginScreen:
    RFIDLoginScreen:
    QRScanScreen:
    UserPassLoginScreen:
    HomeScreen:
    RestockScreen:
    DispenseScreen:
    ProvisionScreen:
"""

class SmartLockerApp(MDApp):
    current_screen_name = StringProperty("main_screen")
    card_border_color = ColorProperty([0.878, 0.878, 0.878, 1]) # เริ่มต้นที่ Light Gray
    card_border_width = NumericProperty(1)
    card_status_text = StringProperty("Status: Ready for card insertion.")
    card_status_color = ColorProperty([0, 0, 0, 0.6])

    status_error_color = [0.906, 0.298, 0.235, 1]      # Red
    status_success_color = [0.18, 0.8, 0.443, 1]    # Green
    status_ready_color = [0.878, 0.878, 0.878, 1]    # Light Gray

    def build(self):
        self.theme_cls.theme_style = "Light"
        self.theme_cls.primary_palette = "Blue"

        self.id_card_controller = IDCardController()
        self.id_card_controller.bind(card_data=self.handle_card_data)

        for file in KV_FILES:
            if os.path.exists(file):
                Builder.load_file(file)
            else:
                print(f"Warning: KV file '{file}' not found.")
        
        screen = Builder.load_string(screen_helper)
        return screen
    
    def on_start(self):
        self.id_card_controller.bind(is_card_detected=self._sync_card_ui)
        self.id_card_controller.bind(status_text=self._sync_text_ui)
        self.id_card_controller.bind(error_msg=self._sync_error_ui)

        Clock.schedule_interval(self._poll_card_reader, 0.5)

    def _poll_card_reader(self, dt):
        if self.current_screen_name == "id_card_login":
            self.id_card_controller.check_status()

    def handle_card_data(self, instance, value):
        """จัดการข้อมูลที่ได้จากบัตร"""
        citizen_id = value.get('citizenID')
        if not citizen_id:
            return
        
        payload = json.dumps({
            "citizen_id": str(citizen_id).strip()
        })

        headers = {'Content-type': 'application/json', 'Accept': 'application/json'}
        
        UrlRequest(
            AUTH_CARD_URL,
            req_body=payload,
            req_headers=headers,
            on_success=self._on_login_success,
            on_failure=self._on_login_failed,
            on_error=self._on_login_error,
            method='POST',
            timeout=10
        )
    
    def _sync_card_ui(self, instance, is_present):
        if is_present:
            self.card_border_color = self.status_success_color
            self.card_border_width = 4
            self.card_status_color = self.status_success_color
        else:
            self.card_border_color = self.status_ready_color
            self.card_border_width = 1
            self.card_status_color = [0, 0, 0, 0.6]

    def _sync_text_ui(self, instance, text):
        self.card_status_text = text

    def _sync_error_ui(self, instance, error_msg):
        if error_msg:
            self.card_border_color = self.status_error_color
            self.card_border_width = 4
            self.card_status_color = self.status_error_color
            self.card_status_text = error_msg

    def process_login(self, username, password):
        # 1. ตรวจสอบค่าว่างเบื้องต้นก่อนส่ง
        if not username.strip() or not password.strip():
            self.show_toast("Please enter both username and password")
            return
            
        print(f"DEBUG: Connecting to Docker API for user: {username}")
        
        # 2. เตรียมข้อมูลในรูปแบบ JSON
        payload = json.dumps({
            "username": username.strip(),
            "password": password.strip()
        })
        
        # 3. ส่ง Request ไปที่ Docker Container
        # headers สำคัญมากเพื่อให้ FastAPI รู้ว่าเป็นข้อมูล JSON
        headers = {'Content-type': 'application/json', 'Accept': 'application/json'}
        
        UrlRequest(
            AUTH_PWD_URL,
            req_body=payload,
            req_headers=headers,
            on_success=self._on_login_success,
            on_failure=self._on_login_failed,
            on_error=self._on_login_error,
            method='POST',
            timeout=10
        )

    def _on_login_success(self, request, result):
        """กรณี Login สำเร็จ (HTTP 200)"""
        print(f"DEBUG: Raw Success Result: {result}")

        # ตรวจสอบโครงสร้างข้อมูล (รองรับทั้งแบบมีคีย์ 'user' ครอบ และแบบส่ง object มาตรงๆ)
        if isinstance(result, dict):
            # ถ้ามีคีย์ 'user' ให้ดึงมา ถ้าไม่มีให้ถือว่า result คือข้อมูล user เลย
            user_data = result.get("user") if "user" in result else result
            
            # ดึงชื่อแสดงผล โดยลองจาก full_name -> username -> ค่าเริ่มต้น "User"
            # ใช้ .get() และตรวจสอบว่าเป็น None หรือไม่
            full_name = user_data.get("full_name") or user_data.get("username") or "User"
            username = user_data.get("username", "Unknown")
            
            self.show_toast(f"Welcome, {full_name}!")
            print(f"DEBUG: Login Success for {username}")
        else:
            # กรณี result ไม่ใช่ dict (เช่น เป็น string)
            self.show_toast("Welcome!")
            print(f"DEBUG: Login Success but result is not a dictionary")
        
        # เปลี่ยนหน้าไปยังหน้าหลักของระบบหลังจากแสดง Toast 1 วินาที
        Clock.schedule_once(lambda dt: self.change_screen("home_screen"), 1)

    def _on_login_failed(self, request, result):
        """กรณีข้อมูลไม่ถูกต้อง (เช่น HTTP 401)"""
        # 1. ตรวจสอบว่า result เป็น Dictionary หรือไม่
        if isinstance(result, dict):
            # ถ้าเป็น Dict ให้ดึงค่าจาก key "detail"
            error_msg = result.get("detail", "Authentication failed")
        else:
            # 2. ถ้าเป็น String หรืออย่างอื่น ให้แปลงเป็น string และใช้งานโดยตรง
            # (บางครั้ง FastAPI อาจจะส่งแค่ string สั้นๆ มาให้)
            error_msg = str(result) if result else "Authentication failed"

        self.show_toast(error_msg)
        print(f"DEBUG: Login Failed - {error_msg}")

    def _on_login_error(self, request, error):
        """กรณีเชื่อมต่อ Server ไม่ได้ (Docker ไม่รัน หรือ Network มีปัญหา)"""
        self.show_toast("Network Error: Cannot connect to Auth Service")
        print(f"DEBUG: Connection Error - {error}")

    def go_to_dispense(self):
        print("Navigating to Dispense Mode")
        # เตรียม Logic สำหรับเปลี่ยนหน้าไปหน้าเบิกของ
        # self.change_screen("dispense_screen") 
        self.change_screen("dispense_screen")

    def go_to_restock(self):
        print("Navigating to Restock Mode")
        # เตรียม Logic สำหรับเปลี่ยนหน้าไปหน้าเติมของ
        self.change_screen("restock_screen")

    def logout(self):
        print("Logging out...")
        # เคลียร์ค่าต่างๆ ถ้าจำเป็น
        self.change_screen("main_screen")
        self.show_toast("ออกจากระบบเรียบร้อยแล้ว")
    
    def change_screen(self, screen_name):
        self.root.current = screen_name
        self.current_screen_name = screen_name
        print(f"Changing screen to: {screen_name}")

    def go_back(self):
        self.change_screen("main_screen")
        
    def show_toast(self, message):
        print(f"Toast: {message}")
        toast(message)
    
if __name__ == '__main__':
    SmartLockerApp().run()