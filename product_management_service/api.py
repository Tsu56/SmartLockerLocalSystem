from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlmodel import Session, select
from typing import List
from datetime import datetime, timezone
import requests
import os
import time
import json
from dotenv import load_dotenv

# นำเข้า models และ schema ที่เราสร้างไว้
from database import get_session, models, schema, engine
from getkey import get_internal_shared_secret

from product_sync_agent import perform_product_sync

load_dotenv()
INTERNAL_SHARED_SECRET = get_internal_shared_secret()
DEVICE_SERVICE_URL = "http://device-identity-service:8000"
CLOUD_SERVER_URL = os.getenv("SERVER_URL", "")
QR_TASK_COMPLETE_CALLBACK_PATH = os.getenv("QR_TASK_COMPLETE_CALLBACK_PATH", "/qrTask/complete-from-locker")

router = APIRouter(prefix="/locker", tags=["Locker Operations"])

# ==========================================
# Helper Functions สำหรับ Sync
# ==========================================

def get_cloud_auth_headers():
    """ดึง Auth Headers จาก Device Identity Service เพื่อใช้ยืนยันตัวตนกับ Cloud Server"""
    try:
        headers = {"X-Internal-Secret": INTERNAL_SHARED_SECRET}
        response = requests.get(
            f"{DEVICE_SERVICE_URL}/device/internal/auth-headers",
            headers=headers,
            timeout=5
        )
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        print(f"📡 [Transaction Sync] Device Service Connection Error: {e}")
        return None


def get_local_locker_id() -> str | None:
    """ดึง locker_id ปัจจุบันของตู้จาก identity service"""
    auth_headers = get_cloud_auth_headers() or {}
    locker_id = auth_headers.get("locker_id")
    if locker_id is None:
        return None
    return str(locker_id)


def _to_utc_aware(dt_value: datetime | None) -> datetime | None:
    """Normalize datetime ให้เป็น UTC-aware เพื่อป้องกัน compare error naive/aware"""
    if dt_value is None:
        return None
    if dt_value.tzinfo is None:
        return dt_value.replace(tzinfo=timezone.utc)
    return dt_value.astimezone(timezone.utc)


def sync_qr_task_completion_to_server(task_payload: dict, max_retries: int = 3):
    """แจ้ง Web Server ว่า QR task ถูกทำเสร็จแล้วจากฝั่งตู้"""
    if not CLOUD_SERVER_URL:
        print("⚠️ [QR Task Sync] SERVER_URL is empty, skip completion callback")
        return {"status": "skipped", "message": "SERVER_URL is empty"}

    callback_url = f"{CLOUD_SERVER_URL.rstrip('/')}{QR_TASK_COMPLETE_CALLBACK_PATH}"
    auth_headers = get_cloud_auth_headers() or {}

    for attempt in range(max_retries):
        try:
            response = requests.post(
                callback_url,
                json=task_payload,
                headers=auth_headers,
                timeout=15,
            )
            if response.status_code in (200, 201):
                print(f"✅ [QR Task Sync] Completion callback success task_id={task_payload.get('task_id')}")
                return {"status": "success", "status_code": response.status_code}

            print(
                f"⚠️ [QR Task Sync] Callback failed status={response.status_code} body={response.text}"
            )
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
            return {
                "status": "error",
                "status_code": response.status_code,
                "detail": response.text,
            }
        except requests.RequestException as e:
            print(f"⚠️ [QR Task Sync] Network error (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
            return {"status": "error", "message": str(e)}

    return {"status": "error", "message": "Max retries exceeded"}


def sync_transaction_to_server(transaction_id: int, max_retries: int = 3):
    """
    Sync Transaction, TransactionDetails และ SlotStock ขึ้น Cloud Server
    
    Args:
        transaction_id: ID ของ Transaction ที่ต้องการ sync
        max_retries: จำนวนครั้งที่จะลองใหม่ถ้า sync ไม่สำเร็จ
    """
    print(f"🔄 [Transaction Sync] Starting sync for transaction_id={transaction_id}")
    
    # Get auth headers
    auth_headers = get_cloud_auth_headers()
    if not auth_headers:
        print(f"❌ [Transaction Sync] Cannot get auth headers")
        return {"status": "error", "message": "Auth headers unavailable"}
    
    # Retry logic
    for attempt in range(max_retries):
        try:
            with Session(engine) as session:
                # 1. ดึงข้อมูล Transaction
                transaction = session.get(models.Transaction, transaction_id)
                if not transaction:
                    print(f"❌ [Transaction Sync] Transaction {transaction_id} not found")
                    return {"status": "error", "message": "Transaction not found"}
                
                # ถ้า sync แล้ว ไม่ต้อง sync ซ้ำ
                if transaction.synced_at:
                    print(f"✅ [Transaction Sync] Transaction {transaction_id} already synced")
                    return {"status": "already_synced", "synced_at": transaction.synced_at}
                
                # 2. ดึง TransactionDetails
                details = session.exec(
                    select(models.TransactionDetail)
                    .where(models.TransactionDetail.transaction_id == transaction_id)
                ).all()
                
                # 3. รวบรวม SlotStock IDs ที่เกี่ยวข้อง
                slot_stock_ids = list(set(detail.slot_stock_id for detail in details))
                slot_stocks = session.exec(
                    select(models.SlotStock)
                    .where(models.SlotStock.slot_stock_id.in_(slot_stock_ids))
                ).all()
                
                # 4. เตรียมข้อมูลสำหรับส่งไปยัง Server
                transaction_payload = {
                    "transaction": {
                        "user_id": transaction.user_id,
                        "activity": transaction.activity,
                        "status": transaction.status,
                        "created_at": transaction.created_at.isoformat(),
                    },
                    "details": [
                        {
                            "product_id": detail.product_id,
                            "slot_id": detail.slot_id,
                            "slot_stock_id": detail.slot_stock_id,
                            "amount": detail.amount,
                            "created_at": detail.created_at.isoformat(),
                        }
                        for detail in details
                    ],
                    "slot_stocks": [
                        {
                            "slot_stock_id": stock.slot_stock_id,
                            "lot_id": stock.lot_id,
                            "product_id": stock.product_id,
                            "slot_id": stock.slot_id,
                            "amount": stock.amount,
                            "expired_at": stock.expired_at.isoformat() if stock.expired_at else None,
                            "created_at": stock.created_at.isoformat() if stock.created_at else None,
                            "updated_at": stock.updated_at.isoformat() if stock.updated_at else None,
                        }
                        for stock in slot_stocks
                    ],
                }

                print(f"DEBUG {transaction_payload}")
                
                # 5. ส่งไปยัง Cloud Server
                sync_url = f"{CLOUD_SERVER_URL}/transaction/createTransactionFromLocker"
                response = requests.post(
                    sync_url,
                    json=transaction_payload,
                    headers=auth_headers,
                    timeout=30
                )
                
                if response.status_code == 200 or response.status_code == 201:
                    sync_result = response.json()
                    print(f"DEBUG Sync Result: {sync_result}")
                    
                    # 6. อัปเดต synced_at และ server_transaction_id
                    transaction.synced_at = datetime.now(timezone.utc)
                    if "transaction_id" in sync_result:
                        transaction.server_transaction_id = sync_result["transaction_id"]
                    
                    session.add(transaction)
                    session.commit()
                    
                    print(f"✅ [Transaction Sync] Successfully synced transaction_id={transaction_id}")
                    return {
                        "status": "success",
                        "transaction_id": transaction_id,
                        "server_transaction_id": transaction.server_transaction_id,
                        "synced_at": transaction.synced_at
                    }
                else:
                    print(f"⚠️ [Transaction Sync] Server returned {response.status_code}: {response.text}")
                    if attempt < max_retries - 1:
                        time.sleep(2 ** attempt)  # Exponential backoff
                        continue
                    return {
                        "status": "error",
                        "message": f"Server error: {response.status_code}",
                        "detail": response.text
                    }
                    
        except requests.RequestException as e:
            print(f"⚠️ [Transaction Sync] Network error (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
                continue
            return {"status": "error", "message": f"Network error: {str(e)}"}
        except Exception as e:
            print(f"❌ [Transaction Sync] Unexpected error: {e}")
            return {"status": "error", "message": f"Unexpected error: {str(e)}"}
    
    return {"status": "error", "message": "Max retries exceeded"}

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

    # แสดงเฉพาะ slot ที่ยังไม่ถูกลบ (soft delete)
    slots = [slot for slot in slots if slot.get("deleted_at") is None]
    
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
            "slot_id": slot["id"],
            "slot_id_from_server": slot["slot_id"],
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


@router.post("/qr-tasks/resolve", response_model=schema.QRTaskResolvePublic)
def resolve_qr_task(payload: schema.QRTaskResolveRequest, session: Session = Depends(get_session)):
    """ตรวจ QR token กับฐานข้อมูลในตู้และยืนยันผู้รับมอบหมาย"""
    qr_token = payload.qr_token.strip()
    user_id = payload.user_id.strip()
    if not qr_token or not user_id:
        raise HTTPException(status_code=400, detail="qr_token and user_id are required")

    db_task = session.exec(
        select(models.QRTask).where(models.QRTask.qr_token == qr_token)
    ).first()

    if not db_task or db_task.deleted_at is not None:
        raise HTTPException(status_code=404, detail="QR task not found")

    local_locker_id = get_local_locker_id()
    if local_locker_id and str(db_task.locker_id) != local_locker_id:
        raise HTTPException(status_code=403, detail="QR task does not belong to this locker")

    now = datetime.now(timezone.utc)
    expires_at = _to_utc_aware(db_task.expires_at)
    if expires_at and expires_at < now:
        db_task.status = "expired"
        db_task.updated_at = now
        session.add(db_task)
        session.commit()
        raise HTTPException(status_code=410, detail="QR task expired")

    if db_task.status != "pending":
        raise HTTPException(status_code=409, detail=f"QR task status is {db_task.status}")

    if db_task.assigned_user_id != user_id:
        raise HTTPException(status_code=403, detail="This user is not assigned to this task")

    try:
        items = json.loads(db_task.items_json) if db_task.items_json else []
        if not isinstance(items, list):
            items = []
    except Exception:
        items = []

    return {
        "task_id": db_task.task_id,
        "task_type": db_task.task_type,
        "assigned_user_id": db_task.assigned_user_id,
        "status": db_task.status,
        "expires_at": db_task.expires_at,
        "items": items,
    }


@router.post("/qr-tasks/{task_id}/complete")
def complete_qr_task(
    task_id: str,
    payload: schema.QRTaskCompleteRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
):
    """ปิดงาน QR task หลังผู้ใช้กดยืนยันทำรายการที่ตู้สำเร็จ"""
    db_task = session.get(models.QRTask, task_id)
    if not db_task:
        raise HTTPException(status_code=404, detail="QR task not found")

    if db_task.assigned_user_id != payload.user_id:
        raise HTTPException(status_code=403, detail="This user is not assigned to this task")

    if db_task.status != "pending":
        raise HTTPException(status_code=409, detail=f"QR task status is {db_task.status}")

    now = datetime.now(timezone.utc)
    db_task.status = "completed"
    db_task.used_at = now
    db_task.updated_at = now
    session.add(db_task)
    session.commit()

    callback_payload = {
        "task_id": db_task.task_id,
        "locker_id": db_task.locker_id,
        "assigned_user_id": db_task.assigned_user_id,
        "status": db_task.status,
        "used_at": db_task.used_at.isoformat() if db_task.used_at else None,
        "updated_at": db_task.updated_at.isoformat() if db_task.updated_at else None,
        "completed_by": payload.user_id,
    }
    background_tasks.add_task(sync_qr_task_completion_to_server, callback_payload)

    return {"status": "success", "task_id": task_id, "completed_at": now}

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
    background_tasks: BackgroundTasks,
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


@router.post("/restock", response_model=schema.RestockPublic)
def restock_items(
    restock_data: schema.RestockCreate, 
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session)
):
    """
    เติมยาแบบยกตะกร้าในคำขอเดียว
    - สร้าง Transaction (activity=restock)
    - ตรวจสอบ Capacity ต่อช่อง
    - สร้าง/อัปเดต SlotStock ตาม product_id + slot_id + lot_id + expired_at
    - สร้าง TransactionDetail พร้อม slot_stock_id ที่ได้จริง
    """
    if not restock_data.items:
        raise HTTPException(status_code=400, detail="Restock items cannot be empty")

    # ดึงข้อมูลช่องเพื่อใช้ตรวจสอบ slot_id และ capacity
    try:
        headers = {"X-Internal-Secret": INTERNAL_SHARED_SECRET}
        slot_response = requests.get(
            f"{DEVICE_SERVICE_URL}/device/internal/slots",
            headers=headers,
            timeout=10,
        )
        if slot_response.status_code != 200:
            raise HTTPException(
                status_code=slot_response.status_code,
                detail="Failed to fetch slots from device service",
            )
        slots = slot_response.json()
    except requests.RequestException as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error connecting to device service: {str(e)}",
        )

    slots_by_id = {}
    for slot in slots:
        if "slot_id" in slot:
            slots_by_id[slot["slot_id"]] = slot
    added_amount_by_slot = {}

    # ตรวจสอบข้อมูลที่ส่งมาก่อนเริ่มบันทึก
    for item in restock_data.items:
        if item.slot_id not in slots_by_id:
            raise HTTPException(status_code=404, detail=f"Slot {item.slot_id} not found")

        product = session.get(models.Product, item.product_id)
        if not product:
            raise HTTPException(status_code=404, detail=f"Product {item.product_id} not found")

        added_amount_by_slot[item.slot_id] = added_amount_by_slot.get(item.slot_id, 0) + item.amount

    # ตรวจสอบ capacity แบบรวมทั้งตะกร้า
    for slot_id, added_amount in added_amount_by_slot.items():
        current_slot_stocks = session.exec(
            select(models.SlotStock).where(models.SlotStock.slot_id == slot_id)
        ).all()
        current_total = sum(stock.amount for stock in current_slot_stocks)
        capacity = slots_by_id[slot_id].get("capacity")

        if capacity is not None and (current_total + added_amount) > capacity:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Amount exceeds slot capacity for slot {slot_id} "
                    f"(capacity={capacity}, current={current_total}, added={added_amount})"
                ),
            )

    db_transaction = models.Transaction(
        user_id=restock_data.user_id,
        activity="restock",
        status="success",
    )
    session.add(db_transaction)
    session.flush()

    response_details = []

    for item in restock_data.items:
        slot_stock = session.exec(
            select(models.SlotStock)
            .where(models.SlotStock.product_id == item.product_id)
            .where(models.SlotStock.slot_id == item.slot_id)
            .where(models.SlotStock.lot_id == item.lot_id)
            .where(models.SlotStock.expired_at == item.expired_at)
        ).first()

        if slot_stock:
            slot_stock.amount += item.amount
        else:
            slot_stock = models.SlotStock(
                lot_id=item.lot_id,
                product_id=item.product_id,
                slot_id=item.slot_id,
                amount=item.amount,
                expired_at=item.expired_at,
            )
            session.add(slot_stock)
            session.flush()

        db_detail = models.TransactionDetail(
            transaction_id=db_transaction.transaction_id,
            product_id=item.product_id,
            slot_stock_id=slot_stock.slot_stock_id,
            slot_id=item.slot_id,
            amount=item.amount,
        )
        session.add(db_detail)
        session.flush()

        response_details.append(
            {
                "transaction_detail_id": db_detail.transaction_detail_id,
                "slot_stock_id": slot_stock.slot_stock_id,
                "product_id": item.product_id,
                "slot_id": item.slot_id,
                "amount": item.amount,
                "lot_id": slot_stock.lot_id,
                "expired_at": slot_stock.expired_at,
            }
        )

    session.commit()
    
    # Sync กับ Server ใน Background
    background_tasks.add_task(sync_transaction_to_server, db_transaction.transaction_id)

    return {
        "transaction_id": db_transaction.transaction_id,
        "activity": db_transaction.activity,
        "status": db_transaction.status,
        "processed_items": len(response_details),
        "details": response_details,
    }

@router.post("/transactions/{transaction_id}/complete-sync")
def complete_transaction_sync(transaction_id: int, background_tasks: BackgroundTasks):
    """สั่งให้ Sync ขึ้น Cloud Server ครั้งเดียวตอนจบรายการ"""
    background_tasks.add_task(sync_transaction_to_server, transaction_id)
    return {"status": "sync_triggered"}

# ==========================================
# 4. Endpoints สำหรับ Manual Sync (Trigger)
# ==========================================

@router.post("/sync/manual-products")
def trigger_manual_product_sync():
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


@router.post("/sync/manual-transactions")
def trigger_manual_transaction_sync(session: Session = Depends(get_session)):
    """
    Sync รายการที่ยังไม่ได้ sync (synced_at = NULL) ทั้งหมดขึ้น Cloud Server
    ใช้สำหรับกรณีที่ offline แล้วกลับมา online ใหม่
    """
    # ค้นหา Transaction ที่ยังไม่ได้ sync
    pending_transactions = session.exec(
        select(models.Transaction)
        .where(models.Transaction.synced_at.is_(None))
        .order_by(models.Transaction.created_at)
    ).all()
    
    if not pending_transactions:
        return {
            "status": "success",
            "message": "No pending transactions to sync",
            "synced_count": 0
        }
    
    results = []
    success_count = 0
    error_count = 0
    
    for transaction in pending_transactions:
        result = sync_transaction_to_server(transaction.transaction_id, max_retries=1)
        results.append({
            "transaction_id": transaction.transaction_id,
            "status": result.get("status"),
            "message": result.get("message", "")
        })
        
        if result.get("status") == "success":
            success_count += 1
        else:
            error_count += 1
    
    return {
        "status": "completed",
        "total_pending": len(pending_transactions),
        "synced_count": success_count,
        "error_count": error_count,
        "details": results
    }

@router.get("/transactions/{transaction_id}", response_model=schema.TransactionPublic)
def get_transaction(transaction_id: int, session: Session = Depends(get_session)):
    """ดึงข้อมูล Transaction (ใช้เพื่อให้ Camera Agent มาเช็ค server_transaction_id)"""
    transaction = session.get(models.Transaction, transaction_id)
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return transaction