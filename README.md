# ⚡ VOLT

> **FastAPI for the physical world.**  
> A Python-native IoT framework for MicroPython · ESP32 · Raspberry Pi Pico W · Edge Devices

[![MicroPython](https://img.shields.io/badge/MicroPython-1.22+-blue.svg)](https://micropython.org/)
[![ESP32](https://img.shields.io/badge/ESP32-supported-green.svg)](https://www.espressif.com/)
[![Pico W](https://img.shields.io/badge/Pico%20W-supported-green.svg)](https://www.raspberrypi.com/products/raspberry-pi-pico/)
[![License](https://img.shields.io/badge/license-MIT-brightgreen.svg)](LICENSE)

---

## The Problem

Writing MicroPython for ESP32 or Raspberry Pi Pico W today means bare metal — no routing, no middleware, no conventions. You wire up pins, call `uasyncio.run()`, and figure out the rest yourself.

**VOLT fixes that.** It brings the developer experience of FastAPI to constrained hardware in a footprint small enough to fit in an ESP32's flash.

---

## Quick Start

```python
from volt import App
from volt.sensors import DHT22
from volt.connectivity import WiFiConfig, MQTTConfig

app = App(device="esp32")
sensor = DHT22(pin=4)

app.config(
    wifi=WiFiConfig(ssid="MyNetwork", password="secret"),
    mqtt=MQTTConfig(broker="192.168.1.10"),
)

# HTTP endpoint
@app.get("/status")
def status():
    return {"temp": sensor.temperature, "uptime": app.uptime()}

# MQTT subscription
@app.subscribe("home/lights/set")
def set_lights(payload):
    lights.set(payload["state"])

# Periodic task
@app.every(seconds=30)
async def heartbeat():
    await app.mqtt.publish("device/heartbeat", {"id": app.device_id})

app.run()
```

Flash it:

```bash
volt flash main.py --port /dev/ttyUSB0
```

---

## Features

### Multi-Protocol Routing
One decorator syntax across HTTP, MQTT, BLE, and WebSocket. Define your handler once — VOLT wires it to the right transport.

```python
@app.get("/sensor")           # HTTP GET
@app.subscribe("topic/in")    # MQTT subscribe
@app.ble_characteristic("temp")  # BLE GATT characteristic
```

### Async Task Scheduler
Clean decorators for every embedded task pattern, built on `uasyncio`:

```python
@app.every(seconds=10)              # periodic
@app.on_pin(pin=4, trigger=RISING)  # hardware interrupt
@app.when(lambda: temp.read() > 80) # threshold trigger
@app.on_connect                     # WiFi/MQTT connected
@app.on_disconnect                  # connection lost
```

### Resilient Connectivity
WiFi drops. MQTT brokers go down. VOLT handles it:

- **Auto-reconnect** with exponential backoff
- **Offline queue** — buffer messages to flash, flush on reconnect
- **AP fallback mode** — become a setup hotspot if WiFi is lost
- **Heartbeat monitoring** — detect silent failures

### Sensor Abstraction
Swap hardware without rewriting application logic:

```python
from volt.sensors import DHT22, SoilMoisture, Ultrasonic, BME280

temp  = DHT22(pin=4)
soil  = SoilMoisture(pin=34, adc_resolution=12)
dist  = Ultrasonic(trigger=5, echo=18)
env   = BME280(i2c_id=0, sda=21, scl=22)

# Unified interface across all sensors
print(temp.temperature, temp.humidity)
print(soil.percentage)
print(dist.cm)
print(env.pressure)
```

### 💾 Persistent State
Survives reboots. Optionally syncs to the cloud:

```python
app.state.set("last_watered", time.time())   # written to flash
app.state.get("last_watered")                # read back after reboot
app.state.sync_to("mqtt")                    # auto-publish on change
```

### 🩺 Health & Watchdog
```python
app.watchdog(timeout=30)        # auto-reboot if hung
app.crash_log(max_entries=10)   # store crashes in flash
app.health_check(interval=60)   # ping home server
```

---

## CLI

```bash
# Deploy code to device
volt flash main.py --port /dev/ttyUSB0

# Stream live logs
volt monitor --port /dev/ttyUSB0

# Open interactive REPL on device
volt shell --port /dev/ttyUSB0

# Discover VOLT devices on your network
volt scan

# Over-the-air update
volt ota push main.py --device 192.168.1.42

# Launch local web dashboard
volt dashboard
```

---

## Dashboard

`volt dashboard` starts a local web UI that auto-discovers devices on your network:

- 📈 Live sensor readings with time-series graphs
- 💓 Device health — uptime, free RAM, WiFi RSSI
- 📨 MQTT message log (filterable by topic)
- 🔄 One-click OTA firmware push
- 🪲 Crash log viewer with full stack traces

---

## Supported Hardware

| Device | WiFi | BLE | Flash | Status |
|--------|------|-----|-------|--------|
| ESP32 | ✅ | ✅ | 4MB | ✅ Supported |
| ESP32-S3 | ✅ | ✅ | 8MB | ✅ Supported |
| ESP8266 | ✅ | ❌ | 1MB | ⚠️ Limited |
| Raspberry Pi Pico W | ✅ | ❌ | 2MB | ✅ Supported |
| Raspberry Pi Pico 2W | ✅ | ✅ | 4MB | 🚧 In Progress |

---

## Architecture

```
┌─────────────────────────────────────────┐
│           Your Application Code          │
│   @app.every  @app.get  @app.subscribe  │
├─────────────────────────────────────────┤
│             Framework Core               │
│   Router | Scheduler | State Manager    │
├──────────┬──────────┬───────────────────┤
│   HTTP   │   MQTT   │   BLE / Serial    │
│  Server  │  Client  │    Handlers       │
├──────────┴──────────┴───────────────────┤
│         Connectivity Manager            │
│     WiFi | Reconnect | Offline Queue    │
├─────────────────────────────────────────┤
│          MicroPython / uasyncio         │
├─────────────────────────────────────────┤
│       ESP32 / Pico W Hardware           │
└─────────────────────────────────────────┘
```

---

## Design Principles

- **Memory-first** — the entire runtime fits under 40KB, leaving headroom for your app
- **Fail gracefully** — disconnections and crashes never permanently brick a device
- **Convention over configuration** — sensible defaults, zero-config for the 80% case
- **No CPython assumptions** — zero reliance on stdlib modules absent in MicroPython
- **Protocol-agnostic handlers** — one function can serve HTTP, MQTT, and BLE simultaneously

---

## Installation

### On the Device

Upload via the CLI (recommended):

```bash
pip install volt-iot
volt flash main.py --port /dev/ttyUSB0
```

Or copy manually using `mpremote` or `ampy`:

```bash
mpremote cp -r volt/ :volt/
mpremote cp main.py :main.py
```

### CLI Tools (Desktop)

```bash
pip install volt-iot
```

Requires Python 3.8+ on the host machine.

---

## Examples

| Example | Description |
|---------|-------------|
| [`examples/temperature_logger`](examples/temperature_logger) | Read DHT22, publish to MQTT every 30s |
| [`examples/smart_switch`](examples/smart_switch) | HTTP + MQTT controlled relay |
| [`examples/soil_monitor`](examples/soil_monitor) | Soil sensor with threshold alerts |
| [`examples/ble_beacon`](examples/ble_beacon) | BLE GATT server with sensor characteristics |
| [`examples/multi_protocol`](examples/multi_protocol) | Same handler over HTTP, MQTT, and BLE |
| [`examples/ota_update`](examples/ota_update) | Self-updating firmware pattern |

---

## Project Status

**v0.1 shipped.** All planned features are implemented and tested.

- [x] WiFi connectivity manager (exponential backoff, AP fallback)
- [x] HTTP server (`@app.get`, `@app.post`, `@app.put`, `@app.delete`)
- [x] MQTT pub/sub (`@app.subscribe`, `app.mqtt.publish`, offline queue)
- [x] Periodic task scheduler (`@app.every`)
- [x] Pin interrupt tasks (`@app.on_pin`)
- [x] Threshold triggers (`@app.when`)
- [x] Lifecycle hooks (`@app.on_connect`, `@app.on_disconnect`)
- [x] Persistent state (flash-backed KV store, atomic writes)
- [x] Watchdog + crash logging
- [x] Health check (periodic HTTP ping)
- [x] BLE GATT server (read + notify via `ubluetooth`)
- [x] WebSocket server (RFC 6455, full frame parsing)
- [x] Sensor library — DHT22, BME280, SoilMoisture, Ultrasonic
- [x] CLI: `flash`, `monitor`, `shell`, `scan`, `ota`, `dashboard`
- [x] Dashboard UI (Chart.js live graphs, OTA panel, crash log viewer)
- [x] OTA updates (`/ota/upload` endpoint + `volt ota push`)

> BLE write-characteristic support is deferred to v0.2.

---

## Contributing

Contributions are very welcome. VOLT is most useful when it supports a wide range of sensors and protocols.

```bash
git clone https://github.com/your-org/volt
cd volt
pip install -e ".[dev]"
pytest
```

Please open an issue before starting large features so we can align on direction.

---

## License

MIT — see [LICENSE](LICENSE) for details.

---

<p align="center">
  Built for the makers, engineers, and hobbyists who believe Python belongs everywhere — including the physical world.
</p>
