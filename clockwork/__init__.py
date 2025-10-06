"""
Clockwork - Factory for intelligent declarative infrastructure tasks.

Define infrastructure in Python using Pydantic models. Clockwork uses AI
to generate dynamic content, then compiles to PyInfra for deployment.

Two-stage compilation:
1. AI generates artifacts (via OpenRouter)
2. Templates compile to PyInfra operations

Start with simple Python resources, let AI handle the complexity.
"""

from .core import ClockworkCore
from .settings import ClockworkSettings, get_settings, reload_settings

__version__ = "0.2.0"
__all__ = [
    "ClockworkCore",
    "ClockworkSettings",
    "get_settings",
    "reload_settings",
]
