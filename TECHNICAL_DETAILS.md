# 🔗 Technical Details: Cross-Database Architecture

คำอธิบายรายละเอียดเกี่ยวกับการออกแบบใหม่หลังจากย้ายตาราง Slot

---

## 📐 Architecture Overview

### Before (ปัญหา)
```
product_management.db
├── product
├── slot          ← ตัวแม่ (Master)
├── slot_stock    ← references slot
└── transaction*

device.db
└── device_info
```

### After (แก้ไข ✅)
```
device.db
├── device_info
└── slot          ← ตัวแม่ (Master) ✨ ย้ายไปแล้ว

product_management.db
├── product
├── slot_stock    ← references slot (via slot_id)
└── transaction*
```

---

## 🔑 Foreign Key Relationship

### SlotStock Model ยังคง Reference Slot

```python
# product_management_service/database/models.py
class SlotStock(SlotStockBase, table=True):
    slot_id: int = Field(
        foreign_key="slot.slot_id",  # ❓ เหลือเป็น FK อย่างไร?
        index=True
    )
    
    # ❌ ลบแล้ว: slot: Optional[Slot] = Relationship(...)
```

### ปัญหา FK
- `foreign_key="slot.slot_id"` assumes ตารางอยู่ในฐานข้อมูลเดียวกัน
- แต่ `slot` ตอนนี้อยู่ใน `device.db`
- SQLAlchemy ไม่สามารถ enforce FK across databases ได้

---

## 💡 Solutions

### Solution 1: Remove FK Constraint (ปัจจุบัน ✓)
```python
# product_management_service/database/models.py
slot_id: int = Field(
    # ❌ ลบ: foreign_key="slot.slot_id",
    index=True,  # ✅ เก็บ index สำหรับ query
    description="ID ของช่องที่เก็บสต็อกนี้"
)
```

**ข้อดี:**
- ✅ ตรงไปตรงมา
- ✅ ค่าใช้จ่ายต่ำ
- ✅ Flexible

**ข้อเสีย:**
- ❌ ไม่มี DB-level constraint
- ❌ ต้อง validate ใน application layer

**แนะนำใช้**: Application-level validation
```python
@router.post("/transactions/{transaction_id}/details")
def add_transaction_detail(detail: TransactionDetailCreate, session: Session):
    # Query device_identity_service เพื่อตรวจสอบ slot_id มีหรือไม่
    slot_exists = check_slot_exists(detail.slot_id)
    if not slot_exists:
        raise HTTPException(status_code=404, detail="Slot not found")
    # ... continue
```

---

### Solution 2: SQLAlchemy Relationship (Advanced ⚠️)
```python
# product_management_service/database/models.py
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship

class SlotStock(SlotStockBase, table=True):
    slot_id: int = Field(
        ForeignKey("slot.slot_id", link_to_remote=True),
        # ⚠️ ต้อง configure connection string
    )
    slot: Optional["Slot"] = Relationship(
        foreign_key="SlotStock.slot_id"
    )
```

**ข้อดี:**
- ✅ ORM สมบูรณ์
- ✅ Lazy loading

**ข้อเสีย:**
- ❌ ยุ่มเหยิง
- ❌ ต้องตั้งค่า multi-database สำหรับ SQLAlchemy
- ❌ Performance overhead

**ไม่แนะนำ**: เนื่องจากความซับซ้อน

---

### Solution 3: Read-Only Relationship (Hybrid ⭐)
```python
# device_identity_service/database/models.py
class Slot(SlotBase, table=True):
    slot_stocks: List["SlotStock"] = Relationship(
        back_populates="slot"
    )

# product_management_service/database/models.py
class SlotStock(SlotStockBase, table=True):
    # ❌ ไม่มี Relationship เชื่อมไปหา Slot
    # ✅ แต่มี method helper
    
    def get_slot(self, device_session) -> Optional[dict]:
        """
        ดึง slot data จาก device_identity_service
        """
        # Pseudo code
        response = requests.get(
            f"{DEVICE_SERVICE_URL}/device/internal/slots/{self.slot_id}",
            headers={"X-Internal-Secret": INTERNAL_SHARED_SECRET}
        )
        return response.json() if response.ok else None
```

**ข้อดี:**
- ✅ Clean architecture
- ✅ API-driven (loosely coupled)
- ✅ ง่ายจะเข้าใจ

**ข้อเสีย:**
- ⚠️ ต้อง API call แต่ละครั้ง
- ⚠️ Network latency

**ใช้เมื่อ**: ต้องการ real-time data

---

## 🗂️ Current Implementation (ปัจจุบัน)

ขณะนี้ใช้ **Solution 1** (Remove FK Constraint):

```
product_management.db
└── slot_stock[slot_id] → Query device.db/slot.slot_id
                          via API (product_management_service/api.py)

device.db
└── slot[slot_id] ← Referenced by slot_stock
```

### Data Access Pattern
```python
# product_management_service/api.py
@router.get("/slots")
def get_slots_with_stock():
    # 1. Get slots from device_identity_service
    response = requests.get(
        f"{DEVICE_SERVICE_URL}/device/internal/slots",
        headers={"X-Internal-Secret": SECRET}
    )
    slots = response.json()
    
    # 2. For each slot, get slot_stocks from product_management.db
    for slot in slots:
        stocks = session.exec(
            select(SlotStock).where(SlotStock.slot_id == slot["slot_id"])
        ).all()
        # ... build response
    
    return result
```

---

## 🔐 Integrity Guarantees

### ระดับ Database
```
❌ No FK constraint (cross-database ไม่ได้)
```

### ระดับ Application
```python
# product_management_service/api.py - Application-level validation

def validate_slot_exists(slot_id: int) -> bool:
    """Check if slot exists before creating/updating slot_stock"""
    try:
        headers = {"X-Internal-Secret": INTERNAL_SHARED_SECRET}
        response = requests.get(
            f"{DEVICE_SERVICE_URL}/device/internal/slots",
            headers=headers,
            timeout=5
        )
        if response.status_code == 200:
            slots = response.json()
            return any(s["slot_id"] == slot_id for s in slots)
    except:
        # Fallback: ถ้าไม่สามารถเชื่อมต่อ allow insertion
        # (Offline-first architecture)
        pass
    return False

@router.post("/slot-stocks")
def create_slot_stock(stock: SlotStockCreate, session: Session):
    if not validate_slot_exists(stock.slot_id):
        raise HTTPException(
            status_code=404,
            detail=f"Slot {stock.slot_id} not found"
        )
    # ... create
```

---

## 📊 Data Consistency

### ปัญหา: Orphaned Records
```sql
-- ถ้ามี slot_stock ที่ reference slot ที่ไม่มี
SELECT ss.* FROM product_management.db:slot_stock ss
LEFT JOIN device.db:slot s ON ss.slot_id = s.slot_id
WHERE s.slot_id IS NULL;
```

### วิธีแก้:
```python
# Periodic validation script
import requests

def validate_slot_stock_integrity():
    """Check for orphaned slot_stock records"""
    pm_session = get_pm_db_session()
    
    # Get all slot_ids that exist
    valid_slots = fetch_all_slots_from_device_service()
    valid_slot_ids = {s["slot_id"] for s in valid_slots}
    
    # Find orphaned records
    stocks = pm_session.exec(select(SlotStock)).all()
    orphaned = [s for s in stocks if s.slot_id not in valid_slot_ids]
    
    if orphaned:
        print(f"⚠️  Found {len(orphaned)} orphaned slot_stock records")
        # Log / Alert / Fix
        # Option 1: Delete orphaned records
        # Option 2: Softdelete (mark as deleted_at)
        # Option 3: Alert and wait for manual review
```

---

## 🚀 Performance Considerations

### Query Paths
```
FastAPI Endpoint Request
    ↓
product_management_service.api.py (GET /slots)
    ├→ Call device_identity_service.api.py (GET /internal/slots)
    │   └→ device.db [slot table] ✅ Fast (local)
    │
    └→ Query product_management.db [slot_stock] ✅ Fast (local)
    
Response Assembly
    └→ Return combined JSON ✅
```

### Optimization Tips
```python
# ✅ Good: Batch request
def get_slots_with_stock():
    # 1 API call to device service
    slots = get_all_slots_from_device()
    
    # Batch query
    slot_ids = {s["slot_id"] for s in slots}
    stocks = session.exec(
        select(SlotStock)
        .where(SlotStock.slot_id.in_(slot_ids))  # ← IN clause (efficient)
    ).all()

# ❌ Bad: N+1 query problem
for slot in slots:
    stocks = session.exec(  # ← Called per slot (slow!)
        select(SlotStock).where(SlotStock.slot_id == slot["slot_id"])
    ).all()
```

---

## 🔄 Sync Strategy

### Option 1: Pull (ปัจจุบัน)
```
Read Request
    → product_management calls device_identity
    → Get fresh data
    ✅ Always up-to-date
    ❌ Depends on network
```

### Option 2: Push (Webhook)
```
Slot Create/Update
    → device_identity triggers webhook
    → product_management receives update
    ✅ Efficient
    ❌ Complex
```

### Option 3: Eventual Consistency
```
Cached data + background sync
    ✅ Fast
    ⚠️  Stale data possible
```

---

## ✅ Implementation Checklist

- [ ] ✅ Slot model moved to device_identity_service
- [ ] ✅ API endpoint `/device/internal/slots` created
- [ ] ✅ INTERNAL_SHARED_SECRET configured
- [ ] ✅ product_management.api calls device_identity endpoint
- [ ] [ ] Application-level FK validation (optional)
- [ ] [ ] Periodic integrity check job (optional)
- [ ] [ ] Caching strategy (optional, for performance)
- [ ] [ ] Error handling for offline scenarios

---

## 📚 See Also

- [MIGRATION_GUIDE.md](./MIGRATION_GUIDE.md) - How to migrate existing data
- [DATA_MIGRATION_OPTIONS.md](./DATA_MIGRATION_OPTIONS.md) - Different migration approaches
- [docker-compose.yml](./docker-compose.yml) - Service configuration
