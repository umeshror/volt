"""
volt/exceptions.py — Global exception hierarchy for VOLT.

This module defines all domain-specific errors thrown by the framework,
enabling developers to build resilient error-handling logic.
"""

class VoltError(Exception):
    """Base generic exception for all VOLT framework errors."""
    pass

class NetworkError(VoltError):
    """Raised when a Wi-Fi or MQTT connection cannot be established or drops unexpectedly."""
    pass

class StateError(VoltError):
    """Raised when the persistent state cannot be read, written, or is corrupted."""
    pass

class HardwareBindingError(VoltError):
    """Raised when a sensor or hardware peripheral fails to initialize or communicate."""
    pass
