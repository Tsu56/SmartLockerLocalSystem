from fastapi import FastAPI
from contextlib import asynccontextmanager
import threading
from api import router, hardware_polling_loop

# ใช้ lifespan แบบใหม่ของ FastAPI แทน on_event("startup")
@asynccontextmanager
async def lifespan(app: FastAPI):
    # สิ่งที่ให้ทำตอนเริ่มแอป (Startup)
    threading.Thread(target=hardware_polling_loop, daemon=True).start()
    yield
    # สิ่งที่ให้ทำตอนปิดแอป (Shutdown) - ใส่ pass ไว้ถ้าไม่มี
    pass

app = FastAPI(title="Locker Device Communication Service", lifespan=lifespan)

# นำเข้า Endpoints จาก api.py
app.include_router(router)

# เพิ่มหน้าแรกกันเบราว์เซอร์หาไม่เจอ (จะได้ไม่ขึ้น 404)
@app.get("/")
def read_root():
    return {"status": "online", "service": "Device Communication Service"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)