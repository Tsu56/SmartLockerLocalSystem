import sys
import os
from typing import Optional
from kivymd.uix.screen import MDScreen
from kivymd.uix.list import TwoLineAvatarIconListItem, IconRightWidget
from kivymd.uix.dialog import MDDialog
from kivymd.uix.button import MDFlatButton, MDRaisedButton
from kivymd.app import MDApp
from sqlmodel import Session, create_engine, select, or_, SQLModel, Field
import requests
import json
from kivymd.uix.list import TwoLineAvatarIconListItem, IconRightWidget, IconLeftWidget
from kivy.clock import Clock
from kivy.network.urlrequest import UrlRequest

try:
    from mfrc522 import SimpleMFRC522
    import RPi.GPIO as GPIO
    HAS_RFID = True
except ImportError:
    print("⚠️ ไม่พบไลบรารี mfrc522 โหมดฮาร์ดแวร์จะถูกปิดใช้งาน (ใช้ปุ่มจำลองแทน)")
    HAS_RFID = False

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
DB_PATH = os.path.join(BASE_DIR, "local_auth_service", "database", "local_auth.db")

if not os.path.exists(DB_PATH):
    print(f"\n❌ หาไฟล์ฐานข้อมูลไม่เจอครับ! ระบบกำลังพยายามหาที่: {DB_PATH}\n")
else:
    print(f"\n✅ เจอไฟล์ฐานข้อมูลแล้วที่: {DB_PATH}\n")

sqlite_url = f"sqlite:///{DB_PATH}"

engine = create_engine(sqlite_url)

class User(SQLModel, table=True):
    __tablename__ = "user"

    user_id: str = Field(primary_key=True)
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    card_uid: Optional[str] = None
    deleted_at: Optional[str] = None

class AdminRfidScreen(MDScreen):
    dialog = None
    active_target_user_id = None
    rfid_event = None  # 👉 ตัวแปรสำหรับเก็บ Event นาฬิกาจับเวลา
    reader = None      # 👉 ตัวแปรสำหรับเก็บตัวอ่านฮาร์ดแวร์

    def on_enter(self):
        """จะทำงานอัตโนมัติเมื่อแอดมินเปิดเข้ามาที่หน้านี้"""
        # ล้างช่องค้นหาเก่าและโหลดพนักงานทั้งหมดขึ้นมาใหม่
        self.ids.search_field.text = ""
        self.load_users_from_db()

        if HAS_RFID and self.reader is None:
            self.reader = SimpleMFRC522()

    def load_users_from_db(self, search_text=""):
        """ดึงข้อมูลจากฐานข้อมูล SQLite ภายในตู้ และกรองตาม Real-time Search"""
        self.ids.employee_list.clear_widgets()

        with Session(engine) as session:
            # ค้นหาคนที่ไม่ถูกลบ (Soft Delete)
            if search_text.strip():
                statement = select(User).where(
                    or_(
                        User.first_name.contains(search_text),
                        User.last_name.contains(search_text),
                        User.email.contains(search_text)
                    ),
                    User.deleted_at == None
                )
            else:
                statement = select(User).where(User.deleted_at == None)

            users = session.exec(statement).all()

            for user in users:
                # ตั้งค่าสถานะข้อความบอกสิทธิ์
                if user.card_uid:
                    status_text = f"ผูกบัตรแล้ว (UID: {user.card_uid})"
                else:
                    status_text = "ยังไม่ได้ผูกบัตรพนักงาน"

                full_name = f"{user.first_name or ''} {user.last_name or ''}".strip() or user.email or "Unknown User"
                
                # สร้าง Item รายชื่อตามสไตล์ธีมแอป
                item = TwoLineAvatarIconListItem(
                    text=full_name,
                    secondary_text=status_text,
                    on_release=lambda x, u_id=user.user_id, u_name=full_name: self.open_scan_dialog(u_id, u_name)
                )

                icon_left = IconLeftWidget(
                    icon="account-circle",
                    theme_icon_color="Custom",
                    icon_color=[0.5, 0.5, 0.5, 1]
                )

                icon_left = IconLeftWidget(icon="account-circle")
                item.add_widget(icon_left)

                icon_right = IconRightWidget(icon="credit-card-plus-outline")
                item.add_widget(icon_right)
                
                self.ids.employee_list.add_widget(item)

    def open_scan_dialog(self, user_id, user_name):
        """เปิดหน้าต่างสแกนบัตร (ถอดดีไซน์แบบเหลี่ยมมุมมนฟุ้งมาจาก dispense_dialog)"""
        self.active_target_user_id = user_id
        app = MDApp.get_running_app()
        
        self.dialog = MDDialog(
            title="ลงทะเบียนผูกบัตร RFID",
            text=f"คุณกำลังเลือกทำรายการให้กับ คุณ {user_name}\n\n[b]กรุณานำบัตรพนักงานใบใหม่ทาบเข้าที่หัวอ่านของตู้ล็อกเกอร์...[/b]",
            radius=[20, 20, 20, 20],
            buttons=[
                MDFlatButton(
                    text="ยกเลิก",
                    theme_text_color="Custom",
                    text_color=[0.9, 0.2, 0.2, 1],
                    on_release=lambda x: self.close_dialog()
                )
            ],
        )
        self.dialog.open()

        if HAS_RFID:
            self.rfid_event = Clock.schedule_interval(self._poll_rfid_reader, 0.5)
    
    def _poll_rfid_reader(self, dt):
        """แอบทำงานอยู่เบื้องหลังทุกๆ 0.5 วินาที"""
        if not self.reader:
            return

        # 👉 3. ใช้ read_no_block() เพื่อไม่ให้หน้าจอ Kivy ค้าง (สำคัญมาก!)
        card_id = self.reader.read_id_no_block()

        if card_id:
            # ✅ ฮาร์ดแวร์อ่านบัตรเจอแล้ว!
            print(f"💳 Hardware RFID Detected: {card_id}")
            self.process_scanned_rfid(str(card_id))

    def process_scanned_rfid(self, card_uid):
        """รวมฟังก์ชันจำลองและของจริงมาเข้าเส้นทางเดียวกัน"""
        if not self.active_target_user_id:
            return
        
        target_id = self.active_target_user_id
            
        app = MDApp.get_running_app()
        self.close_dialog() # สั่งปิดหน้าต่าง (และหยุด Clock อัตโนมัติ)
        
        # ส่งค่าไปบันทึก
        self.submit_rfid_to_server(target_id, card_uid)

    def close_dialog(self):
        """หยุดการแอบอ่านบัตร และปิดหน้าต่าง"""
        # 👉 4. ยกเลิกการอ่านบัตรทันทีเมื่อกดปิด เพื่อประหยัดพลังงาน
        if self.rfid_event:
            self.rfid_event.cancel()
            self.rfid_event = None

        if self.dialog:
            self.dialog.dismiss()
        self.active_target_user_id = None

    def submit_rfid_to_server(self, user_id, card_uid):
        """ส่งเลข UID ไปอัปเดตที่ฝั่ง Server ก่อน ถ้าผ่านแล้วตู้ค่อยบันทึกลง SQLite ในเครื่องตาม"""
        app = MDApp.get_running_app()
        
        GATEWAY_URL = "http://localhost:5000/api"
        BIND_RFID_URL = f"{GATEWAY_URL}/auth/auth/user/bind-rfid" 
        
        payload = json.dumps({
            "user_id": user_id,
            "card_uid": card_uid
        })
        headers = {'Content-Type': 'application/json'}
        
        def on_success(req, result):
            app.show_toast("ผูกบัตรพนักงานและบันทึกเข้าระบบสำเร็จ!")
            self.load_users_from_db() # โหลดรายชื่อใหม่เพื่ออัปเดตหน้าจอ

        def on_failure(req, result):
            app.show_toast(f"เกิดข้อผิดพลาดจาก Backend: {result}")

        def on_error(req, error):
            app.show_toast(f"เชื่อมต่อ Gateway ไม่ได้: {error}")
            
        # ใช้ UrlRequest ยิงข้อมูลไปที่ Gateway
        UrlRequest(
            BIND_RFID_URL,
            req_body=payload,
            req_headers=headers,
            on_success=on_success,
            on_failure=on_failure,
            on_error=on_error
        )

    def go_back_home(self):
        app = MDApp.get_running_app()
        app.change_screen("home_screen")