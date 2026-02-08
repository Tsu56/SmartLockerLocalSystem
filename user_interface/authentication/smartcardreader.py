from smartcard.System import readers
from smartcard.scard import *
import time
import threading

class ThaiSmartCardReader:
    SELECT_CMD = [0x00, 0xA4, 0x04, 0x00, 0x08, 0xA0, 0x00, 0x00, 0x00, 0x54, 0x48, 0x00, 0x01]
    CMD_CID    = [0x80, 0xB0, 0x00, 0x04, 0x02, 0x00, 0x0D]
    CMD_NAME   = [0x80, 0xB0, 0x00, 0x75, 0x02, 0x00, 0x64]
    CMD_BIRTH  = [0x80, 0xB0, 0x00, 0xD9, 0x02, 0x00, 0x08]
    CMD_SEX    = [0x80, 0xB0, 0x00, 0xE1, 0x02, 0x00, 0x01]

    def __init__(self):
        self.connection = None
        self.reader = None
        self._last_state = False

    def card_present(self):
        hcontext = None
        hcard = None
        try:
            # 1. สร้าง Context
            hresult, hcontext = SCardEstablishContext(SCARD_SCOPE_USER)
            if hresult != SCARD_S_SUCCESS:
                return False

            # 2. หา Reader
            hresult, readers_list = SCardListReaders(hcontext, [])
            if hresult != SCARD_S_SUCCESS or len(readers_list) == 0:
                SCardReleaseContext(hcontext) # ต้องคืน context ทันที
                return False

            reader_name = readers_list[0]

            # 3. ลองเชื่อมต่อแบบ SHARED เพื่อเช็คสถานะ
            # เพิ่มการดักจับผลลัพธ์ของ SCardConnect ก่อนส่งเข้า SCardStatus
            hresult, hcard, protocol = SCardConnect(hcontext, reader_name, SCARD_SHARE_SHARED, SCARD_PROTOCOL_T0 | SCARD_PROTOCOL_T1)
            
            if hresult != SCARD_S_SUCCESS:
                SCardReleaseContext(hcontext)
                return False

            # 4. เช็คสถานะและ ATR
            hresult, reader_name, state, protocol, atr = SCardStatus(hcard)
            is_present = (hresult == SCARD_S_SUCCESS and len(atr) > 0)

            return is_present
            
        except Exception as e:
            # ไม่ต้อง print เยอะเพื่อลดความหน่วงใน Main Thread
            return False
        finally:
            # [จุดสำคัญที่สุด] ต้องล้างทุอย่างทิ้งเพื่อให้ Reader ว่างสำหรับ Thread อ่านบัตร
            if hcard:
                SCardDisconnect(hcard, SCARD_LEAVE_CARD)
            if hcontext:
                SCardReleaseContext(hcontext)

    def _connect_reader(self):
        if self.connection:
            return
        
        r = readers()
        if not r:
            raise Exception("No smart card reader found")
        self.reader = r[0]
        self.connection = self.reader.createConnection()
        
        # [FIX 1] ใช้ Shared Mode และรองรับทั้ง T0/T1 เพื่อป้องกันการแย่ง Resource แล้วค้าง
        self.connection.connect(mode=SCARD_SHARE_SHARED, protocol=SCARD_PROTOCOL_T0 | SCARD_PROTOCOL_T1)
        
        time.sleep(0.2)
        data, sw1, sw2 = self.connection.transmit(self.SELECT_CMD)
        
        if sw1 == 0x61:
            data2, sw1, sw2 = self.connection.transmit([0x00, 0xC0, 0x00, 0x00, sw2])
            data.extend(data2)
        
        if sw1 != 0x90:
            raise Exception(f"Failed to select application: SW1={sw1}, SW2={sw2}")

    def _send_apdu(self, apdu):
        try:
            data, sw1, sw2 = self.connection.transmit(apdu)
            if sw1 == 0x61:
                data2, sw1, sw2 = self.connection.transmit([0x00, 0xC0, 0x00, 0x00, sw2])
                data.extend(data2)
            
            if not data: return ""
            return bytearray(data).decode("tis-620", errors="ignore").strip().replace('\x00', '')
        except Exception as e:
            print(f"DEBUG: APDU Transmission Error: {e}")
            return ""

    def read_all(self):
        data = {}
        try:
            time.sleep(0.1)
            print("DEBUG: Reading CID...")
            data["citizenID"] = self._send_apdu(self.CMD_CID)
            time.sleep(0.05)
            
            print("DEBUG: Reading Name...")
            fullname = self._send_apdu(self.CMD_NAME)
            
            if fullname:
                parts = fullname.split("#")
                data["firstname"] = parts[1] if len(parts) > 1 else fullname
                data["lastname"] = parts[-1] if len(parts) > 1 else fullname
            else:
                data["firstname"] = data["lastname"] = "Unknown"

            print("DEBUG: Reading Birth...")
            birth = self._send_apdu(self.CMD_BIRTH)
            if birth and len(birth) >= 8:
                data["birthdate"] = f"{int(birth[:4])-543}-{birth[4:6]}-{birth[6:8]}"
            else:
                data["birthdate"] = ""

            print("DEBUG: Reading Sex...")
            sex = self._send_apdu(self.CMD_SEX)
            data["sex"] = "Male" if sex == "1" else "Female"

            print("DEBUG: Read all completed.")
            return data

        except Exception as e:
            print(f"DEBUG: Error inside read_all: {e}")
            raise e

    def disconnect(self):
        if self.connection:
            self.connection.disconnect()
            self.connection = None

# --- Loop control variable ---
exit_flag = False

# Function to wait for user input to exit
def input_thread():
    global exit_flag
    while True:
        cmd = input("Type 'q' to quit the program: ").strip().lower()
        if cmd == 'q':
            exit_flag = True
            break

# --- Main polling loop ---
if __name__ == "__main__":
    reader = ThaiSmartCardReader()
    threading.Thread(target=input_thread, daemon=True).start()
    print("Program is waiting for card insertion...")

    try:
        while not exit_flag:
            if reader.card_present():
                try:
                    reader._connect_reader()
                    data = reader.read_all()
                    print("Citizen ID:", data["citizenID"])
                    print("Firstname:", data["firstname"])
                    print("Lastname:", data["lastname"])
                    print("Birthdate:", data["birthdate"])
                    print("Sex:", data["sex"])
                except Exception as e:
                    print("Error:", e)
                finally:
                    reader.disconnect()
                # รอถอดบัตร
                while reader.card_present() and not exit_flag:
                    time.sleep(0.2)
            else:
                time.sleep(0.1)

    finally:
        reader.disconnect()
        print("Program exited successfully.")
