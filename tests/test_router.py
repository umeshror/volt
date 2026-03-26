"""
tests/test_router.py — Router unit tests.
"""

import pytest
from volt.router import Router


@pytest.fixture
def router():
    return Router()


def test_register_get_route(router):
    """GET route should appear in the HTTP registry."""
    def handler():
        return {"ok": True}

    router.add_http_route("GET", "/status", handler)
    result = router.resolve_http("GET", "/status")
    assert result is not None
    h, params = result
    assert h is handler
    assert params == {}


def test_register_post_route(router):
    """POST route should be independently registered."""
    def handler():
        return {}

    router.add_http_route("POST", "/data", handler)
    result = router.resolve_http("POST", "/data")
    assert result is not None
    h, params = result
    assert h is handler


def test_register_mqtt_route(router):
    """MQTT topic should be findable in the registry."""
    def handler(payload):
        pass

    router.add_mqtt_route("home/temp", handler)
    result = router.resolve_mqtt("home/temp")
    assert result is not None
    h, _ = result
    assert h is handler


def test_dynamic_path_params(router):
    """/sensor/{id} should resolve with id extracted from the path."""
    def handler(id):
        return {"id": id}

    router.add_http_route("GET", "/sensor/{id}", handler)
    result = router.resolve_http("GET", "/sensor/42")
    assert result is not None
    h, params = result
    assert h is handler
    assert params == {"id": "42"}


def test_unknown_route_returns_none(router):
    """Unregistered route should return None."""
    assert router.resolve_http("GET", "/nope") is None


def test_method_mismatch_returns_none(router):
    """POST handler should not match GET request."""
    router.add_http_route("POST", "/submit", lambda: {})
    assert router.resolve_http("GET", "/submit") is None


def test_query_string_stripped(router):
    """Query string should not affect route matching."""
    router.add_http_route("GET", "/data", lambda: {})
    result = router.resolve_http("GET", "/data?limit=10&offset=0")
    assert result is not None


def test_mqtt_wildcard_plus(router):
    """MQTT + wildcard should match a single topic segment."""
    def handler(payload):
        pass

    router.add_mqtt_route("home/+/set", handler)
    result = router.resolve_mqtt("home/lights/set")
    assert result is not None
    h, _ = result
    assert h is handler


def test_mqtt_wildcard_hash(router):
    """MQTT # wildcard should match any subtopics."""
    def handler(payload):
        pass

    router.add_mqtt_route("device/#", handler)
    assert router.resolve_mqtt("device/sensor/temperature") is not None
    assert router.resolve_mqtt("device/status") is not None


def test_ble_route(router):
    """BLE characteristic should be retrievable by name."""
    def handler():
        return 22.5

    router.add_ble_route("temperature", handler)
    h = router.resolve_ble("temperature")
    assert h is handler


def test_multiple_dynamic_segments(router):
    """Multiple path params should all be extracted correctly."""
    def handler(device, sensor):
        return {}

    router.add_http_route("GET", "/device/{device}/sensor/{sensor}", handler)
    result = router.resolve_http("GET", "/device/esp32-01/sensor/temp")
    assert result is not None
    h, params = result
    assert params == {"device": "esp32-01", "sensor": "temp"}


def test_mqtt_no_match_returns_none(router):
    """Non-matching MQTT topic should return None."""
    router.add_mqtt_route("home/temp", lambda p: None)
    assert router.resolve_mqtt("office/temp") is None
