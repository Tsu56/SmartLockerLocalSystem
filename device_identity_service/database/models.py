from database import DeviceInfoBase
from sqlmodel import Field
from datetime import datetime, timezone

class DeviceInfo(DeviceInfoBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    auth_token: str = Field(description="โทเคนที่ใช้ยืนยันตัวตนกับเซิร์ฟเวอร์")
    registered_at: datetime | None = Field(default_factory=datetime.now(timezone.utc))
    last_sync: datetime | None = Field(default=None, description="เวลาที่ sync ล่าสุดกับ server")
    deleted_at: datetime | None = Field(default=None, description="เวลาที่ถูกลบ (soft delete)")