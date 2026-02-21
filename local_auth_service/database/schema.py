from sqlmodel import SQLModel, Field
from datetime import datetime, timezone
from typing import Optional

# --- User Schemas ---
class UserBase(SQLModel):
    user_id: str = Field(index=True, unique=True, description="ID ของผู้ใช้ในฝั่ง Server")
    email: str = Field(default=None, index=True, unique=True, description="อีเมลของผู้ใช้")
    citizen_id_encrypted: str = Field(index=True, unique=True, description="เลขบัตรประชาชน 13 หลักที่ถูกเข้ารหัสแล้ว")
    card_uid_hashed: Optional[str] = Field(default=None, index=True, nullable=True, unique=True, description="ค่า Hash ของ UID ของ RFID Staff Tag ที่อ่านได้จากเครื่อง")
    qr_uid_hashed: Optional[str] = Field(default=None, index=True, nullable=True, unique=True, description="ค่า Hash ของรหัส QR Code")
    first_name: str = Field(default=None, description="ชื่อจริงของผู้ใช้")
    last_name: str = Field(default=None, description="นามสกุลของผู้ใช้")

class UserCreate(UserBase):
    card_uid_hashed: Optional[str] = None
    qr_uid_hashed: Optional[str] = None
    password: str = Field(description="รหัสผ่าน (Plain text ที่จะถูก Hash ก่อนบันทึก)")

class UserUpdate(SQLModel):
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    password: str | None = None
    updated_at: datetime | None = Field(default_factory=lambda: datetime.now(timezone.utc))

class UserPublic(UserBase):
    id: int
    created_at: datetime
    updated_at: datetime | None = None
    deleted_at: datetime | None = None

class UserLogin(SQLModel):
    username: str
    password: str

class SmartCardLogin(SQLModel):
    citizen_id: str = Field(description="เลขบัตรประชาชน 13 หลักที่อ่านได้จากเครื่อง")

class RFIDTagLogin(SQLModel):
    card_uid: str = Field(description="UID ของ RFID Staff Tag ที่อ่านได้จากเครื่อง")

class QRCodeLogin(SQLModel):
    qr_raw_data: str = Field(description="ข้อมูลดิบที่อ่านได้จากเครื่องสแกน QR")

# --- User Permissions Schemas ---
class UserPermissionBase(SQLModel):
    user_id: str = Field(index=True, description="ID ของผู้ใช้ในฝั่ง Server")
    permission_withdraw: int = Field(default=0, description="สิทธิ์การเบิกของ (0=ไม่มีสิทธิ์, 1=มีสิทธิ์)")
    permission_restock: int = Field(default=0, description="สิทธิ์การเติมของ (0=ไม่มีสิทธิ์, 1=มีสิทธิ์)")

class UserPermissionCreate(UserPermissionBase):
    pass

class UserPermissionUpdate(SQLModel):
    permission_withdraw: int | None = None
    permission_restock: int | None = None
    updated_at: datetime | None = Field(default_factory=lambda: datetime.now(timezone.utc))

class UserPermissionPublic(UserPermissionBase):
    id: int
    created_at: datetime
    updated_at: datetime | None = None
    deleted_at: datetime | None = None

# --- Auth Log Schemas (Optional: เก็บประวัติการเข้าใช้งาน) ---
class AuthLogBase(SQLModel):
    user_id: int | None = None
    username: str | None = None
    login_method: str = Field(description="'password' หรือ 'smartcard' หรือ 'RFID Staff Tag' หรือ 'QR Code'")
    status: str = Field(description="'success' หรือ 'failed'")

class AuthLogCreate(AuthLogBase):
    pass

class AuthLogPublic(AuthLogBase):
    id: int
    timestamp: datetime