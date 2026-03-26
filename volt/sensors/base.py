"""
volt/sensors/base.py — Abstract base class for all VOLT sensors.
"""


class BaseSensor:
    """
    Contract every sensor must satisfy.

    Subclasses must implement `read()` and `to_dict()`.
    """

    def read(self):
        """Trigger a hardware read. Raises NotImplementedError if not implemented."""
        raise NotImplementedError

    def to_dict(self) -> dict:
        """Return the latest readings as a plain dict."""
        raise NotImplementedError
