"""
volt/router.py — Central route registry.

Decoupled from transport: the same registry serves HTTP, MQTT, and BLE.
"""

from __future__ import annotations

import re

try:
    from typing import Any, Dict, List, Optional, Tuple
except ImportError:
    pass


class Router:
    def __init__(self) -> None:
        self._http_routes: dict[Any, Any] = {}
        self._http_dynamic: list[Any] = []
        self._mqtt_routes: dict[Any, Any] = {}
        self._ble_routes: dict[Any, Any] = {}

    # ------------------------------------------------------------------ HTTP

    def add_http_route(self, method: str, path: str, handler: Any) -> None:
        """Register an HTTP handler for (method, path)."""
        method = method.upper()
        if "{" in path:
            # Dynamic route — compile to regex
            param_names = re.findall(r"\{(\w+)\}", path)
            pattern = re.sub(r"\{(\w+)\}", r"([^/]+)", path)
            pattern = f"^{pattern}$"
            self._http_dynamic.append((method, re.compile(pattern), param_names, handler))
        else:
            self._http_routes[(method, path)] = handler

    def resolve_http(self, method: str, path: str) -> tuple[Any, dict[str, str]] | None:
        """
        Return (handler, params_dict) for a matching route, or None.
        Strips query string from path before matching.
        """
        method = method.upper()
        # Strip query string
        if "?" in path:
            path = path.split("?", 1)[0]

        # Static match first
        handler = self._http_routes.get((method, path))
        if handler:
            return handler, {}

        # Dynamic match
        for route_method, pattern, param_names, handler in self._http_dynamic:
            if route_method != method:
                continue
            m = pattern.match(path)
            if m:
                params = dict(zip(param_names, m.groups()))
                return handler, params

        return None

    # ------------------------------------------------------------------ MQTT

    def add_mqtt_route(self, topic: str, handler: Any) -> None:
        """Register an MQTT subscription handler. Topic is always stored as str."""
        # Normalise to str so inbound topics (which arrive as str or bytes) always
        # match correctly regardless of how the pattern was originally provided.
        if isinstance(topic, (bytes, bytearray)):
            topic = topic.decode()
        self._mqtt_routes[topic] = handler

    def resolve_mqtt(self, topic: str) -> tuple[Any, None] | None:
        """
        Return (handler, None) for a matching MQTT topic, or None.
        Supports '+' (single-level) and '#' (multi-level) wildcards.
        """
        # Exact match
        if topic in self._mqtt_routes:
            return self._mqtt_routes[topic], None

        # Wildcard match
        for pattern, handler in self._mqtt_routes.items():
            if self._mqtt_match(pattern, topic):
                return handler, None

        return None

    @staticmethod
    def _mqtt_match(pattern: str, topic: str) -> bool:
        """Match MQTT topic against a pattern with + and # wildcards."""
        p_parts = pattern.split("/")
        t_parts = topic.split("/")
        pi, ti = 0, 0
        while pi < len(p_parts) and ti < len(t_parts):
            p = p_parts[pi]
            if p == "#":
                return True
            if p != "+" and p != t_parts[ti]:
                return False
            pi += 1
            ti += 1
        return pi == len(p_parts) and ti == len(t_parts)

    # ------------------------------------------------------------------ BLE

    def add_ble_route(self, name: str, handler: Any) -> None:
        """Register a BLE GATT characteristic handler."""
        self._ble_routes[name] = handler

    def resolve_ble(self, name: str) -> Any | None:
        """Return handler for a BLE characteristic name, or None."""
        return self._ble_routes.get(name)
