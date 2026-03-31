"""
volt/sensors/ultrasonic.py — HC-SR04 ultrasonic distance sensor.

Uses machine.time_pulse_us for echo timing.
"""

from __future__ import annotations

from ..exceptions import HardwareBindingError
from .base import BaseSensor

try:
    import machine
    _HW_AVAILABLE = True
except ImportError:
    _HW_AVAILABLE = False
try:
    from typing import Any
except ImportError:
    pass

_SOUND_CM_PER_US = 0.01715  # speed of sound / 2 (round-trip), cm/µs


class Ultrasonic(BaseSensor):
    """
    HC-SR04 time-of-flight distance sensor.
    """

    def __init__(self, trigger: int, echo: int) -> None:
        self._cm: float = 0.0
        self._pulse_us: int = -1
        self._start_us: int = 0

        if _HW_AVAILABLE:
            try:
                import time
                self._time = time
                self._trig = machine.Pin(trigger, machine.Pin.OUT)
                self._echo = machine.Pin(echo, machine.Pin.IN)
                self._trig.off()
                self._echo.irq(
                    handler=self._echo_irq,
                    trigger=machine.Pin.IRQ_RISING | machine.Pin.IRQ_FALLING
                )
            except Exception as e:
                self._trig = None
                self._echo = None
                raise HardwareBindingError(f"Ultrasonic init failed: {e}") from e
        else:
            self._trig = None
            self._echo = None

    def _echo_irq(self, pin: Any) -> None:
        t = self._time.ticks_us()
        if pin.value() == 1:
            self._start_us = t
        else:
            self._pulse_us = self._time.ticks_diff(t, self._start_us)

    async def read(self) -> BaseSensor:
        """Emit trigger pulse and measure echo duration asynchronously with IRQ."""
        if self._trig is None or self._echo is None:
            return self

        try:
            import uasyncio as asyncio
        except ImportError:
            import asyncio

        try:
            self._pulse_us = -1
            self._trig.on()
            self._time.sleep_us(10)  # HC-SR04 requires >=10µs trigger pulse
            self._trig.off()

            # Poll for the IRQ to finish (up to 30ms total)
            for _ in range(30):
                if self._pulse_us >= 0:
                    break
                if hasattr(asyncio, "sleep_ms"):
                    await asyncio.sleep_ms(1) # type: ignore
                else:
                    await asyncio.sleep(0.001)

            if self._pulse_us < 0:
                self._cm = -1.0
            else:
                self._cm = self._pulse_us * _SOUND_CM_PER_US
        except Exception as e:
            raise HardwareBindingError(f"Ultrasonic read failed: {e}") from e
        return self

    @property
    def cm(self) -> float:
        """Distance in centimetres."""
        return round(self._cm, 1)

    @property
    def mm(self) -> float:
        """Distance in millimetres."""
        res = self.cm
        if res < 0:
            return -1.0
        return round(res * 10, 1)

    @property
    def inches(self) -> float:
        """Distance in inches."""
        res = self.cm
        if res < 0:
            return -1.0
        return round(res / 2.54, 2)

    def to_dict(self) -> dict[str, Any]:
        return {"cm": self.cm, "mm": self.mm, "inches": self.inches}
