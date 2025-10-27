from smartcard.System import readers
from smartcard.Exceptions import NoCardException
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

    def card_present(self):
        try:
            r = readers()
            print("DEBUG: Readers list:", r)
            if not r:
                print("DEBUG: No readers found.")
                return False
            reader = r[0]
            try:
                conn = reader.createConnection()
                try:
                    conn.connect()  # จะ fail ถ้า card unpowered
                    print("DEBUG: Card connected successfully.")
                except NoCardException:
                    print("DEBUG: No card inserted.")
                    return False
                except Exception as e:
                    print("DEBUG: Other connect error:", e)
                    return False
                finally:
                    try:
                        conn.disconnect()
                    except:
                        pass
                return True
            except Exception:
                return False
        except Exception as e:
            print("DEBUG: Exception in card_present:", e)
            return False

    def _connect_reader(self):
        r = readers()
        if not r:
            raise Exception("No smart card reader found")
        self.reader = r[0]
        self.connection = self.reader.createConnection()
        self.connection.connect()
        
        data, sw1, sw2 = self.connection.transmit(self.SELECT_CMD)
        
        # Handle SW1=0x61 (more data available)
        while sw1 == 0x61:
            data2, sw1, sw2 = self.connection.transmit([0x00, 0xC0, 0x00, 0x00, sw2])
            data.extend(data2)
        
        if sw1 != 0x90:
            raise Exception(f"Failed to select application: SW1={sw1}, SW2={sw2}")

    def _send_apdu(self, apdu):
        data, sw1, sw2 = self.connection.transmit(apdu)
        if sw1 == 0x61:
            data2, sw1, sw2 = self.connection.transmit([0x00, 0xC0, 0x00, 0x00, sw2])
            data.extend(data2)
        return bytearray(data).decode("tis-620", errors="ignore").strip()

    def read_all(self):
        cid = self._send_apdu(self.CMD_CID)
        fullname = self._send_apdu(self.CMD_NAME)
        birth = self._send_apdu(self.CMD_BIRTH)
        sex = self._send_apdu(self.CMD_SEX)
        return {
            "citizenID": cid,
            "firstname": fullname.split("#")[1] if "#" in fullname else fullname,
            "lastname": fullname.split("#")[-1] if "#" in fullname else fullname,
            "birthdate": f"{int(birth[:4])-543}-{birth[4:6]}-{birth[6:8]}",
            "sex": "Male" if sex == "1" else "Female"
        }

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
