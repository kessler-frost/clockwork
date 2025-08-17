"""
Clockwork - Factory for intelligent declarative tasks.

Clockwork provides a simple three-phase pipeline for building intelligent task automation:
1. Intake: Parse .cw (HCL-ish) task definitions into IR (Intermediate Representation)
2. Assembly: Convert IR into ActionList with dependencies and ordering
3. Forge: Compile ActionList to executable artifacts using AI agents and execute them

Key components:
- ClockworkCore: Main pipeline orchestrator for task execution
- Models: Pydantic data models for all pipeline stages
- CLI: Command-line interface (plan, build, apply, verify)

Start with infrastructure tasks, expand to any domain.
"""

from .core import ClockworkCore
from .models import (
    IR, ActionList, ArtifactBundle, ClockworkState, ClockworkConfig,
    ActionType, ResourceType, ExecutionStatus
)
from . import intake, assembly, forge

__version__ = "0.1.0"
__all__ = [
    "ClockworkCore",
    "IR", "ActionList", "ArtifactBundle", "ClockworkState", "ClockworkConfig",
    "ActionType", "ResourceType", "ExecutionStatus",
    "intake", "assembly", "forge"
]