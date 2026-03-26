import pytest
from volt.config import ConfigManager
from volt.state import State
from volt.captive_portal import CaptivePortal
from volt.http_server import Request
import os

@pytest.fixture
def temp_config(tmp_path):
    path = str(tmp_path / "portal_state.json")
    state = State(path)
    yield ConfigManager(state)
    if os.path.exists(path):
        os.remove(path)

def test_portal_index(temp_config):
    portal = CaptivePortal(temp_config)
    req = Request("GET", "/", {}, None, {})
    resp = portal._handle_index(req)
    assert "VOLT Setup" in resp
    assert "<form action=\"/save\"" in resp

@pytest.mark.asyncio
async def test_portal_save(temp_config):
    portal = CaptivePortal(temp_config)
    body = "wifi_ssid=MyNet&wifi_password=secret&mqtt_broker=10.0.0.1"
    req = Request("POST", "/save", {}, body, {})
    resp = portal._handle_save(req)

    
    assert "Configuration saved" in resp
    assert temp_config.get("wifi_ssid") == "MyNet"
    assert temp_config.get("wifi_password") == "secret"
    assert temp_config.get("mqtt_broker") == "10.0.0.1"
