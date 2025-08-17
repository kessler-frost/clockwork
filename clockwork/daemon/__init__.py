"""
Clockwork Daemon module for continuous reconciliation and drift detection.

This module provides the ClockworkDaemon class and related functionality for:
- File system watching of .cw configuration files
- Drift detection and monitoring
- Auto-fix policy engine with decision rules
- Rate limiting and safety controls
- Integration with core Clockwork pipeline
"""

from .types import AutoFixPolicy, DaemonConfig, PatchType, FixDecision, DaemonState, RiskLevel
from .loop import ClockworkDaemon
from .patch_engine import PatchEngine
from .rate_limiter import RateLimiter, CooldownManager

__all__ = [
    'ClockworkDaemon',
    'AutoFixPolicy', 
    'DaemonConfig',
    'DaemonState',
    'PatchEngine',
    'PatchType',
    'FixDecision',
    'RiskLevel',
    'RateLimiter',
    'CooldownManager'
]