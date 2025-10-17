"""
Clockwork - Intelligent, Composable Primitives for Infrastructure.

Build infrastructure using composable primitives in Python. Clockwork provides
atomic building blocks (containers, files, services) with adjustable AI assistance.

You choose how much AI handles per primitive:
- Specify everything → Full control, zero AI
- Specify key details → AI fills gaps
- Describe requirements → AI handles implementation

Pure Python primitives with flexible, intelligent completion and Pulumi deployment.
"""

from .core import ClockworkCore
from .settings import ClockworkSettings, get_settings, reload_settings

__version__ = "0.3.0"
__all__ = [
    "ClockworkCore",
    "ClockworkSettings",
    "get_settings",
    "reload_settings",
]
