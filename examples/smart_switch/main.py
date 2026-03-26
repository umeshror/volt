"""
examples/smart_switch/main.py

HTTP + MQTT controlled GPIO relay (smart switch).
"""

from machine import Pin

from volt import App, MQTTConfig, WiFiConfig

app = App(device="esp32")
relay = Pin(26, Pin.OUT)
relay.off()

# Captive portal handles WiFi/MQTT automatically out of the box!
# app.config(
#     wifi=WiFiConfig(ssid="YourSSID", password="YourPassword"),
#     mqtt=MQTTConfig(broker="192.168.1.10"),
# )


def _set_relay(state: str):
    if state in ("on", "1", "true"):
        relay.on()
        return "on"
    else:
        relay.off()
        return "off"


# HTTP control
@app.post("/relay")
def http_set_relay(request):
    body = request.body or {}
    state = body.get("state", "off")
    result = _set_relay(state)
    return {"relay": result}


@app.get("/relay")
def http_get_relay():
    return {"relay": "on" if relay.value() else "off"}


# MQTT control
@app.subscribe("home/switch/set")
def mqtt_set_relay(payload):
    state = payload.get("state", "off") if isinstance(payload, dict) else str(payload)
    result = _set_relay(state)
    print(f"[app] Relay via MQTT → {result}")


# Pin interrupt — physical button on GPIO 0
@app.on_pin(pin=0, trigger=Pin.IRQ_FALLING)
def button_pressed():
    current = relay.value()
    relay.value(not current)
    print(f"[app] Button toggle → {'on' if relay.value() else 'off'}")


if __name__ == "__main__":
    app.run()
