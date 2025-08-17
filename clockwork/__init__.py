"""
Clockwork - Ultra-simple, agent-assisted infrastructure tool with deterministic core.

Clockwork provides a simple three-phase pipeline:
1. Intake: Parse .cw (HCL-ish) files into IR (Intermediate Representation)
2. Assembly: Convert IR into ActionList with dependencies and ordering
3. Forge: Compile ActionList to executable artifacts using AI agents and execute them

Key components:
- ClockworkCore: Main pipeline orchestrator
- Models: Pydantic data models for all pipeline stages
- CLI: Command-line interface (plan, build, apply, verify)
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