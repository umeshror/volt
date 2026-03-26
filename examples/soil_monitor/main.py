"""
examples/soil_monitor/main.py

Monitors soil moisture and sends an MQTT alert when it drops below threshold.
"""

from volt import App, MQTTConfig, WiFiConfig
from volt.sensors import SoilMoisture

app = App(device="esp32")
soil = SoilMoisture(pin=34, adc_resolution=12, dry_value=3500, wet_value=1200)

ALERT_THRESHOLD = 30.0  # % — alert when moisture below this

# Captive portal will serve a setup page if WiFi is not configured.
# app.config(...)

# Persist last alert time to avoid repeat alerts
app.state.set("last_alert", 0)


@app.every(seconds=60)
async def report_moisture():
    await soil.read()
    pct = soil.percentage
    raw = soil.raw
    data = {"moisture_pct": pct, "raw": raw, "device": app.device_id}
    await app.mqtt.publish("garden/soil/reading", data)
    print(f"[app] Soil moisture: {pct:.1f}% (raw={raw})")


@app.when(lambda: soil.percentage < ALERT_THRESHOLD)
async def low_moisture_alert():
    await soil.read()  # Ensure fresh hardware reading
    import time

    last = app.state.get("last_alert", default=0)
    now = int(time.time())
    if now - last < 3600:  # throttle: max one alert per hour
        return
    app.state.set("last_alert", now)
    pct = soil.percentage
    await app.mqtt.publish(
        "garden/soil/alert",
        {
            "alert": "low_moisture",
            "moisture_pct": pct,
            "device": app.device_id,
        },
    )
    print(f"[app] 🚨 Low moisture alert: {pct:.1f}%")


@app.get("/soil")
async def get_soil():
    await soil.read()
    return soil.to_dict()


if __name__ == "__main__":
    app.run()
