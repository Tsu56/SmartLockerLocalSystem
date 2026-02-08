from fastapi import FastAPI
from api import router as gateway_router

# ส่วนนี้ทำหน้าที่เป็น Entry Point ของแอป
app = FastAPI(title="Locker Display Gateway")

# รวม Router ที่แยกไว้ในไฟล์ api.py เข้ามา
app.include_router(gateway_router)

@app.get("/health")
def health_check():
    """Endpoint สำหรับเช็คว่า Gateway ยังทำงานปกติไหม"""
    return {
        "status": "online", 
        "gateway": "Locker Display Service"
    }