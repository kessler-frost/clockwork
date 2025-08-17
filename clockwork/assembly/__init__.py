"""
Assembly module for the clockwork project.

This module contains the planning and diffing logic for converting intermediate
representation (IR) to action lists and computing state differences.
"""

from .planner import (
    convert_ir_to_actions,
    validate_action_list,
    optimize_action_list,
)
from ..models import Action, ActionList, ActionType

from .differ import (
    StateDiff,
    DiffType,
    compute_state_diff,
    merge_state_diffs,
    apply_state_diff,
)

__all__ = [
    # Planner exports
    "ActionList",
    "Action", 
    "ActionType",
    "convert_ir_to_actions",
    "validate_action_list",
    "optimize_action_list",
    # Differ exports
    "StateDiff",
    "DiffType",
    "compute_state_diff",
    "merge_state_diffs",
    "apply_state_diff",
]