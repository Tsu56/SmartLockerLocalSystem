from sqlmodel import create_engine, Session, SQLModel
from typing import Annotated
from fastapi import Depends
import os

# ตรวจสอบว่ามีโฟลเดอร์ database หรือไม่
if not os.path.exists("database"):
    os.makedirs("database")

sqlite_file_name = "database/device.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"

connect_args = {"check_same_thread": False}
engine = create_engine(sqlite_url, connect_args=connect_args)

def create_db_and_tables():
    # ฟังก์ชันสำหรับสร้าง Table จริงๆ ใน DB
    from . import models  # ต้อง import models เพื่อให้ SQLModel รู้จัก Table
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session

SessionDep = Annotated[Session, Depends(get_session)]