"""
volt/sensors/base.py — Abstract base class for all VOLT sensors.
"""

from __future__ import annotations

try:
    from typing import Any
except ImportError:
    pass

class BaseSensor:
    """
    Contract every sensor must satisfy.

    Subclasses must implement `read()` and `to_dict()`.
    """

    async def read(self) -> BaseSensor:
        """Trigger an asynchronous hardware read. Raises NotImplementedError if not implemented."""
        raise NotImplementedError

    def to_dict(self) -> dict[str, Any]:
        """Return the latest readings as a plain dict."""
        raise NotImplementedError
