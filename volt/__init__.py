"""
VOLT — FastAPI-inspired IoT framework for MicroPython.

Users import everything they need from this single module:

    from volt import App, WiFiConfig, MQTTConfig
"""

from .app import App
from .connectivity import WiFiConfig, MQTTConfig

__all__ = ["App", "WiFiConfig", "MQTTConfig"]
__version__ = "0.1.0"
