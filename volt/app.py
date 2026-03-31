"""
volt/app.py — The App class: central orchestrator for VOLT.

Wires all subsystems together and owns the uasyncio event loop.
This module is designed to run on MicroPython (ESP32/Pico W) but is
structured so the host test suite can import it against mocked stubs.
"""

from __future__ import annotations

from .exceptions import VoltError
from .router import Router

try:
    from collections.abc import Callable
    from typing import Any, List, Optional
except ImportError:
    pass


class App:
    """
    Central VOLT application object.

    Usage::

        from volt import App, WiFiConfig, MQTTConfig

        app = App()
        app.config(wifi=WiFiConfig(ssid="net", password="pw"),
                   mqtt=MQTTConfig(broker="192.168.1.1"))

        @app.get("/status")
        def status():
            return {"ok": True}

        app.run()
    """

    def __init__(self, device: str = "esp32") -> None:
        self.device: str = device
        self._router: Router = Router()
        self._scheduler: Any | None = None
        self._wifi_config: Any | None = None
        self._mqtt_config: Any | None = None
        self._mqtt_manager: Any | None = None
        self._http_server: Any | None = None
        self._ble_server: Any | None = None
        self._state: Any | None = None
        self._health: Any | None = None
        self._watchdog: Any | None = None
        self._telemetry: Any | None = None
        self._ota: Any | None = None
        self._on_connect_handlers: list[Callable[..., Any]] = []
        self._on_disconnect_handlers: list[Callable[..., Any]] = []
        self._boot_time: int | None = None
        self._crash_log: Any | None = None

        self._pending_every: list[tuple[float, Callable[..., Any]]] = []
        self._pending_pin: list[tuple[int, Any, Callable[..., Any]]] = []
        self._pending_when: list[tuple[Callable[[], bool], Callable[..., Any]]] = []

    # ------------------------------------------------------------------ config

    def config(self, wifi: Any | None = None, mqtt: Any | None = None) -> App:
        """Store WiFi and MQTT configuration."""
        if wifi is not None:
            self._wifi_config = wifi
        if mqtt is not None:
            self._mqtt_config = mqtt
        return self

    # ------------------------------------------------------------------ HTTP decorators

    def get(self, path: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Register an HTTP GET handler."""
        def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            self._router.add_http_route("GET", path, fn)
            return fn
        return decorator

    def post(self, path: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Register an HTTP POST handler."""
        def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            self._router.add_http_route("POST", path, fn)
            return fn
        return decorator

    def put(self, path: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Register an HTTP PUT handler."""
        def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            self._router.add_http_route("PUT", path, fn)
            return fn
        return decorator

    def delete(self, path: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Register an HTTP DELETE handler."""
        def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            self._router.add_http_route("DELETE", path, fn)
            return fn
        return decorator

    def ws(self, path: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Register a WebSocket handler."""
        def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            self._router.add_http_route("WS", path, fn)
            return fn
        return decorator

    # ------------------------------------------------------------------ MQTT decorators

    def subscribe(self, topic: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Register an MQTT subscription handler."""
        def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            self._router.add_mqtt_route(topic, fn)
            return fn
        return decorator

    # ------------------------------------------------------------------ BLE decorators

    def ble_characteristic(self, name: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Register a BLE GATT characteristic read handler."""
        def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            self._router.add_ble_route(name, fn)
            return fn
        return decorator

    # ------------------------------------------------------------------ Scheduler decorators

    def every(self, seconds: float) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Register a periodic async task."""
        def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            if self._scheduler is None:
                self._pending_every.append((seconds, fn))
            else:
                self._scheduler.add_every(seconds, fn)
            return fn
        return decorator

    def on_pin(self, pin: int, trigger: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Register a hardware interrupt task."""
        def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            self._pending_pin.append((pin, trigger, fn))
            return fn
        return decorator

    def when(self, condition_fn: Callable[[], bool]) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Register a threshold-polling task."""
        def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            self._pending_when.append((condition_fn, fn))
            return fn
        return decorator

    # ------------------------------------------------------------------ Lifecycle hooks

    def on_connect(self, fn: Callable[..., Any]) -> Callable[..., Any]:
        """Decorator: register a callback for WiFi/MQTT connect events."""
        self._on_connect_handlers.append(fn)
        return fn

    def on_disconnect(self, fn: Callable[..., Any]) -> Callable[..., Any]:
        """Decorator: register a callback for WiFi/MQTT disconnect events."""
        self._on_disconnect_handlers.append(fn)
        return fn

    # ------------------------------------------------------------------ Utility

    def watchdog(self, timeout: int = 30) -> None:
        """Enable hardware WDT with the given timeout in seconds."""
        from .health import Watchdog
        self._watchdog = Watchdog(timeout)

    def crash_log(self, max_entries: int = 10) -> None:
        """Enable flash-backed crash logging."""
        from .health import CrashLog
        self._crash_log = CrashLog(max_entries=max_entries)

    def telemetry(self, interval: int = 300) -> None:
        """Enable periodic MQTT telemetry publishing."""
        from .telemetry import Telemetry
        self._telemetry = Telemetry(self)
        self._telemetry.auto_publish(interval)

    def enable_ota(self) -> None:
        """Enable remote OTA triggers via HTTP POST and MQTT."""
        from .ota import OTAManager
        self._ota = OTAManager()

        @self.post("/ota/upload")
        def _ota_http(request: Any) -> dict[str, Any]:
            if not getattr(request, "json", None) or "url" not in request.json:
                return {"error": "Missing 'url' in JSON payload"}
            if self._ota:
                success = self._ota.install_update(request.json["url"])
                if success:
                    self._ota.reboot()
                    return {"status": "rebooting"}
            return {"error": "OTA failed"}

        # Defer device_id resolution to message-handling time so that the real
        # MAC-derived ID is used even when enable_ota() is called before run().
        @self.subscribe(f"volt/+/ota")
        def _ota_mqtt(payload: Any) -> None:
            if isinstance(payload, dict) and "url" in payload and self._ota:
                success = self._ota.install_update(payload["url"])
                if success:
                    self._ota.reboot()

    def health_check(self, interval: int = 60, url: str | None = None) -> None:
        """Enable periodic HTTP health-check ping."""
        from .health import HealthCheck
        self._health = HealthCheck(
            interval=interval,
            url=url,
            on_failure=self._on_disconnect_handlers,
            crash_log=self._crash_log,  # wire through so failures are crash-logged
        )

    def uptime(self) -> int:
        """Return seconds since boot."""
        try:
            import time
            if self._boot_time is None:
                return 0
            return int(time.time()) - self._boot_time
        except Exception:
            return 0

    @property
    def device_id(self) -> str:
        """Unique device identifier derived from MAC address."""
        try:
            import network
            mac = network.WLAN().config("mac")
            return "".join(f"{b:02x}" for b in mac)
        except Exception:
            return "volt-device"

    @property
    def state(self) -> Any:
        """Lazy-load the persistent state store."""
        if self._state is None:
            from .state import State
            self._state = State()
        return self._state

    @property
    def mqtt(self) -> Any | None:
        """Access the MQTT manager (available after run())."""
        return self._mqtt_manager

    @property
    def router(self) -> Router:
        return self._router

    # ------------------------------------------------------------------ run()

    def run(self) -> None:
        """
        Boot all subsystems and enter the uasyncio event loop.

        Boot sequence:
          1. Record boot time
          2. Connect WiFi (retry + AP fallback)
          3. Connect MQTT (if configured)
          4. Start HTTP server
          5. Start BLE GATT server (if characteristics registered)
          6. Start scheduler tasks
          7. Enter uasyncio.run() — never returns
        """
        try:
            import time
            self._boot_time = int(time.time())
        except Exception:
            pass

        # Resolve asyncio once — avoids run() and _main() binding different modules
        # on environments where both uasyncio and asyncio are importable.
        try:
            import uasyncio as _asyncio
        except ImportError:
            import asyncio as _asyncio  # type: ignore[no-redef]

        _asyncio.run(self._main(_asyncio))

    async def _main(self, asyncio: Any) -> None:
        from .scheduler import Scheduler
        self._scheduler = Scheduler()
        if self._crash_log is not None:
            self._scheduler.set_crash_log(self._crash_log)

        from .config import ConfigManager
        config_mgr = ConfigManager(self.state)

        # 1. Captive Portal (if totally unconfigured)
        if await self._init_captive_portal(config_mgr):
            return  # Blocked in captive portal

        # 2. Connectivity
        await self._init_wifi(config_mgr)
        await self._init_mqtt(config_mgr)

        # 3. Servers & Tasks
        self._init_servers(asyncio)
        self._init_tasks()

        # 4. Start all scheduled tasks
        await self._scheduler.run()

    # ------------------------------------------------------------------ Boot helpers

    async def _init_captive_portal(self, config_mgr: Any) -> bool:
        if self._wifi_config is None and not config_mgr.is_configured():
            from .captive_portal import CaptivePortal
            portal = CaptivePortal(config_mgr)
            await portal.start()
            return True
        return False

    async def _init_wifi(self, config_mgr: Any) -> None:
        if self._wifi_config is None:
            from .connectivity.wifi import WiFiConfig
            self._wifi_config = WiFiConfig(
                ssid=config_mgr.get("wifi_ssid") or "",
                password=config_mgr.get("wifi_password") or "",
            )

        from .connectivity.wifi import connect_wifi
        await connect_wifi(
            self._wifi_config,
            on_connect=self._on_connect_handlers,
            on_disconnect=self._on_disconnect_handlers,
        )

    async def _init_mqtt(self, config_mgr: Any) -> None:
        if self._mqtt_config is None and config_mgr.get("mqtt_broker"):
            from .connectivity.mqtt import MQTTConfig
            self._mqtt_config = MQTTConfig(
                broker=config_mgr.get("mqtt_broker"),
            )

        if self._mqtt_config is not None:
            from .connectivity.mqtt import MQTTManager
            self._mqtt_manager = MQTTManager(
                self._mqtt_config,
                router=self._router,
                on_connect=self._on_connect_handlers,
                on_disconnect=self._on_disconnect_handlers,
            )
            await self._mqtt_manager.connect()

    def _init_servers(self, asyncio: Any) -> None:
        from .http_server import HTTPServer
        self._http_server = HTTPServer(self._router)

        async def _http_server_task() -> None:
            """Wrapper so HTTP server errors are logged, not silently dropped."""
            try:
                await self._http_server.start()  # type: ignore
            except Exception as e:
                print(f"[VOLT/HTTP] Server crashed: {e}")
                if self._crash_log is not None:
                    try:
                        self._crash_log.log(type(e).__name__, str(e))
                    except Exception:
                        pass

        asyncio.create_task(_http_server_task())  # type: ignore

        if hasattr(self._router, "_ble_routes") and self._router._ble_routes:
            from .ble import BLEServer
            self._ble_server = BLEServer(self._router, self.device_id)
            self._ble_server.start()

    def _init_tasks(self) -> None:
        if not self._scheduler:
            return
        for seconds, fn in self._pending_every:
            self._scheduler.add_every(seconds, fn)
        for pin, trigger, fn in self._pending_pin:
            self._scheduler.add_pin(pin, trigger, fn)
        for condition_fn, fn in self._pending_when:
            self._scheduler.add_when(condition_fn, fn)
