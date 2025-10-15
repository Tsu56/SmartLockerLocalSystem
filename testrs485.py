import serial
import select
import sys

# ตั้งค่าพอร์ต RS485
ser = serial.Serial(
    port='/dev/ttyUSB0',
    baudrate=9600,
    timeout=1   # non-blocking
)

print("RS485 Ready (no delay)")

while True:
    # ตรวจว่ามีข้อมูลเข้ามาไหม (ไม่ต้อง sleep)
    rlist, _, _ = select.select([ser, sys.stdin], [], [], 0)

    if ser in rlist:
        data = ser.readline().decode('utf-8').strip()
        if data:
            print("Received:", data)
    
    if sys.stdin in rlist:
        msg = sys.stdin.readline().strip()
        if msg:
            ser.reset_input_buffer()
            ser.write((msg + '\n').encode('utf-8'))
            ser.flush()
            print("Sent:", msg)
