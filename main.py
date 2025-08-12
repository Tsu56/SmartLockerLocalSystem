from kivy.app import App
from kivy.uix.gridlayout import GridLayout
from kivy.uix.button import Button
import serial
import time

# Serial configuration
ser = serial.Serial('/dev/ttyUSB0', 9600, timeout=1)


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


class LockerApp(App):
    def build(self):
        return LockerControl()


if __name__ == '__main__':
    LockerApp().run()
