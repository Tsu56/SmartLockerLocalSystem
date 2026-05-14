import os
import subprocess
from kivymd.app import MDApp
from kivy.lang import Builder
from kivymd.toast import toast
from kivy.properties import StringProperty, ColorProperty, NumericProperty, BooleanProperty, DictProperty
from kivy.core.window import Window
from kivy.core.text import LabelBase, DEFAULT_FONT
from kivymd.uix.button import MDRaisedButton, MDTextButton
from kivymd.uix.textfield import MDTextField
from controller.id_card_controller import IDCardController, Clock
import json
from controller.restock_controller import RestockScreen, MDScreen, MDDataTable, MDBoxLayout
from controller.dispense_controller import DispenseScreen
from kivy.network.urlrequest import UrlRequest

Window.size = (1024, 600)


def setup_default_thai_font():
    font_candidates = [
        {
            "regular": "fonts/NotoSansThai-Regular.ttf",
            "bold": "fonts/NotoSansThai-Bold.ttf",
            "italic": "fonts/NotoSansThai-Regular.ttf",
            "bolditalic": "fonts/NotoSansThai-Bold.ttf",
        },
        {
            "regular": "/usr/share/fonts/truetype/freefont/FreeSerif.ttf",
            "bold": "/usr/share/fonts/truetype/freefont/FreeSerifBold.ttf",
            "italic": "/usr/share/fonts/truetype/freefont/FreeSerifItalic.ttf",
            "bolditalic": "/usr/share/fonts/truetype/freefont/FreeSerifBoldItalic.ttf",
        },
    ]

    for font in font_candidates:
        if os.path.exists(font["regular"]):
            # ลงทะเบียนในชื่อ 'Thai' เพื่อใช้อ้างอิงเฉพาะจุด
            LabelBase.register(
                name="Thai",
                fn_regular=font["regular"],
                fn_bold=font["bold"] if os.path.exists(font["bold"]) else font["regular"],
                fn_italic=font["italic"] if os.path.exists(font["italic"]) else font["regular"],
                fn_bolditalic=font["bolditalic"] if os.path.exists(font["bolditalic"]) else font["regular"],
            )
            
            # [CRITICAL] ทับชื่อ 'Roboto' เพื่อให้มีผลกับ MDDialog และ Widget ทั้งหมดของ KivyMD
            LabelBase.register(
                name=DEFAULT_FONT,
                fn_regular=font["regular"],
                fn_bold=font["bold"] if os.path.exists(font["bold"]) else font["regular"],
                fn_italic=font["italic"] if os.path.exists(font["italic"]) else font["regular"],
                fn_bolditalic=font["bolditalic"] if os.path.exists(font["bolditalic"]) else font["regular"],
            )
            print(f"✅ Using Thai-compatible font: {font['regular']}")
            return

    print("Warning: Thai-compatible font not found. Please add a Thai font in user_interface/fonts/")

GATEWAY_URL = "http://localhost:5000/api"

AUTH_CARD_URL = f"{GATEWAY_URL}/auth/auth/login/smartcard"
AUTH_PWD_URL = f"{GATEWAY_URL}/auth/auth/login/password"
QR_TASK_RESOLVE_URL = f"{GATEWAY_URL}/product/locker/qr-tasks/resolve"
QR_TASK_COMPLETE_BASE_URL = f"{GATEWAY_URL}/product/locker/qr-tasks"

DEVICE_ACTIVATE_URL = f"{GATEWAY_URL}/identity/device/activate"
DEVICE_INFO_URL = f"{GATEWAY_URL}/identity/device/info"

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

class HomeScreen(MDScreen):
    def on_enter(self):
        app = MDApp.get_running_app()
        if app.user_permissions.get("can_withdraw"):
            self.ids.btn_dispense.disabled = False
        else:
            self.ids.btn_dispense.disabled = True
        if app.user_permissions.get("can_restock"):
            self.ids.btn_restock.disabled = False
        else:
            self.ids.btn_restock.disabled = True
        self.ids.btn_qr_task.disabled = not bool(app.user_id)

class SmartLockerApp(MDApp):
    current_screen_name = StringProperty("main_screen")
    card_border_color = ColorProperty([0.878, 0.878, 0.878, 1]) # เริ่มต้นที่ Light Gray
    card_border_width = NumericProperty(1)
    card_status_text = StringProperty("Status: Ready for card insertion.")
    card_status_color = ColorProperty([0, 0, 0, 0.6])
    is_activated = BooleanProperty(False)
    user_id = StringProperty("")
    user_permissions = DictProperty({"can_withdraw": False, "can_restock": False})
    current_qr_task = DictProperty({})

    status_error_color = [0.906, 0.298, 0.235, 1]      # Red
    status_success_color = [0.18, 0.8, 0.443, 1]    # Green
    status_ready_color = [0.878, 0.878, 0.878, 1]    # Light Gray

    def build(self):
        setup_default_thai_font()
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

        Clock.schedule_once(lambda dt: self.check_device_status(), 0.1)

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

    def submit_registration(self, provision_code):
        if not provision_code.strip():
            self.show_toast("Please enter the provision code")
            return
        
        # Logic สำหรับส่ง provision code ไปยัง Server เพื่อทำการลงทะเบียน
        print(f"Submitting provision code: {provision_code}")
        # ตัวอย่างการส่ง Request (สามารถปรับ URL และ Payload ตาม API ที่มี)
        payload = json.dumps({
            "provision_code": provision_code.strip()
        })
        
        headers = {'Content-type': 'application/json', 'Accept': 'application/json'}
        
        UrlRequest(
            DEVICE_ACTIVATE_URL,
            req_body=payload,
            req_headers=headers,
            on_success=self._on_device_activation_success,
            on_failure=self._on_device_activation_failed,
            on_error=self._on_device_activation_error,
            method='POST',
            timeout=10
        )

    def _on_device_activation_success(self, request, result):
        self.show_toast("Device activated successfully!")
        Clock.schedule_once(lambda dt: self.change_screen("main_screen"), 1)
    
    def _on_device_activation_failed(self, request, result):
        self.show_toast("Device activation failed: " + str(result))
    
    def _on_device_activation_error(self, request, error):
        self.show_toast("Network error during device activation: " + str(error))

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
        user_data = result.get("user", {})

        self.user_id = user_data.get("user_id", "")
        self.user_permissions = user_data.get("permissions", {"can_withdraw": False, "can_restock": False})

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

    def check_device_status(self, dt=None):
        """ยิง API ไปเช็คที่ Local Backend ว่าตู้ยังมีสิทธิ์อยู่หรือไม่"""
        UrlRequest(
            DEVICE_INFO_URL,
            on_success=self._on_device_status_success,
            on_failure=self._on_device_status_failed,
            on_error=self._on_device_status_error,
            timeout=3
        )

    def _on_device_status_success(self, request, result):
        """ถ้าตู้ปกติ (HTTP 200) ไม่ต้องทำอะไร ปล่อยให้ใช้งานต่อ"""
        self.is_activated = result.get("is_active", True)
        # (Optional) ถ้าปัจจุบันอยู่หน้า provision_screen แต่ตู้ Activate แล้ว ให้เด้งกลับ main_screen
        if self.current_screen_name == "provision_screen":
            self.change_screen("main_screen")

    def _on_device_status_failed(self, request, result):
        """ถ้า Local Backend ตอบกลับมาเป็น 4xx (เช่น 404 Device not activated)"""
        # ถ้าไม่ได้อยู่หน้า provision_screen ให้เตะส่งไปหน้านั้นทันที
        if self.current_screen_name != "provision_screen":
            print("🔒 Device Revoked or Not Activated! Redirecting to provision_screen...")
            self.change_screen("provision_screen")
            self.show_toast("เครื่องนี้ยังไม่ได้ลงทะเบียน หรือถูกยกเลิกสิทธิ์แล้ว")

    def _on_device_status_error(self, request, error):
        """ถ้าเชื่อมต่อ Local Backend ไม่ได้ (เช่น Docker ดับ)"""
        # ตรงนี้ไม่ต้องเตะไปหน้า provision เพราะอาจจะแค่เน็ตเวิร์คกระตุก
        # ให้รอเช็ครอบถัดไป หรืออาจจะทำเป็นไอคอนแจ้งเตือน Offline
        pass

    def enforce_device_activation(self):
        """ฟังก์ชันกลางสำหรับเช็คว่าถ้าตู้ไม่ active ให้เด้งไปหน้าลงทะเบียนทันที"""
        print(f"Device Activation Status: {self.is_activated}")
        
        if not self.is_activated:
            print("🚨 Alert: Access denied. Device is not activated.")
            if self.current_screen_name != "provision_screen":
                self.change_screen("provision_screen")
                self.show_toast("เครื่องยังไม่ได้ลงทะเบียน หรือถูกระงับการใช้งาน")
                return False
        return True

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
        self.user_id = ""
        self.user_permissions = {"can_withdraw": False, "can_restock": False}
        self.current_qr_task = {}
        self.change_screen("main_screen")
        self.show_toast("ออกจากระบบเรียบร้อยแล้ว")

    def go_to_qr_task_scan(self):
        if not self.user_id:
            self.show_toast("กรุณาเข้าสู่ระบบก่อน")
            return
        self.change_screen("qr_scan_screen")

    def ensure_english_keyboard_layout(self):
        """Best effort: switch active keyboard layout to English on Linux."""
        try:
            subprocess.run(["setxkbmap", "us"], check=False)
        except Exception as e:
            print(f"⚠️ Unable to switch keyboard layout to English: {e}")

    def handle_qr_submit(self, qr_raw_data):
        if self.current_screen_name != "qr_scan_screen":
            return

        qr_token = (qr_raw_data or "").strip()
        if not qr_token:
            self.show_toast("กรุณากรอก/สแกน QR Code")
            return

        payload = json.dumps({
            "qr_token": qr_token,
            "user_id": self.user_id,
        })
        headers = {"Content-type": "application/json", "Accept": "application/json"}

        UrlRequest(
            QR_TASK_RESOLVE_URL,
            req_body=payload,
            req_headers=headers,
            on_success=self._on_qr_task_resolve_success,
            on_failure=self._on_qr_task_resolve_failed,
            on_error=self._on_qr_task_resolve_error,
            method="POST",
            timeout=10,
        )

    def _on_qr_task_resolve_success(self, request, result):
        if not isinstance(result, dict):
            self.show_toast("รูปแบบข้อมูล QR task ไม่ถูกต้อง")
            return

        task_type = (result.get("task_type") or "").strip().lower()
        self.current_qr_task = result

        if task_type == "restock":
            screen = self.root.get_screen("restock_screen")
            screen.load_qr_task(result)
            self.change_screen("restock_screen")
            self.show_toast("โหลดรายการเติมจาก QR สำเร็จ")
            return

        if task_type == "dispense":
            screen = self.root.get_screen("dispense_screen")
            screen.load_qr_task(result)
            self.change_screen("dispense_screen")
            self.show_toast("โหลดรายการเบิกจาก QR สำเร็จ")
            return

        self.show_toast(f"ประเภทรายการไม่รองรับ: {task_type or '-'}")

    def _on_qr_task_resolve_failed(self, request, result):
        detail = "ไม่สามารถตรวจสอบ QR task ได้"
        if isinstance(result, dict):
            detail = result.get("detail", detail)
        self.show_toast(str(detail))

    def _on_qr_task_resolve_error(self, request, error):
        self.show_toast("Network Error: Cannot resolve QR task")
        print(f"DEBUG: QR resolve error - {error}")

    def complete_active_qr_task(self):
        task_id = self.current_qr_task.get("task_id") if isinstance(self.current_qr_task, dict) else None
        if not task_id:
            return

        url = f"{QR_TASK_COMPLETE_BASE_URL}/{task_id}/complete"
        payload = {"user_id": self.user_id}
        try:
            req = UrlRequest(
                url,
                req_body=json.dumps(payload),
                req_headers={"Content-type": "application/json", "Accept": "application/json"},
                method="POST",
                timeout=8,
            )
            _ = req
            self.current_qr_task = {}
        except Exception as e:
            print(f"⚠️ Failed to complete QR task {task_id}: {e}")
    
    def change_screen(self, screen_name):
        if screen_name == "qr_scan_screen":
            self.ensure_english_keyboard_layout()
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