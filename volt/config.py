"""
volt/config.py — Persistent fleet configuration manager.
"""
from __future__ import annotations

try:
    from typing import Any
except ImportError:
    pass

from .state import State


class ConfigManager:
    """
    Manages device configuration securely via the state engine.
    Provides sane defaults for WiFi AP and MQTT bootstrapping.
    """

    def __init__(self, state: State) -> None:
        self._state = state
        self._defaults: dict[str, Any] = {
            "wifi_ssid": "",
            "wifi_password": "",
            "wifi_ap_ssid": "VOLT-Setup",
            # No default AP password: the AP starts open so users can connect
            # without credentials. The captive portal then collects WiFi config.
            # Set a password explicitly via config.set() if isolation is needed.
            "wifi_ap_password": "",
            "mqtt_broker": "",
            "mqtt_port": 1883,
            "mqtt_client_id": "volt-device",
        }

    def get(self, key: str) -> Any:
        """Get configuration value, falling back to default."""
        val = self._state.get(key)
        if val is None:
            return self._defaults.get(key)
        return val

    def set(self, key: str, value: Any) -> None:
        """Update and persist configuration value."""
        self._state.set(key, value)

    def is_configured(self) -> bool:
        """Returns True if the device has basic WiFi configuration injected."""
        ssid = self.get("wifi_ssid")
        return bool(ssid and isinstance(ssid, str) and len(ssid) > 0)
