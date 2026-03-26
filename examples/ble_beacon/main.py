"""
examples/ble_beacon/main.py

BLE GATT server exposing temperature and humidity as readable characteristics.
"""
from volt import App, WiFiConfig
from volt.sensors import DHT22

app = App(device="esp32")
sensor = DHT22(pin=4)

# WiFi optional for BLE-only devices
app.config(wifi=WiFiConfig(ssid="YourSSID", password="YourPassword"))


@app.ble_characteristic("temperature")
def ble_temperature():
    """Read temperature; returned as float → packed as 4-byte IEEE 754."""
    return sensor.temperature


@app.ble_characteristic("humidity")
def ble_humidity():
    return sensor.humidity


@app.ble_characteristic("uptime")
def ble_uptime():
    return app.uptime()


# Still expose an HTTP endpoint for debugging
@app.get("/status")
def status():
    return {
        "temp": sensor.temperature,
        "humidity": sensor.humidity,
        "uptime": app.uptime(),
        "device": app.device_id,
    }


# Notify all BLE clients every 10s
@app.every(seconds=10)
async def ble_notify():
    # BLE server is accessible via app._ble_server after run() starts
    ble = app._ble_server
    if ble is not None:
        ble.notify_all("temperature", sensor.temperature)
        ble.notify_all("humidity", sensor.humidity)


if __name__ == "__main__":
    app.run()
