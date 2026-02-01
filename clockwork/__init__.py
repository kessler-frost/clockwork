"""
Clockwork - Intelligent, Composable Primitives for Infrastructure in Python.

Define resources with Pydantic models. Specify what matters, leave the rest
to intelligent completion. Deploy with Pulumi.
"""

from .core import ClockworkCore
from .settings import ClockworkSettings, get_settings, reload_settings

try:
    from ._version import __version__
except ImportError:
    __version__ = "0.0.0.dev0"

__all__ = [
    "ClockworkCore",
    "ClockworkSettings",
    "get_settings",
    "reload_settings",
]
