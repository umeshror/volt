"""
examples/temperature_logger/main.py

Reads temperature and humidity from a DHT22 sensor
and publishes to MQTT every 30 seconds.
"""

from volt import App, MQTTConfig, WiFiConfig
from volt.sensors import DHT22

app = App(device="esp32")
sensor = DHT22(pin=4)

# No wifi config needed! Captive portal handles it if unconfigured.
# To hardcode, you can uncomment below:
# app.config(
#     wifi=WiFiConfig(ssid="YourSSID", password="YourPassword"),
#     mqtt=MQTTConfig(broker="192.168.1.10"),
# )

# Enable remote OTA flashing from Dashboard
app.enable_ota()


@app.on_connect
async def on_connected():
    print(f"[app] Connected — device ID: {app.device_id}")


@app.every(seconds=30)
async def publish_reading():
    await sensor.read()  # Non-blocking async hardware read
    data = sensor.to_dict()
    data["device"] = app.device_id
    data["uptime"] = app.uptime()
    if app.mqtt and app.mqtt.is_connected:
        await app.mqtt.publish("home/sensors/temperature", data)
        print(f"[app] Published: {data}")


@app.get("/status")
async def status():
    await sensor.read()
    return {
        "temp": sensor.temperature,
        "humidity": sensor.humidity,
        "uptime": app.uptime(),
        "device": app.device_id,
    }


if __name__ == "__main__":
    app.run()
