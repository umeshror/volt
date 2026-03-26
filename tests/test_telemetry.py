import pytest
from unittest.mock import AsyncMock, MagicMock
from volt.telemetry import Telemetry

@pytest.fixture
def mock_app():
    app = MagicMock()
    app.uptime.return_value = 120
    app.device_id = "test-device"
    app.mqtt = MagicMock()
    app.every.return_value = lambda f: f
    return app

def test_telemetry_collects_fallback_metrics(mock_app):
    t = Telemetry(mock_app)
    metrics = t.collect()
    
    assert metrics["uptime"] == 120
    assert "mem_free" in metrics
    assert "disk_free" in metrics
    assert "rssi" in metrics

def test_telemetry_auto_publish_registers_task(mock_app):
    t = Telemetry(mock_app)
    t.auto_publish(60)
    mock_app.every.assert_called_with(60)

@pytest.mark.asyncio
async def test_telemetry_publish_task_sends_mqtt(mock_app):
    t = Telemetry(mock_app)
    await t._publish_task()
    
    mock_app.mqtt.publish.assert_called_once()
    args = mock_app.mqtt.publish.call_args[0]
    assert args[0] == "telemetry/test-device"
    assert "uptime" in args[1]
