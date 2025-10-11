"""
Clockwork - Intelligent Infrastructure Orchestration in Python.

Define infrastructure in Python using Pydantic models. Clockwork orchestrates
deployment using AI-powered intelligence and PyInfra automation.

Orchestration pipeline:
1. AI generates artifacts and configurations (via OpenRouter)
2. Compiles to PyInfra operations
3. Automates deployment

Pure Python infrastructure with intelligent AI assistance.
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
