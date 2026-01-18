from fastapi import APIRouter, HTTPException, status
from sqlmodel import select
from typing import List
import hashlib

# นำเข้าส่วนประกอบจากโมดูล local_auth ที่เราสร้างไว้
from database import SessionDep
from database.models import User, SmartCard, AuthLog
from database.schema import (
    UserCreate, UserPublic, UserLogin,
    SmartCardCreate, SmartCardPublic,
    AuthLogCreate, AuthLogPublic
)

router = APIRouter(prefix="/auth", tags=["Local Authentication"])

def hash_password(password: str) -> str:
    """ฟังก์ชันเข้ารหัสรหัสผ่านแบบพื้นฐาน"""
    return hashlib.sha256(password.encode()).hexdigest()

# --- User Management ---

@router.post("/register", response_model=UserPublic)
def register_user(user_in: UserCreate, session: SessionDep):
    """ลงทะเบียนผู้ใช้งานใหม่"""
    # ตรวจสอบว่า Username ซ้ำหรือไม่
    statement = select(User).where(User.username == user_in.username)
    existing_user = session.exec(statement).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    
    # สร้าง User ใหม่พร้อมเข้ารหัสรหัสผ่าน
    db_user = User(
        username=user_in.username,
        full_name=user_in.full_name,
        role=user_in.role,
        hashed_password=hash_password(user_in.password)
    )
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return db_user

# --- Smart Card Management ---

@router.post("/link-card", response_model=SmartCardPublic)
def link_smart_card(card_in: SmartCardCreate, session: SessionDep):
    """ผูกบัตรประชาชนเข้ากับบัญชีผู้ใช้ (1 คน ต่อ 1 ใบ)"""
    # 1. ตรวจสอบว่ามี User นี้จริงไหม
    user = session.get(User, card_in.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # 2. ตรวจสอบว่า User นี้มีบัตรผูกไว้แล้วหรือยัง (1-to-1 check)
    if user.smart_card:
        raise HTTPException(status_code=400, detail="User already has a linked smart card")
    
    # 3. ตรวจสอบว่าเลขบัตรนี้ถูกใช้ไปแล้วหรือยัง
    statement = select(SmartCard).where(SmartCard.citizen_id == card_in.citizen_id)
    existing_card = session.exec(statement).first()
    if existing_card:
        raise HTTPException(status_code=400, detail="Citizen ID already linked to another user")
    
    # 4. บันทึกข้อมูลบัตร
    db_card = SmartCard(
        citizen_id=card_in.citizen_id,
        user_id=card_in.user_id
    )
    session.add(db_card)
    session.commit()
    session.refresh(db_card)
    return db_card

# --- Login Logic ---

@router.post("/login/password")
def login_with_password(login_data: UserLogin, session: SessionDep):
    """เข้าสู่ระบบด้วย Username และ Password"""
    statement = select(User).where(User.username == login_data.username)
    user = session.exec(statement).first()
    
    if not user or user.hashed_password != hash_password(login_data.password):
        # บันทึก Log กรณีล้มเหลว
        log = AuthLog(username=login_data.username, login_method="password", status="failed")
        session.add(log)
        session.commit()
        raise HTTPException(status_code=401, detail="Invalid username or password")
    
    # บันทึก Log กรณีสำเร็จ
    log = AuthLog(user_id=user.id, username=user.username, login_method="password", status="success")
    session.add(log)
    session.commit()
    
    return {"message": "Login successful", "user": user}

@router.post("/login/smartcard")
def login_with_smartcard(citizen_id: str, session: SessionDep):
    """เข้าสู่ระบบด้วยการเสียบบัตรประชาชน"""
    statement = select(SmartCard).where(SmartCard.citizen_id == citizen_id)
    card = session.exec(statement).first()
    
    if not card or not card.user:
        # บันทึก Log กรณีล้มเหลว
        log = AuthLog(login_method="smartcard", status="failed")
        session.add(log)
        session.commit()
        raise HTTPException(status_code=401, detail="This card is not registered")
    
    # บันทึก Log กรณีสำเร็จ
    user = card.user
    log = AuthLog(user_id=user.id, username=user.username, login_method="smartcard", status="success")
    session.add(log)
    session.commit()
    
    return {"message": "Login successful", "user": user}