from sqlmodel import SQLModel, Field
from datetime import datetime, timezone, date
from typing import Optional

# --- Slot Schemas ---
class SlotBase(SQLModel):
    slot_id: int = Field(index=True, unique=True, description="ID ของช่อง Slot ในฝั่ง Server")
    locker_id: str = Field(description="รหัสตู้ที่เป็นเจ้าของช่องนี้ เช่น LKR-001")
    slot_status: Optional[str] = Field(default="active", description="สถานะของช่อง เช่น active, maintenance")
    capacity: Optional[int] = Field(default=0, description="ความจุสูงสุดของช่อง")

class SlotCreate(SlotBase):
    pass

class SlotUpdate(SQLModel):
    slot_status: Optional[str] = None
    capacity: Optional[int] = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class SlotPublic(SlotBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

class DeviceInfoBase(SQLModel):
    locker_id: str = Field(index=True, unique=True, description="รหัสประจำตู้ locker เช่น LKR-001")
    locker_location_detail: str | None = Field(default=None, description="รายละเอียดสถานที่ เช่น 'อาคาร 1 ชั้น 1 ห้องผ่าตัด'")
    is_active: bool = Field(default=True, description="สถานะของตู้ (พร้อมใช้งานหรือไม่)")

class DeviceInfoPublic(DeviceInfoBase):
    id: int
    registered_at: datetime | None
    last_sync: datetime | None
    deleted_at: datetime | None = None

class DeviceInfoCreate(DeviceInfoBase):
    api_token_encrypted: str = Field(description="โทเคนที่ใช้ยืนยันตัวตนกับเซิร์ฟเวอร์")

class DeviceInfoUpdate(SQLModel):
    locker_location_detail: str | None = None
    is_active: bool | None = None
    last_sync: datetime | None = None

class DeviceActivationRequest(SQLModel):
    provision_code: str = Field(description="รหัส 6 หลักสำหรับลงทะเบียนตู้")