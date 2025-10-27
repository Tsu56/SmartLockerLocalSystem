from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
import requests
import os

app = FastAPI(title="Device Identity Service")

@app.get("/")
async def index():
    backoffice_url = os.getenv("BACKOFFICE_URL", "NOT SET")
    return {"message": f"Device Identity Service is running. And Backoffice URL is {backoffice_url}"}


@app.post("/device-identity/sync")
async def sync_device_identity(request: Request):
    try:
        req_data = await request.json()
        locker_id = req_data.get("locker_id")
        pair_code = req_data.get("pair_code")

        if not locker_id or not pair_code:
            raise HTTPException(status_code=400, detail="Missing locker_id or pair_code")

        headers = {"Authorization": f"Bearer {pair_code}"}
        backoffice_url = os.getenv("BACKOFFICE_URL")

        if not backoffice_url:
            raise HTTPException(status_code=500, detail="BACKOFFICE_URL not set in environment variables")

        response = requests.post(
            f"{backoffice_url}/api/device-identity/sync",
            json={"locker_id": locker_id},
            headers=headers,
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            return {"status": "success", "data": data}
        else:
            return JSONResponse(
                status_code=response.status_code,
                content={"status": "error", "message": response.text}
            )

    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=5000, reload=True)
