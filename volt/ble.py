"""
volt/ble.py — BLE GATT server.

Wraps ubluetooth (MicroPython built-in) with a decorator-driven
GATT characteristic interface. Supports read + notify; write deferred to v0.2.
"""

from __future__ import annotations

import struct

try:
    from typing import Any, Callable
except ImportError:
    pass

try:
    import ubluetooth as bluetooth
    _BT_AVAILABLE = True
except ImportError:
    bluetooth = None
    _BT_AVAILABLE = False


# Standard VOLT service UUID (custom 128-bit)
_VOLT_SERVICE_UUID = bluetooth.UUID("6E400001-B5A3-F393-E0A9-E50E24DCCA9E") if _BT_AVAILABLE else None


class BLEServer:
    """
    BLE GATT server exposing router-registered characteristics.
    """

    def __init__(self, router: Any, device_id: str = "device") -> None:
        self._router = router
        self._device_id = device_id
        self._ble: Any = None
        self._connections: set[Any] = set()
        self._char_handles: dict[str, Any] = {}   # handle → characteristic name
        self._name_handles: dict[str, Any] = {}   # name → (value_handle, notify_handle)

    def start(self) -> None:
        """Initialise BLE, build GATT table, start advertising."""
        if not _BT_AVAILABLE:
            print("[VOLT/BLE] ubluetooth not available — BLE disabled")
            return

        self._ble = bluetooth.BLE()
        self._ble.active(True)
        self._ble.irq(self._irq)

        services = self._build_services()
        handles = self._ble.gatts_register_services(services)
        self._map_handles(handles)

        adv_name = f"VOLT-{self._device_id[-4:]}".encode()
        self._advertise(adv_name)
        print(f"[VOLT/BLE] Advertising as {adv_name.decode()}")

    def _build_services(self) -> tuple[Any, ...]:
        """Build a GATT service descriptor from registered BLE routes."""
        characteristics = []
        routes = getattr(self._router, "_ble_routes", {})
        for name in routes:
            char_uuid = bluetooth.UUID(hash(name) & 0xFFFF)
            flags = bluetooth.FLAG_READ | bluetooth.FLAG_NOTIFY
            characteristics.append((char_uuid, flags))
            self._char_handles[name] = char_uuid

        service = (_VOLT_SERVICE_UUID, characteristics)
        return (service,)

    def _map_handles(self, handles: Any) -> None:
        """Map handles returned by gatts_register_services to characteristic names."""
        routes = getattr(self._router, "_ble_routes", {})
        names = list(routes.keys())
        try:
            svc_handles = handles[0]
            for i, name in enumerate(names):
                self._name_handles[name] = svc_handles[i]
        except Exception as e:
            print(f"[VOLT/BLE] Handle mapping error: {e}")

    def _irq(self, event: int, data: Any) -> None:
        """Single BLE IRQ handler dispatching all events."""
        _IRQ_CENTRAL_CONNECT    = 1
        _IRQ_CENTRAL_DISCONNECT = 2
        _IRQ_GATTS_READ_REQUEST = 3

        if event == _IRQ_CENTRAL_CONNECT:
            conn_handle, _, _ = data
            self._connections.add(conn_handle)
            print(f"[VOLT/BLE] Connected: handle={conn_handle}")

        elif event == _IRQ_CENTRAL_DISCONNECT:
            conn_handle, _, _ = data
            self._connections.discard(conn_handle)
            print(f"[VOLT/BLE] Disconnected: handle={conn_handle}")
            self._advertise(f"VOLT-{self._device_id[-4:]}".encode())

        elif event == _IRQ_GATTS_READ_REQUEST:
            conn_handle, attr_handle = data
            self._serve_read(attr_handle)

    def _serve_read(self, attr_handle: Any) -> None:
        """Find the handler for this attribute and write the response."""
        for name, handle in self._name_handles.items():
            if handle == attr_handle:
                resolve_func = getattr(self._router, "resolve_ble", None)
                if resolve_func:
                    handler = resolve_func(name)
                    if handler:
                        try:
                            value = handler()
                            payload = self._encode(value)
                            if self._ble is not None:
                                self._ble.gatts_write(attr_handle, payload)
                        except Exception as e:
                            print(f"[VOLT/BLE] Read handler error for '{name}': {e}")
                break

    def notify_all(self, name: str, value: Any) -> None:
        """Send a notify to all connected centrals for a named characteristic."""
        handle = self._name_handles.get(name)
        if handle is None or self._ble is None:
            return
        payload = self._encode(value)
        self._ble.gatts_write(handle, payload)
        for conn in self._connections:
            try:
                self._ble.gatts_notify(conn, handle)
            except Exception:
                pass

    @staticmethod
    def _encode(value: Any) -> bytes:
        """Auto-convert Python value to BLE bytes."""
        if isinstance(value, bytes):
            return value
        if isinstance(value, float):
            return struct.pack("<f", value)
        if isinstance(value, int):
            return struct.pack("<i", value)
        if isinstance(value, str):
            return value.encode()
        return str(value).encode()

    def _advertise(self, name: bytes) -> None:
        """Start BLE advertising with the device name."""
        if self._ble is None:
            return
        adv_data = (
            b"\x02\x01\x06"                          # Flags: LE General Discoverable
            + bytes([len(name) + 1, 0x09])           # Complete local name
            + name
        )
        self._ble.gap_advertise(100_000, adv_data)
