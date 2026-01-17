from kivy.clock import Clock
import threading
from threading import Lock

card_lock = Lock()

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

class IDCardController:
    def __init__(self, on_data_callback, on_status_callback):
        self.reader = ThaiSmartCardReader()
        self.on_data_callback = on_data_callback     # ส่งข้อมูลกลับไปเมื่ออ่านเสร็จ
        self.on_status_callback = on_status_callback # ส่งสถานะ UI กลับไป (Reading, Error)
        self.is_reading = False
        self.card_present_status = False
    
    def check_status(self, dt=None):
        if self.is_reading:
            return
        
        if card_lock.acquire(blocking=False):
            try:
                card_now_present = self.reader.card_present()
                
                if card_now_present and not self.card_present_status:
                    self.card_present_status = True
                    # หน่วงเวลาเล็กน้อยเพื่อให้บัตรนิ่งก่อนอ่าน
                    Clock.schedule_once(lambda dt: self.start_reading(), 0.5)
                
                elif not card_now_present and self.card_present_status:
                    self.card_present_status = False
                    self.is_reading = False
                    self.reader.disconnect()
                    self.on_status_callback(is_present=False)

            except Exception as e:
                self.on_status_callback(is_present=False, error=True, msg=str(e))
                self.card_present_status = False

            finally:
                card_lock.release()

    def start_reading(self):
        if not self.is_reading:
            self.is_reading = True
            threading.Thread(target=self._read_thread, daemon=True).start()

    def _read_thread(self):
        Clock.schedule_once(lambda dt: self.on_status_callback(is_present=True, status_text="Reading card..."), 0)
        
        with card_lock:
            try:
                self.reader._connect_reader()
                data = self.reader.read_all()
                # ส่งข้อมูลกลับไปให้ App ผ่าน callback
                Clock.schedule_once(lambda dt: self.on_data_callback(data), 0)
                Clock.schedule_once(lambda dt: self.on_status_callback(
                    is_present=True, 
                    status_text="Read Success!"
                ), 0)
            except Exception as e:
                try:
                    self.reader.disconnect()
                except:
                    pass

                error_msg = str(e)
                print(f"Read Thread Error: {error_msg}")
                Clock.schedule_once(lambda dt: self.on_status_callback(is_present=True, error=True, status_text=f"Error: {error_msg}"), 0)
            finally:
                self.is_reading = False