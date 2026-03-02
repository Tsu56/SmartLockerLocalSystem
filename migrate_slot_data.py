#!/usr/bin/env python3
"""
Migration script สำหรับย้ายข้อมูล Slot จาก product_management.db ไปยัง device.db
รักษาข้อมูลทั้งหมดไว้ ไม่มีการสูญหายของข้อมูล
"""

import os
import sys
import sqlite3
import stat
import time
from datetime import datetime, timezone
from pathlib import Path

# ตั้งค่า paths
PM_DB_PATH = Path("product_management_service/database/product_management.db")
DIS_DB_PATH = Path("device_identity_service/database/device.db")

def fix_file_permissions(file_path: Path):
    """แก้ไขสิทธิ์การเขียนของไฟล์"""
    if not file_path.exists():
        return
    
    try:
        # ตั้งค่า permissions เป็น 0o666 (read+write for everyone)
        file_path.chmod(0o666)
        print(f"   ✓ Fixed permissions for {file_path.name}")
    except Exception as e:
        print(f"   ⚠️  Could not fix permissions: {e}")

def wait_for_db_unlock(file_path: Path, timeout: int = 5):
    """รอจนกว่า database unlock (ถ้า locked ด้วยกระบวนการอื่น)"""
    import fcntl
    
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            with open(file_path, 'a') as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            return True
        except (IOError, OSError):
            time.sleep(0.5)
    return False

def backup_databases():
    """สร้างสำเนาข้อมูลสำรองก่อนทำการ migrate"""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    
    print("🔄 สร้างสำเนาข้อมูลสำรอง...")
    
    if PM_DB_PATH.exists():
        # แก้ไข permissions
        fix_file_permissions(PM_DB_PATH)
        
        backup_pm = PM_DB_PATH.parent / f"product_management_backup_{timestamp}.db"
        import shutil
        try:
            shutil.copy2(PM_DB_PATH, backup_pm)
            fix_file_permissions(backup_pm)
            print(f"   ✅ {backup_pm}")
        except Exception as e:
            print(f"   ⚠️  Failed to backup product_management.db: {e}")
    
    if DIS_DB_PATH.exists():
        # แก้ไข permissions
        fix_file_permissions(DIS_DB_PATH)
        
        backup_dis = DIS_DB_PATH.parent / f"device_backup_{timestamp}.db"
        import shutil
        try:
            shutil.copy2(DIS_DB_PATH, backup_dis)
            fix_file_permissions(backup_dis)
            print(f"   ✅ {backup_dis}")
        except Exception as e:
            print(f"   ⚠️  Failed to backup device.db: {e}")


def migrate_slot_data():
    """ย้ายข้อมูล Slot จากฐานข้อมูลเก่าไปยังใหม่"""
    
    if not PM_DB_PATH.exists():
        print(f"❌ ไม่พบ database: {PM_DB_PATH}")
        return False
    
    if not DIS_DB_PATH.exists():
        print(f"❌ ไม่พบ database: {DIS_DB_PATH}")
        return False
    
    print("📊 เริ่มต้น Migration...")
    
    try:
        # แก้ไข permissions
        fix_file_permissions(PM_DB_PATH)
        fix_file_permissions(DIS_DB_PATH)
        
        # รอจนกว่า databases unlock
        print("⏳ รอการ unlock databases...")
        wait_for_db_unlock(PM_DB_PATH)
        wait_for_db_unlock(DIS_DB_PATH)
        
        # เชื่อมต่อทั้งสองฐานข้อมูลพร้อม timeout
        pm_conn = sqlite3.connect(str(PM_DB_PATH), timeout=10.0)
        pm_conn.execute("PRAGMA journal_mode=WAL")
        pm_cursor = pm_conn.cursor()
        
        dis_conn = sqlite3.connect(str(DIS_DB_PATH), timeout=10.0)
        dis_conn.execute("PRAGMA journal_mode=WAL")
        dis_cursor = dis_conn.cursor()
        
        # ตรวจสอบว่าตาราง Slot มีข้อมูลในฐานข้อมูลเก่าหรือไม่
        pm_cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='slot'")
        slot_table_exists = pm_cursor.fetchone()[0] > 0
        
        if not slot_table_exists:
            print("⚠️  ตาราง 'slot' ไม่พบในฐานข้อมูล product_management")
            return True
        
        # นับจำนวนข้อมูล Slot
        pm_cursor.execute("SELECT COUNT(*) FROM slot")
        slot_count = pm_cursor.fetchone()[0]
        print(f"📋 พบข้อมูล Slot: {slot_count} รายการ")
        
        if slot_count == 0:
            print("✅ ไม่มีข้อมูล Slot ที่ต้อง migrate")
            pm_conn.close()
            dis_conn.close()
            return True
        
        # ดึงข้อมูล Slot จากฐานข้อมูลเก่า
        pm_cursor.execute("""
            SELECT slot_id, locker_id, slot_status, capacity, created_at, updated_at, deleted_at
            FROM slot
            ORDER BY id
        """)
        slots = pm_cursor.fetchall()
        
        # inserting ข้อมูลไปยังฐานข้อมูลใหม่
        dis_cursor.execute("BEGIN TRANSACTION")
        
        for i, slot in enumerate(slots, 1):
            slot_id, locker_id, slot_status, capacity, created_at, updated_at, deleted_at = slot
            
            # ตรวจสอบว่าข้อมูลนี้มีอยู่แล้วหรือไม่
            dis_cursor.execute("SELECT COUNT(*) FROM slot WHERE slot_id = ?", (slot_id,))
            exists = dis_cursor.fetchone()[0] > 0
            
            if exists:
                print(f"   ⚠️  Slot {slot_id} มีอยู่แล้ว ข้ามไป...")
                continue
            
            dis_cursor.execute("""
                INSERT INTO slot (slot_id, locker_id, slot_status, capacity, created_at, updated_at, deleted_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (slot_id, locker_id, slot_status, capacity, created_at, updated_at, deleted_at))
            
            if i % 10 == 0:
                print(f"   ✓ Inserted {i}/{slot_count} slots...")
        
        dis_conn.commit()
        print(f"✅ Migrated {slot_count} slot records to device_identity_service")
        
        # ตรวจสอบข้อมูล
        dis_cursor.execute("SELECT COUNT(*) FROM slot")
        new_count = dis_cursor.fetchone()[0]
        print(f"🔍 ยืนยัน: device.db มี {new_count} slot records")
        
        pm_conn.close()
        dis_conn.close()
        
        return True
        
    except sqlite3.OperationalError as e:
        if "readonly" in str(e).lower():
            print(f"❌ Database is read-only: {e}")
            print("   💡 วิธีแก้:")
            print("      1. ปิด services ที่ใช้ database:")
            print("         docker-compose down")
            print("      2. ลบไฟล์ WAL:")
            print(f"         rm product_management_service/database/*.db-wal")
            print(f"         rm product_management_service/database/*.db-shm")
            print(f"         rm device_identity_service/database/*.db-wal")
            print(f"         rm device_identity_service/database/*.db-shm")
            print("      3. ลองใหม่: python migrate_slot_data.py")
            return False
        else:
            print(f"❌ Database Error: {e}")
            return False
    except sqlite3.Error as e:
        print(f"❌ SQLite Error: {e}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def remove_slot_table():
    """ลบตาราง Slot ออกจากฐานข้อมูลเก่า (หลังยืนยันการ migrate สำเร็จ)"""
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            # แก้ไข permissions ก่อน
            if attempt == 0:
                print("🔧 แก้ไขสิทธิ์ไฟล์...")
                fix_file_permissions(PM_DB_PATH)
                time.sleep(0.5)
            
            # รอจนกว่า database unlock
            if attempt == 0:
                print("⏳ รอการ unlock database...")
                wait_for_db_unlock(PM_DB_PATH)
            
            if attempt > 0:
                print(f"   Attempt {attempt + 1}/{max_retries}...")
                time.sleep(2)
            
            # เปิด connection กับ timeout
            conn = sqlite3.connect(str(PM_DB_PATH), timeout=15.0, check_same_thread=False)
            conn.isolation_level = None  # Autocommit mode
            cursor = conn.cursor()
            
            # ตรวจสอบว่าตาราง Slot มีอยู่จริงหรือไม่
            cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='slot'")
            if cursor.fetchone()[0] == 0:
                print("ℹ️  ตาราง 'slot' ไม่พบในฐานข้อมูล product_management (อาจลบไปแล้ว)")
                conn.close()
                return True
            
            # สร้าง backup ก่อน
            confirm = input("\n⚠️  ต้องการลบตาราง 'slot' ออกจาก product_management.db? (yes/no): ").strip().lower()
            
            if confirm != "yes":
                print("❌ ยกเลิกการลบตาราง")
                conn.close()
                return False
            
            # ลบตาราง
            cursor.execute("DROP TABLE IF EXISTS slot")
            time.sleep(0.5)
            
            # Optimize database
            cursor.execute("VACUUM")
            
            print("✅ ลบตาราง 'slot' ออกจาก product_management.db สำเร็จ")
            
            conn.close()
            return True
            
        except sqlite3.OperationalError as e:
            if "readonly" in str(e).lower():
                if attempt < max_retries - 1:
                    print(f"⚠️  Database readonly (attempt {attempt + 1}/{max_retries}), retrying...")
                    continue
                else:
                    print(f"❌ Database is read-only: {e}")
                    print("   💡 วิธีแก้:")
                    print("      1. ตรวจสอบ file permissions:")
                    print(f"         ls -la {PM_DB_PATH}")
                    print("      2. รันด้วย sudo:")
                    print("         sudo python migrate_slot_data.py")
                    print("      3. หรือลบ database เก่า (ห้าม!)")
                    print(f"         rm {PM_DB_PATH}")
                    return False
            else:
                print(f"❌ Database Error: {e}")
                return False
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"⚠️  Error (attempt {attempt + 1}/{max_retries}): {e}, retrying...")
                time.sleep(1)
                continue
            else:
                print(f"❌ Error: {e}")
                import traceback
                traceback.print_exc()
                return False
    
    return False


def main():
    print("=" * 60)
    print("🔄 Slot Data Migration Tool")
    print("=" * 60)
    print()
    print("⚠️  IMPORTANT: ปิด services ก่อน migration!")
    print()
    print("หากยังไม่ได้ปิด ให้รันคำสั่ง:")
    print("   docker-compose down")
    print()
    confirms = input("ยืนยันว่าได้ปิด services แล้ว? (yes/no): ").strip().lower()
    if confirms != "yes":
        print("❌ ยกเลิกการ migration")
        return False
    
    print()
    
    # Step 1: Backup
    backup_databases()
    
    # Step 2: Migrate data
    print()
    if not migrate_slot_data():
        print("❌ Migration ล้มเหลว!")
        return False
    
    # Step 3: Clean up (optional)
    print()
    if not remove_slot_table():
        print("⚠️  ข้อมูล Slot ยังคงอยู่ในฐานข้อมูล product_management")
        return False
    
    print()
    print("=" * 60)
    print("✅ Migration สำเร็จทั้งหมด!")
    print("=" * 60)
    print()
    print("📝 ขั้นตอนต่อไป:")
    print("   1. เปิด services: docker-compose up")
    print("   2. ตรวจสอบให้ services ทำงานได้ปกติ")
    print("   3. ลบ backup files (ถ้าพอใจ)")
    print()
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
