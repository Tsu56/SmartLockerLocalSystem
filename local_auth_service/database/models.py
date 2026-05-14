from database import UserBase, UserPermissionBase, AuthLogBase
from sqlmodel import SQLModel, Field, Relationship
from datetime import datetime, timezone
from typing import List, Optional

class User(UserBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    hashed_password: str = Field(description="รหัสผ่านที่ถูกเข้ารหัสแล้ว")
    citizen_id_search_hash: Optional[str] = Field(default=None, index=True, description="Hash สำหรับใช้ค้นหาบัตรประชาชน")
    created_at: datetime | None = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime | None = Field(default=None)
    deleted_at: datetime | None = Field(default=None)
    
    # Relationships
    user_permissions: List["UserPermission"] = Relationship(back_populates="user")
    auth_logs: List["AuthLog"] = Relationship(back_populates="user")

class UserPermission(UserPermissionBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: str = Field(foreign_key="user.user_id")
    created_at: datetime | None = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime | None = Field(default=None)
    deleted_at: datetime | None = Field(default=None)
    
    # Relationships
    user: Optional[User] = Relationship(back_populates="user_permissions")

class AuthLog(AuthLogBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: str | None = Field(default=None, foreign_key="user.user_id")
    timestamp: datetime | None = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Relationships
    user: Optional[User] = Relationship(back_populates="auth_logs")


class ProcessedEvent(SQLModel, table=True):
    """บันทึก event_id ที่ประมวลผลแล้วเพื่อกันข้อความซ้ำ"""
    __tablename__ = "processed_event"

    event_id: str = Field(primary_key=True, max_length=128, description="ID ของ event")
    event_type: str = Field(max_length=64, description="ชนิด event")
    processed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))