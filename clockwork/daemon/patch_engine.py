"""
Patch Engine for Clockwork Daemon - Auto-fix policy engine with decision rules.

This module implements the PatchEngine class which determines appropriate fixes
for detected drift based on configurable policies and safety rules.
"""

import logging
from typing import Dict, List, Any, Optional, Set
from datetime import datetime

from ..models import ResourceType
from .types import AutoFixPolicy, PatchType, RiskLevel, FixDecision


logger = logging.getLogger(__name__)




class PatchEngine:
    """
    Auto-fix policy engine that determines appropriate fixes for detected drift.
    
    The engine implements the decision rules from the README:
    - Auto-apply: artifact patches to retries/healthchecks/logging
    - Require approval: .cw changes to ports, mounts, privileges
    - Never auto: destructive ops or secrets rotation → runbook
    """
    
    def __init__(self, default_policy: AutoFixPolicy):
        """Initialize the patch engine with a default policy."""
        self.default_policy = default_policy
        self.logger = logging.getLogger(__name__ + ".PatchEngine")
        
        # Define safe fields that can be auto-fixed with artifact patches
        self.safe_artifact_fields = {
            "retries", "retry_delay", "timeout", "healthcheck", "logging", 
            "monitoring", "metrics", "labels", "annotations", "restart_policy"
        }
        
        # Define sensitive fields that require approval for config changes
        self.sensitive_config_fields = {
            "ports", "mounts", "volumes", "secrets", "privileges", "security_context",
            "capabilities", "host_network", "host_pid", "host_ipc", "image"
        }
        
        # Define destructive operations that always require manual intervention
        self.destructive_operations = {
            "delete", "destroy", "remove", "purge", "reset", "rotate_secrets",
            "change_security_context", "escalate_privileges"
        }
    
    def determine_fix_decision(
        self, 
        resource_id: str,
        resource_type: str,
        drift_details: Dict[str, Any],
        current_policy: Optional[AutoFixPolicy] = None
    ) -> FixDecision:
        """
        Determine the appropriate fix for detected drift.
        
        Args:
            resource_id: Identifier of the drifted resource
            resource_type: Type of the resource
            drift_details: Details about the detected drift
            current_policy: Policy to use (defaults to engine's default)
            
        Returns:
            FixDecision with the determined fix approach
        """
        policy = current_policy or self.default_policy
        
        self.logger.debug(f"Determining fix for {resource_id} with policy {policy.value}")
        
        try:
            # Extract drift information
            drift_type = drift_details.get("drift_type", "unknown")
            severity = drift_details.get("severity", "medium")
            config_drift = drift_details.get("config_drift_details", {})
            runtime_drift = drift_details.get("runtime_drift_details", {})
            suggested_actions = drift_details.get("suggested_actions", [])
            
            # Check for destructive operations first
            if self._is_destructive_operation(drift_details):
                return FixDecision(
                    patch_type=PatchType.RUNBOOK,
                    should_auto_apply=False,
                    risk_level=RiskLevel.CRITICAL,
                    reason="Destructive operation detected - manual intervention required",
                    description="This change involves destructive operations that could cause data loss or service disruption",
                    suggested_actions=suggested_actions,
                    risk_factors=["destructive_operation", "potential_data_loss"]
                )
            
            # Analyze the type of changes needed
            change_analysis = self._analyze_required_changes(config_drift, runtime_drift)
            
            # Determine patch type based on change analysis
            if change_analysis["config_changes_required"]:
                return self._decide_config_patch(
                    resource_id, resource_type, change_analysis, policy, drift_details
                )
            elif change_analysis["artifact_changes_sufficient"]:
                return self._decide_artifact_patch(
                    resource_id, resource_type, change_analysis, policy, drift_details
                )
            else:
                return self._decide_no_action(resource_id, drift_details)
        
        except Exception as e:
            self.logger.error(f"Error determining fix decision for {resource_id}: {e}")
            return FixDecision(
                patch_type=PatchType.RUNBOOK,
                should_auto_apply=False,
                risk_level=RiskLevel.HIGH,
                reason=f"Error analyzing drift: {str(e)}",
                description="An error occurred while analyzing the drift, manual review required",
                suggested_actions=["Manual investigation required", "Check daemon logs"],
                risk_factors=["analysis_error"]
            )
    
    def _is_destructive_operation(self, drift_details: Dict[str, Any]) -> bool:
        """Check if the drift involves destructive operations."""
        
        # Check suggested actions for destructive keywords
        suggested_actions = drift_details.get("suggested_actions", [])
        for action in suggested_actions:
            action_lower = action.lower()
            for destructive_op in self.destructive_operations:
                if destructive_op in action_lower:
                    return True
        
        # Check config drift for destructive changes
        config_drift = drift_details.get("config_drift_details", {})
        removed_fields = config_drift.get("removed_fields", {})
        
        # Check if critical fields are being removed
        critical_removals = {"image", "command", "entrypoint", "volumes"}
        if any(field in removed_fields for field in critical_removals):
            return True
        
        return False
    
    def _analyze_required_changes(
        self, 
        config_drift: Dict[str, Any], 
        runtime_drift: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Analyze what types of changes are required to fix the drift.
        
        Returns:
            Dictionary with analysis results
        """
        analysis = {
            "config_changes_required": False,
            "artifact_changes_sufficient": False,
            "changed_fields": set(),
            "sensitive_fields_affected": set(),
            "safe_fields_affected": set(),
            "runtime_issues_only": False
        }
        
        # Analyze configuration drift
        if config_drift.get("has_drift", False):
            changed_fields = set(config_drift.get("changed_fields", {}).keys())
            added_fields = set(config_drift.get("added_fields", {}).keys())
            removed_fields = set(config_drift.get("removed_fields", {}).keys())
            
            all_changed_fields = changed_fields | added_fields | removed_fields
            analysis["changed_fields"] = all_changed_fields
            
            # Categorize fields
            analysis["sensitive_fields_affected"] = all_changed_fields & self.sensitive_config_fields
            analysis["safe_fields_affected"] = all_changed_fields & self.safe_artifact_fields
            
            # Determine if config changes are required
            if analysis["sensitive_fields_affected"] or analysis["changed_fields"] - self.safe_artifact_fields:
                analysis["config_changes_required"] = True
            elif analysis["safe_fields_affected"]:
                analysis["artifact_changes_sufficient"] = True
        
        # Analyze runtime drift
        if runtime_drift.get("has_drift", False):
            # Runtime-only issues can often be fixed with artifact patches
            if not config_drift.get("has_drift", False):
                analysis["runtime_issues_only"] = True
                analysis["artifact_changes_sufficient"] = True
        
        return analysis
    
    def _decide_config_patch(
        self,
        resource_id: str,
        resource_type: str,
        change_analysis: Dict[str, Any],
        policy: AutoFixPolicy,
        drift_details: Dict[str, Any]
    ) -> FixDecision:
        """Decide on configuration patch approach."""
        
        sensitive_fields = change_analysis["sensitive_fields_affected"]
        
        # Calculate risk level
        if sensitive_fields:
            risk_level = RiskLevel.HIGH if len(sensitive_fields) > 2 else RiskLevel.MEDIUM
            risk_factors = [f"sensitive_field_{field}" for field in sensitive_fields]
        else:
            risk_level = RiskLevel.LOW
            risk_factors = ["config_change"]
        
        # Determine if auto-apply based on policy
        should_auto_apply = False
        
        if policy == AutoFixPolicy.AGGRESSIVE:
            should_auto_apply = risk_level in [RiskLevel.LOW, RiskLevel.MEDIUM]
        elif policy == AutoFixPolicy.MODERATE:
            should_auto_apply = risk_level == RiskLevel.LOW and len(sensitive_fields) == 0
        # CONSERVATIVE and DISABLED never auto-apply config patches
        
        reason = self._generate_config_patch_reason(sensitive_fields, should_auto_apply, policy)
        
        suggested_changes = self._generate_config_changes(drift_details)
        
        return FixDecision(
            patch_type=PatchType.CONFIG_PATCH,
            should_auto_apply=should_auto_apply,
            risk_level=risk_level,
            reason=reason,
            description=f"Configuration changes required for {resource_id}",
            suggested_actions=drift_details.get("suggested_actions", []),
            suggested_changes=suggested_changes,
            risk_factors=risk_factors,
            additional_context={
                "sensitive_fields": list(sensitive_fields),
                "changed_fields": list(change_analysis["changed_fields"]),
                "policy": policy.value
            }
        )
    
    def _decide_artifact_patch(
        self,
        resource_id: str,
        resource_type: str,
        change_analysis: Dict[str, Any],
        policy: AutoFixPolicy,
        drift_details: Dict[str, Any]
    ) -> FixDecision:
        """Decide on artifact patch approach."""
        
        # Artifact patches are generally safe for most policies
        should_auto_apply = policy != AutoFixPolicy.DISABLED
        risk_level = RiskLevel.LOW
        
        # Special cases that might increase risk
        risk_factors = []
        if change_analysis["runtime_issues_only"]:
            risk_factors.append("runtime_drift")
        if drift_details.get("severity") == "critical":
            risk_level = RiskLevel.MEDIUM
            risk_factors.append("critical_severity")
        
        reason = f"Artifact patch can resolve drift in safe fields: {change_analysis['safe_fields_affected']}"
        
        return FixDecision(
            patch_type=PatchType.ARTIFACT_PATCH,
            should_auto_apply=should_auto_apply,
            risk_level=risk_level,
            reason=reason,
            description=f"Artifact-only fix for {resource_id} (no .cw changes needed)",
            suggested_actions=drift_details.get("suggested_actions", []),
            risk_factors=risk_factors,
            additional_context={
                "safe_fields": list(change_analysis["safe_fields_affected"]),
                "runtime_only": change_analysis["runtime_issues_only"],
                "policy": policy.value
            }
        )
    
    def _decide_no_action(self, resource_id: str, drift_details: Dict[str, Any]) -> FixDecision:
        """Decide when no action is appropriate."""
        return FixDecision(
            patch_type=PatchType.NO_ACTION,
            should_auto_apply=False,
            risk_level=RiskLevel.LOW,
            reason="No actionable drift detected or changes not recommended",
            description=f"No automatic fix available for {resource_id}",
            suggested_actions=drift_details.get("suggested_actions", ["Manual review recommended"]),
            additional_context=drift_details
        )
    
    def _generate_config_patch_reason(
        self, 
        sensitive_fields: Set[str], 
        should_auto_apply: bool, 
        policy: AutoFixPolicy
    ) -> str:
        """Generate reason for config patch decision."""
        
        if sensitive_fields:
            fields_str = ", ".join(sensitive_fields)
            if should_auto_apply:
                return f"Auto-applying config patch for sensitive fields: {fields_str} (policy: {policy.value})"
            else:
                return f"Manual approval required for sensitive fields: {fields_str}"
        else:
            if should_auto_apply:
                return f"Auto-applying safe config patch (policy: {policy.value})"
            else:
                return f"Config patch requires approval (policy: {policy.value})"
    
    def _generate_config_changes(self, drift_details: Dict[str, Any]) -> Dict[str, Any]:
        """Generate suggested configuration changes from drift details."""
        config_drift = drift_details.get("config_drift_details", {})
        
        suggested_changes = {}
        
        # Extract specific field changes
        changed_fields = config_drift.get("changed_fields", {})
        for field, change_info in changed_fields.items():
            if isinstance(change_info, dict) and "desired" in change_info:
                suggested_changes[field] = change_info["desired"]
        
        # Extract added fields
        added_fields = config_drift.get("added_fields", {})
        suggested_changes.update(added_fields)
        
        # Mark removed fields for removal
        removed_fields = config_drift.get("removed_fields", {})
        for field in removed_fields:
            suggested_changes[field] = None  # None indicates removal
        
        return suggested_changes
    
    def get_policy_summary(self, policy: AutoFixPolicy) -> Dict[str, Any]:
        """Get a summary of what a policy allows."""
        return {
            "policy": policy.value,
            "auto_apply_artifact_patches": policy != AutoFixPolicy.DISABLED,
            "auto_apply_safe_config_patches": policy in [AutoFixPolicy.MODERATE, AutoFixPolicy.AGGRESSIVE],
            "auto_apply_sensitive_config_patches": policy == AutoFixPolicy.AGGRESSIVE,
            "never_auto_apply": list(self.destructive_operations),
            "safe_artifact_fields": list(self.safe_artifact_fields),
            "sensitive_config_fields": list(self.sensitive_config_fields)
        }


# =============================================================================
# Decision Rule Helpers
# =============================================================================

def is_safe_for_auto_fix(drift_details: Dict[str, Any], policy: AutoFixPolicy) -> bool:
    """Quick check if drift is safe for auto-fix under the given policy."""
    engine = PatchEngine(policy)
    decision = engine.determine_fix_decision(
        resource_id="test",
        resource_type="service",
        drift_details=drift_details,
        current_policy=policy
    )
    return decision.should_auto_apply and decision.risk_level in [RiskLevel.LOW, RiskLevel.MEDIUM]


def classify_drift_risk(drift_details: Dict[str, Any]) -> RiskLevel:
    """Classify the risk level of detected drift."""
    engine = PatchEngine(AutoFixPolicy.CONSERVATIVE)
    decision = engine.determine_fix_decision(
        resource_id="test",
        resource_type="service", 
        drift_details=drift_details
    )
    return decision.risk_level