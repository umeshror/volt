"""
volt/sensors/bme280.py — BME280 temperature, humidity & pressure sensor.

Communicates over I²C via machine.I2C. Includes a lightweight register-level
driver so no external library is required.
"""

from __future__ import annotations

try:
    from typing import Any
except ImportError:
    pass

from ..exceptions import HardwareBindingError
from .base import BaseSensor

try:
    from machine import I2C, Pin
    _HW_AVAILABLE = True
except ImportError:
    _HW_AVAILABLE = False

# BME280 register addresses
_BME280_REG_DATA = 0xF7
_BME280_REG_CTRL_HUM = 0xF2
_BME280_REG_CTRL_MEAS = 0xF4
_BME280_REG_CONFIG = 0xF5
_BME280_REG_CALIB = 0x88
_BME280_REG_CALIB2 = 0xE1


class BME280(BaseSensor):
    """
    BME280 environment sensor (temperature, humidity, pressure).
    """

    def __init__(
        self,
        i2c_id: int = 0,
        sda: int = 21,
        scl: int = 22,
        address: int = 0x76,
    ) -> None:
        self._address = address
        self._i2c: Any = None
        self._calibration: dict[str, Any] | None = None
        self._temperature: float = 0.0
        self._humidity: float = 0.0
        self._pressure: float = 0.0

        if _HW_AVAILABLE:
            try:
                self._i2c = I2C(i2c_id, sda=Pin(sda), scl=Pin(scl), freq=400_000)
                self._load_calibration()
                self._configure()
            except Exception as e:
                print(f"[VOLT/BME280] Init error: {e}")

    def _configure(self) -> None:
        if self._i2c is None:
            return
        self._i2c.writeto_mem(self._address, _BME280_REG_CTRL_HUM, bytes([0x01])) # type: ignore
        self._i2c.writeto_mem(self._address, _BME280_REG_CTRL_MEAS, bytes([0x27])) # type: ignore
        self._i2c.writeto_mem(self._address, _BME280_REG_CONFIG, bytes([0x10])) # type: ignore

    def _load_calibration(self) -> None:
        if self._i2c is None:
            return
        try:
            raw = self._i2c.readfrom_mem(self._address, _BME280_REG_CALIB, 24)  # type: ignore
            raw2 = self._i2c.readfrom_mem(self._address, _BME280_REG_CALIB2, 7)  # type: ignore
            # H1 lives at a separate register (0xA1), not in the main calibration block
            raw_h1 = self._i2c.readfrom_mem(self._address, 0xA1, 1)  # type: ignore
            import struct
            dig = struct.unpack("<HhhHhhhhhhhh", raw)
            c: dict[str, Any] = {
                "T1": dig[0], "T2": dig[1], "T3": dig[2],
                "P1": dig[3], "P2": dig[4], "P3": dig[5],
                "P4": dig[6], "P5": dig[7], "P6": dig[8],
                "P7": dig[9], "P8": dig[10], "P9": dig[11],
                "H1": raw_h1[0],
                "H2": struct.unpack("<h", raw2[0:2])[0],
                "H3": raw2[2],
                "H4": (raw2[3] << 4) | (raw2[4] & 0x0F),
                "H5": (raw2[5] << 4) | (raw2[4] >> 4),
                "H6": struct.unpack("<b", bytes([raw2[6]]))[0],
            }
            self._calibration = c
        except Exception as e:
            print(f"[VOLT/BME280] Calibration load error: {e}")

    async def read(self) -> BaseSensor:
        """Read all three values from the sensor asynchronously."""
        if self._i2c is None:
            return self
            
        try:
            import uasyncio as asyncio
        except ImportError:
            import asyncio
        await asyncio.sleep(0)
        
        try:
            data = self._i2c.readfrom_mem(self._address, _BME280_REG_DATA, 8) # type: ignore
            temp, press, hum = self._compensate(data)
            self._temperature = temp
            self._pressure = press
            self._humidity = hum
        except Exception as e:
            print(f"[VOLT/BME280] Read error: {e}")
        return self

    def _compensate(self, data: bytes | bytearray | list[int]) -> tuple[float, float, float]:
        """Apply Bosch compensation formula."""
        adc_p = (data[0] << 12) | (data[1] << 4) | (data[2] >> 4)
        adc_t = (data[3] << 12) | (data[4] << 4) | (data[5] >> 4)
        adc_h = (data[6] << 8) | data[7]
        c: dict[str, Any] = self._calibration or {}

        T1, T2, T3 = c.get("T1", 0), c.get("T2", 0), c.get("T3", 0)
        var1 = ((adc_t / 16384.0) - (T1 / 1024.0)) * T2
        var2 = ((adc_t / 131072.0) - (T1 / 8192.0)) ** 2 * T3
        t_fine = var1 + var2
        temp = t_fine / 5120.0

        P1 = c.get("P1", 1)
        var1 = t_fine / 2.0 - 64000.0
        var2 = var1 * var1 * c.get("P6", 0) / 32768.0
        var2 = var2 + var1 * c.get("P5", 0) * 2.0
        var2 = var2 / 4.0 + c.get("P4", 0) * 65536.0
        var1 = (c.get("P3", 0) * var1 * var1 / 524288.0 + c.get("P2", 0) * var1) / 524288.0
        var1 = (1.0 + var1 / 32768.0) * P1
        if var1 == 0.0:
            press = 0.0
        else:
            press = 1048576.0 - adc_p
            press = (press - var2 / 4096.0) * 6250.0 / var1
            var1 = c.get("P9", 0) * press * press / 2147483648.0
            var2 = press * c.get("P8", 0) / 32768.0
            press = press + (var1 + var2 + c.get("P7", 0)) / 16.0
            press /= 100.0  # hPa

        hum = t_fine - 76800.0
        if hum != 0.0:
            hum = (adc_h - (c.get("H4", 0) * 64.0 + (c.get("H5", 0) / 16384.0) * hum)) * (
                c.get("H2", 0) / 65536.0 * (1.0 + c.get("H6", 0) / 67108864.0 * hum * (
                    1.0 + c.get("H3", 0) / 67108864.0 * hum))
            )
            hum = hum * (1.0 - c.get("H1", 0) * hum / 524288.0)
            hum = max(0.0, min(100.0, hum))

        return float(round(temp, 2)), float(round(press, 2)), float(round(hum, 2))

    @property
    def temperature(self) -> float:
        return self._temperature

    @property
    def humidity(self) -> float:
        return self._humidity

    @property
    def pressure(self) -> float:
        return self._pressure

    def to_dict(self) -> dict[str, Any]:
        return {
            "temp": self.temperature,
            "humidity": self.humidity,
            "pressure": self.pressure,
        }
