from database import DeviceInfoBase, SlotBase
from sqlmodel import SQLModel, Field, Relationship
from datetime import datetime, timezone
from typing import Optional, List

class Slot(SlotBase, table=True):
    """ข้อมูลช่อง: ใช้ slot_id (int) จาก Server เป็น PK"""
    __tablename__ = "slot"

    id: Optional[int] = Field(default=None, primary_key=True, description="ID Local Auto-increment")
    locker_id: str = Field(foreign_key="deviceinfo.locker_id", max_length=45, index=True, description="รหัสตู้ที่เป็นเจ้าของช่องนี้ เช่น LKR-001")
    slot_status: Optional[str] = Field(default="active", max_length=45, description="สถานะของช่อง เช่น active, maintenance") 
    capacity: Optional[int] = Field(default=0, description="ความจุสูงสุดของช่อง")
    
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None

    # Relationship กับ DeviceInfo
    device: Optional["DeviceInfo"] = Relationship(back_populates="slots")
    
    # หมายเหตุ: SlotStock อยู่ใน product_management_service ดังนั้นไม่มี Relationship ที่นี่
    # ใช้ slot_id ในการ query SlotStock จาก product_management.db แทน


class DeviceInfo(DeviceInfoBase, table=True):
    __tablename__ = "deviceinfo"
    
    id: int | None = Field(default=None, primary_key=True)
    api_token_encrypted: str = Field(description="โทเคนที่ใช้ยืนยันตัวตนกับเซิร์ฟเวอร์")
    registered_at: datetime | None = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_sync: datetime | None = Field(default=None, description="เวลาที่ sync ล่าสุดกับ server")
    deleted_at: datetime | None = Field(default=None, description="เวลาที่ถูกลบ (soft delete)")
    
    # Relationship กับ Slot (one-to-many)
    slots: List["Slot"] = Relationship(back_populates="device")


class ProcessedEvent(SQLModel, table=True):
    """บันทึก event_id ที่ประมวลผลแล้วเพื่อกันข้อความซ้ำ"""
    __tablename__ = "processed_event"

    event_id: str = Field(primary_key=True, max_length=128, description="ID ของ event")
    event_type: str = Field(max_length=64, description="ชนิด event")
    processed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))