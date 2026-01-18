from sqlmodel import SQLModel, Field
from datetime import datetime
from typing import Optional

# --- User Schemas ---
class UserBase(SQLModel):
    username: str = Field(index=True, unique=True, description="ชื่อผู้ใช้งานสำหรับ Login")
    full_name: str | None = Field(default=None, description="ชื่อ-นามสกุลจริง")
    role: str = Field(default="user", description="สิทธิ์ผู้ใช้งาน เช่น 'admin', 'staff', 'user'")
    is_active: bool = Field(default=True, description="สถานะบัญชี")

class UserCreate(UserBase):
    password: str = Field(description="รหัสผ่าน (Plain text ที่จะถูก Hash ก่อนบันทึก)")

class UserUpdate(SQLModel):
    full_name: str | None = None
    password: str | None = None
    role: str | None = None
    is_active: bool | None = None

class UserPublic(UserBase):
    id: int
    created_at: datetime
    # เราจะไม่ส่ง password hash ออกไปใน response

class UserLogin(SQLModel):
    username: str
    password: str

# --- Smart Card Schemas ---
class SmartCardBase(SQLModel):
    citizen_id: str = Field(index=True, unique=True, description="เลขบัตรประชาชน 13 หลัก")
    is_active: bool = Field(default=True)

class SmartCardCreate(SmartCardBase):
    user_id: int = Field(description="ID ของ User ที่เป็นเจ้าของบัตรนี้")

class SmartCardPublic(SmartCardBase):
    id: int
    user_id: int
    registered_at: datetime

# --- Auth Log Schemas (Optional: เก็บประวัติการเข้าใช้งาน) ---
class AuthLogBase(SQLModel):
    user_id: int | None = None
    username: str | None = None
    login_method: str = Field(description="'password' หรือ 'smartcard'")
    status: str = Field(description="'success' หรือ 'failed'")
    ip_address: str | None = None

class AuthLogCreate(AuthLogBase):
    pass

class AuthLogPublic(AuthLogBase):
    id: int
    timestamp: datetime