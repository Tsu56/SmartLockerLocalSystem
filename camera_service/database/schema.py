from sqlmodel import SQLModel, Field
from typing import Optional

class SyncQueueBase(SQLModel):
    transaction_id: str = Field(index=True, description="ID ของ Transaction จากระบบหลัก")
    slot_id: str = Field(description="รหัสตู้ เช่น S1")
    
    # 👉 เพิ่มฟิลด์ session_dir เพื่อให้ Worker รู้ว่าต้องไปกวาดรูปจากโฟลเดอร์ไหน
    session_dir: str = Field(description="Path ของโฟลเดอร์ที่เก็บรูปรอบนี้ทั้งหมด (เช่น captures/S1_TXN123_...)")
    
    before_image_local: str = Field(description="Path รูป Before ในเครื่อง")
    after_image_local: str = Field(description="Path รูป After ในเครื่อง")
    before_count: int = Field(default=0, description="จำนวนขวดก่อนทำรายการ")
    after_count: int = Field(default=0, description="จำนวนขวดหลังทำรายการ")
    camera_amount: int = Field(default=0, description="จำนวนส่วนต่างที่ YOLO นับได้")
    action_type: str = Field(description="RESTOCK, WITHDRAW, หรือ NO_CHANGE")
    
    sync_status: str = Field(default="PENDING", description="สถานะ: PENDING, COMPLETED, FAILED")