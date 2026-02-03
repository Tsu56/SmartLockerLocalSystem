import requests
from dotenv import load_dotenv
import os
from fastapi import APIRouter, HTTPException, status
from sqlmodel import select
from datetime import datetime, timezone

from database import SessionDep
from database.models import DeviceInfo
from database.schema import (
    DeviceInfoCreate, 
    DeviceInfoPublic, 
    DeviceInfoUpdate, 
    DeviceActivationRequest
)

router = APIRouter(prefix="/device", tags=["Device Identification"])

load_dotenv()

CLOUD_SERVER_URL = os.getenv("SERVER_URL", "")

@router.post("/activate", response_model=DeviceInfoPublic)
def activate_device(activation_data: DeviceActivationRequest, session: SessionDep):
    try:
        endpoint = f"{CLOUD_SERVER_URL}/lockerProvision/getProvisionByCode/{activation_data.provision_code}"
        response = requests.get(
            endpoint,  
            timeout=10
        )

        response.raise_for_status()
        cloud_data = response.json() 
    
    except requests.exceptions.RequestException as e:
        detail = "Connection to server failed"
        if response_err := getattr(e, 'response', None):
            try:
                detail = response_err.json().get("detail", detail)
            except:
                pass
        raise HTTPException(status_code=503, detail=detail)
    
    existing_device = session.exec(select(DeviceInfo)).first()

    if existing_device:
        existing_device.device_id = cloud_data["data"]["locker_id"]
        existing_device.api_token_encrypted = cloud_data["data"]["api_token"]
        existing_device.locker_location_detail = cloud_data["data"]["locker_location_detail"]
        existing_device.last_sync = datetime.now(timezone.utc)
        session.add(existing_device)
        session.commit()
        session.refresh(existing_device)
        return existing_device
    else:
        new_device = DeviceInfo(
            device_id=cloud_data["data"]["locker_id"],
            api_token_encrypted=cloud_data["data"]["api_token"],
            locker_location_detail=cloud_data["data"]["locker_location_detail"],
            is_active=True
        )
        session.add(new_device)
        session.commit()
        session.refresh(new_device)
        return new_device
    
@router.get("/info", response_model=DeviceInfoPublic)
def get_device_info(session: SessionDep):
    """ดึงข้อมูลสถานะปัจจุบันของตู้"""
    device = session.exec(select(DeviceInfo)).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not activated yet")
    return device