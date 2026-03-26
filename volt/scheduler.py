"""
volt/scheduler.py — Async task scheduler.

Manages all background tasks via uasyncio. Wraps coroutine creation so
users never call create_task directly.
"""

try:
    import uasyncio as asyncio
except ImportError:
    import asyncio


def _sleep_ms(ms: int):
    """Portable sleep: uses uasyncio.sleep_ms on device, asyncio.sleep on host."""
    if hasattr(asyncio, "sleep_ms"):
        return asyncio.sleep_ms(ms)
    return asyncio.sleep(ms / 1000)


class Scheduler:
    def __init__(self):
        self._tasks: list = []
        self._crash_log = None

    def set_crash_log(self, crash_log):
        self._crash_log = crash_log

    # ------------------------------------------------------------------ every

    def add_every(self, seconds: float, fn):
        """Register a periodic task that fires every `seconds` seconds."""
        self._tasks.append(self._every_loop(seconds, fn))

    async def _every_loop(self, seconds: float, fn):
        interval_ms = int(seconds * 1000)
        while True:
            try:
                import inspect
                if asyncio.iscoroutinefunction(fn):
                    await fn()
                else:
                    fn()
            except Exception as e:
                self._log_error(fn, e)
            await _sleep_ms(interval_ms)

    # ------------------------------------------------------------------ on_pin

    def add_pin(self, pin, trigger, fn):
        """Register a GPIO interrupt task."""
        self._tasks.append(self._pin_task(pin, trigger, fn))

    async def _pin_task(self, pin, trigger, fn):
        try:
            from machine import Pin
            p = Pin(pin, Pin.IN, Pin.PULL_UP)
            # Set up IRQ — use a simple queue approach
            _triggered = []

            def _irq_handler(_):
                _triggered.append(True)

            p.irq(trigger=trigger, handler=_irq_handler)

            while True:
                if _triggered:
                    _triggered.clear()
                    try:
                        if asyncio.iscoroutinefunction(fn):
                            await fn()
                        else:
                            fn()
                    except Exception as e:
                        self._log_error(fn, e)
                await asyncio.sleep_ms(50)
        except Exception as e:
            self._log_error(fn, e)

    # ------------------------------------------------------------------ when

    def add_when(self, condition_fn, fn):
        """Register a condition-polling task."""
        self._tasks.append(self._when_loop(condition_fn, fn))

    async def _when_loop(self, condition_fn, fn):
        while True:
            try:
                if condition_fn():
                    if asyncio.iscoroutinefunction(fn):
                        await fn()
                    else:
                        fn()
            except Exception as e:
                self._log_error(fn, e)
            await _sleep_ms(100)

    # ------------------------------------------------------------------ run

    async def run(self):
        """Launch all registered tasks concurrently and run forever."""
        if not self._tasks:
            # Nothing to schedule — just keep the event loop alive
            while True:
                await asyncio.sleep(1)

        coros = list(self._tasks)
        await asyncio.gather(*coros)

    # ------------------------------------------------------------------ error

    def _log_error(self, fn, exc):
        name = getattr(fn, "__name__", repr(fn))
        print(f"[VOLT] Task error in '{name}': {exc}")
        if self._crash_log is not None:
            try:
                self._crash_log.log(type(exc).__name__, str(exc))
            except Exception:
                pass
