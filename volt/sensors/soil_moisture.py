"""
volt/sensors/soil_moisture.py — Capacitive soil moisture sensor.

ADC-based analog sensor via machine.ADC.
"""

from __future__ import annotations

from ..exceptions import HardwareBindingError
from .base import BaseSensor

try:
    from machine import ADC, Pin
    _HW_AVAILABLE = True
except ImportError:
    _HW_AVAILABLE = False
try:
    from typing import Any
except ImportError:
    pass


class SoilMoisture(BaseSensor):
    """
    Capacitive soil moisture sensor connected to an ADC pin.
    """

    def __init__(
        self,
        pin: int,
        adc_resolution: int = 12,
        dry_value: int = 4095,
        wet_value: int = 0,
    ) -> None:
        self._dry: int = dry_value
        self._wet: int = wet_value
        self._max_val: int = (1 << adc_resolution) - 1
        self._raw: int = 0

        if _HW_AVAILABLE:
            try:
                self._adc = ADC(Pin(pin))
                try:
                    self._adc.atten(ADC.ATTN_11DB)  # type: ignore
                except AttributeError:
                    pass
            except Exception as e:
                self._adc = None
                raise HardwareBindingError(f"ADC init failed: {e}") from e
        else:
            self._adc = None

    async def read(self) -> BaseSensor:
        """Read raw ADC value from hardware asynchronously."""
        if self._adc is not None:
            try:
                import uasyncio as asyncio
            except ImportError:
                import asyncio
            await asyncio.sleep(0)
            try:
                self._raw = self._adc.read()
            except Exception as e:
                raise HardwareBindingError(f"ADC read failed: {e}") from e
        return self

    @property
    def raw(self) -> int:
        """Raw ADC reading (0 – max_val)."""
        return self._raw

    @property
    def percentage(self) -> float:
        """Calibrated soil moisture percentage (0–100%)."""
        raw = self.raw
        span = self._dry - self._wet
        if span == 0:
            return 0.0
        pct = (self._dry - raw) / span * 100.0
        return round(max(0.0, min(100.0, pct)), 1)

    def to_dict(self) -> dict[str, Any]:
        return {"raw": self.raw, "percentage": self.percentage}
