import sqlite3
import os

DB_FILE = 'device_identity.db'

SQL_CREATE_TABLE = """
--- 1. ตาราง lockers ---
CREATE TABLE IF NOT EXISTS lockers (
    id TEXT PRIMARY KEY NOT NULL,
    group_location_id INTEGER NOT NULL,
    location_id INTEGER NOT NULL,
    group_location_name TEXT NOT NULL,
    location_name TEXT NOT NULL,
    locker_department TEXT,
    latitude REAL,
    longitude REAL,
    created_at TEXT NOT NULL DEFAULT (STRFTIME('%Y-%m-%d %H:%M:%f', 'NOW')),
    updated_at TEXT NOT NULL DEFAULT (STRFTIME('%Y-%m-%d %H:%M:%f', 'NOW')),
    deleted_at TEXT
);

CREATE TRIGGER IF NOT EXISTS update_lockers_updated_at
AFTER UPDATE ON lockers
FOR EACH ROW
BEGIN
    UPDATE lockers SET updated_at = STRFTIME('%Y-%m-%d %H:%M:%f', 'NOW') WHERE id = NEW.id;
END;

--- 2. ตาราง slots ---
CREATE TABLE IF NOT EXISTS slots (
    slot_number INTEGER PRIMARY KEY AUTOINCREMENT,
    slot_id INTEGER UNIQUE NOT NULL,
    locker_id TEXT NOT NULL,
    slot_status TEXT NOT NULL DEFAULT 'available',
    capacity INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (STRFTIME('%Y-%m-%d %H:%M:%f', 'NOW')),
    updated_at TEXT NOT NULL DEFAULT (STRFTIME('%Y-%m-%d %H:%M:%f', 'NOW')),
    deleted_at TEXT,
    FOREIGN KEY (locker_id) REFERENCES lockers(id)
);

CREATE TRIGGER IF NOT EXISTS update_slots_updated_at
AFTER UPDATE ON slots
FOR EACH ROW
BEGIN
    UPDATE slots SET updated_at = STRFTIME('%Y-%m-%d %H:%M:%f', 'NOW') WHERE slot_number = NEW.slot_number;
END;
"""

def init_db():
    conn = None
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.executescript(SQL_CREATE_TABLE)
        conn.commit()
        print(f"[/] Database '{DB_FILE}' created and schema initialized successfully.")
    except sqlite3.Error as e:
        print(f"[X] An error occurred during DB initialization: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    if not os.path.exists(DB_FILE):
        init_db()
    else:
        os.remove(DB_FILE)
        print(f"Removed existing '{DB_FILE}'.")
        init_db()