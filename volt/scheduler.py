"""
volt/scheduler.py — Async task scheduler.

Manages all background tasks via uasyncio. Wraps coroutine creation so
users never call create_task directly.
"""

from __future__ import annotations

try:
    from collections.abc import Callable, Coroutine
    from typing import Any, List, Optional
except ImportError:
    pass

try:
    import uasyncio as asyncio
except ImportError:
    import asyncio


def _sleep_ms(ms: int) -> Any:
    """Portable sleep: uses uasyncio.sleep_ms on device, asyncio.sleep on host."""
    if hasattr(asyncio, "sleep_ms"):
        return asyncio.sleep_ms(ms)
    return asyncio.sleep(ms / 1000)


class Scheduler:
    def __init__(self) -> None:
        self._tasks: list[Any] = []
        self._crash_log: Any | None = None

    def set_crash_log(self, crash_log: Any) -> None:
        self._crash_log = crash_log

    # ------------------------------------------------------------------ every

    def add_every(self, seconds: float, fn: Callable[..., Any]) -> None:
        """Register a periodic task that fires every `seconds` seconds."""
        # Pre-compute the coroutine check once — not on every loop tick.
        is_coro = asyncio.iscoroutinefunction(fn)
        self._tasks.append(lambda: self._every_loop(seconds, fn, is_coro))

    async def _every_loop(self, seconds: float, fn: Callable[..., Any], is_coro: bool) -> None:
        interval_ms: int = int(seconds * 1000)
        while True:
            try:
                if is_coro:
                    await fn()
                else:
                    fn()
            except Exception as e:
                self._log_error(fn, e)
            await _sleep_ms(interval_ms)

    # ------------------------------------------------------------------ on_pin

    def add_pin(self, pin: int, trigger: Any, fn: Callable[..., Any]) -> None:
        """Register a GPIO interrupt task."""
        is_coro = asyncio.iscoroutinefunction(fn)
        self._tasks.append(lambda: self._pin_task(pin, trigger, fn, is_coro))

    async def _pin_task(self, pin: int, trigger: Any, fn: Callable[..., Any], is_coro: bool) -> None:
        try:
            from machine import Pin
            p = Pin(pin, Pin.IN, Pin.PULL_UP)

            # Set up IRQ — use a simple queue approach
            _triggered: list[bool] = []

            def _irq_handler(_: Any) -> None:
                _triggered.append(True)

            p.irq(trigger=trigger, handler=_irq_handler)

            while True:
                if _triggered:
                    _triggered.clear()
                    try:
                        if is_coro:
                            await fn()
                        else:
                            fn()
                    except Exception as e:
                        self._log_error(fn, e)
                await _sleep_ms(50)
        except Exception as e:
            self._log_error(fn, e)

    # ------------------------------------------------------------------ when

    def add_when(self, condition_fn: Callable[[], bool], fn: Callable[..., Any]) -> None:
        """Register a condition-polling task."""
        is_coro = asyncio.iscoroutinefunction(fn)
        self._tasks.append(lambda: self._when_loop(condition_fn, fn, is_coro))

    async def _when_loop(self, condition_fn: Callable[[], bool], fn: Callable[..., Any], is_coro: bool) -> None:
        while True:
            try:
                if condition_fn():
                    if is_coro:
                        await fn()
                    else:
                        fn()
            except Exception as e:
                self._log_error(fn, e)
            await _sleep_ms(100)

    # ------------------------------------------------------------------ run

    async def run(self) -> None:
        """Launch all registered tasks concurrently and run forever."""
        if not self._tasks:
            # Nothing to schedule — just keep the event loop alive
            while True:
                await asyncio.sleep(1)

        # _tasks holds callables (lambda wrappers) — invoke each to get a fresh
        # coroutine so run() is safe to call more than once.
        coros: list[Any] = [factory() for factory in self._tasks]
        await asyncio.gather(*coros)

    # ------------------------------------------------------------------ error

    def _log_error(self, fn: Callable[..., Any], exc: Exception) -> None:
        name = getattr(fn, "__name__", repr(fn))
        print(f"[VOLT] Task error in '{name}': {exc}")
        if self._crash_log is not None:
            try:
                self._crash_log.log(type(exc).__name__, str(exc))
            except Exception:
                pass
