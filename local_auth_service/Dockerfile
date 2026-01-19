# เลือกใช้ slim version เพื่อประหยัดพื้นที่
FROM python:3.11-slim

# ตั้งค่า environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# กำหนดโฟลเดอร์ทำงาน
WORKDIR /local_auth_service

# คัดลอกและติดตั้ง python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# คัดลอกไฟล์โปรเจกต์ทั้งหมด
COPY . .

# เปิดพอร์ต 5000
EXPOSE 5000
CMD ["fastapi", "run", "app.py", "--port", "5000"]