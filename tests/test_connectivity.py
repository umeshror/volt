"""
tests/test_connectivity.py — WiFiConfig, MQTTConfig, and MQTTManager tests.
"""

import pytest
from volt.connectivity.wifi import WiFiConfig
from volt.connectivity.mqtt import MQTTConfig, MQTTManager
from volt.router import Router


# ------------------------------------------------------------------ WiFiConfig

def test_wifi_config_stores_ssid():
    """WiFiConfig should store ssid correctly."""
    cfg = WiFiConfig(ssid="MyNetwork", password="secret")
    assert cfg.ssid == "MyNetwork"


def test_wifi_config_defaults():
    """WiFiConfig defaults should match spec."""
    cfg = WiFiConfig(ssid="net", password="pw")
    assert cfg.max_retries == 10
    assert cfg.ap_ssid == "volt-setup"


def test_wifi_config_custom():
    """WiFiConfig should accept custom values."""
    cfg = WiFiConfig(ssid="n", password="p", max_retries=3, ap_ssid="my-ap")
    assert cfg.max_retries == 3
    assert cfg.ap_ssid == "my-ap"


# ------------------------------------------------------------------ MQTTConfig

def test_mqtt_config_defaults():
    """MQTTConfig port should default to 1883."""
    cfg = MQTTConfig(broker="192.168.1.10")
    assert cfg.port == 1883
    assert cfg.client_id == "volt-device"
    assert cfg.keepalive == 60
    assert cfg.user is None
    assert cfg.password is None


def test_mqtt_config_custom():
    """Custom MQTTConfig values should be stored correctly."""
    cfg = MQTTConfig(broker="mqtt.example.com", port=8883,
                     client_id="my-id", user="admin", password="pass")
    assert cfg.broker == "mqtt.example.com"
    assert cfg.port == 8883
    assert cfg.client_id == "my-id"
    assert cfg.user == "admin"


# ------------------------------------------------------------------ MQTTManager

def test_connect_fires_on_connect_callback():
    """on_connect callback should be called once connection succeeds."""
    import asyncio
    cfg = MQTTConfig(broker="127.0.0.1")
    fired = []

    def on_conn():
        fired.append(True)

    manager = MQTTManager(cfg, on_connect=[on_conn])

    async def run():
        await manager.connect()

    asyncio.run(run())
    assert len(fired) == 1


def test_publish_queues_when_disconnected():
    """Messages published while disconnected should go into the offline queue."""
    import os
    cfg = MQTTConfig(broker="127.0.0.1")
    manager = MQTTManager(cfg)
    manager._connected = False  # force disconnected state

    manager.publish("home/temp", {"value": 22.5})

    assert len(manager._queue) == 1
    assert manager._queue[0]["topic"] == "home/temp"

    # Cleanup
    try:
        os.remove("/mqtt_queue.json")
    except FileNotFoundError:
        pass


def test_mqtt_manager_dispatches_to_router():
    """Incoming MQTT messages should be dispatched to the registered handler."""
    import json
    cfg = MQTTConfig(broker="127.0.0.1")
    router = Router()
    received = []

    def my_handler(payload):
        received.append(payload)

    router.add_mqtt_route("home/temp", my_handler)
    manager = MQTTManager(cfg, router=router)

    # Simulate incoming message
    manager._on_message(b"home/temp", json.dumps({"temp": 23.0}).encode())

    assert len(received) == 1
    assert received[0]["temp"] == 23.0
