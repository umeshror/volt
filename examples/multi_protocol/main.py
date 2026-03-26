"""
examples/multi_protocol/main.py

Demonstrates the same sensor data accessible simultaneously via
HTTP, MQTT, and BLE — the core multi-protocol capability of VOLT.
"""
from volt import App, WiFiConfig, MQTTConfig
from volt.sensors import DHT22

app = App(device="esp32")
sensor = DHT22(pin=4)

app.config(
    wifi=WiFiConfig(ssid="YourSSID", password="YourPassword"),
    mqtt=MQTTConfig(broker="192.168.1.10"),
)

# ── One handler function, three protocols ── #

def get_reading():
    """Shared business logic: returns latest sensor data."""
    return {
        "temp": sensor.temperature,
        "humidity": sensor.humidity,
        "uptime": app.uptime(),
        "device": app.device_id,
    }


# HTTP — GET /sensor
@app.get("/sensor")
def http_reading():
    return get_reading()


# MQTT — subscribe to request topic, publish response
@app.subscribe("sensor/request")
async def mqtt_reading(payload):
    data = get_reading()
    await app.mqtt.publish("sensor/response", data)


# BLE — expose temperature and humidity characteristics
@app.ble_characteristic("temperature")
def ble_temp():
    return sensor.temperature


@app.ble_characteristic("humidity")
def ble_hum():
    return sensor.humidity


# Heartbeat via all protocols
@app.every(seconds=30)
async def heartbeat():
    data = get_reading()
    await app.mqtt.publish("device/heartbeat", data)
    if app._ble_server:
        app._ble_server.notify_all("temperature", data["temp"])
        app._ble_server.notify_all("humidity", data["humidity"])


if __name__ == "__main__":
    app.run()
