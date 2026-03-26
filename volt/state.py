"""
volt/state.py — Flash-backed persistent key-value store.

Writes are synchronous (write-through). Uses atomic write (write to a temp
file then rename) to guard against corruption on power loss.
"""

from __future__ import annotations

from .exceptions import StateError

try:
    from typing import Any, Dict, List, Optional
except ImportError:
    pass

try:
    import ujson as json
except ImportError:
    import json

try:
    import uos as os
except ImportError:
    import os

_DEFAULT_PATH = "/state.json"
_TMP_PATH = "/state.tmp"


class State:
    """
    Persistent key-value store backed by flash (JSON file).

    Usage::

        state = State()
        state.set("last_watered", 1234567890)
        ts = state.get("last_watered", default=None)
        state.delete("last_watered")
        state.update({"temp": 22.5, "humidity": 60})
    """

    def __init__(self, path: str = _DEFAULT_PATH, tmp_path: str = _TMP_PATH) -> None:
        self._path: str = path
        self._tmp_path: str = tmp_path
        self._data: dict[str, Any] = {}
        self._sync_targets: list[str] = []
        self._mqtt_manager: Any | None = None
        self._http_url: str | None = None
        self._load()

    # ------------------------------------------------------------------ load / save

    def _load(self) -> None:
        try:
            with open(self._path) as f:
                self._data = json.loads(f.read())
        except Exception:
            self._data = {}

    def _save(self) -> None:
        """Atomic write: write to .tmp then rename."""
        try:
            content = json.dumps(self._data)
            with open(self._tmp_path, "w") as f:
                f.write(content)
            # Rename — atomic on most filesystems
            try:
                os.rename(self._tmp_path, self._path)
            except OSError:
                # If rename fails (e.g. cross-device link on test environments), attempt direct overwrite
                try:
                    with open(self._path, "w") as f:
                        f.write(content)
                except Exception as e:
                    raise StateError(f"Failed atomic rename and fallback overwrite: {e}") from e
        except Exception as e:
            print(f"[VOLT/State] Save error: {e}")
            raise StateError(f"Failed to persist state: {e}") from e

    # ------------------------------------------------------------------ public API

    def set(self, key: str, value: Any) -> None:
        """Set a key and persist to flash."""
        self._data[key] = value
        self._save()
        self._notify_sync(key, value)

    def get(self, key: str, default: Any = None) -> Any:
        """Get key value, returning `default` if absent."""
        return self._data.get(key, default)

    def delete(self, key: str) -> None:
        """Remove a key and persist."""
        self._data.pop(key, None)
        self._save()

    def update(self, mapping: dict[str, Any]) -> None:
        """Batch-update multiple keys atomically."""
        self._data.update(mapping)
        self._save()
        for k, v in mapping.items():
            self._notify_sync(k, v)

    def all(self) -> dict[str, Any]:
        """Return a copy of the entire state dict."""
        return dict(self._data)

    # ------------------------------------------------------------------ sync

    def sync_to(self, target: str, mqtt_manager: Any | None = None, url: str | None = None) -> None:
        """
        Enable auto-publish on every set().

        Args:
            target: 'mqtt' or 'http'
            mqtt_manager: MQTTManager instance (required for 'mqtt')
            url: HTTP endpoint (required for 'http')
        """
        if target == "mqtt":
            self._sync_targets.append("mqtt")
            if mqtt_manager is not None:
                self._mqtt_manager = mqtt_manager
        elif target == "http":
            self._sync_targets.append("http")
            if url is not None:
                self._http_url = url

    def _notify_sync(self, key: str, value: Any) -> None:
        for target in self._sync_targets:
            try:
                if target == "mqtt" and self._mqtt_manager is not None:
                    self._mqtt_manager.publish(f"state/{key}", {key: value})
                elif target == "http" and self._http_url is not None:
                    import urequests as requests  # type: ignore
                    requests.post(self._http_url, json={key: value})
            except Exception as e:
                print(f"[VOLT/State] Sync error ({target}): {e}")
