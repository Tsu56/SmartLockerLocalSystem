from sqlmodel import SQLModel, Field
from datetime import datetime, timezone, date
from typing import Optional, List

# --- Product Schemas ---
class ProductBase(SQLModel):
    product_id: str = Field(index=True, unique=True, description="ID ของสินค้าในฝั่ง Server")
    product_name: Optional[str] = Field(description="ชื่อของสินค้า")
    product_detail: Optional[str] = Field(default=None, description="รายละเอียดของสินค้า")

class ProductCreate(ProductBase):
    pass

class ProductUpdate(SQLModel):
    product_name: str | None = None
    product_detail: str | None = None
    updated_at: datetime | None = Field(default_factory=lambda: datetime.now(timezone.utc))

class ProductPublic(ProductBase):
    created_at: datetime
    updated_at: datetime | None = None
    deleted_at: datetime | None = None

# --- Slot Stock Schemas ---
class SlotStockBase(SQLModel):
    slot_stock_id: int = Field(index=True, unique=True, description="ID ของ Stock Record จาก Server")
    lot_id: str = Field(description="เลขล็อตของสินค้า")
    product_id: str = Field(description="ID ของสินค้าที่อยู่ในสต็อกนี้")
    slot_id: int = Field(description="ID ของช่องที่เก็บสต็อกนี้")
    amount: int = Field(default=0, description="จำนวนสินค้าที่มีอยู่")
    expired_at: Optional[date] = Field(default=None, description="วันหมดอายุของล็อตนี้")

class SlotStockCreate(SlotStockBase):
    pass

class SlotStockUpdate(SQLModel):
    amount: int
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class SlotStockPublic(SlotStockBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

# --- Transactions Schemas ---
class TransactionBase(SQLModel):
    user_id: str = Field(description="UUID ของผู้ใช้งานที่ทำรายการ")
    activity: Optional[str] = Field(default=None, description="ประเภทรายการ เช่น dispense, restock")
    status: Optional[str] = Field(default="pending", description="สถานะรายการ เช่น pending, success, failed")

class TransactionCreate(TransactionBase):
    pass

class TransactionPublic(TransactionBase):
    transaction_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    # เพิ่มเพื่อเช็คสถานะการส่งข้อมูลขึ้น Cloud
    synced_at: Optional[datetime] = Field(default=None, description="เวลาที่ข้อมูลนี้ถูกส่งขึ้น Cloud สำเร็จ")

# --- Transaction Details Schemas ---
class TransactionDetailBase(SQLModel):
    transaction_id: int = Field(description="ID ของ Transaction หลัก")
    product_id: str = Field(description="ID ของสินค้าที่เบิก/เติม")
    slot_stock_id: int = Field(description="ID ของสต็อกจาก Server (unique index)")
    slot_id: int = Field(description="ID ของช่องตู้")
    amount: int = Field(default=0, description="จำนวนที่เบิกหรือเติม")

class TransactionDetailCreate(TransactionDetailBase):
    pass

class TransactionDetailPublic(TransactionDetailBase):
    transaction_detail_id: int
    created_at: datetime

# --- Snapshot Schemas ---
class SnapshotBase(SQLModel):
    image_path: Optional[str] = Field(default=None, description="พาร์ทรูปภาพในเครื่อง Local")
    transaction_id: int = Field(description="ID ของ Transaction")
    transaction_detail_id: int = Field(description="ID ของรายละเอียดรายการ")
    slot_stock_id: int = Field(description="ID ของสต็อกจาก Server (unique index)")
    camera_id: int = Field(description="ID ของกล้องที่ถ่าย")

class SnapshotCreate(SnapshotBase):
    pass

class SnapshotPublic(SnapshotBase):
    snapshot_id: int
    created_at: datetime
    # เพิ่มฟิลด์สำคัญสำหรับ Agent
    is_synced: bool = Field(default=False, description="สถานะการอัปโหลดรูปภาพขึ้น Cloud")
    synced_at: Optional[datetime] = Field(default=None, description="เวลาที่อัปโหลดรูปสำเร็จ")

# Specialized Response Schemas (สำหรับ Kivy UI)

class StockDetailPublic(SQLModel):
    """ข้อมูลสต็อกที่รวมชื่อสินค้ามาแล้ว เพื่อแสดงผลในหน้าเบิก/เติมของ"""
    id: int
    slot_stock_id: int
    lot_id: str
    amount: int
    expired_at: Optional[date]
    product: ProductBase # ดึง product_name และ product_detail มาแสดง

class SlotWithStocksPublic(SQLModel):
    """ข้อมูลช่อง 1 ช่อง พร้อมสต็อกทั้งหมดข้างใน (ใช้สำหรับหน้าจอ Dispense)"""
    slot_id: int
    slot_status: str
    capacity: int
    stocks: List[StockDetailPublic] = []

class TransactionWithDetailsPublic(TransactionPublic):
    """ข้อมูลประวัติการทำรายการ พร้อมรายละเอียดรายการทั้งหมด"""
    details: List[TransactionDetailPublic] = []