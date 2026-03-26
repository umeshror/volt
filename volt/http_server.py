"""
volt/http_server.py — Minimal async HTTP/1.1 server.

Designed to run on MicroPython without external dependencies.
Stays under ~200 lines to conserve flash.
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
    from typing import Any, Callable
except ImportError:
    pass


class Request:
    __slots__ = ("method", "path", "headers", "body", "query", "params")

    def __init__(self, method: str, path: str, headers: dict[str, str], body: Any, query: dict[str, str], params: dict[str, str] | None = None) -> None:
        self.method = method
        self.path = path
        self.headers = headers
        self.body = body
        self.query = query
        self.params = params or {}


class HTTPServer:
    PORT = 80

    def __init__(self, router: Any, port: int | None = None) -> None:
        self._router = router
        self._port = port or self.PORT

    async def start(self) -> None:
        server = await asyncio.start_server(self._handle, "0.0.0.0", self._port) # type: ignore
        print(f"[VOLT/HTTP] Listening on port {self._port}")
        async with server:
            await server.wait_closed()

    async def _handle(self, reader: Any, writer: Any) -> None:
        try:
            request = await self._parse(reader)
            if request is None:
                writer.close()
                return
            response_body, status = await self._dispatch(request)
            await self._send(writer, status, response_body)
        except Exception as e:
            print(f"[VOLT/HTTP] Error: {e}")
            await self._send(writer, 500, {"error": "Internal Server Error"})
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    async def _parse(self, reader: Any) -> Request | None:
        try:
            first_line = await reader.readline()
            if not first_line:
                return None
            parts = first_line.decode().strip().split(" ")
            if len(parts) < 2:
                return None
            method, full_path = parts[0], parts[1]

            # Split query string
            if "?" in full_path:
                path, qs = full_path.split("?", 1)
                query = self._parse_qs(qs)
            else:
                path, query = full_path, {}

            # Headers
            headers: dict[str, str] = {}
            content_length = 0
            while True:
                line = await reader.readline()
                if line in (b"\r\n", b"\n", b""):
                    break
                key, _, val = line.decode().partition(":")
                headers[key.strip().lower()] = val.strip()
                if key.strip().lower() == "content-length":
                    content_length = int(val.strip())

            # Body
            body: Any = None
            if content_length > 0:
                raw = await reader.read(content_length)
                ct = headers.get("content-type", "")
                if "application/json" in ct:
                    try:
                        body = json.loads(raw) # type: ignore
                    except Exception:
                        body = raw
                else:
                    body = raw

            return Request(method, path, headers, body, query)
        except Exception as e:
            print(f"[VOLT/HTTP] Parse error: {e}")
            return None

    async def _dispatch(self, request: Request) -> tuple[Any, int]:
        resolve_func = getattr(self._router, "resolve_http", None)
        if resolve_func is None:
            return {"error": "Not Found"}, 404

        result = resolve_func(request.method, request.path)
        if result is None:
            return {"error": "Not Found"}, 404

        handler, params = result
        request.params = params

        try:
            import inspect
            if asyncio.iscoroutinefunction(handler): # type: ignore
                response = await handler(**params)
            else:
                # Check if handler accepts request
                sig = inspect.signature(handler)
                if "request" in sig.parameters:
                    response = handler(request=request, **params)
                else:
                    response = handler(**params)
            return response, 200
        except TypeError:
            # Handler doesn't accept params — call plain
            try:
                if asyncio.iscoroutinefunction(handler): # type: ignore
                    response = await handler()
                else:
                    response = handler()
                return response, 200
            except Exception as e:
                print(f"[VOLT/HTTP] Handler error: {e}")
                return {"error": str(e)}, 500
        except Exception as e:
            print(f"[VOLT/HTTP] Handler error: {e}")
            return {"error": str(e)}, 500

    async def _send(self, writer: Any, status: int, body: Any) -> None:
        status_text = {
            200: "OK", 201: "Created", 400: "Bad Request",
            404: "Not Found", 405: "Method Not Allowed",
            500: "Internal Server Error",
        }.get(status, "OK")

        if isinstance(body, (dict, list)):
            body_bytes = json.dumps(body).encode() # type: ignore
            content_type = "application/json"
        elif isinstance(body, str):
            body_bytes = body.encode()
            content_type = "text/plain"
        else:
            body_bytes = body if isinstance(body, bytes) else b""
            content_type = "application/octet-stream"

        response = (
            f"HTTP/1.1 {status} {status_text}\r\n"
            f"Content-Type: {content_type}\r\n"
            f"Content-Length: {len(body_bytes)}\r\n"
            f"Connection: close\r\n"
            f"\r\n"
        ).encode() + body_bytes

        writer.write(response)
        await writer.drain()

    @staticmethod
    def _parse_qs(qs: str) -> dict[str, str]:
        result: dict[str, str] = {}
        for pair in qs.split("&"):
            if "=" in pair:
                k, v = pair.split("=", 1)
                result[k] = v
        return result
