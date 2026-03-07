from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from typing import List
from datetime import datetime, timezone
import requests
import os
from dotenv import load_dotenv

# นำเข้า models และ schema ที่เราสร้างไว้
from database import get_session, models, schema
from getkey import get_internal_shared_secret

from product_sync_agent import perform_product_sync

load_dotenv()
INTERNAL_SHARED_SECRET = get_internal_shared_secret()
DEVICE_SERVICE_URL = "http://device-identity-service:8000"

router = APIRouter(prefix="/locker", tags=["Locker Operations"])

# ==========================================
# 1. Endpoints สำหรับหน้าจอ UI (ดึงข้อมูล)
# ==========================================

@router.get("/slots", response_model=List[schema.SlotWithStocksPublic])
def get_slots_with_stock(session: Session = Depends(get_session)):
    """
    ดึงข้อมูลช่องทั้งหมด พร้อมกับสต็อกสินค้าและชื่อสินค้าที่อยู่ข้างใน
    ใช้สำหรับแสดงผลในหน้า DispenseScreen / RestockScreen
    """
    # ดึงข้อมูล Slot จาก device_identity_service
    try:
        headers = {"X-Internal-Secret": INTERNAL_SHARED_SECRET}
        response = requests.get(
            f"{DEVICE_SERVICE_URL}/device/internal/slots",
            headers=headers,
            timeout=10
        )
        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail="Failed to fetch slots from device service"
            )
        slots = response.json()
    except requests.RequestException as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error connecting to device service: {str(e)}"
        )
    
    result = []
    for slot in slots:
        stocks_data = []
        # ดึงสต็อกที่อยู่ในช่องนี้
        stocks = session.exec(
            select(models.SlotStock).where(models.SlotStock.slot_id == slot["slot_id"])
        ).all()
        
        for stock in stocks:
            stocks_data.append({
                "slot_stock_id": stock.slot_stock_id,
                "lot_id": stock.lot_id,
                "amount": stock.amount,
                "expired_at": stock.expired_at,
                "product": stock.product  # SQLModel จะดึงข้อมูล Product ให้อัตโนมัติ
            })
            
        result.append({
            "slot_id": slot["slot_id"],
            "slot_status": slot["slot_status"],
            "capacity": slot["capacity"],
            "stocks": stocks_data
        })
        
    return result

@router.get("/products", response_model=List[schema.ProductPublic])
def get_all_products(session: Session = Depends(get_session)):
    """ดึงข้อมูลสินค้าทั้งหมด (Master Data)"""
    products = session.exec(select(models.Product).order_by(models.Product.product_id)).all()
    return products

# ==========================================
# 2. Endpoints สำหรับการทำรายการ (Transactions)
# ==========================================

@router.post("/transactions", response_model=schema.TransactionPublic)
def create_transaction(transaction: schema.TransactionCreate, session: Session = Depends(get_session)):
    """
    สร้าง Transaction ใหม่ (เมื่อพยาบาลเริ่มกดเบิกหรือเติมของ)
    """
    db_transaction = models.Transaction.model_validate(transaction)
    session.add(db_transaction)
    session.commit()
    session.refresh(db_transaction)
    return db_transaction

@router.post("/transactions/{transaction_id}/details", response_model=schema.TransactionDetailPublic)
def add_transaction_detail(
    transaction_id: int, 
    detail: schema.TransactionDetailCreate, 
    session: Session = Depends(get_session)
):
    """
    บันทึกรายละเอียดการเบิก/เติม (พร้อมทั้งตัด/เพิ่ม สต็อกอัตโนมัติ)
    """
    if detail.transaction_id != transaction_id:
        raise HTTPException(status_code=400, detail="Transaction ID mismatch")

    # 1. ตรวจสอบว่ามี Transaction หลักหรือไม่
    transaction = session.get(models.Transaction, transaction_id)
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    # 2. ตรวจสอบว่ามี Stock ในช่องนั้นหรือไม่
    stock = session.get(models.SlotStock, detail.slot_stock_id)
    if not stock:
        raise HTTPException(status_code=404, detail="Slot Stock not found")

    # 3. อัปเดตจำนวนสต็อก (ตัด/เพิ่ม) ตามประเภท Activity
    if transaction.activity == "dispense":
        if stock.amount < detail.amount:
            raise HTTPException(
                status_code=400, 
                detail=f"Not enough stock. Available: {stock.amount}, Requested: {detail.amount}"
            )
        stock.amount -= detail.amount
        
    elif transaction.activity == "restock":
        # (Optional) ตรวจสอบ Capacity ของช่องจาก device_identity_service
        try:
            headers = {"X-Internal-Secret": INTERNAL_SHARED_SECRET}
            response = requests.get(
                f"{DEVICE_SERVICE_URL}/device/internal/slots",
                headers=headers,
                timeout=10
            )
            if response.status_code == 200:
                slots = response.json()
                slot_data = next((s for s in slots if s["slot_id"] == detail.slot_id), None)
                if slot_data and slot_data.get("capacity") < (stock.amount + detail.amount):
                    raise HTTPException(
                        status_code=400, 
                        detail=f"Amount exceeds slot capacity ({slot_data.get('capacity')})"
                    )
        except requests.RequestException:
            # ถ้าไม่สามารถเชื่อมต่อ device_identity_service ให้ข้ามการตรวจสอบ capacity
            pass
        
        stock.amount += detail.amount

    # 4. บันทึกข้อมูล Detail และอัปเดต Stock
    db_detail = models.TransactionDetail.model_validate(detail)
    session.add(db_detail)
    session.add(stock)
    
    session.commit()
    session.refresh(db_detail)
    return db_detail

# ==========================================
# 3. Endpoints สำหรับรูปภาพ (Snapshots)
# ==========================================

@router.post("/snapshots", response_model=schema.SnapshotPublic)
def create_snapshot(snapshot: schema.SnapshotCreate, session: Session = Depends(get_session)):
    """
    บันทึกข้อมูลภาพถ่ายลง Local Database หลังจากถ่ายรูปเสร็จ
    เพื่อให้ Image Sync Agent นำไปส่งขึ้น Cloud ต่อไป
    """
    db_snapshot = models.Snapshot.model_validate(snapshot)
    session.add(db_snapshot)
    session.commit()
    session.refresh(db_snapshot)
    return db_snapshot

@router.get("/transactions/{transaction_id}/history", response_model=schema.TransactionWithDetailsPublic)
def get_transaction_history(transaction_id: int, session: Session = Depends(get_session)):
    """
    ดูข้อมูลประวัติรายการ 1 รายการแบบเต็ม พร้อม Details ทัั้งหมด (สำหรับ UI เช็คประวัติ)
    """
    transaction = session.get(models.Transaction, transaction_id)
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return transaction

# ==========================================
# 4. Endpoints สำหรับ Manual Sync (Trigger)
# ==========================================

@router.post("/sync/manual")
def trigger_manual_sync():
    """
    สั่งให้ตู้ทำการ Sync ข้อมูลสินค้าจาก Cloud ทันทีโดยไม่ต้องรอรอบเวลา
    ใช้สำหรับทดสอบ หรือจังหวะที่ต้องการข้อมูลล่าสุดทันที
    """
    result = perform_product_sync()
    
    if result["status"] == "success":
        return result
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=result["message"]
        )