"""
Clockwork - Intelligent Infrastructure Orchestration in Python.

Define infrastructure in Python using Pydantic models. Clockwork orchestrates
deployment using AI-powered intelligence and Pulumi automation.

Orchestration pipeline:
1. AI generates artifacts and configurations (via PydanticAI)
2. Compiles to Pulumi resources
3. Automates deployment with state management

Pure Python infrastructure with intelligent AI assistance.
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
