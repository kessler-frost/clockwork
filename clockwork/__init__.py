"""
Clockwork - Factory for intelligent declarative tasks.

Clockwork provides a simplified two-phase pipeline for building intelligent task automation:
1. Parse: Convert .cw (HCL-ish) task definitions directly to pyinfra operations
2. Execute: Run pyinfra operations on target infrastructure

Key components:
- ClockworkCore: Main pipeline orchestrator for task execution
- Models: Pydantic data models for all pipeline stages
- CLI: Command-line interface (plan, apply, verify)
- PyInfraParser: Direct conversion from .cw files to pyinfra Python code

Start with infrastructure tasks, expand to any domain.
"""

from .models import (
    IR, ResourceType, ActionType, ExecutionStatus
)

__version__ = "0.1.0"
__all__ = [
    "IR", "ResourceType", "ActionType", "ExecutionStatus"
]