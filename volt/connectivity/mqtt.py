"""
volt/connectivity/mqtt.py — MQTT manager.

Wraps umqtt.simple.MQTTClient with:
  - Topic subscription management (re-subscribes on reconnect)
  - Offline queue (flash-backed /mqtt_queue.json, bounded to prevent OOM)
  - Inbound message dispatch to router
  - Background polling loop (check_msg every 100ms)
"""

from __future__ import annotations

try:
    import uasyncio as asyncio
except ImportError:
    import asyncio

try:
    import ujson as json
except ImportError:
    import json

try:
    from collections import deque
except ImportError:
    deque = None  # type: ignore[assignment,misc]

try:
    from typing import Any, Callable
except ImportError:
    pass

_QUEUE_PATH = "/mqtt_queue.json"


def _sleep_ms(ms: int) -> Any:
    """Portable sleep: uses uasyncio.sleep_ms on device, asyncio.sleep on host."""
    if hasattr(asyncio, "sleep_ms"):
        return asyncio.sleep_ms(ms)  # type: ignore[attr-defined]
    return asyncio.sleep(ms / 1000)


class MQTTConfig:
    """MQTT broker connection parameters."""

    def __init__(
        self,
        broker: str,
        port: int = 1883,
        client_id: str | None = None,
        user: str | None = None,
        password: str | None = None,
        keepalive: int = 60,
        max_queue_size: int = 50,
        queue_overflow: str = "drop_oldest",
    ) -> None:
        self.broker = broker
        self.port = port
        self.client_id = client_id or "volt-device"
        self.user = user
        self.password = password
        self.keepalive = keepalive
        self.max_queue_size = max_queue_size
        self.queue_overflow = queue_overflow


class MQTTManager:
    def __init__(self, config: MQTTConfig, router: Any = None,
                 on_connect: list[Callable[..., Any]] | None = None,
                 on_disconnect: list[Callable[..., Any]] | None = None) -> None:
        self._config = config
        self._router = router
        self._on_connect: list[Callable[..., Any]] = on_connect or []
        self._on_disconnect: list[Callable[..., Any]] = on_disconnect or []
        self._client: Any = None
        self._connected: bool = False
        self._reconnecting: bool = False  # guard against duplicate reconnect tasks
        self._queue: list[dict[str, Any]] = []
        self._load_queue()

    # ------------------------------------------------------------------ connect

    async def connect(self) -> None:
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
            asyncio.create_task(self._poll_loop())  # type: ignore
        except Exception as e:
            print(f"[VOLT/MQTT] Connection error: {e}")
            self._connected = False
            # Do NOT spawn _reconnect_loop here — the poll_loop caller is
            # responsible for that, or the caller must trigger reconnect.
            # Spawning here would bypass the _reconnecting guard.

    def _subscribe_all(self) -> None:
        if self._router is None or self._client is None:
            return
        # Access protected member dynamically as router structure may vary
        mqtt_routes = getattr(self._router, "_mqtt_routes", {})
        for topic in mqtt_routes:
            self._client.subscribe(topic.encode() if isinstance(topic, str) else topic)

    # ------------------------------------------------------------------ publish

    def publish(self, topic: str, payload: Any, retain: bool = False) -> None:
        """Publish a message; queues to flash if currently disconnected."""
        if isinstance(payload, dict):
            payload = json.dumps(payload) # type: ignore
        if isinstance(payload, str):
            payload = payload.encode()

        if self._connected and self._client is not None:
            try:
                self._client.publish(topic, payload, retain=retain)
            except Exception as e:
                print(f"[VOLT/MQTT] Publish error: {e}")
                self._connected = False
                str_payload = payload.decode() if isinstance(payload, bytes) else payload
                self._enqueue(topic, str_payload)
        else:
            str_payload = payload.decode() if isinstance(payload, bytes) else payload
            self._enqueue(topic, str_payload)

    # ------------------------------------------------------------------ offline queue

    def _enqueue(self, topic: str, payload: Any) -> None:
        modified = False
        if len(self._queue) >= self._config.max_queue_size:
            policy = self._config.queue_overflow
            if policy == "drop_oldest":
                del self._queue[0]
                self._queue.append({"topic": topic, "payload": payload})
                modified = True
            elif policy == "drop_newest":
                pass  # discard incoming — queue unchanged, no write needed
            elif policy == "raise":
                from ..exceptions import NetworkError
                raise NetworkError("MQTT offline queue overflow")
            else:
                del self._queue[0]
                self._queue.append({"topic": topic, "payload": payload})
                modified = True
        else:
            self._queue.append({"topic": topic, "payload": payload})
            modified = True

        if modified:
            self._save_queue()

    def _load_queue(self) -> None:
        try:
            with open(_QUEUE_PATH) as f:
                self._queue = json.loads(f.read()) # type: ignore
        except Exception:
            self._queue = []

    def _save_queue(self) -> None:
        try:
            with open(_QUEUE_PATH, "w") as f:
                f.write(json.dumps(self._queue)) # type: ignore
        except Exception as e:
            print(f"[VOLT/MQTT] Queue save error: {e}")

    async def _flush_queue(self) -> None:
        if not self._queue or self._client is None:
            return
        remaining: list[dict[str, Any]] = []
        for item in self._queue:
            try:
                pay = item["payload"]
                self._client.publish(
                    item["topic"],
                    pay.encode() if isinstance(pay, str) else pay,
                )
            except Exception:
                remaining.append(item)
        self._queue = remaining
        self._save_queue()

    # ------------------------------------------------------------------ incoming messages

    def _on_message(self, topic: Any, msg: Any) -> None:
        if isinstance(topic, bytes):
            topic = topic.decode()
        try:
            payload = json.loads(msg) # type: ignore
        except Exception:
            payload = msg.decode() if isinstance(msg, bytes) else msg

        if self._router is None:
            return

        # Call the router resolve dynamically
        resolve_func = getattr(self._router, "resolve_mqtt", None)
        if not resolve_func:
            return

        result = resolve_func(topic)
        if result:
            handler, _ = result
            try:
                handler(payload)
            except Exception as e:
                print(f"[VOLT/MQTT] Handler error for '{topic}': {e}")

    # ------------------------------------------------------------------ loops

    async def _poll_loop(self) -> None:
        while True:
            if self._connected and self._client is not None:
                try:
                    self._client.check_msg()
                except Exception as e:
                    print(f"[VOLT/MQTT] Poll error: {e}")
                    self._connected = False
                    asyncio.create_task(self._reconnect_loop())  # type: ignore
                    return
            await _sleep_ms(100)

    async def _reconnect_loop(self) -> None:
        # Guard: only one reconnect loop may run at a time.
        if self._reconnecting:
            return
        self._reconnecting = True
        delay = 5
        try:
            while not self._connected:
                print(f"[VOLT/MQTT] Reconnecting in {delay}s")
                await asyncio.sleep(delay)
                delay = min(delay * 2, 60)
                await self.connect()
        finally:
            self._reconnecting = False

    async def _fire_callbacks(self, callbacks: list[Callable[..., Any]]) -> None:
        for cb in callbacks:
            try:
                if asyncio.iscoroutinefunction(cb): # type: ignore
                    await cb()
                else:
                    cb()
            except Exception as e:
                print(f"[VOLT/MQTT] Callback error: {e}")

    @property
    def is_connected(self) -> bool:
        return self._connected
