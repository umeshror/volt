"""
simulator.py — Run VOLT on the host (CPython) for local development and testing.

Installs typed hardware stubs that faithfully mimic the MicroPython API surface,
then boots the VOLT app on port 8085 instead of 80.
"""
import sys
import types
from unittest.mock import MagicMock

# --------------------------------------------------------------------------- #
# Typed hardware stubs — more faithful than bare MagicMock()                  #
# --------------------------------------------------------------------------- #

# --- machine ---
_machine = types.ModuleType("machine")
_machine.RISING = 1
_machine.FALLING = 2
_machine.IRQ_RISING = 1
_machine.IRQ_FALLING = 2


class _PinStub:
    IN = 0
    OUT = 1
    PULL_UP = 2

    def __init__(self, pin, mode=None, pull=None):
        self.pin = pin
        self._value = 0

    def value(self, val=None):
        if val is not None:
            self._value = val
        return self._value

    def irq(self, trigger=None, handler=None):
        pass

    def on(self):
        self._value = 1

    def off(self):
        self._value = 0


class _WDTStub:
    def __init__(self, id=0, timeout=8000):
        pass

    def feed(self):
        pass


_machine.Pin = _PinStub
_machine.ADC = MagicMock
_machine.WDT = _WDTStub
_machine.time_pulse_us = MagicMock(return_value=580)
_machine.reset = MagicMock()
_machine.freq = MagicMock(return_value=240_000_000)
_machine.sleep_us = MagicMock()
sys.modules["machine"] = _machine

# --- network ---
_network = types.ModuleType("network")
_network.STA_IF = 0
_network.AP_IF = 1


class _WLANStub:
    def __init__(self, interface=None):
        self._active = True
        self._connected = True

    def active(self, val=None):
        if val is not None:
            self._active = val
        return self._active

    def isconnected(self):
        return self._connected

    def connect(self, ssid, password):
        self._connected = True

    def config(self, *args, **kwargs):
        if args == ("mac",) or "mac" in kwargs:
            return b"\xde\xad\xbe\xef\x00\x01"
        return None

    def ifconfig(self):
        return ("127.0.0.1", "255.255.255.0", "127.0.0.1", "8.8.8.8")

    def status(self, param=None):
        if param == "rssi":
            return -55
        return 1010  # STAT_GOT_IP


_network.WLAN = _WLANStub
sys.modules["network"] = _network

# --- esp32 ---
sys.modules["esp32"] = MagicMock()

# --------------------------------------------------------------------------- #
# Port override — use 8085 on host instead of 80                              #
# --------------------------------------------------------------------------- #
import volt.http_server

_original_init = volt.http_server.HTTPServer.__init__


def _mock_init(self, router, port=None):
    _original_init(self, router, port=8085)


volt.http_server.HTTPServer.__init__ = _mock_init  # type: ignore

# --------------------------------------------------------------------------- #
# Application                                                                  #
# --------------------------------------------------------------------------- #
from volt.app import App
from volt.connectivity import WiFiConfig
import time

app = App(device="simulated-device")
app.config(wifi=WiFiConfig("SimulatorNetwork", "password"))

# Enable enterprise features
app.enable_ota()
app.crash_log(max_entries=5)


@app.get("/status")
def get_status():
    return {
        "status": "online",
        "uptime": app.uptime(),
        "device": app.device_id,
        "message": "VOLT Simulator Running",
    }


@app.post("/relay")
def post_relay(request):
    body = request.body or {}
    state = body.get("state", "off")
    print(f"[Simulator] Relay requested to turn {state}")
    return {"relay": state, "message": f"Relay toggled to {state}"}


@app.every(5)
def sim_heartbeat():
    print(f"[Simulator] Heartbeat tick. Uptime: {app.uptime()}s")


if __name__ == "__main__":
    print("=====================================================")
    print(" ⚡ VOLT Framework Simulator (Host Environment)      ")
    print("=====================================================")
    print("HTTP Server listening at: http://localhost:8085")
    print("Available Routes:")
    print("  GET  /status")
    print("  POST /relay    (JSON: {'state': 'on'})")
    print("  POST /ota/upload")
    print("=====================================================\n")
    app.run()
