"""
examples/ota_update/main.py

Demonstrates VOLT v0.2's extremely simple one-line OTA enabling.
When called, endpoints /ota/upload (HTTP) and volt/<device_id>/ota (MQTT)
are instantly registered and protected against bad uploads.

Push firmware seamlessly:
volt ota push 192.168.X.X path/to/new_main.py
"""

from volt import App

app = App(device="esp32")

# 1. Powers up Captive Portal if WiFi is missing.
# 2. Exposes remote OTA flashing capabilities over HTTP and MQTT instantly.
app.enable_ota()


@app.get("/")
def index():
    return {
        "name": "VOLT v0.2 OTA Example",
        "device": app.device_id,
        "uptime": app.uptime(),
        "status": "Ready for OTA updates",
    }


if __name__ == "__main__":
    app.run()
