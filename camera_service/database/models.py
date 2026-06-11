from .schema import SyncQueueBase
from sqlmodel import Field
from datetime import datetime, timezone
from typing import Optional

class SyncQueue(SyncQueueBase, table=True):
    """ตารางคิวสำหรับรออัปโหลดรูปและส่งข้อมูลไป Server หลัก"""
    __tablename__ = "sync_queue"

    id: Optional[int] = Field(default=None, primary_key=True, description="ID Local Auto-increment")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))