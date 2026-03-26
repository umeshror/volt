"""
volt/sensors/soil_moisture.py — Capacitive soil moisture sensor.

ADC-based analog sensor via machine.ADC.
"""

from .base import BaseSensor

try:
    from machine import ADC, Pin
    _HW_AVAILABLE = True
except ImportError:
    _HW_AVAILABLE = False


class SoilMoisture(BaseSensor):
    """
    Capacitive soil moisture sensor connected to an ADC pin.

    Usage::

        soil = SoilMoisture(pin=34)
        print(soil.raw)         # e.g. 2850
        print(soil.percentage)  # e.g. 34.5
    """

    def __init__(
        self,
        pin: int,
        adc_resolution: int = 12,
        dry_value: int = 4095,
        wet_value: int = 0,
    ):
        """
        Args:
            pin: ADC-capable GPIO pin.
            adc_resolution: Bit resolution (12 = 0–4095 on ESP32).
            dry_value: Raw ADC reading in dry air (max moisture = 0%).
            wet_value: Raw ADC reading submerged in water (max moisture = 100%).
        """
        self._dry = dry_value
        self._wet = wet_value
        self._max_val = (1 << adc_resolution) - 1
        self._raw = 0

        if _HW_AVAILABLE:
            try:
                self._adc = ADC(Pin(pin))
                # Attenuation for 0–3.3V range on ESP32
                try:
                    self._adc.atten(ADC.ATTN_11DB)  # type: ignore
                except AttributeError:
                    pass
            except Exception as e:
                print(f"[VOLT/SoilMoisture] Init error: {e}")
                self._adc = None
        else:
            self._adc = None

    def read(self):
        """Read raw ADC value from hardware."""
        if self._adc is not None:
            try:
                self._raw = self._adc.read()
            except Exception as e:
                print(f"[VOLT/SoilMoisture] Read error: {e}")
        return self

    @property
    def raw(self) -> int:
        """Raw ADC reading (0 – max_val)."""
        self.read()
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

    def to_dict(self) -> dict:
        return {"raw": self.raw, "percentage": self.percentage}
