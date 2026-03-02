# 🔄 Database Migration Guide - Slot Table Transfer

คำแนะนำสำหรับย้ายข้อมูล Slot จาก `product_management_service` ไปยัง `device_identity_service` โดยไม่สูญเสียข้อมูล

## 📋 ข้อมูลที่ย้าย

- **ตาราง**: `slot`
- **จาก**: `product_management_service/database/product_management.db`
- **ไป**: `device_identity_service/database/device.db`

## ⚙️ วิธีดำเนินการ

### ขั้นตอนที่ 1: ตรวจสอบสถานะปัจจุบัน

```bash
# ตรวจสอบจำนวนข้อมูล Slot ปัจจุบัน
sqlite3 product_management_service/database/product_management.db "SELECT COUNT(*) FROM slot;"
```

### ขั้นตอนที่ 2: รันสคริปต์ Migration

```bash
# เปิด terminal และไปยังโฟลเดอร์ root
cd /home/tphu/Desktop/SmartLocker

# รัน migration script
python migrate_slot_data.py
```

### ขั้นตอนที่ 3: ตรวจสอบการ Migrate

```bash
# ตรวจสอบว่าข้อมูล Slot ถูกย้ายไปแล้ว
sqlite3 device_identity_service/database/device.db "SELECT COUNT(*) FROM slot;"

# ตรวจสอบว่าตาราง Slot ถูกลบออกจากฐานข้อมูลเก่า
sqlite3 product_management_service/database/product_management.db ".tables"
```

## 🛡️ ความปลอดภัย

Script นี้ทำให้:
1. ✅ **สร้างสำเนาข้อมูลสำรอง** ก่อน migration
   - `product_management_backup_YYYYMMDD_HHMMSS.db`
   - `device_backup_YYYYMMDD_HHMMSS.db`

2. ✅ **ยืนยันข้อมูล** ก่อนลบตาราง

3. ✅ **ข้ามข้อมูลซ้ำ** หากมี duplicate

4. ✅ **รักษาข้อมูล** ทั้งหมด ไม่มีการลบโดยไม่ตั้งใจ

## 📊 ข้อมูลที่ย้าย

| ฟิลด์ | ประเภท | หมายเหตุ |
|------|---------|---------|
| `slot_id` | INTEGER | Primary Key จาก Server |
| `locker_id` | INTEGER | ID ของตู้ |
| `slot_status` | TEXT | สถานะช่อง (active, maintenance) |
| `capacity` | INTEGER | ความจุของช่อง |
| `created_at` | DATETIME | เวลาสร้าง |
| `updated_at` | DATETIME | เวลาอัปเดตล่าสุด |
| `deleted_at` | DATETIME | เวลาลบ (soft delete) |

## ⚠️ หากเกิดข้อผิดพลาด

### ก้อมลความผิดพลาด
```bash
# ดูเนื้อหาของ slot table
sqlite3 product_management_service/database/product_management.db "SELECT * FROM slot LIMIT 10;"

sqlite3 device_identity_service/database/device.db "SELECT * FROM slot LIMIT 10;"
```

### Restore จาก Backup
```bash
# หากต้องการคืนค่าจาก backup
cp product_management_service/database/product_management_backup_*.db \
   product_management_service/database/product_management.db

cp device_identity_service/database/device_backup_*.db \
   device_identity_service/database/device.db
```

## 🔄 ตัวเลือกเพิ่มเติม

### เฉพาะ Dry Run (ไม่ทำการ commit)
```python
# แก้ไข migrate_slot_data.py บรรทัด 110
# เปลี่ยนจาก: dis_conn.commit()
# เป็น: # dis_conn.commit()  # Commented out for dry run
```

### ลบตาราง Slot โดยอัตโนมัติ
```bash
# แก้ไข migrate_slot_data.py บรรทัด 166
# เปลี่ยนจาก: confirm = input(...)
# เป็น: confirm = "yes"
```

## ✅ หลังจาก Migration

1. **ยืนยันความม้ค่าของ API**
   ```bash
   curl -X GET http://localhost:5003/locker/slots \
     -H "X-Internal-Secret: YOUR_SECRET"
   ```

2. **ทดสอบการเชื่อมต่อ Service**
   - product_management_service สามารถเรียก device_identity_service ได้
   - SlotStock ยังคง reference ไปยัง Slot ได้ (ผ่าน slot_id)

3. **เก็บ Backups**
   - รักษา `*_backup_*.db` ไว้สำหรับ recovery

## 📝 บันทึกการ Migrate

```
วันที่/เวลา: [timestamp]
จำนวนข้อมูล: [count]
สถานะ: SUCCESS/FAILED
Backup files: [list]
```

---

**หมายเหตุ**: หากต้องการย้อนกลับ สามารถ restore จาก backup files ได้ตลอดเวลา
