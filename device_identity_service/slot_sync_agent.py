"""
Slot Sync Agent
ดึงข้อมูล Slot จาก Cloud Server มาเก็บใน device_identity_service
"""
import json
import os
import threading
import time
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv
from sqlmodel import select, func

from database import Session, engine
from database.models import Slot, DeviceInfo, ProcessedEvent
from getkey import get_internal_shared_secret, get_mqtt_config

try:
    import paho.mqtt.client as mqtt
except Exception:
    mqtt = None

load_dotenv()

CLOUD_SERVER_URL = os.getenv("SERVER_URL", "")
INTERNAL_SECRET = get_internal_shared_secret()
MQTT_ENABLED = os.getenv("MQTT_ENABLED", "false").strip().lower() == "true"
MQTT_BROKER_PORT = int(os.getenv("MQTT_BROKER_PORT", "8883"))
MQTT_KEEPALIVE = int(os.getenv("MQTT_KEEPALIVE_SECONDS", "60"))


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


def get_auth_headers():
    """ดึง authentication headers จาก device_identity_service's own data"""
    try:
        with Session(engine) as session:
            device = session.exec(select(DeviceInfo)).first()
            if not device or not device.api_token_encrypted:
                return None

            from encryption import decrypt_data

            decrypted_token = decrypt_data(device.api_token_encrypted)
            return {
                "locker_id": str(device.locker_id),
                "api_token": f"Bearer {decrypted_token}",
            }
    except Exception as e:
        print(f"❌ Failed to get auth headers: {e}")
        return None


def process_slot_sync(session, slot_data):
    """
    จัดการข้อมูล Slot แบบ Upsert
    - Insert ถ้ายังไม่มี
    - Update ถ้ามีอยู่แล้ว
    """
    slot_id = slot_data.get("slot_id")
    if slot_id is None:
        return False

    slot = session.exec(select(Slot).where(Slot.slot_id == slot_id)).first()
    incoming_updated_at = _parse_utc(slot_data.get("updated_at")) or datetime.now(timezone.utc)

    if slot and slot.updated_at:
        current_updated_at = _parse_utc(slot.updated_at)
        if current_updated_at and incoming_updated_at < current_updated_at:
            return False

    if not slot:
        slot = Slot(slot_id=slot_id)
        if slot_data.get("created_at"):
            slot.created_at = _parse_utc(slot_data.get("created_at"))
        print(f"🆕 Sync: Preparing New Slot {slot_id}")

    slot.locker_id = str(slot_data.get("locker_id") or "")
    slot.slot_status = slot_data.get("slot_status", "active")
    slot.capacity = slot_data.get("capacity", 0)
    slot.updated_at = incoming_updated_at

    delete_ts = slot_data.get("deleted_at")
    slot.deleted_at = _parse_utc(delete_ts) if delete_ts else None

    session.add(slot)
    return True


def run_slot_sync_logic():
    """Logic หลักในการดึงข้อมูล Slot จาก Server มาลงเครื่อง"""
    try:
        cloud_headers = get_auth_headers()
        if not cloud_headers:
            return {
                "status": "error",
                "message": "Device not activated or missing auth headers",
                "synced_count": 0,
            }

        with Session(engine) as session:
            last_sync_time = "1970-01-01T00:00:00Z"

            slot_max = session.exec(
                select(
                    func.max(Slot.created_at),
                    func.max(Slot.updated_at),
                    func.max(Slot.deleted_at),
                )
            ).first()

            all_ts = [_parse_utc(ts) for ts in (slot_max or []) if ts is not None]
            if all_ts:
                last_sync_time = max(all_ts).astimezone(timezone.utc).isoformat()

            sync_url = f"{CLOUD_SERVER_URL}/slot/sync/slots"
            params = {"last_sync": last_sync_time}

            response = requests.get(sync_url, headers=cloud_headers, params=params, timeout=15)
            if response.status_code != 200:
                error_msg = f"Server responded with status {response.status_code}"
                print(f"❌ Sync Error: {error_msg}")
                return {"status": "error", "message": error_msg, "synced_count": 0}

            sync_data = response.json()
            slots_to_sync = sync_data.get("data", [])
            applied = 0

            for slot_data in slots_to_sync:
                if process_slot_sync(session, slot_data):
                    applied += 1

            if slots_to_sync:
                session.commit()
                print(f"✅ Synced {applied}/{len(slots_to_sync)} slot updates")

            return {
                "status": "success",
                "message": "Sync completed",
                "synced_count": applied,
            }

    except Exception as e:
        error_msg = str(e)
        print(f"❌ Slot Sync Error: {error_msg}")
        return {"status": "error", "message": error_msg, "synced_count": 0}


def slot_sync_agent():
    """Polling worker fallback"""
    print("🚀 Slot Sync Agent Started...")
    time.sleep(10)

    while True:
        try:
            run_slot_sync_logic()
        except Exception as e:
            print(f"📡 Slot Sync Agent Error: {e}")
        time.sleep(300)


def _extract_event_payload(raw_event: dict):
    if not isinstance(raw_event, dict):
        return None

    payload = raw_event.get("payload")
    if isinstance(payload, dict):
        return payload

    return raw_event


def _process_slot_event_message(message_payload: dict):
    event_id = message_payload.get("event_id") if isinstance(message_payload, dict) else None
    slot_payload = _extract_event_payload(message_payload)
    if not slot_payload or "slot_id" not in slot_payload:
        return

    with Session(engine) as session:
        if event_id and session.get(ProcessedEvent, event_id):
            print(f"ℹ️ [Slot MQTT] Duplicate event_id={event_id}, skipping")
            return

        if not process_slot_sync(session, slot_payload):
            return

        if event_id:
            session.add(ProcessedEvent(event_id=event_id, event_type="slot.upsert"))

        session.commit()

    print(f"✅ [Slot MQTT] Applied slot_id={slot_payload.get('slot_id')}")


def _get_mqtt_runtime_config():
    config = get_mqtt_config()
    host = config.get("MQTT_BROKER_HOST")
    username = config.get("MQTT_USERNAME")
    password = config.get("MQTT_PASSWORD")

    if not host or not username or not password:
        return None

    auth_headers = get_auth_headers() or {}
    locker_id = auth_headers.get("locker_id")
    if not locker_id:
        return None

    topic = f"smartlocker/{locker_id}/cloud/locker/slot/upsert"
    client_id = f"{locker_id}-device-identity"

    return {
        "host": host,
        "username": username,
        "password": password,
        "topic": topic,
        "client_id": client_id,
    }


def slot_sync_mqtt_agent():
    """รับ event slot จาก HiveMQ Cloud"""
    if mqtt is None:
        print("⚠️ [Slot MQTT] paho-mqtt is not installed; fallback to polling")
        slot_sync_agent()
        return

    print("🚀 Slot MQTT Agent Started...")
    time.sleep(10)

    while True:
        cfg = _get_mqtt_runtime_config()
        if not cfg:
            print("⚠️ [Slot MQTT] Waiting for locker activation or mqtt_config.json")
            time.sleep(20)
            continue

        client = mqtt.Client(client_id=cfg["client_id"], clean_session=False)
        client.username_pw_set(cfg["username"], cfg["password"])
        client.tls_set()

        def on_connect(client_obj, _userdata, _flags, rc):
            if rc == 0:
                client_obj.subscribe(cfg["topic"], qos=1)
                print(f"✅ [Slot MQTT] Connected and subscribed: {cfg['topic']}")
            else:
                print(f"❌ [Slot MQTT] Connect failed rc={rc}")

        def on_message(_client_obj, _userdata, msg):
            try:
                payload = json.loads(msg.payload.decode("utf-8"))
                _process_slot_event_message(payload)
            except Exception as e:
                print(f"❌ [Slot MQTT] Message processing error: {e}")

        client.on_connect = on_connect
        client.on_message = on_message

        try:
            client.connect(cfg["host"], MQTT_BROKER_PORT, MQTT_KEEPALIVE)
            client.loop_forever()
        except Exception as e:
            print(f"📡 [Slot MQTT] Broker connection error: {e}")
            time.sleep(10)


def start_slot_sync_agent():
    """เริ่มต้น Slot Sync worker ใน background thread"""
    target = slot_sync_mqtt_agent if MQTT_ENABLED else slot_sync_agent
    sync_thread = threading.Thread(target=target, daemon=True)
    sync_thread.start()
    mode = "MQTT" if MQTT_ENABLED else "Polling"
    print(f"✅ Slot Sync worker thread started ({mode})")
