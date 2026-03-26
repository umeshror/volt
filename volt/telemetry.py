"""
volt/telemetry.py — Device health and resource monitoring.
"""

from __future__ import annotations

try:
    from typing import Any
except ImportError:
    pass

class Telemetry:
    """
    Collects system metrics (RAM, storage, uptime) for fleet monitoring.
    """
    
    def __init__(self, app: Any) -> None:
        self._app = app
        self._metrics: dict[str, Any] = {}
        
    def collect(self) -> dict[str, Any]:
        """Gather current system metrics directly from hardware bindings."""
        # 1. Uptime
        self._metrics["uptime"] = self._app.uptime()
        
        # 2. Memory
        try:
            import gc  # type: ignore
            gc.collect()
            self._metrics["mem_free"] = gc.mem_free()  # type: ignore
            self._metrics["mem_alloc"] = gc.mem_alloc()  # type: ignore
        except (ImportError, AttributeError, NameError):
            self._metrics["mem_free"] = 0
            self._metrics["mem_alloc"] = 0
            
        # 3. Disk Space
        try:
            import os  # type: ignore
            st = os.statvfs("/")
            self._metrics["disk_free"] = st[0] * st[3]
        except (ImportError, AttributeError, OSError, NameError):
            self._metrics["disk_free"] = 0
            
        # 4. WiFi RSSI
        self._metrics["rssi"] = 0
        try:
            import network  # type: ignore
            sta = network.WLAN(network.STA_IF)
            if sta.active() and sta.isconnected():
                self._metrics["rssi"] = sta.status("rssi")
        except Exception:
            pass
            
        return self._metrics

    def auto_publish(self, interval: int = 300) -> None:
        """Schedule periodic MQTT publishing of telemetry data."""
        self._app.every(interval)(self._publish_task)
            
    async def _publish_task(self) -> None:
        if self._app.mqtt is not None:
            metrics = self.collect()
            topic = f"telemetry/{self._app.device_id}"
            self._app.mqtt.publish(topic, metrics)
