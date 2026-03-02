from fastapi import FastAPI
from api import router as auth_router
from contextlib import asynccontextmanager
from sqlmodel import SQLModel
from database import create_db_and_tables
from slot_sync_agent import start_slot_sync_agent

@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    start_slot_sync_agent()  # เริ่ม Slot Sync Agent
    yield

app = FastAPI(lifespan=lifespan)

app.include_router(auth_router)