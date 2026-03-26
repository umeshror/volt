"""
volt/health.py — Watchdog, crash logging, and health check.
"""

from __future__ import annotations

from .exceptions import VoltError

try:
    from collections.abc import Callable
    from typing import Any, Dict, List, Optional
except ImportError:
    pass

try:
    import ujson as json
except ImportError:
    import json

try:
    import uasyncio as asyncio
except ImportError:
    import asyncio

import time

_CRASH_LOG_PATH = "/crashes.json"


class Watchdog:
    """
    Hardware watchdog wrapper.

    VOLT feeds it automatically from the main event loop heartbeat.
    If not fed within `timeout` seconds, the device reboots.
    """

    def __init__(self, timeout: int = 30) -> None:
        self._timeout: int = timeout
        self._wdt: Any | None = None
        self._start()

    def _start(self) -> None:
        try:
            from machine import WDT
            self._wdt = WDT(id=0, timeout=self._timeout * 1000)
            print(f"[VOLT/WDT] Enabled (timeout={self._timeout}s)")
        except Exception as e:
            print(f"[VOLT/WDT] Not available: {e}")

    def feed(self) -> None:
        """Feed the watchdog to prevent reboot."""
        if self._wdt is not None:
            try:
                self._wdt.feed()
            except Exception:
                pass


class CrashLog:
    """
    Flash-backed crash log.

    On unhandled exception, writes a fully structured JSON entry to /crashes.json.
    Rotates entries — keeps last `max_entries` only.
    """

    def __init__(self, max_entries: int = 10, path: str = _CRASH_LOG_PATH) -> None:
        self._path: str = path
        self._max_entries: int = max_entries
        self._entries: list[dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        try:
            with open(self._path) as f:
                self._entries = json.loads(f.read())
        except Exception:
            self._entries = []

    def _save(self) -> None:
        try:
            with open(self._path, "w") as f:
                f.write(json.dumps(self._entries))
        except Exception as e:
            print(f"[VOLT/CrashLog] Save error: {e}")

    def log(self, exception_type: str, message: str, traceback: str = "") -> None:
        """Append a crash entry and rotate if necessary."""
        entry: dict[str, Any] = {
            "timestamp": int(time.time()),
            "exception": exception_type,
            "message": message,
            "traceback": traceback,
        }
        self._entries.append(entry)
        # Rotate
        if len(self._entries) > self._max_entries:
            self._entries = self._entries[-self._max_entries:]
        self._save()
        print(f"[VOLT/CrashLog] Logged: {exception_type}: {message}")

    def all(self) -> list[dict[str, Any]]:
        """Return all crash log entries."""
        return list(self._entries)

    def clear(self) -> None:
        """Clear all crash log entries."""
        self._entries = []
        self._save()


class HealthCheck:
    """
    Periodic HTTP heartbeat to a configured URL.

    Fires on_disconnect callbacks after `consecutive_failures_threshold`
    consecutive failures.
    """

    def __init__(
        self,
        interval: int = 60,
        url: str | None = None,
        on_failure: list[Callable[..., Any]] | None = None,
        consecutive_failures_threshold: int = 3,
        crash_log: CrashLog | None = None,
    ) -> None:
        self._interval: int = interval
        self._url: str | None = url
        self._on_failure: list[Callable[..., Any]] = on_failure or []
        self._threshold: int = consecutive_failures_threshold
        self._crash_log: CrashLog | None = crash_log
        self._consecutive_failures: int = 0

    async def start(self) -> None:
        """Run the periodic health check loop."""
        if self._url is None:
            return
        while True:
            await asyncio.sleep(self._interval)
            await self._ping()

    async def _ping(self) -> None:
        try:
            import urequests as requests  # type: ignore
            resp = requests.get(self._url, timeout=10)
            resp.close()
            self._consecutive_failures = 0
        except Exception as e:
            self._consecutive_failures += 1
            msg = f"Health check failed ({self._consecutive_failures}): {e}"
            print(f"[VOLT/Health] {msg}")
            if self._crash_log:
                self._crash_log.log("HealthCheckFailure", msg)
            if self._consecutive_failures >= self._threshold:
                await self._fire_failure_callbacks()

    async def _fire_failure_callbacks(self) -> None:
        for cb in self._on_failure:
            try:
                if asyncio.iscoroutinefunction(cb):
                    await cb()
                else:
                    cb()
            except Exception as e:
                print(f"[VOLT/Health] Callback error: {e}")
