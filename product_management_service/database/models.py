from database import (
    ProductBase, SlotStockBase, 
    TransactionBase, TransactionDetailBase, SnapshotBase
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
    """ข้อมูลสต็อก: ใช้ slot_stock_id (int) จาก Server เป็น PK"""
    __tablename__ = "slot_stock"
    
    # Override เพื่อเพิ่ม primary_key, foreign_key และ max_length
    slot_stock_id: int = Field(primary_key=True, index=True, unique=True, description="ID ของ Stock Record จาก Server")
    lot_id: str = Field(max_length=45, index=True, description="เลขล็อตของสินค้า")
    
    product_id: str = Field(foreign_key="product.product_id", max_length=45, index=True, description="ID ของสินค้าที่อยู่ในสต็อกนี้")
    slot_id: int = Field(index=True, description="ID ของช่องที่เก็บสต็อกนี้ (FK to device_identity_service.slot)")
    
    amount: int = Field(default=0, description="จำนวนสินค้าที่มีอยู่")
    expired_at: Optional[date] = Field(default=None, description="วันหมดอายุของล็อตนี้")
    
    created_at: Optional[datetime] = None
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
    snapshots: List["Snapshot"] = Relationship(back_populates="transaction")


class TransactionDetail(TransactionDetailBase, table=True):
    """รายละเอียดรายการ: ใช้ Local ID"""
    __tablename__ = "transaction_detail"

    # เพิ่ม Local Primary Key
    transaction_detail_id: Optional[int] = Field(default=None, primary_key=True)
    
    # Override เพื่อเพิ่ม foreign_key และ max_length
    transaction_id: int = Field(foreign_key="transaction.transaction_id", description="ID ของ Transaction หลัก")
    product_id: str = Field(max_length=45, description="ID ของสินค้าที่เบิก/เติม")
    slot_id: int = Field(description="ID ของช่องตู้")
    slot_stock_id: int = Field(foreign_key="slot_stock.slot_stock_id", description="ID ของสต็อกที่ถูกตัด/เพิ่ม")
    
    amount: int = Field(default=0, description="จำนวนที่เบิกหรือเติม")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    transaction: Optional[Transaction] = Relationship(back_populates="details")
    slot_stock: Optional[SlotStock] = Relationship(back_populates="transaction_details")
    snapshots: List["Snapshot"] = Relationship(back_populates="transaction_detail")


class Snapshot(SnapshotBase, table=True):
    """ข้อมูลภาพถ่าย: ใช้ Local ID"""
    __tablename__ = "snapshot"

    # เพิ่ม Local Primary Key
    snapshot_id: Optional[int] = Field(default=None, primary_key=True)
    
    # Override เพื่อเพิ่ม foreign_key และใช้ชื่อที่สอดคล้องกับ schema (image_path → local_path)
    transaction_id: int = Field(foreign_key="transaction.transaction_id", description="ID ของ Transaction")
    transaction_detail_id: int = Field(foreign_key="transaction_detail.transaction_detail_id", description="ID ของรายละเอียดรายการ")
    slot_stock_id: int = Field(description="ID ของสต็อกในช่อง")
    camera_id: int = Field(description="ID ของกล้องที่ถ่าย")
    
    # ใช้ image_path จาก SnapshotBase แต่ map เป็น local_path
    image_path: Optional[str] = Field(default=None, description="พาร์ทรูปภาพในเครื่อง Local", alias="local_path")
    cloud_url: Optional[str] = None 
    
    is_synced: bool = Field(default=False, index=True, description="สถานะการอัปโหลดรูปภาพขึ้น Cloud")
    synced_at: Optional[datetime] = Field(default=None, description="เวลาที่อัปโหลดรูปสำเร็จ")
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    transaction: Optional[Transaction] = Relationship(back_populates="snapshots")
    transaction_detail: Optional[TransactionDetail] = Relationship(back_populates="snapshots")