import pytest
from unittest.mock import MagicMock
import volt.sensors.dht22 as dht22_mod
import volt.sensors.ultrasonic as us_mod
from volt.sensors.dht22 import DHT22
from volt.sensors.ultrasonic import Ultrasonic
from volt.exceptions import HardwareBindingError

@pytest.fixture
def mock_hardware(monkeypatch):
    mock_machine = MagicMock()
    mock_dht = MagicMock()
    
    monkeypatch.setattr(dht22_mod, "dht", mock_dht)
    monkeypatch.setattr(dht22_mod, "machine", mock_machine)
    
    monkeypatch.setattr(us_mod, "_HW_AVAILABLE", True)
    monkeypatch.setattr(us_mod, "machine", mock_machine)
    
    return mock_machine, mock_dht

@pytest.mark.asyncio
async def test_dht22_async_read(mock_hardware):
    mock_machine, mock_dht = mock_hardware
    
    sensor_mock = MagicMock()
    sensor_mock.temperature.return_value = 25.5
    sensor_mock.humidity.return_value = 60.0
    mock_dht.DHT22.return_value = sensor_mock
    
    sensor = DHT22(pin=4)
    assert sensor.temperature == 0.0  # Initial state
    assert sensor.humidity == 0.0
    
    await sensor.read()
    
    assert sensor.temperature == 25.5
    assert sensor.humidity == 60.0
    sensor_mock.measure.assert_called_once()

@pytest.mark.asyncio
async def test_dht22_read_failure(mock_hardware):
    mock_machine, mock_dht = mock_hardware
    
    sensor_mock = MagicMock()
    sensor_mock.measure.side_effect = Exception("HW Error")
    mock_dht.DHT22.return_value = sensor_mock
    
    sensor = DHT22(pin=4)
    with pytest.raises(HardwareBindingError):
        await sensor.read()

@pytest.mark.asyncio
async def test_ultrasonic_async_read(mock_hardware):
    mock_machine, _ = mock_hardware
    
    sensor = Ultrasonic(trigger=4, echo=5)
    
    import asyncio
    async def simulate_irq():
        await asyncio.sleep(0.005)
        sensor._pulse_us = 1000
    
    asyncio.create_task(simulate_irq())
    await sensor.read()
    
    assert sensor.cm == round(1000 * 0.01715, 1)
    
@pytest.mark.asyncio
async def test_ultrasonic_timeout(mock_hardware):
    mock_machine, _ = mock_hardware
    
    sensor = Ultrasonic(trigger=4, echo=5)
    await sensor.read()
    
    assert sensor.cm == -1.0

def test_ultrasonic_derived_properties(mock_hardware):
    mock_machine, _ = mock_hardware
    sensor = Ultrasonic(trigger=4, echo=5)
    sensor._cm = 10.0
    
    assert sensor.mm == 100.0
    assert sensor.inches == round(10.0 / 2.54, 2)
