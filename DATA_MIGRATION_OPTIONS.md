# Database Migration: เก็บข้อมูลเดิมไว้ 💾

สำหรับกรณีที่คุณศูนย์ประชากรข้าว Slot ที่มีอยู่แล้วใน database ไม่ให้หายไป

## 🎯 สถานการณ์ต่างๆ

### สถานการณ์ 1: ยังไม่มีข้อมูล Slot ในระบบ (เริ่มต้นใหม่)

```
✅ ง่ายที่สุด - ไม่ต้องทำ migration
- ลบฐานข้อมูล product_management.db
- ลบฐานข้อมูล device.db
- เรียก app.py ใหม่ → สร้างตารางใหม่
- ข้อมูล Slot จะอยู่ใน device.db
```

### สถานการณ์ 2: มีข้อมูล Slot ในระบบแล้ว (ปัจจุบัน)

```
⚠️  ต้องใช้ Migration Script
- ใช้ migrate_slot_data.py
- ข้อมูล Slot ถูกย้ายจาก product_management.db → device.db
- เก็บ backup ไว้เสมอ
- ลบตาราง Slot จากฐานข้อมูลเก่า (optional)
```

### สถานการณ์ 3: บางช่องมีข้อมูล บางช่องไม่มี

```
📋 ใช้ Migration Script + Manual Sync
- migration script ย้ายv้อมูลที่มีอยู่
- SlotStock จะ reference slot_id ต่อไปได้
- ข้อมูลใหม่จะเก็บไว้ใน device.db
```

---

## 🚀 ทำไมต้อง Migrate?

### ปัญหาหลัก:
1. **ตาราง Slot อยู่ใน 2 ที่**: 
   - database: `product_management.db` (เก่า)
   - database: `device.db` (ใหม่)

2. **ประกาย Relationship**:
   - SlotStock ยังคง reference `slot.slot_id`
   - ต้องมี Slot data ที่สามารถเข้าถึงได้

3. **Inconsistency**:
   - ข้อมูล Slot เก่าอยู่คนละที่กับเก่า

### วิธีแก้:
✅ Migrate ข้อมูล Slot ทั้งหมด → device.db
✅ ลบตาราง Slot เก่า (ลบตามต้องการ)
✅ SlotStock query ผ่าน FK ไป device.db

---

## 📊 Migration Options

### Option A: ใช้ Script (แนะนำ ⭐⭐⭐⭐⭐)

```bash
python migrate_slot_data.py
```

**ข้อดี:**
- ✅ Safe - สร้าง backup อัตโนมัติ
- ✅ Verify - ตรวจสอบข้อมูล
- ✅ Rollback - สามารถย้อนกลับได้
- ✅ Fast - เร็วและเชื่อถือได้

**ขั้นตอน:**
1. Backup databases
2. Read Slot data from product_management.db
3. Insert into device.db
4. Verify count matches
5. Delete table from product_management.db (Ask confirmation)

---

### Option B: Manual SQL

```sql
-- 1. Insert ข้อมูล
INSERT INTO device.db:slot
SELECT slot_id, locker_id, slot_status, capacity, 
       created_at, updated_at, deleted_at
FROM product_management.db:slot

-- 2. Verify
SELECT COUNT(*) FROM slot;

-- 3. Delete old table
DROP TABLE product_management.db:slot
```

**ข้อดี:**
- ✅ Control เต็ม (ได้ดูค่า SQL)
- ✅ Debug ได้ง่าย

**ข้อเสีย:**
- ❌ Hand-written SQL error-prone
- ❌ ต้อง backup เอง
- ❌ ต้อง verify เอง

**วิธีทำ:**
```bash
# Export schema from product_management.db
sqlite3 product_management_service/database/product_management.db \
  ".schema slot" > /tmp/slot_schema.sql

# ดูว่าฟิลด์มีอะไรบ้าง
cat /tmp/slot_schema.sql

# Insert data (attach databases in SQLite)
sqlite3 <<EOF
ATTACH DATABASE 'product_management_service/database/product_management.db' AS pm;
ATTACH DATABASE 'device_identity_service/database/device.db' AS dis;

INSERT INTO dis.slot 
SELECT * FROM pm.slot;

SELECT COUNT(*) FROM dis.slot;
EOF
```

---

### Option C: Restart Fresh (ง่ายสุด แต่สูญเสียข้อมูล ❌)

```bash
# ⚠️ เตือน: ข้อมูลทั้งหมดจะหายไป!
rm product_management_service/database/product_management.db
rm device_identity_service/database/device.db

# เรียก service → สร้างตาราง Slot ใหม่ใน device.db
python -c "from device_identity_service.database import create_db_and_tables; create_db_and_tables()"
```

**ข้อดี:**
- ✅ ตรงไปตรงมา

**ข้อเสีย:**
- ❌ ข้อมูลเก่าหายไป
- ❌ ต้องมีข้อมูลสำรองที่อื่น

---

## 📝 Check List

- [ ] ตรวจสอบจำนวนข้อมูล Slot เดิม
  ```bash
  sqlite3 product_management_service/database/product_management.db \
    "SELECT COUNT(*) FROM slot;"
  ```

- [ ] เลือกวิธี migration (แนะนำ: Option A)

- [ ] Backup databases
  ```bash
  cp product_management_service/database/product_management.db \
     product_management_service/database/product_management.db.backup
  ```

- [ ] รัน migration

- [ ] ตรวจสอบข้อมูลหลังจาก migration
  ```bash
  sqlite3 device_identity_service/database/device.db \
    "SELECT COUNT(*) FROM slot;"
  ```

- [ ] ทดสอบ API
  ```bash
  curl -X GET http://localhost:5003/locker/slots
  ```

- [ ] ลบ backup files (ถ้าพอใจ)

---

## 🔧 Advanced: Custom Migration

หากต้องการ "selective migration" (ย้ายเฉพาะบางส่วน):

```python
# แก้ไข migrate_slot_data.py
# บรรทัด 70
# FROM
pm_cursor.execute("SELECT ... FROM slot ORDER BY id")

# TO (เฉพาะ active slots)
pm_cursor.execute("""
    SELECT ... FROM slot 
    WHERE slot_status = 'active' AND deleted_at IS NULL
    ORDER BY id
""")
```

---

## ✅ Verification

หลังจาก migration ให้ตรวจสอบ:

```bash
# 1. นับข้อมูล
sqlite3 device_identity_service/database/device.db "SELECT COUNT(*) FROM slot;"

# 2. ตรวจสอบ data integrity
sqlite3 device_identity_service/database/device.db \
  "SELECT slot_id, locker_id, slot_status FROM slot LIMIT 5;"

# 3. Verify SlotStock relationships
sqlite3 product_management_service/database/product_management.db \
  "SELECT COUNT(*) FROM slot_stock WHERE slot_id = 1;"
```

---

## 🚨 Recovery (ถ้าหากมีปัญหา)

```bash
# Restore from backup
cp product_management_service/database/product_management_backup_*.db \
   product_management_service/database/product_management.db

# Restart services
docker-compose restart product-management-service device-identity-service
```

---

**สรุป:** ใช้ `python migrate_slot_data.py` มันเป็นวิธีที่ปลอดภัย เร็ว และน่าเชื่อถือที่สุด! 🎯
