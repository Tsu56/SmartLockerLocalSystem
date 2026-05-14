# SmartLocker: Event-driven Sync via MQTT (HiveMQ Cloud)

## 1) Goal
เปลี่ยนการ Sync แบบ `schedule polling (ทุก 5 นาที)` เป็น `event-driven` ผ่าน MQTT เพื่อให้ข้อมูลใหม่เข้าตู้เร็วขึ้น, ลด API load, และยังคงทำงานได้ปลอดภัยเมื่อเน็ตไม่เสถียร

## 2) Current State (จากโค้ดปัจจุบัน)
- `device_identity_service/slot_sync_agent.py`: poll `GET /slot/sync/slots?last_sync=...` ทุก 300 วินาที
- `product_management_service/product_sync_agent.py`: poll `GET /product/sync/products?last_sync=...` ทุก 300 วินาที
- `local_auth_service/api.py` (`user_sync_agent`): poll `GET /userLockerGrant/sync/users?last_sync=...` ทุก 300 วินาที

ปัญหา:
- Latency สูงสุดตามรอบ polling
- เรียก API ซ้ำแม้ไม่มีข้อมูลเปลี่ยน
- หากมี burst update จะ delay จนถึงรอบถัดไป

## 3) Target Architecture

### 3.1 High-level
- Cloud เป็นแหล่ง Truth และเป็น MQTT publisher ของเหตุการณ์ข้อมูล
- Locker services เป็น MQTT subscribers ตาม domain ที่ตนรับผิดชอบ
- ใช้ Cloud Broker เป็น `HiveMQ Cloud` (Managed MQTT)
- แต่ละ service ทำ `idempotent upsert` ลงฐานข้อมูลตัวเอง (เหมือน logic เดิม)

### 3.2 Broker Security
- TLS บังคับ (`8883`) สำหรับ HiveMQ Cloud
- Auth แบบ username/password (ค่าเริ่มต้นที่ใช้ง่ายกับนักศึกษา)
- ACL จำกัด topic ตาม `locker_id`
- แนะนำให้ Cloud ออก credential แบบ short-lived

### 3.4 HiveMQ Cloud Notes
- รูปแบบ host มักเป็น: `<cluster-id>.s1.eu.hivemq.cloud` (หรือ region ที่ใช้งานจริง)
- ใช้ MQTT over TLS บนพอร์ต `8883`
- แนะนำตั้งผู้ใช้แยกต่อ locker หรืออย่างน้อยแยกตามกลุ่มตู้ เพื่อจัด ACL ง่าย
- กำหนด ACL ให้ publish/subscribe ได้เฉพาะ prefix `smartlocker/{locker_id}/#`

### 3.3 Topic Convention (ฉบับเข้าใจง่าย)
แนะนำรูปแบบที่อ่านเหมือนประโยค:
`smartlocker/{locker_id}/{sender}/{receiver}/{resource}/{action}`

ความหมายแต่ละส่วน:
- `{sender}`: ใครเป็นคนส่ง (`cloud` หรือ `locker`)
- `{receiver}`: ใครเป็นคนรับ (`locker` หรือ `cloud`)
- `{resource}`: ข้อมูลอะไร (`slot`, `product`, `user-grant`, `device`, `snapshot`, `ack`)
- `{action}`: ทำอะไรกับข้อมูล (`upsert`, `revoke`, `request`, `ok`, `error`)

ตัวอย่างที่ใช้จริง:
- Slot update (Cloud -> Locker): `smartlocker/LKR-001/cloud/locker/slot/upsert`
- Product update (Cloud -> Locker): `smartlocker/LKR-001/cloud/locker/product/upsert`
- User grant update (Cloud -> Locker): `smartlocker/LKR-001/cloud/locker/user-grant/upsert`
- Revoke device (Cloud -> Locker): `smartlocker/LKR-001/cloud/locker/device/revoke`
- Snapshot request (Cloud -> Locker, optional): `smartlocker/LKR-001/cloud/locker/snapshot/request`
- ACK success (Locker -> Cloud): `smartlocker/LKR-001/locker/cloud/ack/ok`
- ACK failed (Locker -> Cloud): `smartlocker/LKR-001/locker/cloud/ack/error`

ตัวอย่าง wildcard ที่ทีม Dev ใช้ง่าย:
- ฝั่ง Locker subscribe: `smartlocker/LKR-001/cloud/locker/+/+`
- ฝั่ง Cloud subscribe ACK: `smartlocker/LKR-001/locker/cloud/ack/+`

## 4) Event Contract (Payload)

### 4.1 Envelope (ทุก event ใช้ร่วมกัน)
```json
{
  "event_id": "01JXYZ...",
  "event_type": "slot.upsert.v1",
  "occurred_at": "2026-03-12T10:15:20Z",
  "producer": "cloud-sync-service",
  "locker_id": "LKR-001",
  "entity_id": "101",
  "trace_id": "req-abc-123",
  "schema_version": 1,
  "payload": {}
}
```

### 4.2 Domain Payload Example
`slot.upsert.v1`
```json
{
  "slot_id": 101,
  "locker_id": "LKR-001",
  "slot_status": "active",
  "capacity": 24,
  "created_at": "2026-03-12T10:10:00Z",
  "updated_at": "2026-03-12T10:15:00Z",
  "deleted_at": null
}
```

`product.upsert.v1`
```json
{
  "product_id": "P0001",
  "product_name": "Paracetamol 500mg",
  "product_detail": "Tablet",
  "created_at": "2026-03-12T10:10:00Z",
  "updated_at": "2026-03-12T10:15:00Z",
  "deleted_at": null
}
```

`user-grant.upsert.v1`
```json
{
  "User": {
    "user_id": "uuid-user",
    "email": "nurse@example.com",
    "first_name": "A",
    "last_name": "B",
    "password": "<hashed-from-cloud>",
    "citizen_id": "1103700...",
    "created_at": "2026-03-12T10:10:00Z",
    "updated_at": "2026-03-12T10:15:00Z",
    "deleted_at": null
  },
  "permission_withdraw": 1,
  "permission_restock": 0,
  "updated_at": "2026-03-12T10:15:00Z",
  "deleted_at": null
}
```

## 5) Delivery Semantics
- QoS แนะนำ:
  - Master data (`slot/product/user-grant`): QoS 1
  - Control (`revoke`): QoS 1 หรือ 2
- ใช้ `clean session = false` / persistent session เพื่อรับข้อความค้างตอน offline
- ใช้ retained เฉพาะ `snapshot` หรือ `last-known state` (ถ้าใช้ event log ไม่ควร retained ทุก event)

## 6) Idempotency + Ordering

### 6.1 Idempotency
เพิ่มตาราง `processed_event` ในแต่ละ service:
- `event_id` (PK/unique)
- `event_type`
- `processed_at`

ลำดับการทำงาน:
1. ตรวจ `event_id` ซ้ำหรือไม่
2. ถ้ายังไม่เคยประมวลผล -> upsert domain data
3. บันทึก `processed_event`
4. commit transaction เดียวกัน

### 6.2 Ordering
- คีย์ตัดสินล่าสุดใช้ `payload.updated_at` (หรือ `occurred_at`) เทียบกับใน DB
- ถ้า event เก่ากว่าข้อมูลปัจจุบัน ให้ ignore อย่างปลอดภัย

## 7) Bootstrap and Recovery
เมื่อ service เริ่มใหม่:
1. ต่อ MQTT และ subscribe ทันที
2. ขอ snapshot ครั้งแรก 1 รอบ (HTTP หรือ MQTT snapshot topic)
3. apply snapshot แบบ upsert
4. เริ่มรับ incremental events ต่อ

หมายเหตุ:
- ช่วง migration ให้คง polling แบบ low-frequency fallback (เช่นทุก 30-60 นาที) เพื่อ self-heal หากมี event loss

## 8) Proposed Changes by Service

### 8.1 `device_identity_service`
- แยก `slot_sync_agent.py` เป็นสองส่วน:
  - `apply_slot_event(payload)` ใช้ logic `process_slot_sync` เดิม
  - `slot_mqtt_consumer.py` สำหรับ subscribe topic `.../cloud/locker/slot/upsert`
- เพิ่ม endpoint internal สำหรับ MQTT config (optional):
  - `GET /device/internal/mqtt-config`

### 8.2 `product_management_service`
- เปลี่ยน `product_sync_agent.py` จาก loop polling เป็น MQTT consumer
- reuse logic upsert product เดิมจาก `perform_product_sync`
- เพิ่ม consumer สำหรับ event transaction control (ถ้าจะขยายในอนาคต)

### 8.3 `local_auth_service`
- แยก `process_user_sync(session, u_data)` ออกมาใช้กับ MQTT โดยตรง
- เปลี่ยน `user_sync_agent` loop เป็น MQTT consumer ของ `user-grant.upsert`

## 9) Shared MQTT Module (แนะนำทำเป็น utility กลาง)
สร้างไฟล์ใหม่ในแต่ละ service หรือ shared package:
- `mqtt_client.py`

Responsibilities:
- connect/reconnect with exponential backoff
- subscribe list จาก config
- parse envelope + validate schema_version
- dispatch handler ตาม `event_type`
- publish ack/metrics

## 10) Configuration
ตั้งค่าผ่าน env (ที่ไม่ใช่ความลับ) ในแต่ละ service:
- `MQTT_ENABLED=true`
- `MQTT_BROKER_PORT=8883`
- `MQTT_CLIENT_ID=${LOCKER_ID}-device-identity`
- `MQTT_TOPIC_PREFIX=smartlocker/${LOCKER_ID}`
- `MQTT_TLS_CA_CERT=/etc/ssl/certs/ca-certificates.crt`
- `MQTT_KEEPALIVE_SECONDS=60`
- `MQTT_CLEAN_SESSION=false`
- `SYNC_FALLBACK_POLL_MINUTES=60`

ตั้งค่าความลับผ่านไฟล์ `secret/mqtt_config.json` ของแต่ละ service (mount แบบ read-only):
```json
{
  "MQTT_BROKER_HOST": "<cluster-id>.s1.eu.hivemq.cloud",
  "MQTT_USERNAME": "<hivemq-username>",
  "MQTT_PASSWORD": "<hivemq-password>"
}
```

ตัวอย่างตำแหน่งไฟล์ในโปรเจกต์:
- `device_identity_service/secret/mqtt_config.json`
- `local_auth_service/secret/mqtt_config.json`
- `product_management_service/secret/mqtt_config.json`
- `display_service/secret/mqtt_config.json`

## 11) Docker Compose Adjustments
ใน `docker-compose.yml` ของแต่ละ service:
- เพิ่ม env ของ HiveMQ Cloud เฉพาะค่าที่ไม่ใช่ความลับ
- mount `./<service>/secret:/<service>/secret:ro` เพื่อส่งความลับเข้า container แบบ read-only
- mount cert volume ถ้าใช้ TLS CA file
- ไม่จำเป็นต้องเปิดพอร์ตเพิ่มภายในตู้ (เชื่อมต่อ outbound ไป HiveMQ Cloud)

## 12) Observability
- Structured logs: `event_id`, `event_type`, `locker_id`, `result`, `duration_ms`
- Metrics:
  - `mqtt_connected` (gauge)
  - `sync_event_processed_total`
  - `sync_event_failed_total`
  - `sync_event_lag_seconds`
- Health endpoint ควรเช็ค:
  - DB reachable
  - MQTT connected ล่าสุดไม่เกิน threshold

## 13) Rollout Plan (Safe Migration)
1. Phase 0: เตรียม Cloud publisher + topic + contract
2. Phase 1: Locker subscribe + apply event แต่ยังคง polling 5 นาที
3. Phase 2: ลด polling เหลือ 30-60 นาที fallback
4. Phase 3: ปิด polling เหลือเฉพาะ manual trigger/recovery
5. Phase 4: เปิด snapshot-request/replay สำหรับ disaster recovery

## 14) Minimal Code-level Refactor Strategy
- คง `run_*_sync_logic()` สำหรับ fallback/manual
- แตก logic domain เป็น `apply_*_upsert(session, payload)` ให้ทั้ง HTTP sync และ MQTT เรียกซ้ำได้
- จุดที่แก้หลัก:
  - `device_identity_service/slot_sync_agent.py`
  - `product_management_service/product_sync_agent.py`
  - `local_auth_service/api.py` (ส่วน `user_sync_agent`)
  - `*/app.py` เพื่อ start MQTT consumer แทน loop เดิม

## 15) Risks and Mitigation
- Duplicate delivery: ใช้ `processed_event` + unique key
- Out-of-order events: compare `updated_at`
- Temporary disconnect: persistent session + reconnect backoff
- Contract drift: lock `event_type` + `schema_version`

## 16) Example Consumer Flow (Pseudo)
```text
on_message(event):
  parse envelope
  validate locker_id matches local device
  begin db transaction
    if event_id already processed: return ack_duplicate
    dispatch by event_type -> apply_upsert(payload)
    insert processed_event(event_id)
  commit
  publish ack_success
```

---

เอกสารนี้ออกแบบให้รองรับโค้ดฐานเดิมโดยเปลี่ยนเฉพาะกลไก "รับข้อมูลเข้า" จาก Polling เป็น MQTT โดยยัง reuse upsert logic เดิมให้มากที่สุด
