"""
Daemon types and enums for Clockwork Daemon.

This module contains shared types, enums, and data classes used across
the daemon modules to avoid circular imports.
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Dict, Any


class DaemonState(str, Enum):
    """Daemon operational states."""
    STOPPED = "stopped"
    STARTING = "starting" 
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    ERROR = "error"


class AutoFixPolicy(str, Enum):
    """Auto-fix policy levels."""
    DISABLED = "disabled"           # No auto-fixes, only manual approval
    CONSERVATIVE = "conservative"   # Only safe artifact patches
    MODERATE = "moderate"          # Artifact patches + safe .cw changes
    AGGRESSIVE = "aggressive"      # All fixes except destructive operations


class PatchType(str, Enum):
    """Types of patches that can be applied."""
    ARTIFACT_PATCH = "artifact_patch"     # Regenerate artifacts only
    CONFIG_PATCH = "config_patch"         # Modify .cw configuration
    RUNBOOK = "runbook"                   # Manual intervention required
    NO_ACTION = "no_action"               # No fix needed/possible


class RiskLevel(str, Enum):
    """Risk levels for fixes."""
    LOW = "low"           # Safe to auto-apply
    MEDIUM = "medium"     # Requires approval for some policies  
    HIGH = "high"         # Requires manual approval
    CRITICAL = "critical" # Never auto-apply


@dataclass
class DaemonConfig:
    """Configuration for the Clockwork daemon."""
    
    # Core settings
    watch_paths: List[Path] = field(default_factory=list)
    check_interval_seconds: int = 60
    auto_fix_policy: AutoFixPolicy = AutoFixPolicy.CONSERVATIVE
    
    # Rate limiting and safety
    max_fixes_per_hour: int = 2
    cooldown_minutes: int = 10
    max_consecutive_failures: int = 3
    
    # Drift detection settings
    drift_check_interval_minutes: int = 5
    staleness_threshold_hours: int = 1
    
    # File watching settings
    watch_file_patterns: List[str] = field(default_factory=lambda: ["*.cw", "*.cwvars"])
    ignore_patterns: List[str] = field(default_factory=lambda: [".git/*", "*.tmp", "*.bak"])
    
    # Pipeline settings
    timeout_per_step: int = 300
    enable_verification_after_fix: bool = True
    
    # Logging and monitoring
    log_level: str = "INFO"
    enable_metrics: bool = True
    metrics_port: int = 8080
    
    def validate(self) -> List[str]:
        """Validate configuration and return any issues."""
        issues = []
        
        if self.check_interval_seconds < 10:
            issues.append("check_interval_seconds must be at least 10 seconds")
        
        if self.max_fixes_per_hour < 1:
            issues.append("max_fixes_per_hour must be at least 1")
        
        if self.cooldown_minutes < 1:
            issues.append("cooldown_minutes must be at least 1")
        
        if not self.watch_paths:
            issues.append("watch_paths cannot be empty")
        
        for path in self.watch_paths:
            if not path.exists():
                issues.append(f"watch_path does not exist: {path}")
        
        return issues


@dataclass
class FixDecision:
    """Decision on how to fix a detected drift."""
    
    patch_type: PatchType
    should_auto_apply: bool
    risk_level: RiskLevel
    reason: str
    description: str = ""
    suggested_actions: List[str] = field(default_factory=list)
    suggested_changes: Dict[str, Any] = field(default_factory=dict)
    risk_factors: List[str] = field(default_factory=list)
    additional_context: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "patch_type": self.patch_type.value,
            "should_auto_apply": self.should_auto_apply,
            "risk_level": self.risk_level.value,
            "reason": self.reason,
            "description": self.description,
            "suggested_actions": self.suggested_actions,
            "suggested_changes": self.suggested_changes,
            "risk_factors": self.risk_factors,
            "additional_context": self.additional_context
        }