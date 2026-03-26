"""
volt/connectivity/mqtt.py — MQTT manager.

Wraps umqtt.simple.MQTTClient with:
  - Topic subscription management (re-subscribes on reconnect)
  - Offline queue (flash-backed /mqtt_queue.json)
  - Inbound message dispatch to router
  - Background polling loop (check_msg every 100ms)
"""

try:
    import uasyncio as asyncio
except ImportError:
    import asyncio

try:
    import ujson as json
except ImportError:
    import json

_QUEUE_PATH = "/mqtt_queue.json"


class MQTTConfig:
    """MQTT broker connection parameters."""

    def __init__(
        self,
        broker: str,
        port: int = 1883,
        client_id: str = None,
        user: str = None,
        password: str = None,
        keepalive: int = 60,
    ):
        self.broker = broker
        self.port = port
        self.client_id = client_id or "volt-device"
        self.user = user
        self.password = password
        self.keepalive = keepalive


class MQTTManager:
    def __init__(self, config: MQTTConfig, router=None,
                 on_connect=None, on_disconnect=None):
        self._config = config
        self._router = router
        self._on_connect = on_connect or []
        self._on_disconnect = on_disconnect or []
        self._client = None
        self._connected = False
        self._queue: list = []
        self._load_queue()

    # ------------------------------------------------------------------ connect

    async def connect(self):
        try:
            from umqtt.simple import MQTTClient
        except ImportError:
            print("[VOLT/MQTT] umqtt not available")
            return

        cfg = self._config
        self._client = MQTTClient(
            cfg.client_id, cfg.broker, cfg.port,
            user=cfg.user, password=cfg.password,
            keepalive=cfg.keepalive,
        )
        self._client.set_callback(self._on_message)

        try:
            self._client.connect()
            self._connected = True
            print(f"[VOLT/MQTT] Connected to {cfg.broker}:{cfg.port}")
            self._subscribe_all()
            await self._flush_queue()
            await self._fire_callbacks(self._on_connect)
            asyncio.create_task(self._poll_loop())
        except Exception as e:
            print(f"[VOLT/MQTT] Connection error: {e}")
            self._connected = False
            asyncio.create_task(self._reconnect_loop())

    def _subscribe_all(self):
        if self._router is None:
            return
        for topic in self._router._mqtt_routes:
            self._client.subscribe(topic.encode() if isinstance(topic, str) else topic)

    # ------------------------------------------------------------------ publish

    def publish(self, topic: str, payload, retain: bool = False):
        """Publish a message; queues to flash if currently disconnected."""
        if isinstance(payload, dict):
            payload = json.dumps(payload)
        if isinstance(payload, str):
            payload = payload.encode()

        if self._connected and self._client is not None:
            try:
                self._client.publish(topic, payload, retain=retain)
            except Exception as e:
                print(f"[VOLT/MQTT] Publish error: {e}")
                self._connected = False
                self._enqueue(topic, payload.decode() if isinstance(payload, bytes) else payload)
        else:
            self._enqueue(topic, payload.decode() if isinstance(payload, bytes) else payload)

    # ------------------------------------------------------------------ offline queue

    def _enqueue(self, topic: str, payload):
        self._queue.append({"topic": topic, "payload": payload})
        self._save_queue()

    def _load_queue(self):
        try:
            with open(_QUEUE_PATH) as f:
                self._queue = json.loads(f.read())
        except Exception:
            self._queue = []

    def _save_queue(self):
        try:
            with open(_QUEUE_PATH, "w") as f:
                f.write(json.dumps(self._queue))
        except Exception as e:
            print(f"[VOLT/MQTT] Queue save error: {e}")

    async def _flush_queue(self):
        if not self._queue:
            return
        remaining = []
        for item in self._queue:
            try:
                self._client.publish(
                    item["topic"],
                    item["payload"].encode() if isinstance(item["payload"], str) else item["payload"],
                )
            except Exception:
                remaining.append(item)
        self._queue = remaining
        self._save_queue()

    # ------------------------------------------------------------------ incoming messages

    def _on_message(self, topic, msg):
        if isinstance(topic, bytes):
            topic = topic.decode()
        try:
            payload = json.loads(msg)
        except Exception:
            payload = msg.decode() if isinstance(msg, bytes) else msg

        if self._router is None:
            return
        result = self._router.resolve_mqtt(topic)
        if result:
            handler, _ = result
            try:
                handler(payload)
            except Exception as e:
                print(f"[VOLT/MQTT] Handler error for '{topic}': {e}")

    # ------------------------------------------------------------------ loops

    async def _poll_loop(self):
        while True:
            if self._connected and self._client is not None:
                try:
                    self._client.check_msg()
                except Exception as e:
                    print(f"[VOLT/MQTT] Poll error: {e}")
                    self._connected = False
                    asyncio.create_task(self._reconnect_loop())
                    return
            await asyncio.sleep_ms(100)

    async def _reconnect_loop(self):
        delay = 5
        while not self._connected:
            print(f"[VOLT/MQTT] Reconnecting in {delay}s")
            await asyncio.sleep(delay)
            delay = min(delay * 2, 60)
            await self.connect()

    async def _fire_callbacks(self, callbacks: list):
        for cb in callbacks:
            try:
                if asyncio.iscoroutinefunction(cb):
                    await cb()
                else:
                    cb()
            except Exception as e:
                print(f"[VOLT/MQTT] Callback error: {e}")

    @property
    def is_connected(self) -> bool:
        return self._connected
