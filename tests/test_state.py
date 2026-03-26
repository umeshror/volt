"""
tests/test_state.py — State unit tests.
"""

import os
import pytest
from volt.state import State

TMP_STATE = "/tmp/volt_test_state.json"
TMP_STATE_TMP = "/tmp/volt_test_state.tmp"


@pytest.fixture(autouse=True)
def cleanup():
    """Remove test state files before and after each test."""
    for p in (TMP_STATE, TMP_STATE_TMP):
        try:
            os.remove(p)
        except FileNotFoundError:
            pass
    yield
    for p in (TMP_STATE, TMP_STATE_TMP):
        try:
            os.remove(p)
        except FileNotFoundError:
            pass


@pytest.fixture
def state():
    return State(path=TMP_STATE, tmp_path=TMP_STATE_TMP)


def test_set_and_get(state):
    """Value should be retrievable after set()."""
    state.set("key", "value")
    assert state.get("key") == "value"


def test_default_on_missing_key(state):
    """get() with a default should return that default for missing keys."""
    assert state.get("nonexistent", default=99) == 99


def test_persistence():
    """A new State instance should load data written by a previous one."""
    s1 = State(path=TMP_STATE, tmp_path=TMP_STATE_TMP)
    s1.set("last_watered", 1234567890)

    s2 = State(path=TMP_STATE, tmp_path=TMP_STATE_TMP)
    assert s2.get("last_watered") == 1234567890


def test_delete(state):
    """Key should be absent after delete()."""
    state.set("temp", 22.5)
    state.delete("temp")
    assert state.get("temp") is None


def test_update_batch(state):
    """All keys should be present after update({...})."""
    state.update({"temp": 22.5, "humidity": 60, "status": "ok"})
    assert state.get("temp") == 22.5
    assert state.get("humidity") == 60
    assert state.get("status") == "ok"


def test_overwrite_existing_key(state):
    """set() on an existing key should overwrite it."""
    state.set("count", 1)
    state.set("count", 2)
    assert state.get("count") == 2


def test_all_returns_copy(state):
    """all() should return a dict equal to the internal data."""
    state.update({"a": 1, "b": 2})
    result = state.all()
    assert result == {"a": 1, "b": 2}
    # Modifying the returned dict should not affect internal state
    result["c"] = 3
    assert state.get("c") is None
