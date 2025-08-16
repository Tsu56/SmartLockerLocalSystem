from kivy.app import App
from kivymd.app import MDApp
from kivy.uix.gridlayout import GridLayout
from kivy.uix.button import Button
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.lang import Builder
from kivy.uix.gridlayout import GridLayout
from kivymd.uix.button import MDRaisedButton
from kivymd.uix.button import MDTextButton
from kivymd.uix.textfield import MDTextField
from kivymd.uix.snackbar import Snackbar
from kivy.core.window import Window


import serial
import time



# Serial configuration
# ser = serial.Serial('/dev/ttyUSB0', 9600, timeout=1)


def send_command(address, command):
    """
    command = "1" -> Open locker
    command = "?" -> Check door status
    """
    message = f"{address}:{command}\n"
    print(f"Sending: {message.strip()}")

    ser.reset_input_buffer()  # Clear buffer before sending
    ser.write(message.encode())

    time.sleep(0.5)  # Wait after sending

    timeout = time.time() + 2
    response = None

    while time.time() < timeout:
        if ser.in_waiting:
            raw = ser.readline()
            try:
                decoded = raw.decode().strip()
                print(f"Received: {decoded}")
                response = decoded
                break
            except UnicodeDecodeError:
                print("Decode failed")
                continue

    return response


def send_open_command(address):
    response = send_command(address, "1")
    if response:
        if response.startswith(address):
            parts = response.split(":")
            if len(parts) >= 2:
                status = parts[-1]
                if status == "1":
                    print(f"{address} Opened.")
                else:
                    print(f"Warning: Please check {address}'s door.")
            else:
                print(f"{address} Invalid response format")
        else:
            print(f"{address} Mismatched response")
    else:
        print(f"Warning: {address} No response.")


def check_door_status(address):
    response = send_command(address, "?")
    if response:
        if response.startswith(address):
            parts = response.split(":")
            if len(parts) >= 2:
                status = parts[-1]
                if status == "0":
                    print(f"{address} DOOR CLOSED")
                else:
                    print(f"{address} DOOR OPEN")
            else:
                print(f"{address} Invalid response format")
        else:
            print(f"{address} Mismatched response")
    else:
        print(f"{address} No response when checking door.")


class LockerControl(GridLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.cols = 2  # Two buttons per row: Open / Check
        for i in range(1, 7):
            address = f"A{i}"
            btn_open = Button(
                text=f"Open Locker {address}",
                font_size=20,
                on_press=lambda btn, addr=address: send_open_command(addr)
            )
            btn_check = Button(
                text=f"Check Door {address}",
                font_size=20,
                on_press=lambda btn, addr=address: check_door_status(addr)
            )
            self.add_widget(btn_open)
            self.add_widget(btn_check)

class LoginScreen(Screen):
    def do_login(self):
        username = self.ids.username_input.text
        password = self.ids.password_input.text
        print(f"Username: {username}, Password: {password}")
        # ตรงนี้คุณสามารถเพิ่มการตรวจสอบ username/password ได้
        if username == "admin" and password == "1234":
            self.manager.current = "locker"
        else:
            print("Login Failed!")

class LockerScreen(Screen):
    def on_enter(self, *args):
        # แสดง LockerControl ตอนเข้าหน้า
        self.clear_widgets()
        self.add_widget(LockerControl())

class LoginApp(MDApp):
    def build(self):
        self.theme_cls.primary_palette = "Blue"
        self.theme_cls.theme_style = "Light"  # ลอง "Dark" ได้
        root = Builder.load_file("login.kv")
        Window.bind(on_key_down=self.on_key_down)   # <== ฟัง event keyboard
        return root
    
    def on_key_down(self, window, key, scancode, codepoint, modifiers):
        # key == 9 หมายถึง TAB
        if key == 9:
            sm = self.root
            if sm.current == "login":  # ตรวจว่าตอนนี้อยู่ที่หน้าล็อกอิน
                login_screen = sm.get_screen("login")
                if login_screen.ids.username_input.focus:
                    login_screen.ids.username_input.focus = False
                    login_screen.ids.password_input.focus = True
                    return True
                elif login_screen.ids.password_input.focus:
                    login_screen.ids.username_input.focus = True
                    login_screen.ids.password_input.focus = False
                    return True
        
        elif key == 13:  # key == 13 หมายถึง ENTER
            sm = self.root
            if sm.current == "login":
                login_screen = sm.get_screen("login")
                login_screen.do_login()
        return False
        


if __name__ == '__main__':
    LoginApp().run()
