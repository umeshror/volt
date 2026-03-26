"""
volt/sensors/dht22.py — DHT22 temperature & humidity sensor.

Wraps MicroPython's built-in `dht.DHT22` with a unified VOLT sensor API.
Reads are lazy — hardware is only polled when a property is accessed.
"""

from .base import BaseSensor

try:
    import dht
    import machine
except ImportError:
    dht = None
    machine = None


class DHT22(BaseSensor):
    """
    DHT22 temperature and humidity sensor.

    Usage::

        sensor = DHT22(pin=4)
        print(sensor.temperature)   # 22.5
        print(sensor.humidity)      # 55.0
        print(sensor.to_dict())     # {"temp": 22.5, "humidity": 55.0}
    """

    def __init__(self, pin: int):
        """
        Args:
            pin: GPIO pin number the data line is connected to.
        """
        if dht is not None and machine is not None:
            self._sensor = dht.DHT22(machine.Pin(pin))
        else:
            self._sensor = None
        self._temperature: float = 0.0
        self._humidity: float = 0.0

    def read(self):
        """Trigger a hardware measurement."""
        if self._sensor is not None:
            self._sensor.measure()
            val = self._sensor.temperature()
            self._temperature = float(val) if callable(val) else float(self._sensor.temperature())
            val2 = self._sensor.humidity()
            self._humidity = float(val2) if callable(val2) else float(self._sensor.humidity())
        return self

    @property
    def temperature(self) -> float:
        """Latest temperature reading in Celsius."""
        self.read()
        if self._sensor is not None:
            try:
                v = self._sensor.temperature()
                return float(v)
            except Exception:
                pass
        return self._temperature

    @property
    def humidity(self) -> float:
        """Latest relative humidity reading (0–100%)."""
        self.read()
        if self._sensor is not None:
            try:
                v = self._sensor.humidity()
                return float(v)
            except Exception:
                pass
        return self._humidity

    def to_dict(self) -> dict:
        return {"temp": self.temperature, "humidity": self.humidity}
