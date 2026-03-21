import json
import os
import threading
import time
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv
from sqlmodel import Session, select, func

from database import engine, models
from getkey import get_internal_shared_secret, get_mqtt_config

try:
    import paho.mqtt.client as mqtt
except Exception:
    mqtt = None

load_dotenv()

CLOUD_SERVER_URL = os.getenv("SERVER_URL", "http://localhost:3000/api")
DEVICE_SERVICE_URL = "http://device-identity-service:8000/device/internal/auth-headers"
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


def get_cloud_auth_headers():
    """ดึง Auth Headers จาก Identity Service"""
    try:
        headers = {"X-Internal-Secret": INTERNAL_SECRET}
        response = requests.get(DEVICE_SERVICE_URL, headers=headers, timeout=5)
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        print(f"📡 [Product Sync] Device Service Connection Error: {e}")
        return None


def perform_product_sync():
    """Incremental Sync แบบ polling (fallback/manual)"""
    print(f"🔄 [Product Sync] Checking for updates at {datetime.now(timezone.utc)}")

    auth_headers = get_cloud_auth_headers()
    if not auth_headers:
        return {"status": "error", "message": "Auth headers unavailable"}

    try:
        with Session(engine) as session:
            last_sync_time = "1970-01-01T00:00:00Z"
            p_max = session.exec(
                select(
                    func.max(models.Product.created_at),
                    func.max(models.Product.updated_at),
                    func.max(models.Product.deleted_at),
                )
            ).first()

            all_ts = [_parse_utc(ts) for ts in list(p_max or []) if ts is not None]
            if all_ts:
                last_sync_time = max(all_ts).astimezone(timezone.utc).isoformat()

            sync_url = f"{CLOUD_SERVER_URL}/product/sync/products"
            params = {"last_sync": last_sync_time}
            response = requests.get(sync_url, headers=auth_headers, params=params, timeout=15)

            if response.status_code != 200:
                error_msg = f"Cloud API Error {response.status_code}: {response.text}"
                print(f"⚠️ [Product Sync] {error_msg}")
                return {"status": "error", "message": error_msg}

            sync_res = response.json()
            cloud_products = sync_res.get("data", []) if isinstance(sync_res, dict) else sync_res

            applied = 0
            for cp in cloud_products:
                if _apply_product_upsert(session, cp):
                    applied += 1

            if cloud_products:
                session.commit()

            msg = f"Synced {applied}/{len(cloud_products)} items"
            print(f"✅ [Product Sync] {msg}")
            return {"status": "success", "message": msg, "data_count": applied}

    except Exception as e:
        error_msg = f"Unexpected sync error: {str(e)}"
        print(f"❌ [Product Sync] {error_msg}")
        return {"status": "error", "message": error_msg}


def _apply_product_upsert(session: Session, product_payload: dict):
    product_id = product_payload.get("product_id")
    if not product_id:
        return False

    db_product = session.get(models.Product, product_id)
    incoming_updated_at = _parse_utc(product_payload.get("updated_at")) or datetime.now(timezone.utc)

    if db_product and db_product.updated_at:
        current_updated_at = _parse_utc(db_product.updated_at)
        if current_updated_at and incoming_updated_at < current_updated_at:
            return False

    if db_product:
        db_product.product_name = product_payload.get("product_name")
        db_product.product_detail = product_payload.get("product_detail")
        db_product.updated_at = incoming_updated_at
        db_product.deleted_at = _parse_utc(product_payload.get("deleted_at")) if product_payload.get("deleted_at") else None
        session.add(db_product)
    else:
        session.add(
            models.Product(
                product_id=product_id,
                product_name=product_payload.get("product_name"),
                product_detail=product_payload.get("product_detail"),
                created_at=_parse_utc(product_payload.get("created_at")) or datetime.now(timezone.utc),
                updated_at=incoming_updated_at,
                deleted_at=_parse_utc(product_payload.get("deleted_at")) if product_payload.get("deleted_at") else None,
            )
        )

    return True


def _apply_qr_task_upsert(session: Session, task_payload: dict):
    task_id = task_payload.get("task_id")
    if not task_id:
        return False

    db_task = session.get(models.QRTask, task_id)
    incoming_updated_at = _parse_utc(task_payload.get("updated_at")) or datetime.now(timezone.utc)

    if db_task and db_task.updated_at:
        current_updated_at = _parse_utc(db_task.updated_at)
        if current_updated_at and incoming_updated_at < current_updated_at:
            return False

    if not db_task:
        db_task = models.QRTask(task_id=task_id, created_at=datetime.now(timezone.utc))

    db_task.locker_id = str(task_payload.get("locker_id") or "")
    db_task.task_type = str(task_payload.get("task_type") or "")
    db_task.assigned_user_id = str(task_payload.get("assigned_user_id") or "")
    db_task.qr_token = task_payload.get("qr_token")
    db_task.status = str(task_payload.get("status") or "pending")
    db_task.expires_at = _parse_utc(task_payload.get("expires_at"))
    db_task.used_at = _parse_utc(task_payload.get("used_at"))
    db_task.updated_at = incoming_updated_at
    db_task.deleted_at = _parse_utc(task_payload.get("deleted_at")) if task_payload.get("deleted_at") else None

    items = task_payload.get("items", [])
    if not isinstance(items, list):
        items = []
    db_task.items_json = json.dumps(items, ensure_ascii=True)

    session.add(db_task)
    return True


def _apply_qr_task_cancel(session: Session, task_payload: dict):
    task_id = task_payload.get("task_id")
    if not task_id:
        return False

    db_task = session.get(models.QRTask, task_id)
    if not db_task:
        db_task = models.QRTask(
            task_id=task_id,
            locker_id=str(task_payload.get("locker_id") or ""),
            task_type=str(task_payload.get("task_type") or ""),
            assigned_user_id=str(task_payload.get("assigned_user_id") or ""),
            items_json="[]",
            created_at=datetime.now(timezone.utc),
        )

    db_task.status = "cancelled"
    db_task.updated_at = _parse_utc(task_payload.get("updated_at")) or datetime.now(timezone.utc)
    db_task.deleted_at = _parse_utc(task_payload.get("deleted_at")) or datetime.now(timezone.utc)
    session.add(db_task)
    return True


def _extract_event_payload(raw_event: dict):
    if not isinstance(raw_event, dict):
        return None

    payload = raw_event.get("payload")
    if isinstance(payload, dict):
        return payload

    return raw_event


def _process_mqtt_event_message(message_payload: dict, topic: str):
    event_id = message_payload.get("event_id") if isinstance(message_payload, dict) else None
    event_type = message_payload.get("event_type", "") if isinstance(message_payload, dict) else ""
    payload = _extract_event_payload(message_payload)

    if not payload or not isinstance(payload, dict):
        return

    with Session(engine) as session:
        if event_id and session.get(models.ProcessedEvent, event_id):
            print(f"ℹ️ [Product MQTT] Duplicate event_id={event_id}, skipping")
            return

        applied = False

        if "product" in topic and ("upsert" in topic or event_type.startswith("product.upsert")):
            applied = _apply_product_upsert(session, payload)
        elif "qr-task" in topic and ("upsert" in topic or event_type.startswith("qr-task.upsert")):
            applied = _apply_qr_task_upsert(session, payload)
        elif "qr-task" in topic and ("cancel" in topic or event_type.startswith("qr-task.cancel")):
            applied = _apply_qr_task_cancel(session, payload)

        if not applied:
            return

        if event_id:
            session.add(
                models.ProcessedEvent(
                    event_id=event_id,
                    event_type=event_type or "mqtt.event",
                )
            )

        session.commit()

    print(f"✅ [Product MQTT] Applied event topic={topic}")


def _get_mqtt_runtime_config():
    config = get_mqtt_config()
    host = config.get("MQTT_BROKER_HOST")
    username = config.get("MQTT_USERNAME")
    password = config.get("MQTT_PASSWORD")

    if not host or not username or not password:
        return None

    auth_headers = get_cloud_auth_headers() or {}
    locker_id = auth_headers.get("locker_id")
    if not locker_id:
        return None

    return {
        "host": host,
        "username": username,
        "password": password,
        "topics": [
            f"smartlocker/{locker_id}/cloud/locker/product/upsert",
            f"smartlocker/{locker_id}/cloud/locker/qr-task/upsert",
            f"smartlocker/{locker_id}/cloud/locker/qr-task/cancel",
        ],
        "client_id": f"{locker_id}-product-management",
    }


def sync_products_mqtt_loop():
    """รับ event product และ qr-task จาก HiveMQ Cloud"""
    if mqtt is None:
        print("⚠️ [Product MQTT] paho-mqtt is not installed; fallback to polling")
        sync_products_loop()
        return

    print("🚀 Product MQTT Agent Loop Started...")
    time.sleep(10)

    while True:
        cfg = _get_mqtt_runtime_config()
        if not cfg:
            print("⚠️ [Product MQTT] Waiting for locker activation or mqtt_config.json")
            time.sleep(20)
            continue

        client = mqtt.Client(client_id=cfg["client_id"], clean_session=False)
        client.username_pw_set(cfg["username"], cfg["password"])
        client.tls_set()

        def on_connect(client_obj, _userdata, _flags, rc):
            if rc == 0:
                for topic in cfg["topics"]:
                    client_obj.subscribe(topic, qos=1)
                    print(f"✅ [Product MQTT] Subscribed: {topic}")
            else:
                print(f"❌ [Product MQTT] Connect failed rc={rc}")

        def on_message(_client_obj, _userdata, msg):
            try:
                payload = json.loads(msg.payload.decode("utf-8"))
                _process_mqtt_event_message(payload, msg.topic)
            except Exception as e:
                print(f"❌ [Product MQTT] Message processing error: {e}")

        client.on_connect = on_connect
        client.on_message = on_message

        try:
            client.connect(cfg["host"], MQTT_BROKER_PORT, MQTT_KEEPALIVE)
            client.loop_forever()
        except Exception as e:
            print(f"📡 [Product MQTT] Broker connection error: {e}")
            time.sleep(10)


def sync_products_loop():
    """รอบการทำงานเบื้องหลังแบบ polling"""
    print("🚀 Product Sync Agent Loop Started...")
    time.sleep(10)

    while True:
        perform_product_sync()
        time.sleep(300)


def start_product_sync_agent():
    """เริ่มต้น Product Sync worker ใน Background Thread"""
    target = sync_products_mqtt_loop if MQTT_ENABLED else sync_products_loop
    agent_thread = threading.Thread(target=target, daemon=True)
    agent_thread.start()
    mode = "MQTT" if MQTT_ENABLED else "Polling"
    print(f"✅ Product Sync worker thread started ({mode})")
