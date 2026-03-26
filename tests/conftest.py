"""
tests/conftest.py — MicroPython stub modules for host-side testing.

Installs lightweight mock modules for every MicroPython built-in so the
framework can be imported and tested on CPython without any hardware.
"""

import sys
import asyncio
import json
import os
import types
from unittest.mock import MagicMock, AsyncMock

# --------------------------------------------------------------------------- #
# uasyncio → asyncio                                                           #
# --------------------------------------------------------------------------- #
sys.modules.setdefault("uasyncio", asyncio)

# --------------------------------------------------------------------------- #
# ujson → json                                                                 #
# --------------------------------------------------------------------------- #
sys.modules.setdefault("ujson", json)

# --------------------------------------------------------------------------- #
# uos → os                                                                     #
# --------------------------------------------------------------------------- #
sys.modules.setdefault("uos", os)

# --------------------------------------------------------------------------- #
# network stub                                                                  #
# --------------------------------------------------------------------------- #
_network = types.ModuleType("network")
_network.STA_IF = 0
_network.AP_IF = 1

_wlan_stub_connected = True  # default: always connected


class _WLANStub:
    def __init__(self, interface=None):
        self._active = False
        self._connected = _wlan_stub_connected

    def active(self, val=None):
        if val is not None:
            self._active = val
        return self._active

    def isconnected(self):
        return self._connected

    def connect(self, ssid, password):
        self._connected = True

    def disconnect(self):
        self._connected = False

    def config(self, *args, **kwargs):
        if args == ("mac",) or "mac" in kwargs:
            return b"\xaa\xbb\xcc\xdd\xee\xff"
        if args == ("essid",):
            return "TestSSID"
        return None

    def ifconfig(self):
        return ("192.168.1.100", "255.255.255.0", "192.168.1.1", "8.8.8.8")

    def status(self):
        return 1010  # STAT_GOT_IP


_network.WLAN = _WLANStub
sys.modules["network"] = _network

# --------------------------------------------------------------------------- #
# machine stub                                                                  #
# --------------------------------------------------------------------------- #
_machine = types.ModuleType("machine")
_machine.RISING = 1
_machine.FALLING = 2
_machine.IRQ_RISING = 1
_machine.IRQ_FALLING = 2


class _PinStub:
    IN = 0
    OUT = 1
    PULL_UP = 2
    IRQ_RISING = 1
    IRQ_FALLING = 2

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


class _ADCStub:
    def __init__(self, pin):
        self.pin = pin

    def read(self):
        return 2048

    def read_u16(self):
        return 32768


class _WDTStub:
    def __init__(self, id=0, timeout=8000):
        pass

    def feed(self):
        pass


def _time_pulse_us(pin, pulse_level, timeout_us=1000000):
    return 580  # ~10 cm at speed of sound


_machine.Pin = _PinStub
_machine.ADC = _ADCStub
_machine.WDT = _WDTStub
_machine.time_pulse_us = _time_pulse_us
_machine.reset = MagicMock()
_machine.freq = MagicMock(return_value=240_000_000)
sys.modules["machine"] = _machine

# --------------------------------------------------------------------------- #
# dht stub                                                                      #
# --------------------------------------------------------------------------- #
_dht = types.ModuleType("dht")


class _DHT22Stub:
    def __init__(self, pin):
        self.pin = pin
        self._temp = 22.5
        self._humidity = 55.0

    def measure(self):
        pass

    def temperature(self):
        return self._temp

    def humidity(self):
        return self._humidity


_dht.DHT22 = _DHT22Stub
sys.modules["dht"] = _dht

# --------------------------------------------------------------------------- #
# umqtt stub                                                                    #
# --------------------------------------------------------------------------- #
_umqtt = types.ModuleType("umqtt")
_umqtt_simple = types.ModuleType("umqtt.simple")


class _MQTTClientStub:
    def __init__(self, client_id, server, port=1883, user=None, password=None,
                 keepalive=60):
        self.client_id = client_id
        self.server = server
        self.port = port
        self._published: list = []
        self._subscribed: list = []
        self._connected = False
        self.cb = None

    def set_callback(self, cb):
        self.cb = cb

    def connect(self):
        self._connected = True

    def disconnect(self):
        self._connected = False

    def subscribe(self, topic):
        self._subscribed.append(topic)

    def publish(self, topic, msg, retain=False, qos=0):
        self._published.append((topic, msg))

    def check_msg(self):
        pass

    def ping(self):
        pass


_umqtt_simple.MQTTClient = _MQTTClientStub
sys.modules["umqtt"] = _umqtt
sys.modules["umqtt.simple"] = _umqtt_simple

# --------------------------------------------------------------------------- #
# ubluetooth stub                                                               #
# --------------------------------------------------------------------------- #
_ubluetooth = types.ModuleType("ubluetooth")
_ubluetooth.BLE = MagicMock
_ubluetooth.UUID = MagicMock
_ubluetooth.FLAG_READ = 0x0002
_ubluetooth.FLAG_NOTIFY = 0x0010
_ubluetooth.FLAG_WRITE = 0x0008
sys.modules["ubluetooth"] = _ubluetooth
