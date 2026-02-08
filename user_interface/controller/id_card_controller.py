from kivy.clock import Clock
import threading
from threading import Lock
from kivy.event import EventDispatcher
from kivy.properties import BooleanProperty, DictProperty, StringProperty

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

class IDCardController(EventDispatcher):
    is_card_detected = BooleanProperty(False)
    card_data = DictProperty({})
    status_text = StringProperty("Ready")
    error_msg = StringProperty("")

    def __init__(self, **kwargs):
        super(IDCardController, self).__init__(**kwargs)
        self.reader = ThaiSmartCardReader()
        self.is_reading = False
    
    def check_status(self, dt=None):
        if self.is_reading: return
        
        if card_lock.acquire(blocking=False):
            try:
                card_now_present = self.reader.card_present()
                
                if card_now_present != self.is_card_detected:
                    self.is_card_detected = card_now_present

            except Exception as e:
                print(f"Check status error: {e}")

            finally:
                card_lock.release()

    def on_is_card_detected(self, instance, value):
        if value: # ถ้าบัตรถูกเสียบ (True)
            self.status_text = "Card detected, reading..."
            Clock.schedule_once(lambda dt: self.start_reading(), 0.5)
        else: # ถ้าบัตรถูกถอด (False)
            self.status_text = "Ready for card insertion."
            self.reader.disconnect()

    def start_reading(self):
        if not self.is_reading:
            self.is_reading = True
            threading.Thread(target=self._read_thread, daemon=True).start()

    def _read_thread(self):
        with card_lock:
            try:
                self.reader._connect_reader()
                data = self.reader.read_all()
                Clock.schedule_once(lambda dt: self._update_data(data), 0)
            except Exception as e:
                try:
                    self.reader.disconnect()
                except:
                    pass

                Clock.schedule_once(lambda dt: self._set_error(str(e)), 0)
            finally:
                self.is_reading = False
    
    def _update_data(self, data):
        self.card_data = data
        self.status_text = "Read Success!"

    def _set_error(self, msg):
        self.error_msg = msg
        self.status_text = f"Error: {msg}"