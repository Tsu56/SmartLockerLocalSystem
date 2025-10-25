import os
from kivymd.app import MDApp
from kivy.lang import Builder
from kivymd.toast import toast
from kivy.properties import StringProperty
from kivy.core.window import Window
from kivymd.uix.button import MDRaisedButton, MDTextButton
from kivymd.uix.textfield import MDTextField

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

    def build(self):
        self.theme_cls.theme_style = "Light"
        self.theme_cls.primary_palette = "Blue"
        for file in KV_FILES:
            Builder.load_file(file)
        return Builder.load_string(screen_helper)
    
    def change_screen(self, screen_name):
        self.root.current = screen_name
        self.current_screen_name = screen_name
        print(f"Changing screen to: {screen_name}")

    def select_login_method(self, screen_name):
        toast(f"Selected: {screen_name.replace('_', ' ').title()}")
        self.change_screen(screen_name)

    def go_back(self):
        self.change_screen("main_screen")
        
    def show_toast(self, message):
        toast(message)
    
if __name__ == '__main__':
    SmartLockerApp().run()