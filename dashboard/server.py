"""
dashboard/server.py — FastAPI dashboard server for VOLT devices.
"""

import json
import asyncio
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import httpx

app = FastAPI(title="VOLT Dashboard", version="0.1.0")

STATIC_DIR = Path(__file__).parent / "static"

# Mount static files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# In-memory device registry
_devices: dict = {}


@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the dashboard SPA."""
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/api/devices")
async def list_devices():
    """Return discovered devices."""
    return list(_devices.values())


@app.post("/api/devices/register")
async def register_device(data: dict):
    """Device self-registration endpoint."""
    device_id = data.get("id")
    if device_id:
        _devices[device_id] = data
    return {"ok": True}


@app.post("/api/ota/{device_id}")
async def ota_push(device_id: str, file: UploadFile = File(...)):
    """Proxy OTA firmware push to a specific device."""
    device = _devices.get(device_id)
    if not device:
        return {"error": f"Device '{device_id}' not found"}, 404

    ip = device.get("ip")
    if not ip:
        return {"error": "Device IP unknown"}, 400

    contents = await file.read()
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                f"http://{ip}/ota/upload",
                content=contents,
                timeout=30,
            )
            return {"status": resp.status_code, "device": device_id}
        except Exception as e:
            return {"error": str(e)}


# WebSocket connection manager
class _ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast(self, message: str):
        dead = []
        for ws in self.active:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


_manager = _ConnectionManager()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Real-time WebSocket bridge for live sensor data."""
    await _manager.connect(websocket)
    try:
        while True:
            # Echo back any messages from client
            data = await websocket.receive_text()
            await websocket.send_text(data)
    except WebSocketDisconnect:
        _manager.disconnect(websocket)


async def broadcast_event(event: dict):
    """Push an event to all connected dashboard clients."""
    await _manager.broadcast(json.dumps(event))
