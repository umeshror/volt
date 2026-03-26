import sys
from unittest.mock import MagicMock

# --- MicroPython Hardware Mocks ---
sys.modules["machine"] = MagicMock()
sys.modules["network"] = MagicMock()
sys.modules["esp32"] = MagicMock()

import volt.http_server

# Monkey patch HTTPServer to always use 8085 on host
original_init = volt.http_server.HTTPServer.__init__
def mock_init(self, router, port=None):
    original_init(self, router, port=8085)
volt.http_server.HTTPServer.__init__ = mock_init # type: ignore

from volt.app import App
from volt.connectivity import WiFiConfig
import time

app = App(device="simulated-device")
app.config(wifi=WiFiConfig("SimulatorNetwork", "password"))

# Enable enterprise features
app.enable_ota()
app.crash_log(max_entries=5)

@app.get("/status")
def get_status():
    return {
        "status": "online",
        "uptime": app.uptime(),
        "device": app.device_id,
        "message": "VOLT Simulator Running"
    }

@app.post("/relay")
def post_relay(request):
    body = request.body or {}
    state = body.get("state", "off")
    print(f"[Simulator] Relay requested to turn {state}")
    return {"relay": state, "message": f"Relay toggled to {state}"}

@app.every(5)
def sim_heartbeat():
    print(f"[Simulator] Heartbeat tick. Uptime: {app.uptime()}s")

if __name__ == "__main__":
    print("=====================================================")
    print(" ⚡ VOLT Framework Simulator (Host Environment)      ")
    print("=====================================================")
    print("HTTP Server listening at: http://localhost:8085")
    print("Available Routes:")
    print("  GET  /status")
    print("  POST /relay    (JSON: {'state': 'on'})")
    print("  POST /ota/upload")
    print("=====================================================\n")
    app.run()
