import pytest
from volt.config import ConfigManager
from volt.state import State
import os

@pytest.fixture
def temp_state(tmp_path):
    path = str(tmp_path / "state.json")
    state = State(path)
    yield state
    if os.path.exists(path):
        os.remove(path)

def test_config_defaults(temp_state):
    mgr = ConfigManager(temp_state)
    assert mgr.get("wifi_ssid") == ""
    assert mgr.get("wifi_ap_ssid") == "VOLT-Setup"
    assert mgr.get("mqtt_port") == 1883

def test_config_set_get(temp_state):
    mgr = ConfigManager(temp_state)
    mgr.set("wifi_ssid", "test_net")
    assert mgr.get("wifi_ssid") == "test_net"

def test_is_configured(temp_state):
    mgr = ConfigManager(temp_state)
    assert not mgr.is_configured()
    mgr.set("wifi_ssid", "Home_Suite")
    assert mgr.is_configured()
