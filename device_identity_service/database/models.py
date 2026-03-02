from database import DeviceInfoBase, SlotBase
from sqlmodel import Field, Relationship
from datetime import datetime, timezone
from typing import Optional, List

class Slot(SlotBase, table=True):
    """ข้อมูลช่อง: ใช้ slot_id (int) จาก Server เป็น PK"""
    __tablename__ = "slot"

    id: Optional[int] = Field(default=None, primary_key=True, description="ID Local Auto-increment")
    locker_id: int = Field(index=True, description="ID ของตู้ที่เป็นเจ้าของช่องนี้")
    slot_status: Optional[str] = Field(default="active", max_length=45, description="สถานะของช่อง เช่น active, maintenance") 
    capacity: Optional[int] = Field(default=0, description="ความจุสูงสุดของช่อง")
    
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None

    # Relationship กับ SlotStock (ชี้ไปยัง product_management_service)
    slot_stocks: List["SlotStock"] = Relationship(back_populates="slot")

class DeviceInfo(DeviceInfoBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    api_token_encrypted: str = Field(description="โทเคนที่ใช้ยืนยันตัวตนกับเซิร์ฟเวอร์")
    registered_at: datetime | None = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_sync: datetime | None = Field(default=None, description="เวลาที่ sync ล่าสุดกับ server")
    deleted_at: datetime | None = Field(default=None, description="เวลาที่ถูกลบ (soft delete)")