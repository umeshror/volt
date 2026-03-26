"""
volt/router.py — Central route registry.

Decoupled from transport: the same registry serves HTTP, MQTT, and BLE.
"""

import re


class Router:
    def __init__(self):
        # { (method: str, path: str): handler }
        self._http_routes: dict = {}
        # { pattern_str: (compiled_re, param_names, handler) }
        self._http_dynamic: list = []
        # { topic: str: handler }
        self._mqtt_routes: dict = {}
        # { name: str: handler }
        self._ble_routes: dict = {}

    # ------------------------------------------------------------------ HTTP

    def add_http_route(self, method: str, path: str, handler):
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

    def resolve_http(self, method: str, path: str):
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

    def add_mqtt_route(self, topic: str, handler):
        """Register an MQTT subscription handler."""
        self._mqtt_routes[topic] = handler

    def resolve_mqtt(self, topic: str):
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

    def add_ble_route(self, name: str, handler):
        """Register a BLE GATT characteristic handler."""
        self._ble_routes[name] = handler

    def resolve_ble(self, name: str):
        """Return handler for a BLE characteristic name, or None."""
        return self._ble_routes.get(name)
