"""
volt/sensors/dht22.py — DHT22 temperature & humidity sensor.

Wraps MicroPython's built-in `dht.DHT22` with a unified VOLT sensor API.
Reads are lazy — hardware is only polled when a property is accessed.
"""

from __future__ import annotations

from ..exceptions import HardwareBindingError
from .base import BaseSensor

try:
    import dht
    import machine
except ImportError:
    dht = None
    machine = None

try:
    from typing import Any
except ImportError:
    pass


class DHT22(BaseSensor):
    """
    DHT22 temperature and humidity sensor.
    """

    def __init__(self, pin: int) -> None:
        if dht is not None and machine is not None:
            self._sensor = dht.DHT22(machine.Pin(pin))
        else:
            self._sensor = None
        self._temperature: float = 0.0
        self._humidity: float = 0.0

    async def read(self) -> BaseSensor:
        """Trigger a hardware measurement asynchronously."""
        if self._sensor is not None:
            try:
                import uasyncio as asyncio
            except ImportError:
                import asyncio
            
            await asyncio.sleep(0)
            try:
                self._sensor.measure()
                self._temperature = float(self._sensor.temperature())
                self._humidity = float(self._sensor.humidity())
            except Exception as e:
                raise HardwareBindingError(f"DHT22 read failed: {e}") from e
            await asyncio.sleep(0)
        return self

    @property
    def temperature(self) -> float:
        """Latest temperature reading in Celsius."""
        return self._temperature

    @property
    def humidity(self) -> float:
        """Latest relative humidity reading (0–100%)."""
        return self._humidity

    def to_dict(self) -> dict[str, Any]:
        return {"temp": self.temperature, "humidity": self.humidity}
