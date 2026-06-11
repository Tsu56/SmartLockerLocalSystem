from fastapi import FastAPI
from contextlib import asynccontextmanager
import uvicorn

# Import ฟังก์ชันสร้าง Database จากโฟลเดอร์ database
from database.database import create_db_and_tables

# Import Router จากไฟล์ api.py
from api import router as camera_router

# ==========================================
# 🗄️ จัดการ Database Lifecycle
# ==========================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🗄️ กำลังตรวจสอบและสร้างตารางฐานข้อมูล (Camera Queue)...")
    create_db_and_tables()
    yield

# ==========================================
# 🚀 สร้าง FastAPI Application
# ==========================================
app = FastAPI(title="SmartLocker Camera Service", lifespan=lifespan)

# เสียบปลั๊ก Router เข้ากับแอปหลัก
app.include_router(camera_router)

if __name__ == "__main__":
    # รันเซิร์ฟเวอร์
    uvicorn.run("app:app", host="0.0.0.0", port=8002, reload=True)