"""
examples/ota_update/main.py

Self-updating firmware pattern using VOLT's OTA endpoint.

The HTTP server exposes /ota/upload — the CLI tool `volt ota push`
POSTs a new main.py here, which is written to flash and triggers a reboot.
"""
import machine

from volt import App, WiFiConfig, MQTTConfig

app = App(device="esp32")

app.config(
    wifi=WiFiConfig(ssid="YourSSID", password="YourPassword"),
    mqtt=MQTTConfig(broker="192.168.1.10"),
)


@app.get("/")
def index():
    return {
        "name": "VOLT OTA example",
        "version": "0.1.0",
        "device": app.device_id,
        "uptime": app.uptime(),
    }


@app.post("/ota/upload")
async def ota_upload(request):
    """
    Receive a firmware file and write it to flash.

    The CLI sends:
        POST /ota/upload
        Content-Type: application/octet-stream
        <file bytes>
    """
    if request.body is None:
        return {"error": "No file received"}, 400

    raw = request.body
    if isinstance(raw, dict):
        return {"error": "Expected raw file bytes, not JSON"}, 400

    try:
        # Write to temporary file first
        tmp = "/ota_pending.py"
        with open(tmp, "wb") as f:
            f.write(raw if isinstance(raw, bytes) else raw.encode())

        # Rename to main.py
        import uos
        uos.rename(tmp, "/main.py")

        print("[OTA] Firmware written. Rebooting in 2s…")
        await _delayed_reboot(2)
        return {"ok": True, "message": "Firmware updated — rebooting"}
    except Exception as e:
        return {"error": str(e)}, 500


async def _delayed_reboot(seconds: int):
    try:
        import uasyncio as asyncio
    except ImportError:
        import asyncio
    await asyncio.sleep(seconds)
    machine.reset()


# MQTT-triggered OTA (pull mode)
@app.subscribe("ota/command")
async def mqtt_ota_trigger(payload):
    """Trigger an OTA check when instructed via MQTT."""
    if payload.get("action") == "reboot":
        print("[OTA] Reboot triggered via MQTT")
        await _delayed_reboot(1)
    elif payload.get("action") == "version":
        await app.mqtt.publish("ota/version", {
            "version": "0.1.0",
            "device": app.device_id,
        })


if __name__ == "__main__":
    app.run()
