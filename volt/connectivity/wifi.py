"""
volt/connectivity/wifi.py — WiFi manager.

Responsibilities:
  - Connect using network.WLAN(STA_IF) with exponential backoff
  - Fall back to AP mode after max_retries failures
  - Fire on_connect / on_disconnect callbacks
  - Background reconnection loop
"""

from __future__ import annotations

try:
    import uasyncio as asyncio
except ImportError:
    import asyncio

try:
    import network
except ImportError:
    network = None

try:
    from typing import Any, Callable
except ImportError:
    pass


class WiFiConfig:
    """WiFi connection parameters."""

    def __init__(
        self,
        ssid: str,
        password: str,
        max_retries: int = 10,
        ap_ssid: str = "volt-setup",
        ap_password: str = "",  # empty = open AP; captive portal handles auth
    ) -> None:
        self.ssid = ssid
        self.password = password
        self.max_retries = max_retries
        self.ap_ssid = ap_ssid
        self.ap_password = ap_password


async def connect_wifi(
    config: WiFiConfig,
    on_connect: list[Callable[..., Any]] | None = None,
    on_disconnect: list[Callable[..., Any]] | None = None,
    _monitor_task: list[Any] | None = None,
) -> bool:
    """
    Connect to WiFi with exponential backoff.

    Returns True on success, False if AP fallback was triggered.
    """
    if network is None:
        return False

    on_connect_cbs: list[Callable[..., Any]] = on_connect or []
    on_disconnect_cbs: list[Callable[..., Any]] = on_disconnect or []

    sta = network.WLAN(network.STA_IF)  # type: ignore
    sta.active(True)

    if sta.isconnected():
        await _fire_callbacks(on_connect_cbs)
        return True

    sta.connect(config.ssid, config.password)

    delay = 1
    for attempt in range(config.max_retries):
        if sta.isconnected():
            print(f"[VOLT/WiFi] Connected: {sta.ifconfig()[0]}")
            await _fire_callbacks(on_connect_cbs)
            # Cancel any existing monitor task before creating a new one
            if _monitor_task and _monitor_task[0] is not None:
                try:
                    _monitor_task[0].cancel()
                except Exception:
                    pass
            task_holder: list[Any] = [None]
            task_holder[0] = asyncio.create_task(  # type: ignore
                _monitor_connection(sta, config, on_connect_cbs, on_disconnect_cbs, task_holder)
            )
            if _monitor_task is not None:
                _monitor_task[0] = task_holder[0]
            return True
        print(f"[VOLT/WiFi] Attempt {attempt + 1}/{config.max_retries} — waiting {delay}s")
        await asyncio.sleep(delay)
        delay = min(delay * 2, 60)

    print("[VOLT/WiFi] Could not connect — starting AP fallback")
    await _start_ap(config)
    return False


async def _start_ap(config: WiFiConfig) -> None:
    if network is None:
        return
    ap = network.WLAN(network.AP_IF) # type: ignore
    ap.active(True)
    ap.config(essid=config.ap_ssid, password=config.ap_password)
    print(f"[VOLT/WiFi] AP mode: SSID={config.ap_ssid}")


async def _monitor_connection(
    sta: Any,
    config: WiFiConfig,
    on_connect: list[Callable[..., Any]],
    on_disconnect: list[Callable[..., Any]],
    task_holder: list[Any] | None = None,
) -> None:
    """Background task: silently reconnect if connection drops."""
    was_connected: bool = True
    while True:
        await asyncio.sleep(10)
        currently_connected: bool = sta.isconnected()
        if was_connected and not currently_connected:
            print("[VOLT/WiFi] Connection lost — reconnecting")
            await _fire_callbacks(on_disconnect)
            # Pass task_holder so reconnect won't spawn a duplicate monitor
            await connect_wifi(config, on_connect, on_disconnect, task_holder)
        was_connected = currently_connected


async def _fire_callbacks(callbacks: list[Callable[..., Any]]) -> None:
    for cb in callbacks:
        try:
            if asyncio.iscoroutinefunction(cb): # type: ignore
                await cb()
            else:
                cb()
        except Exception as e:
            print(f"[VOLT/WiFi] Callback error: {e}")
