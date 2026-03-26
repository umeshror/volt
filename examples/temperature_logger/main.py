"""
examples/temperature_logger/main.py

Reads temperature and humidity from a DHT22 sensor
and publishes to MQTT every 30 seconds.
"""
from volt import App, WiFiConfig, MQTTConfig
from volt.sensors import DHT22

app = App(device="esp32")
sensor = DHT22(pin=4)

app.config(
    wifi=WiFiConfig(ssid="YourSSID", password="YourPassword"),
    mqtt=MQTTConfig(broker="192.168.1.10"),
)


@app.on_connect
async def on_connected():
    print(f"[app] Connected — device ID: {app.device_id}")


@app.every(seconds=30)
async def publish_reading():
    data = sensor.to_dict()
    data["device"] = app.device_id
    data["uptime"] = app.uptime()
    await app.mqtt.publish("home/sensors/temperature", data)
    print(f"[app] Published: {data}")


@app.get("/status")
def status():
    return {
        "temp": sensor.temperature,
        "humidity": sensor.humidity,
        "uptime": app.uptime(),
        "device": app.device_id,
    }


if __name__ == "__main__":
    app.run()
