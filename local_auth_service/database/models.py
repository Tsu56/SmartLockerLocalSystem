from database import UserBase, SmartCardBase, AuthLogBase
from sqlmodel import Field, Relationship
from datetime import datetime, timezone
from typing import List, Optional

class User(UserBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    hashed_password: str = Field(description="รหัสผ่านที่ถูกเข้ารหัสแล้ว")
    created_at: datetime | None = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Relationships
    smart_card: Optional["SmartCard"] = Relationship(back_populates="user")
    auth_logs: List["AuthLog"] = Relationship(back_populates="user")

class SmartCard(SmartCardBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    registered_at: datetime | None = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Foreign Key
    user_id: int = Field(foreign_key="user.id", unique=True)
    
    # Relationships
    user: User = Relationship(back_populates="smart_card")

class AuthLog(AuthLogBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    timestamp: datetime | None = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Foreign Key (Optional เพราะบางที Login fail อาจจะไม่รู้ User ID ที่แน่นอน)
    user_id: int | None = Field(default=None, foreign_key="user.id")
    
    # Relationships
    user: Optional[User] = Relationship(back_populates="auth_logs")