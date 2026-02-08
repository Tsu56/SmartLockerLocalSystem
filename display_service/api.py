import httpx
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse

router = APIRouter()

# ภายใน Docker Network ทุกตัวคุยกันผ่านพอร์ต 8000
SERVICES = {
    "identity": "http://device-identity-service:8000",
    "auth": "http://local-auth-service:8000",
    "product": "http://product-management-service:8000",
    "comm": "http://device-communication-service:8000"
}

@router.api_route("/api/{service_name}/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def gateway_proxy(service_name: str, path: str, request: Request):
    if service_name not in SERVICES:
        raise HTTPException(status_code=404, detail="Service not found")

    target_url = f"{SERVICES[service_name]}/{path}"
    body = await request.body()
    headers = dict(request.headers)
    
    if "host" in headers:
        del headers["host"]

    # กำหนด timeout รวมไว้ที่ตัว Client เลย (เช่น 10 วินาที)
    # วิธีนี้จะปลอดภัยและเสถียรที่สุดสำหรับ AsyncClient
    async with httpx.AsyncClient(timeout=10.0) as client:
        
        # 1. จัดการเรื่อง Auth Headers สำหรับ Product Service
        if service_name == "product":
            try:
                auth_res = await client.get(f"{SERVICES['identity']}/device/internal/auth-headers")
                if auth_res.status_code == 200:
                    headers.update(auth_res.json())
            except Exception as e:
                print(f"DEBUG: Auth fetch failed: {e}")

        # 2. ส่งต่อ Request ไปยัง Service เป้าหมาย
        try:
            proxy_req = client.build_request(
                method=request.method,
                url=target_url,
                params=request.query_params,
                headers=headers,
                content=body
            )
            
            # ลบ timeout=10 ออกจากตรงนี้ เพราะเราตั้งที่ AsyncClient(timeout=10.0) แล้ว
            response = await client.send(proxy_req)

            return JSONResponse(
                content=response.json() if "application/json" in response.headers.get("content-type", "") else response.text,
                status_code=response.status_code
            )
            
        except httpx.RequestError as e:
            raise HTTPException(status_code=503, detail=f"Service {service_name} unreachable: {str(e)}")