from sqlmodel import SQLModel, Field
from datetime import datetime, timezone

class DeviceInfoBase(SQLModel):
    device_id: str = Field(index=True, unique=True, description="รหัสประจำตู้ locker เช่น LKR-001")
    name: str | None = Field(default=None, description="ชื่อหรือตัวระบุของตู้ เช่น 'ตู้ยาเวรกลางคืน'")
    location_detail: str | None = Field(default=None, description="รายละเอียดสถานที่ เช่น 'อาคาร 1 ชั้น 1 ห้องผ่าตัด'")
    is_active: bool = Field(default=True, description="สถานะของตู้ (พร้อมใช้งานหรือไม่)")

class DeviceInfoPublic(DeviceInfoBase):
    id: int
    registered_at: datetime | None
    last_sync: datetime | None
    deleted_at: datetime | None = None

class DeviceInfoCreate(DeviceInfoBase):
    auth_token: str = Field(description="โทเคนที่ใช้ยืนยันตัวตนกับเซิร์ฟเวอร์")

class DeviceInfoUpdate(SQLModel):
    name: str | None = None
    location_detail: str | None = None
    is_active: bool | None = None
    last_sync: datetime | None = None