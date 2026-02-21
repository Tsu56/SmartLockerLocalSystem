from sqlmodel import SQLModel, Field
from datetime import datetime, timezone

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