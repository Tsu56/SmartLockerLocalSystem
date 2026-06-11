from fastapi import FastAPI
from api import router as auth_router
from contextlib import asynccontextmanager
from sqlmodel import SQLModel
from database import create_db_and_tables
import threading
from api import heartbeat_agent
from slot_sync_agent import start_slot_sync_agent

# ✅ รวมทุกอย่างไว้ใน lifespan ที่เดียวจบ!
@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    
    print("🚀 สตาร์ท Background Workers จาก Lifespan...")

    threading.Thread(target=heartbeat_agent, daemon=True).start()
    
    start_slot_sync_agent()
    
    yield

app = FastAPI(lifespan=lifespan)

app.include_router(auth_router)