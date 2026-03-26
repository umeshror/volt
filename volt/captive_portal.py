"""
volt/captive_portal.py — AP mode captive portal for initial configuration.
"""
from __future__ import annotations

try:
    import network
    import uasyncio as asyncio
except ImportError:
    import asyncio
    network = None
from typing import Any

from .config import ConfigManager
from .http_server import HTTPServer, Request
from .router import Router

_HTML = """
<!DOCTYPE html>
<html>
<head><meta name="viewport" content="width=device-width, initial-scale=1"></head>
<body>
<h2>VOLT Setup</h2>
<form action="/save" method="POST">
  <label>WiFi SSID:</label><br><input type="text" name="wifi_ssid"><br><br>
  <label>WiFi Password:</label><br><input type="password" name="wifi_password"><br><br>
  <label>MQTT Broker:</label><br><input type="text" name="mqtt_broker"><br><br>
  <input type="submit" value="Save & Reboot">
</form>
</body>
</html>
"""


class CaptivePortal:
    """
    Spins up an Access Point and an HTTP server to collect credentials.
    Reboots the device upon successful configuration.
    """

    def __init__(self, config: ConfigManager, port: int = 80) -> None:
        self._config = config
        self._router = Router()
        self._server = HTTPServer(self._router, port=port)
        self._ap: Any = None

        self._router.add_http_route("GET", "/", self._handle_index)
        self._router.add_http_route("POST", "/save", self._handle_save)

    async def start(self) -> None:
        """Activate AP and start listening for HTTP requests."""
        if network is not None:
            self._ap = network.WLAN(network.AP_IF) # type: ignore
            self._ap.active(True)
            self._ap.config(essid=self._config.get("wifi_ap_ssid"), password=self._config.get("wifi_ap_password"))
            print(f"[VOLT/Portal] AP Mode active: {self._config.get('wifi_ap_ssid')}")
        await self._server.start()

    def _handle_index(self, request: Request) -> Any:
        return _HTML

    def _handle_save(self, request: Request) -> Any:
        body = request.body
        if not isinstance(body, dict):
            decoded = body.decode() if isinstance(body, bytes) else str(body)
            body = self._server._parse_qs(decoded)

        if "wifi_ssid" in body:
            self._config.set("wifi_ssid", body["wifi_ssid"])
        if "wifi_password" in body:
            self._config.set("wifi_password", body["wifi_password"])
        if "mqtt_broker" in body:
            self._config.set("mqtt_broker", body["mqtt_broker"])

        print("[VOLT/Portal] Configuration saved. Rebooting...")
        try:
            import machine
            asyncio.create_task(self._delayed_reboot()) # type: ignore
        except ImportError:
            pass
        return "Configuration saved! Rebooting..."

    async def _delayed_reboot(self) -> None:
        await asyncio.sleep(1)
        import machine
        machine.reset()
