import os
from kivymd.app import MDApp
from kivy.lang import Builder
from kivymd.toast import toast
from kivy.properties import StringProperty
from kivy.core.window import Window
from kivymd.uix.button import MDRaisedButton, MDTextButton
from kivymd.uix.textfield import MDTextField
from controller.id_card_controller import IDCardController, Clock

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

        self.id_card_controller = IDCardController(
            on_data_callback=self.handle_card_data,
            on_status_callback=self.update_ui_card_status
        )

        for file in KV_FILES:
            if os.path.exists(file):
                Builder.load_file(file)
            else:
                print(f"Warning: KV file '{file}' not found.")
        
        screen = Builder.load_string(screen_helper)
        return screen
    
    def on_start(self):
        Clock.schedule_interval(self._poll_card_reader, 0.5)

    def _poll_card_reader(self, dt):
        if self.current_screen_name == "id_card_login":
            self.id_card_controller.check_status()

    def handle_card_data(self, data):
        """จัดการข้อมูลที่ได้จากบัตร"""
        print(f"Welcome {data['firstname']}")
        self.update_ui_card_status(is_present=True, status_text="Success!")
        Clock.schedule_once(lambda dt: self.change_screen("main_screen"), 2)
    
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