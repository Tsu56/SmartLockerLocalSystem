#!/bin/bash

# หน่วงเวลา 15 วินาทีรอให้ระบบ Pi 5 และ Docker Engine รันให้เสร็จก่อน
sleep 15

# ไปที่โฟลเดอร์โปรเจกต์
cd /home/tphu/Desktop/SmartLocker

# สั่งเปิด xfce4-terminal แบบเต็มจอ (--maximize) และแยกแท็บเฉพาะ Service ที่มีอยู่
xfce4-terminal \
    --maximize \
    --tab --title="Identity Service" --command="bash -c 'docker compose logs -f device-identity-service; exec bash'" \
    --tab --title="Local Auth" --command="bash -c 'docker compose logs -f local-auth-service; exec bash'" \
    --tab --title="Display" --command="bash -c 'docker compose logs -f display-service; exec bash'" \
    --tab --title="Product Mgmt" --command="bash -c 'docker compose logs -f product-management-service; exec bash'" \
    --tab --title="Hardware Log" --command="bash -c 'journalctl -u locker-hardware.service -f; exec bash'" \
    --tab --title="Camera Service" --command="bash -c 'cd /home/tphu/Desktop/SmartLocker && python3 camera_service.py; exec bash'" \
    --tab --title="Camera Sync Agent" --command="bash -c 'cd /home/tphu/Desktop/SmartLocker && python3 camera_sync_agent.py; exec bash'" \
    --tab --title="SmartLocker UI" --command="bash -c 'cd /home/tphu/Desktop/SmartLocker/user_interface && source user_interface_venv/bin/activate && python main.py; exec bash'"