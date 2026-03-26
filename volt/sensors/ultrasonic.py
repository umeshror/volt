"""
volt/sensors/ultrasonic.py — HC-SR04 ultrasonic distance sensor.

Uses machine.time_pulse_us for echo timing.
"""

from .base import BaseSensor

try:
    import machine
    _HW_AVAILABLE = True
except ImportError:
    _HW_AVAILABLE = False

_SOUND_CM_PER_US = 0.01715  # speed of sound / 2 (round-trip), cm/µs


class Ultrasonic(BaseSensor):
    """
    HC-SR04 time-of-flight distance sensor.

    Usage::

        dist = Ultrasonic(trigger=5, echo=18)
        print(dist.cm)     # 24.3
        print(dist.mm)     # 243.0
        print(dist.inches) # 9.57
    """

    def __init__(self, trigger: int, echo: int):
        """
        Args:
            trigger: GPIO pin number for the TRIG line.
            echo:    GPIO pin number for the ECHO line.
        """
        self._cm = 0.0
        if _HW_AVAILABLE:
            try:
                self._trig = machine.Pin(trigger, machine.Pin.OUT)
                self._echo = machine.Pin(echo, machine.Pin.IN)
                self._trig.off()
            except Exception as e:
                print(f"[VOLT/Ultrasonic] Init error: {e}")
                self._trig = None
                self._echo = None
        else:
            self._trig = None
            self._echo = None

    def read(self):
        """Emit trigger pulse and measure echo duration."""
        if self._trig is None or self._echo is None:
            return self
        try:
            # 10µs trigger pulse
            self._trig.on()
            # Busy-wait ~10µs
            for _ in range(40):
                pass
            self._trig.off()

            duration = machine.time_pulse_us(self._echo, 1, 30_000)
            if duration < 0:
                # Timeout
                self._cm = -1.0
            else:
                self._cm = duration * _SOUND_CM_PER_US
        except Exception as e:
            print(f"[VOLT/Ultrasonic] Read error: {e}")
        return self

    @property
    def cm(self) -> float:
        """Distance in centimetres."""
        self.read()
        return round(self._cm, 1)

    @property
    def mm(self) -> float:
        """Distance in millimetres."""
        return round(self.cm * 10, 1)

    @property
    def inches(self) -> float:
        """Distance in inches."""
        return round(self.cm / 2.54, 2)

    def to_dict(self) -> dict:
        return {"cm": self.cm, "mm": self.mm, "inches": self.inches}
