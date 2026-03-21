from dotenv import load_dotenv
import httpx, os, threading, time, requests, hashlib, json
from fastapi import APIRouter, BackgroundTasks, HTTPException, status, Header
from sqlmodel import select, delete, func, or_, update
from typing import List
from datetime import datetime, timezone
from passlib.context import CryptContext
import re

load_dotenv()

# นำเข้าส่วนประกอบจากโมดูล local_auth ที่เราสร้างไว้
from database import SessionDep, engine, Session
from database.models import User, UserPermission, AuthLog, ProcessedEvent
from database.schema import (
    UserCreate, UserPublic, UserLogin,
    SmartCardLogin, RFIDTagLogin, QRCodeLogin,
    AuthLogCreate, AuthLogPublic
)
from encryption import encrypt_data, decrypt_data
from getkey import get_internal_shared_secret, get_search_hash_salt, get_mqtt_config

try:
    import paho.mqtt.client as mqtt
except Exception:
    mqtt = None

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__truncate_error=True)

router = APIRouter(prefix="/auth", tags=["Local Authentication"])

CLOUD_SERVER_URL = os.getenv("SERVER_URL", "")

IDENTITY_SERVICE_URL = "http://device-identity-service:8000/device/internal/auth-headers"

INTERNAL_SECRET = get_internal_shared_secret()

# Salt ลับสำหรับการทำ Blind Index (ควรดึงจาก .env เพื่อความปลอดภัย)
SEARCH_HASH_SALT = get_search_hash_salt()
MQTT_ENABLED = os.getenv("MQTT_ENABLED", "false").strip().lower() == "true"
MQTT_BROKER_PORT = int(os.getenv("MQTT_BROKER_PORT", "8883"))
MQTT_KEEPALIVE = int(os.getenv("MQTT_KEEPALIVE_SECONDS", "60"))

def get_search_hash(data: str) -> str:
    """สร้างค่า Hash สำหรับใช้ค้นหา (Blind Index)"""
    if not data:
        return None
    combined = f"{str(data).strip()}{SEARCH_HASH_SALT}"
    return hashlib.sha256(combined.encode()).hexdigest()

def verify_password(plain_password, hashed_password):
    # ฟังก์ชันนี้จะดึง Salt ออกมาจาก hashed_password เองอัตโนมัติ 
    # แล้วคำนวณว่า plain_password ตรงกันหรือไม่
    return pwd_context.verify(plain_password, hashed_password)

# --- User Management ---

def user_sync_agent():
    """
    Agent ทำงานเบื้องหลัง คอยดึงข้อมูลผู้ใช้และสิทธิ์จาก Server มาอัปเดตลงตู้
    """
    print("🚀 User Sync Agent Started...")
    time.sleep(10)

    while True:
        try:
            # 1. ขอ Headers ยืนยันตัวตน
            auth_res = requests.get(
                IDENTITY_SERVICE_URL, 
                headers={"X-Internal-Secret": INTERNAL_SECRET},
                timeout=5
            )
            
            if auth_res.status_code == 200:
                cloud_headers = auth_res.json()
                
                with Session(engine) as session:
                    # 2. หาเวลาที่ Sync ล่าสุดจากทั้งตาราง User และ UserPermission
                    last_sync_time = "1970-01-01T00:00:00Z"
                    
                    # ค้นหาค่าวันเวลาที่ใหม่ที่สุดจาก User
                    u_max = session.exec(select(
                        func.max(User.created_at), 
                        func.max(User.updated_at), 
                        func.max(User.deleted_at)
                    )).first()
                    
                    # ค้นหาค่าวันเวลาที่ใหม่ที่สุดจาก UserPermission
                    p_max = session.exec(select(
                        func.max(UserPermission.created_at), 
                        func.max(UserPermission.updated_at), 
                        func.max(UserPermission.deleted_at)
                    )).first()
                    
                    # รวม Timestamps ทั้งหมดเพื่อหาจุดที่ใหม่ที่สุดจริง ๆ
                    all_ts = [_parse_utc(ts) for ts in list(u_max or []) + list(p_max or []) if ts is not None]
                    
                    if all_ts:
                        last_sync_time = max(all_ts).astimezone(timezone.utc).isoformat()

                    # 3. ยิงไปที่ Server
                    sync_url = f"{CLOUD_SERVER_URL}/userLockerGrant/sync/users"
                    params = {"last_sync": last_sync_time}
                    
                    response = requests.get(sync_url, headers=cloud_headers, params=params, timeout=15)
                    
                    if response.status_code == 200:
                        sync_data = response.json()
                        users_to_sync = sync_data.get("data", [])
                        print(f"📥 Received sync data: {users_to_sync}")
                        
                        if users_to_sync:
                            print(f"🔄 Sync: Received {len(users_to_sync)} updates (including permissions)")
                            for u_data in users_to_sync:
                                process_user_sync(session, u_data)
                            session.commit()
                        
        except Exception as e:
            print(f"📡 User Sync Agent Error: {e}")

        time.sleep(300)

def process_user_sync(session, u_data):
    """จัดการข้อมูล User และ UserPermission แบบ Relational Upsert"""
    user_info = u_data.get("User", {})
    user_id = user_info.get("user_id")
    
    # --- 1. จัดการข้อมูลตาราง User ---
    user = session.exec(select(User).where(User.user_id == user_id)).first()
    
    server_now_str = u_data.get("updated_at") or datetime.now(timezone.utc).isoformat()
    server_now = datetime.fromisoformat(server_now_str.replace('Z', '+00:00'))

    if not user:
        user = User(user_id=user_id)
        if user_info.get("created_at"):
            user.created_at = datetime.fromisoformat(user_info["created_at"].replace('Z', '+00:00'))
        print(f"🆕 Sync: Preparing New User {user_id}")
    
    # Mapping User Data
    user.email = user_info.get("email")
    user.first_name = user_info.get("first_name")
    user.last_name = user_info.get("last_name")
    user.hashed_password = user_info.get("password")
    # เข้ารหัส citizen_id_encrypted ก่อนบันทึกลงฐานข้อมูล
    raw_citizen_id = user_info.get("citizen_id") or user_info.get("citizen_id_encrypted")
    if raw_citizen_id:
        # เข้ารหัสสำหรับเก็บ (AES-Fernet)
        user.citizen_id_encrypted = encrypt_data(str(raw_citizen_id))
        # ทำ Hash สำหรับค้นหา (Blind Index)
        if hasattr(user, 'citizen_id_search_hash'):
            user.citizen_id_search_hash = get_search_hash(str(raw_citizen_id))
    user.updated_at = server_now
    
    # จัดการ Soft Delete ของ User
    delete_ts = user_info.get("deleted_at") or u_data.get("deleted_at")
    if delete_ts:
        user.deleted_at = datetime.fromisoformat(delete_ts.replace('Z', '+00:00'))
    else:
        user.deleted_at = None

    session.add(user)
    
    # --- 2. จัดการข้อมูลตาราง UserPermission ---
    permission = session.exec(select(UserPermission).where(UserPermission.user_id == user_id)).first()
    
    if not permission:
        permission = UserPermission(user_id=user_id)
        print(f"🔑 Sync: Initialized Permissions for {user_id}")
    
    # Mapping Permission Data (0/1 ตามที่ได้รับจาก Server)
    permission.permission_withdraw = u_data.get("permission_withdraw", 1)
    permission.permission_restock = u_data.get("permission_restock", 0)
    permission.updated_at = server_now
    
    # กรณีสิทธิ์ถูกลบ (เช่น Server ยกเลิกชุดสิทธิ์นี้)
    if u_data.get("deleted_at"):
        permission.deleted_at = user.deleted_at
    else:
        permission.deleted_at = None
        
    session.add(permission)

def run_user_sync_logic():
    """
    Logic หลักในการดึงข้อมูลจาก Server มาลงเครื่อง
    แยกออกมาเพื่อให้เรียกใช้ได้จากทั้ง Agent และ Manual Trigger
    """
    try:
        secret_hint = f"{INTERNAL_SECRET[:3]}***" if INTERNAL_SECRET else "MISSING"
        print(f"🔍 DEBUG: Attempting Identity Auth with Secret: {secret_hint}")

        # 1. ขอ Headers ยืนยันตัวตน
        auth_res = requests.get(
            IDENTITY_SERVICE_URL, 
            headers={"X-Internal-Secret": INTERNAL_SECRET},
            timeout=5
        )
        
        if auth_res.status_code == 200:
            cloud_headers = auth_res.json()
            
            with Session(engine) as session:
                last_sync_time = "1970-01-01T00:00:00Z"
                
                # หาจุดเวลาล่าสุดจากทั้งสองตาราง
                u_max = session.exec(select(func.max(User.created_at), func.max(User.updated_at), func.max(User.deleted_at))).first()
                p_max = session.exec(select(func.max(UserPermission.created_at), func.max(UserPermission.updated_at), func.max(UserPermission.deleted_at))).first()
                
                all_ts = [_parse_utc(ts) for ts in list(u_max or []) + list(p_max or []) if ts is not None]
                if all_ts:
                    last_sync_time = max(all_ts).astimezone(timezone.utc).isoformat()

                sync_url = f"{CLOUD_SERVER_URL}/userLockerGrant/sync/users"
                params = {"last_sync": last_sync_time}
                
                response = requests.get(sync_url, headers=cloud_headers, params=params, timeout=15)
                
                if response.status_code == 200:
                    sync_data = response.json()
                    users_to_sync = sync_data.get("data", [])
                    
                    if users_to_sync:
                        print(f"🔄 Sync: Received {len(users_to_sync)} updates")
                        for u_data in users_to_sync:
                            process_user_sync(session, u_data)
                        session.commit()
                        return len(users_to_sync)
                else:
                    print(f"📡 Sync Server Error: {response.status_code}")
        elif auth_res.status_code == 404:
            print(f"❌ Revoke detected (Status: {auth_res.status_code})")
            print(f"Response: {auth_res.text}")
            with Session(engine) as session:
                # Soft Delete ทุกคนในตาราง User และ UserPermission
                session.exec(update(User).values(deleted_at=datetime.now(timezone.utc)))
                session.exec(update(UserPermission).values(deleted_at=datetime.now(timezone.utc)))
                session.commit()
            print("✅ All users locally revoked due to missing auth headers")

    except Exception as e:
        print(f"📡 User Sync Error: {e}")
    return 0


def _extract_event_payload(raw_event: dict):
    if not isinstance(raw_event, dict):
        return None

    payload = raw_event.get("payload")
    if isinstance(payload, dict):
        return payload

    return raw_event


def _parse_utc(value):
    if not value:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    return None


def _get_locker_id_from_identity():
    try:
        auth_res = requests.get(
            IDENTITY_SERVICE_URL,
            headers={"X-Internal-Secret": INTERNAL_SECRET},
            timeout=5,
        )
        if auth_res.status_code == 200:
            locker_id = auth_res.json().get("locker_id")
            return str(locker_id) if locker_id is not None else None
    except Exception:
        pass
    return None


def _get_mqtt_runtime_config():
    config = get_mqtt_config()
    host = config.get("MQTT_BROKER_HOST")
    username = config.get("MQTT_USERNAME")
    password = config.get("MQTT_PASSWORD")

    if not host or not username or not password:
        return None

    locker_id = _get_locker_id_from_identity()
    if not locker_id:
        return None

    return {
        "host": host,
        "username": username,
        "password": password,
        "topic": f"smartlocker/{locker_id}/cloud/locker/user-grant/upsert",
        "client_id": f"{locker_id}-local-auth",
    }


def _process_user_event_message(message_payload: dict):
    event_id = message_payload.get("event_id") if isinstance(message_payload, dict) else None
    user_payload = _extract_event_payload(message_payload)
    if not user_payload or not isinstance(user_payload, dict):
        return

    with Session(engine) as session:
        if event_id and session.get(ProcessedEvent, event_id):
            print(f"ℹ️ [User MQTT] Duplicate event_id={event_id}, skipping")
            return

        user_info = user_payload.get("User", {})
        user_id = user_info.get("user_id")
        if not user_id:
            return

        db_user = session.exec(select(User).where(User.user_id == user_id)).first()
        if db_user and db_user.updated_at:
            incoming_updated_at = _parse_utc(user_payload.get("updated_at"))
            current_updated_at = _parse_utc(db_user.updated_at)
            if incoming_updated_at and current_updated_at and incoming_updated_at < current_updated_at:
                return

        process_user_sync(session, user_payload)
        if event_id:
            session.add(ProcessedEvent(event_id=event_id, event_type="user-grant.upsert"))
        session.commit()

    print(f"✅ [User MQTT] Applied user_id={user_payload.get('User', {}).get('user_id')}")


def user_sync_mqtt_agent():
    """รับ event user-grant จาก HiveMQ Cloud"""
    if mqtt is None:
        print("⚠️ [User MQTT] paho-mqtt is not installed; fallback to polling")
        user_sync_agent()
        return

    print("🚀 User MQTT Agent Started...")
    time.sleep(10)

    while True:
        cfg = _get_mqtt_runtime_config()
        if not cfg:
            print("⚠️ [User MQTT] Waiting for locker activation or mqtt_config.json")
            time.sleep(20)
            continue

        client = mqtt.Client(client_id=cfg["client_id"], clean_session=False)
        client.username_pw_set(cfg["username"], cfg["password"])
        client.tls_set()

        def on_connect(client_obj, _userdata, _flags, rc):
            if rc == 0:
                client_obj.subscribe(cfg["topic"], qos=1)
                print(f"✅ [User MQTT] Connected and subscribed: {cfg['topic']}")
            else:
                print(f"❌ [User MQTT] Connect failed rc={rc}")

        def on_message(_client_obj, _userdata, msg):
            try:
                payload = json.loads(msg.payload.decode("utf-8"))
                _process_user_event_message(payload)
            except Exception as e:
                print(f"❌ [User MQTT] Message processing error: {e}")

        client.on_connect = on_connect
        client.on_message = on_message

        try:
            client.connect(cfg["host"], MQTT_BROKER_PORT, MQTT_KEEPALIVE)
            client.loop_forever()
        except Exception as e:
            print(f"📡 [User MQTT] Broker connection error: {e}")
            time.sleep(10)


def start_local_auth_sync_worker():
    """เริ่ม worker ตามโหมด MQTT/Polling"""
    target = user_sync_mqtt_agent if MQTT_ENABLED else user_sync_agent
    sync_thread = threading.Thread(target=target, daemon=True)
    sync_thread.start()
    mode = "MQTT" if MQTT_ENABLED else "Polling"
    print(f"✅ Local Auth sync worker thread started ({mode})")

@router.post("/sync/trigger")
async def trigger_sync(background_tasks: BackgroundTasks):
    """
    Endpoint สำหรับสั่งให้ตู้ทำการ Sync ทันที (Manual Trigger)
    เหมาะสำหรับการทดสอบ หรือสั่งการจาก UI
    """
    # รันเป็น Background Task เพื่อไม่ให้ API ค้างถ้าระบบ Sync ใช้เวลานาน
    background_tasks.add_task(run_user_sync_logic)
    return {"message": "User sync process triggered in background"}

# --- Login Logic ---

@router.post("/login/password")
def login_with_password(login_data: UserLogin, session: SessionDep):
    """เข้าสู่ระบบด้วย Email หรือ CitizenID และ Password"""
    identifier = login_data.username.strip()
    search_hash = ""
    is_email = re.match(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$", identifier)
    is_citizen_id = re.match(r"^\d{13}$", identifier)

    # สร้าง Hash สำหรับใช้ค้นหาใน SQL
    search_hash = get_search_hash(identifier)
    
    # ค้นหา User จากหลายช่องทางด้วย SQL เพียงคำสั่งเดียว (O(1) Search)
    statement = select(User).where(
        or_(
            User.email == identifier,
            User.citizen_id_search_hash == search_hash
        ),
        User.deleted_at == None
    )
    user = session.exec(statement).first()
    
    if not user or not verify_password(login_data.password, user.hashed_password):
        log = AuthLog(username=identifier, login_method="password", status="failed")
        session.add(log)
        session.commit()
        raise HTTPException(status_code=401, detail="ข้อมูลประจำตัวหรือรหัสผ่านไม่ถูกต้อง")
    
    # ดึงสิทธิ์การใช้งาน
    perm_stmt = select(UserPermission).where(
        UserPermission.user_id == user.user_id,
        UserPermission.deleted_at == None
    )
    permission = session.exec(perm_stmt).first()
    
    # บันทึก Log สำเร็จ
    if is_email:
        log = AuthLog(user_id=user.user_id, username=user.email, login_method="password", status="success")
    elif is_citizen_id:
        log = AuthLog(user_id=user.user_id, username=f"CitizenID:{identifier[-4:]}", login_method="password", status="success")
    else:
        log = AuthLog(user_id=user.user_id, username=identifier, login_method="password", status="success")
    session.add(log)
    session.commit()
    
    return {
        "message": "Login successful", 
        "user": {
            "user_id": user.user_id,
            "full_name": f"{user.first_name} {user.last_name}",
            "permissions": {
                "can_withdraw": bool(permission.permission_withdraw) if permission else True,
                "can_restock": bool(permission.permission_restock) if permission else False
            }
        }
    }

@router.post("/login/smartcard")
def login_with_smartcard(login_in: SmartCardLogin, session: SessionDep):
    """เข้าสู่ระบบด้วยการเสียบบัตรประชาชน (ใช้ Blind Index ค้นหา)"""
    raw_citizen_id = login_in.citizen_id.strip()
    search_hash = get_search_hash(raw_citizen_id)

    # ค้นหาโดยตรงผ่าน Hash Index ไม่ต้องดึงทุกคนมาวนลูปถอดรหัส
    statement = select(User).where(
        User.citizen_id_search_hash == search_hash,
        User.deleted_at == None
    )
    user = session.exec(statement).first()
    
    if not user:
        log = AuthLog(login_method="smartcard", status="failed")
        session.add(log)
        session.commit()
        raise HTTPException(status_code=401, detail="ไม่พบข้อมูลผู้ใช้จากบัตรประชาชนใบนี้")
    
    # ดึงสิทธิ์การใช้งาน
    perm_stmt = select(UserPermission).where(
        UserPermission.user_id == user.user_id,
        UserPermission.deleted_at == None
    )
    permission = session.exec(perm_stmt).first()

    # บันทึก Log สำเร็จ
    log = AuthLog(user_id=user.user_id, username=f"CitizenID:{raw_citizen_id[-4:]}", login_method="smartcard", status="success")
    session.add(log)
    session.commit()
    
    return {
        "message": "Login successful", 
        "user": {
            "user_id": user.user_id,
            "full_name": f"{user.first_name} {user.last_name}",
            "permissions": {
                "can_withdraw": bool(permission.permission_withdraw) if permission else True,
                "can_restock": bool(permission.permission_restock) if permission else False
            }
        }
    }

# --- [NEW] API สำหรับเช็คสิทธิ์ผู้ใช้ ---

@router.get("/permissions/{user_id}")
async def get_user_permissions(
    user_id: str, 
    session: SessionDep,
    x_internal_secret: str = Header(None, alias="X-Internal-Secret") # เพิ่มการเช็ค Header
):
    """
    ตรวจสอบสิทธิ์ของผู้ใช้รายบุคคล
    ใช้สำหรับให้ Service อื่นๆ หรือ UI มาถามว่า User คนนี้ทำอะไรได้บ้าง
    """
    # ตรวจสอบ Header ลับก่อนเข้าถึงข้อมูล
    if x_internal_secret != INTERNAL_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized internal call")
    
    # 1. ค้นหาสิทธิ์จากตาราง UserPermission
    statement = select(UserPermission).where(
        UserPermission.user_id == user_id,
        UserPermission.deleted_at == None
    )
    permission = session.exec(statement).first()

    if not permission:
        # หากไม่เจอบันทึกสิทธิ์ ให้ถือว่าเป็นผู้ใช้ทั่วไปที่ไม่มีสิทธิ์พิเศษ
        return {
            "user_id": user_id,
            "permissions": {
                "can_withdraw": 0,
                "can_restock": 0
            },
            "status": "default_restricted"
        }

    return {
        "user_id": user_id,
        "permissions": {
            "can_withdraw": permission.permission_withdraw,
            "can_restock": permission.permission_restock
        },
        "status": "active"
    }
