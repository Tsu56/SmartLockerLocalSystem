import os
from kivymd.app import MDApp
from kivy.lang import Builder
from kivymd.toast import toast
from kivy.properties import StringProperty, ColorProperty, NumericProperty
from kivy.core.window import Window
from kivymd.uix.button import MDRaisedButton, MDTextButton
from kivymd.uix.textfield import MDTextField
from controller.id_card_controller import IDCardController, Clock

Window.size = (1024, 600)

KV_FILES = [
    "screen/main_screen.kv",
    "screen/id_card_login.kv",
    "screen/rfid_staff_tag.kv",
    "screen/qr_scan_screen.kv",
    "screen/user_pass_login.kv"
]

screen_helper = """
MDScreenManager:
    id: screen_manager
    MainScreen:
    IDCardLoginScreen:
    RFIDLoginScreen:
    QRScanScreen:
    UserPassLoginScreen:
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
        print(f"Welcome {value.get('firstname')}")
        Clock.schedule_once(lambda dt: self.change_screen("main_screen"), 2)
    
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
        if not username.strip() or not password.strip():
            self.show_toast("Please enter both username and password")
            return
            
        print(f"DEBUG: Attempting login - Username: {username}")
    
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