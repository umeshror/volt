"""
volt/websocket.py — WebSocket server (RFC 6455).

Layered on top of http_server.py as an HTTP upgrade handler.
Handshake: SHA1 key exchange. Frame parsing: supports text and binary
frames with/without masking. One async task per connected client.
"""

import hashlib
import base64
import struct

try:
    import uasyncio as asyncio
except ImportError:
    import asyncio

try:
    import ujson as json
except ImportError:
    import json

_WS_MAGIC = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

# Opcodes
_OP_CONT  = 0x0
_OP_TEXT  = 0x1
_OP_BIN   = 0x2
_OP_CLOSE = 0x8
_OP_PING  = 0x9
_OP_PONG  = 0xA


class WebSocket:
    """Async WebSocket connection handle passed to the user's handler."""

    def __init__(self, reader, writer):
        self._reader = reader
        self._writer = writer
        self._closed = False

    async def receive(self):
        """Receive the next message (returns str or bytes)."""
        while True:
            header = await self._reader.read(2)
            if len(header) < 2:
                self._closed = True
                return None

            fin  = (header[0] & 0x80) != 0
            opcode = header[0] & 0x0F
            masked = (header[1] & 0x80) != 0
            length = header[1] & 0x7F

            if length == 126:
                ext = await self._reader.read(2)
                length = struct.unpack(">H", ext)[0]
            elif length == 127:
                ext = await self._reader.read(8)
                length = struct.unpack(">Q", ext)[0]

            mask_key = await self._reader.read(4) if masked else b""
            payload  = await self._reader.read(length)

            if masked:
                payload = bytes(b ^ mask_key[i % 4] for i, b in enumerate(payload))

            if opcode == _OP_CLOSE:
                self._closed = True
                await self._send_raw(_OP_CLOSE, b"")
                return None
            if opcode == _OP_PING:
                await self._send_raw(_OP_PONG, payload)
                continue
            if opcode in (_OP_TEXT, _OP_BIN):
                if opcode == _OP_TEXT:
                    text = payload.decode("utf-8", errors="replace")
                    try:
                        return json.loads(text)
                    except Exception:
                        return text
                return payload

    async def send(self, data):
        """Send a message to the client (dict → JSON, str → text frame)."""
        if self._closed:
            return
        if isinstance(data, dict) or isinstance(data, list):
            payload = json.dumps(data).encode()
            await self._send_raw(_OP_TEXT, payload)
        elif isinstance(data, str):
            await self._send_raw(_OP_TEXT, data.encode())
        else:
            await self._send_raw(_OP_BIN, data)

    async def _send_raw(self, opcode: int, payload: bytes):
        n = len(payload)
        header = bytes([0x80 | opcode])
        if n < 126:
            header += bytes([n])
        elif n < 65536:
            header += bytes([126]) + struct.pack(">H", n)
        else:
            header += bytes([127]) + struct.pack(">Q", n)
        self._writer.write(header + payload)
        await self._writer.drain()

    def is_closed(self) -> bool:
        return self._closed


async def upgrade(reader, writer, key: str, handler):
    """
    Perform the WebSocket handshake and hand off to the user handler.

    Args:
        reader:  asyncio StreamReader from the HTTP server
        writer:  asyncio StreamWriter
        key:     Sec-WebSocket-Key header value
        handler: user's async function(ws: WebSocket)
    """
    accept = base64.b64encode(
        hashlib.sha1((key.strip() + _WS_MAGIC).encode()).digest()
    ).decode()

    response = (
        "HTTP/1.1 101 Switching Protocols\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        f"Sec-WebSocket-Accept: {accept}\r\n"
        "\r\n"
    )
    writer.write(response.encode())
    await writer.drain()

    ws = WebSocket(reader, writer)
    try:
        await handler(ws)
    except Exception as e:
        print(f"[VOLT/WS] Handler error: {e}")
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass
