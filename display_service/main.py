import os
from kivymd.app import MDApp
from kivy.lang import Builder
from kivymd.toast import toast
from kivy.properties import StringProperty
from kivy.core.window import Window
from kivymd.uix.button import MDRaisedButton, MDTextButton
from kivymd.uix.textfield import MDTextField
from kivy.clock import Clock
import threading

try:
    from authentication.smartcardreader import ThaiSmartCardReader
except ImportError:
    class ThaiSmartCardReader:
        def __init__(self): pass
        def card_present(self): return False
        def read_all(self): return {
            "citizenID": "1234567890123",
            "firstname": "John",
            "lastname": "Doe"
            }
        def disconnect(self): pass
    print("Warning: authentication module not found. Using mock ThaiSmartCardReader.")

Window.size = (1024, 600)

KV_FILES = [
    "main_screen.kv",
    "id_card_login.kv",
    "qr_scan_screen.kv",
    "user_pass_login.kv"
]

screen_helper = """
MDScreenManager:
    id: screen_manager
    MainScreen:
    IDCardLoginScreen:
    QRScanScreen:
    UserPassLoginScreen:
"""

class SmartLockerApp(MDApp):
    current_screen_name = StringProperty("main_screen")
    card_present_status = False
    is_reading_card = False
    get_data = False

    status_error_color = [0.906, 0.298, 0.235, 1]      # Red
    status_success_color = [0.18, 0.8, 0.443, 1]    # Green
    status_ready_color = [0.878, 0.878, 0.878, 1]    # Light Gray

    def build(self):
        self.theme_cls.theme_style = "Light"
        self.theme_cls.primary_palette = "Blue"
        self.reader = ThaiSmartCardReader()

        for file in KV_FILES:
            if os.path.exists(file):
                Builder.load_file(file)
            else:
                print(f"Warning: KV file '{file}' not found.")
        
        screen = Builder.load_string(screen_helper)
        return screen
    
    def on_start(self):
        print("App started.")
        try:
            print("Initializing card reader...")
            print(self.card_present_status)
            Clock.schedule_interval(self.check_card_status, 0.5)
        except Exception as e:
            print(f"Error initializing card reader: {str(e)}")

    def check_card_status(self, dt):
        if self.current_screen_name != "id_card_login":
            return
        if self.get_data:
            return
        try:
            card_now_present = self.reader.card_present()
        except Exception as e:
            self.card_present_status = False
            self.is_reading_card = False
            self.update_ui_card_status(is_present=False, error=True)
            self.show_toast(f"Reader error: {str(e)}")
            return
        
        if card_now_present and not self.card_present_status:
            self.card_present_status = True
            if not self.is_reading_card:
                self.is_reading_card = True
                threading.Thread(target=self.read_card_thread, daemon=True).start()
        
        elif not card_now_present and self.card_present_status:
            self.card_present_status = False
            self.is_reading_card = False
            try:
                if getattr(self.reader, 'connection', None):
                    self.reader.disconnect()
            except Exception as e:
                print(f"Warning: failed to disconnect reader: {e}")
        
        if not self.is_reading_card:
            self.update_ui_card_status(is_present=self.card_present_status)
    
    def read_card_thread(self):
        Clock.schedule_once(lambda dt: self.update_ui_card_status(is_present=True, status_text="Reading card..."), 0)
        try:
            self.reader._connect_reader()
            data = self.reader.read_all()
            self.get_data = True

            Clock.schedule_once(lambda dt: self.update_ui_card_status(is_present=True, status_text="Card read successfully!"), 0)
            print("Welcome,", data["firstname"], data["lastname"])

            # TODO: นำข้อมูล ddata ไปใช้ในการล็อกอิน
            # self.do_login(data)

            # เปลี่ยนหน้าจอหลังจากแสดงผลสำเร็จ (ตัวอย่าง: กลับไปหน้าหลัก)
            # ต้องใช้ Clock.schedule_once เพื่อเปลี่ยน UI ใน Main Thread
            Clock.schedule_once(lambda dt: self.change_screen("main_screen"), 2)
        except Exception as e:
            self.get_data = False
            Clock.schedule_once(lambda dt, exc=e: self.update_ui_card_status(is_present=True, status_text="Error reading card.", error=True), 0)
            print(f"Error reading card: {str(e)}")
        finally:
            try:
                if getattr(self.reader, 'connection', None):
                    self.reader.disconnect()
            except Exception as e:
                print(f"Warning: failed to disconnect reader in thread: {e}")
            self.is_reading_card = False
    
    def update_ui_card_status(self, is_present, status_text=None, error=False):
        def update(dt):
            try:
                screen = self.root.get_screen('id_card_login')
                card = screen.ids.id_card_holder
                status_label = screen.ids.status_label
            except AttributeError:
                return
            
            if error:
                card.line_color = self.status_error_color
                card.line_width = 4
                status_label.text = status_text if status_text else "Error: Card not detected."
                status_label.theme_text_color = "Custom"
                status_label.text_color = self.status_error_color
            elif is_present:
                card.line_color = self.status_success_color
                card.line_width = 4
                status_label.text = status_text if status_text else "Card detected."
                status_label.theme_text_color = "Custom"
                status_label.text_color = self.status_success_color
            else:
                card.line_color = self.status_ready_color
                card.line_width = 1
                status_label.text = "Status: Ready for card insertion."
                status_label.theme_text_color = "Secondary"
                status_label.text_color = [0, 0, 0, 0.6]
        
        Clock.schedule_once(update, 0)
    
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