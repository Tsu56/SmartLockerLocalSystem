from database import (
    ProductBase, SlotStockBase, 
    TransactionBase, TransactionDetailBase
)
from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime, date, timezone

# ==========================================
# Master Data Models (ใช้ ID จาก Server เป็น Primary Key)
# ==========================================

class Product(ProductBase, table=True):
    """ข้อมูลสินค้า: ใช้ product_id (string) จาก Server เป็น PK"""
    __tablename__ = "product"

    # Override เพื่อเพิ่ม primary_key และ max_length
    product_id: str = Field(primary_key=True, max_length=45, index=True, unique=True, description="ID จากฝั่ง Server")
    product_name: Optional[str] = Field(default=None, max_length=45, description="ชื่อของสินค้า")
    product_detail: Optional[str] = Field(default=None, max_length=255, description="รายละเอียดของสินค้า")
    
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None

    slot_stocks: List["SlotStock"] = Relationship(back_populates="product")


class SlotStock(SlotStockBase, table=True):
    """ข้อมูลสต็อก: ใช้ slot_stock_id เป็น Local Primary Key (auto-increment)"""
    __tablename__ = "slot_stock"
    
    # Local Primary Key (auto-increment)
    slot_stock_id: Optional[int] = Field(default=None, primary_key=True, description="Local ID ของ Stock Record (auto-increment)")
    lot_id: str = Field(max_length=45, index=True, description="เลขล็อตของสินค้า")
    
    product_id: str = Field(foreign_key="product.product_id", max_length=45, index=True, description="ID ของสินค้าที่อยู่ในสต็อกนี้")
    slot_id: int = Field(index=True, description="ID ของช่องที่เก็บสต็อกนี้ (FK to device_identity_service.slot)")
    
    amount: int = Field(default=0, description="จำนวนสินค้าที่มีอยู่")
    expired_at: Optional[date] = Field(default=None, description="วันหมดอายุของล็อตนี้")
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None

    product: Optional[Product] = Relationship(back_populates="slot_stocks")
    transaction_details: List["TransactionDetail"] = Relationship(back_populates="slot_stock")


# ==========================================
# Local Activity Models (ใช้ Local Auto-increment เป็น Primary Key)
# ==========================================

class Transaction(TransactionBase, table=True):
    """ข้อมูลรายการ: เกิดขึ้นที่ตู้ ใช้ Auto-increment Local ID"""
    __tablename__ = "transaction"

    # ใช้ Local ID เป็น PK เพื่อให้ Insert ได้ทันทีแม้ Offline
    transaction_id: Optional[int] = Field(default=None, primary_key=True)
    
    # Override เพื่อเพิ่ม max_length
    user_id: str = Field(index=True, description="UUID ของผู้ใช้งานที่ทำรายการ") 
    activity: Optional[str] = Field(default=None, max_length=45, description="ประเภทรายการ เช่น dispense, restock") # dispense, restock
    status: Optional[str] = Field(default="success", max_length=45, description="สถานะรายการ เช่น pending, success, failed")
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # เก็บ ID ที่ Server ตอบกลับมาหลังจาก Sync สำเร็จ (Optional)
    server_transaction_id: Optional[int] = Field(default=None, index=True)
    synced_at: Optional[datetime] = Field(default=None, description="เวลาที่ข้อมูลนี้ถูกส่งขึ้น Cloud สำเร็จ")

    details: List["TransactionDetail"] = Relationship(back_populates="transaction")


class TransactionDetail(TransactionDetailBase, table=True):
    """รายละเอียดรายการ: ใช้ Local ID"""
    __tablename__ = "transaction_detail"

    # เพิ่ม Local Primary Key
    transaction_detail_id: Optional[int] = Field(default=None, primary_key=True)
    
    # Override เพื่อเพิ่ม foreign_key และ max_length
    transaction_id: int = Field(foreign_key="transaction.transaction_id", description="ID ของ Transaction หลัก")
    product_id: str = Field(max_length=45, description="ID ของสินค้าที่เบิก/เติม")
    slot_id: int = Field(description="ID ของช่องตู้")
    
    # เปลี่ยนให้ slot_stock_id อ้างอิงไปที่ slot_stock.slot_stock_id (primary key)
    slot_stock_id: int = Field(foreign_key="slot_stock.slot_stock_id", description="FK ไปที่ SlotStock.slot_stock_id")
    
    amount: int = Field(default=0, description="จำนวนที่เบิกหรือเพิ่ม")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    transaction: Optional[Transaction] = Relationship(back_populates="details")
    slot_stock: Optional[SlotStock] = Relationship(back_populates="transaction_details")


class ProcessedEvent(SQLModel, table=True):
    """บันทึก event_id ที่ประมวลผลแล้วเพื่อกันข้อความซ้ำ"""
    __tablename__ = "processed_event"

    event_id: str = Field(primary_key=True, max_length=128, description="ID ของ event")
    event_type: str = Field(max_length=64, description="ชนิด event")
    processed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class QRTask(SQLModel, table=True):
    """งานที่ Cloud ส่งเข้าตู้ผ่าน MQTT เพื่อรอสแกน QR ที่ตู้"""
    __tablename__ = "qr_task"

    task_id: str = Field(primary_key=True, max_length=128, description="รหัสงานจาก Cloud")
    locker_id: str = Field(index=True, max_length=45)
    task_type: str = Field(max_length=32, description="restock หรือ dispense")
    assigned_user_id: str = Field(index=True, max_length=128)
    qr_token: Optional[str] = Field(default=None, index=True, max_length=255)
    items_json: str = Field(default="[]", description="รายการยาในรูป JSON string")
    status: str = Field(default="pending", index=True, max_length=32)
    expires_at: Optional[datetime] = Field(default=None, index=True)
    used_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None