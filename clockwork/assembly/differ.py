"""
Differ module for computing state differences in the clockwork system.

This module provides functionality to compare desired state vs current state
and compute what changes need to be made to achieve the desired configuration.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union, Tuple
import logging
from copy import deepcopy
from datetime import datetime, timedelta
from ..models import ClockworkState, ResourceState as ModelResourceState, ExecutionStatus


logger = logging.getLogger(__name__)


class DiffType(Enum):
    """Enumeration of types of differences that can be detected."""
    
    CREATE = "create"      # Resource needs to be created
    UPDATE = "update"      # Resource needs to be updated
    DELETE = "delete"      # Resource needs to be deleted
    NO_CHANGE = "no_change"  # No changes needed


class DriftType(Enum):
    """Types of drift that can be detected."""
    
    CONFIGURATION_DRIFT = "configuration_drift"  # Config has changed
    RUNTIME_DRIFT = "runtime_drift"              # Runtime state differs from config
    EXTERNAL_DRIFT = "external_drift"            # External changes detected
    NO_DRIFT = "no_drift"                        # No drift detected


class DriftSeverity(Enum):
    """Severity levels for drift detection."""
    
    CRITICAL = "critical"    # Requires immediate attention
    HIGH = "high"           # Should be addressed soon
    MEDIUM = "medium"       # Should be monitored
    LOW = "low"            # Minor drift
    INFO = "info"          # Informational only


@dataclass
class DriftDetection:
    """
    Represents drift detection for a resource.
    
    Attributes:
        resource_id: Resource identifier
        resource_type: Type of resource
        drift_type: Type of drift detected
        severity: Severity of the drift
        detected_at: When drift was detected
        last_checked: When resource was last checked
        config_drift_details: Details about configuration drift
        runtime_drift_details: Details about runtime drift
        suggested_actions: Suggested remediation actions
        drift_score: Numeric score indicating amount of drift (0-100)
    """
    
    resource_id: str
    resource_type: str
    drift_type: DriftType
    severity: DriftSeverity
    detected_at: datetime = field(default_factory=datetime.now)
    last_checked: datetime = field(default_factory=datetime.now)
    config_drift_details: Dict[str, Any] = field(default_factory=dict)
    runtime_drift_details: Dict[str, Any] = field(default_factory=dict)
    suggested_actions: List[str] = field(default_factory=list)
    drift_score: float = 0.0
    
    def is_stale(self, max_age_minutes: int = 60) -> bool:
        """Check if drift detection is stale."""
        cutoff = datetime.now() - timedelta(minutes=max_age_minutes)
        return self.last_checked < cutoff
    
    def requires_immediate_action(self) -> bool:
        """Check if drift requires immediate action."""
        return self.severity in [DriftSeverity.CRITICAL, DriftSeverity.HIGH]


@dataclass
class StateDiff:
    """
    Represents a difference between desired and current state.
    
    Attributes:
        resource_type: Type of resource (e.g., 'service', 'namespace', 'configmap')
        resource_name: Name/identifier of the resource
        diff_type: Type of difference detected
        current_value: Current value of the resource (None if doesn't exist)
        desired_value: Desired value of the resource (None if should be deleted)
        field_diffs: Specific field-level differences for updates
        priority: Priority for applying this diff (lower number = higher priority)
        drift_detection: Optional drift detection information
    """
    
    resource_type: str
    resource_name: str
    diff_type: DiffType
    current_value: Optional[Dict[str, Any]] = None
    desired_value: Optional[Dict[str, Any]] = None
    field_diffs: Dict[str, Any] = field(default_factory=dict)
    priority: int = 100
    drift_detection: Optional[DriftDetection] = None
    
    def __post_init__(self):
        """Validate diff after initialization."""
        if not self.resource_type:
            raise ValueError("Resource type cannot be empty")
        
        if not self.resource_name:
            raise ValueError("Resource name cannot be empty")
        
        # Validate diff type consistency
        if self.diff_type == DiffType.CREATE and self.current_value is not None:
            raise ValueError("CREATE diff cannot have current_value")
        
        if self.diff_type == DiffType.DELETE and self.desired_value is not None:
            raise ValueError("DELETE diff cannot have desired_value")
        
        if self.diff_type == DiffType.UPDATE:
            if self.current_value is None or self.desired_value is None:
                raise ValueError("UPDATE diff must have both current and desired values")
    
    def is_significant(self) -> bool:
        """
        Check if this diff represents a significant change that requires action.
        
        Returns:
            bool: True if the diff requires action, False otherwise
        """
        return self.diff_type != DiffType.NO_CHANGE
    
    def get_summary(self) -> str:
        """
        Get a human-readable summary of this diff.
        
        Returns:
            str: Summary string describing the difference
        """
        if self.diff_type == DiffType.CREATE:
            return f"Create {self.resource_type} '{self.resource_name}'"
        elif self.diff_type == DiffType.DELETE:
            return f"Delete {self.resource_type} '{self.resource_name}'"
        elif self.diff_type == DiffType.UPDATE:
            fields = list(self.field_diffs.keys())
            field_summary = f" (fields: {', '.join(fields)})" if fields else ""
            return f"Update {self.resource_type} '{self.resource_name}'{field_summary}"
        else:
            return f"No change for {self.resource_type} '{self.resource_name}'"


class DifferError(Exception):
    """Base exception for differ-related errors."""
    pass


class InvalidStateError(DifferError):
    """Raised when state data is invalid or malformed."""
    pass


def compute_state_diff(current_state: Dict[str, Any], desired_state: Dict[str, Any]) -> List[StateDiff]:
    """
    Compare current state vs desired state and compute differences.
    
    This function performs a deep comparison between the current and desired
    states, identifying what resources need to be created, updated, or deleted.
    
    Args:
        current_state: Dictionary representing the current state
        desired_state: Dictionary representing the desired state
        
    Returns:
        List[StateDiff]: List of differences that need to be applied
        
    Raises:
        InvalidStateError: If state data is invalid or malformed
    """
    try:
        if not isinstance(current_state, dict):
            raise InvalidStateError("Current state must be a dictionary")
        
        if not isinstance(desired_state, dict):
            raise InvalidStateError("Desired state must be a dictionary")
        
        logger.info("Computing state differences")
        diffs = []
        
        # Get all resource types from both states
        current_resources = _extract_resources(current_state)
        desired_resources = _extract_resources(desired_state)
        
        all_resource_types = set(current_resources.keys()) | set(desired_resources.keys())
        
        for resource_type in all_resource_types:
            current_items = current_resources.get(resource_type, {})
            desired_items = desired_resources.get(resource_type, {})
            
            # Find all resource names for this type
            all_names = set(current_items.keys()) | set(desired_items.keys())
            
            for name in all_names:
                current_item = current_items.get(name)
                desired_item = desired_items.get(name)
                
                diff = _compute_resource_diff(
                    resource_type, name, current_item, desired_item
                )
                
                if diff:
                    diffs.append(diff)
        
        # Sort diffs by priority (lower number = higher priority)
        diffs.sort(key=lambda d: (d.priority, d.resource_type, d.resource_name))
        
        logger.info(f"Computed {len(diffs)} state differences")
        return diffs
        
    except Exception as e:
        logger.error(f"Failed to compute state diff: {str(e)}")
        if isinstance(e, InvalidStateError):
            raise
        raise InvalidStateError(f"Unexpected error during state comparison: {str(e)}")


def merge_state_diffs(diff_lists: List[List[StateDiff]]) -> List[StateDiff]:
    """
    Merge multiple lists of state differences into a single consolidated list.
    
    This function handles deduplication and conflict resolution when merging
    multiple diff lists, such as from different sources or validation stages.
    
    Args:
        diff_lists: List of diff lists to merge
        
    Returns:
        List[StateDiff]: Consolidated list of differences
    """
    try:
        if not diff_lists:
            return []
        
        # Flatten all diffs
        all_diffs = []
        for diff_list in diff_lists:
            if isinstance(diff_list, list):
                all_diffs.extend(diff_list)
        
        # Group diffs by resource key
        diff_groups = {}
        for diff in all_diffs:
            key = (diff.resource_type, diff.resource_name)
            if key not in diff_groups:
                diff_groups[key] = []
            diff_groups[key].append(diff)
        
        # Resolve conflicts and merge
        merged_diffs = []
        for key, group in diff_groups.items():
            if len(group) == 1:
                merged_diffs.append(group[0])
            else:
                # Multiple diffs for same resource - resolve conflicts
                resolved_diff = _resolve_diff_conflicts(group)
                if resolved_diff:
                    merged_diffs.append(resolved_diff)
        
        # Sort by priority
        merged_diffs.sort(key=lambda d: (d.priority, d.resource_type, d.resource_name))
        
        logger.info(f"Merged {len(all_diffs)} diffs into {len(merged_diffs)} consolidated diffs")
        return merged_diffs
        
    except Exception as e:
        logger.error(f"Failed to merge state diffs: {str(e)}")
        return []


def apply_state_diff(current_state: Dict[str, Any], diffs: List[StateDiff]) -> Dict[str, Any]:
    """
    Apply a list of state differences to the current state.
    
    This function simulates applying the given diffs to produce the new state
    that would result from executing all the changes.
    
    Args:
        current_state: The current state to apply changes to
        diffs: List of differences to apply
        
    Returns:
        Dict[str, Any]: New state after applying all diffs
    """
    try:
        # Deep copy to avoid modifying original state
        new_state = deepcopy(current_state)
        
        logger.info(f"Applying {len(diffs)} state differences")
        
        for diff in diffs:
            if not diff.is_significant():
                continue
            
            # Ensure resource type exists in state
            if diff.resource_type not in new_state:
                new_state[diff.resource_type] = {}
            
            resource_collection = new_state[diff.resource_type]
            
            if diff.diff_type == DiffType.CREATE:
                if diff.desired_value:
                    resource_collection[diff.resource_name] = deepcopy(diff.desired_value)
                    logger.debug(f"Created {diff.resource_type}/{diff.resource_name}")
            
            elif diff.diff_type == DiffType.DELETE:
                if diff.resource_name in resource_collection:
                    del resource_collection[diff.resource_name]
                    logger.debug(f"Deleted {diff.resource_type}/{diff.resource_name}")
            
            elif diff.diff_type == DiffType.UPDATE:
                if diff.resource_name in resource_collection and diff.desired_value:
                    # Apply field-level updates
                    current_resource = resource_collection[diff.resource_name]
                    for field, new_value in diff.field_diffs.items():
                        _set_nested_field(current_resource, field, new_value)
                    logger.debug(f"Updated {diff.resource_type}/{diff.resource_name}")
        
        logger.info("Successfully applied all state differences")
        return new_state
        
    except Exception as e:
        logger.error(f"Failed to apply state diffs: {str(e)}")
        raise DifferError(f"Error applying state differences: {str(e)}")


def _extract_resources(state: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """
    Extract resources from state dictionary, normalizing the structure.
    
    Args:
        state: State dictionary to extract from
        
    Returns:
        Dict[str, Dict[str, Any]]: Normalized resource structure
    """
    resources = {}
    
    # Known resource types that we handle
    resource_types = ['services', 'namespaces', 'configmaps', 'secrets', 'deployments']
    
    for resource_type in resource_types:
        if resource_type in state:
            resource_data = state[resource_type]
            if isinstance(resource_data, dict):
                resources[resource_type] = resource_data
            elif isinstance(resource_data, list):
                # Convert list to dict using name as key
                resource_dict = {}
                for item in resource_data:
                    if isinstance(item, dict) and 'name' in item:
                        resource_dict[item['name']] = item
                resources[resource_type] = resource_dict
    
    return resources


def _compute_resource_diff(
    resource_type: str, 
    name: str, 
    current: Optional[Dict[str, Any]], 
    desired: Optional[Dict[str, Any]]
) -> Optional[StateDiff]:
    """
    Compute the difference for a single resource.
    
    Args:
        resource_type: Type of the resource
        name: Name of the resource
        current: Current state of the resource (None if doesn't exist)
        desired: Desired state of the resource (None if should be deleted)
        
    Returns:
        Optional[StateDiff]: The computed diff, or None if no change needed
    """
    # Determine priority based on resource type
    priority_map = {
        'namespaces': 10,
        'configmaps': 20,
        'secrets': 20,
        'deployments': 30,
        'services': 40
    }
    priority = priority_map.get(resource_type, 100)
    
    if current is None and desired is None:
        # Both are None - shouldn't happen but handle gracefully
        return None
    
    elif current is None and desired is not None:
        # Resource needs to be created
        return StateDiff(
            resource_type=resource_type,
            resource_name=name,
            diff_type=DiffType.CREATE,
            desired_value=desired,
            priority=priority
        )
    
    elif current is not None and desired is None:
        # Resource needs to be deleted
        return StateDiff(
            resource_type=resource_type,
            resource_name=name,
            diff_type=DiffType.DELETE,
            current_value=current,
            priority=priority
        )
    
    else:
        # Both exist - check for differences
        field_diffs = _compute_field_diffs(current, desired)
        
        if field_diffs:
            return StateDiff(
                resource_type=resource_type,
                resource_name=name,
                diff_type=DiffType.UPDATE,
                current_value=current,
                desired_value=desired,
                field_diffs=field_diffs,
                priority=priority
            )
        else:
            return StateDiff(
                resource_type=resource_type,
                resource_name=name,
                diff_type=DiffType.NO_CHANGE,
                current_value=current,
                desired_value=desired,
                priority=priority
            )


def _compute_field_diffs(current: Dict[str, Any], desired: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compute field-level differences between current and desired states.
    
    Args:
        current: Current resource state
        desired: Desired resource state
        
    Returns:
        Dict[str, Any]: Dictionary of field differences
    """
    diffs = {}
    
    # Check all fields in desired state
    for key, desired_value in desired.items():
        current_value = current.get(key)
        
        if current_value != desired_value:
            diffs[key] = desired_value
    
    # Check for removed fields (present in current but not in desired)
    for key in current.keys():
        if key not in desired:
            diffs[key] = None  # Indicates field should be removed
    
    return diffs


def _resolve_diff_conflicts(diffs: List[StateDiff]) -> Optional[StateDiff]:
    """
    Resolve conflicts when multiple diffs exist for the same resource.
    
    Args:
        diffs: List of conflicting diffs for the same resource
        
    Returns:
        Optional[StateDiff]: Resolved diff, or None if no resolution possible
    """
    if not diffs:
        return None
    
    if len(diffs) == 1:
        return diffs[0]
    
    # Priority order: DELETE > CREATE > UPDATE > NO_CHANGE
    type_priority = {
        DiffType.DELETE: 1,
        DiffType.CREATE: 2, 
        DiffType.UPDATE: 3,
        DiffType.NO_CHANGE: 4
    }
    
    # Sort by type priority
    sorted_diffs = sorted(diffs, key=lambda d: type_priority.get(d.diff_type, 5))
    
    # Return the highest priority diff
    resolved = sorted_diffs[0]
    
    # If we have multiple UPDATE diffs, merge their field_diffs
    if resolved.diff_type == DiffType.UPDATE:
        merged_field_diffs = {}
        for diff in diffs:
            if diff.diff_type == DiffType.UPDATE:
                merged_field_diffs.update(diff.field_diffs)
        
        resolved.field_diffs = merged_field_diffs
    
    logger.debug(f"Resolved {len(diffs)} conflicting diffs to {resolved.diff_type}")
    return resolved


def _set_nested_field(obj: Dict[str, Any], field_path: str, value: Any) -> None:
    """
    Set a nested field in a dictionary using dot notation.
    
    Args:
        obj: Dictionary to modify
        field_path: Dot-separated path to the field (e.g., "spec.replicas")
        value: Value to set
    """
    if '.' not in field_path:
        obj[field_path] = value
        return
    
    parts = field_path.split('.', 1)
    key = parts[0]
    remaining_path = parts[1]
    
    if key not in obj:
        obj[key] = {}
    
    if not isinstance(obj[key], dict):
        obj[key] = {}
    
    _set_nested_field(obj[key], remaining_path, value)


# =============================================================================
# Comprehensive Drift Detection Functions
# =============================================================================

def detect_resource_drift(
    current_resource: ModelResourceState,
    desired_config: Dict[str, Any],
    max_age_minutes: int = 60
) -> DriftDetection:
    """
    Detect drift for a specific resource by comparing current state with desired configuration.
    
    Args:
        current_resource: Current resource state from ClockworkState
        desired_config: Desired configuration for the resource
        max_age_minutes: Maximum age before drift detection is considered stale
        
    Returns:
        DriftDetection: Comprehensive drift analysis
    """
    try:
        logger.debug(f"Detecting drift for resource: {current_resource.resource_id}")
        
        # Check if resource verification is stale
        cutoff_time = datetime.now() - timedelta(minutes=max_age_minutes)
        is_stale = current_resource.last_verified < cutoff_time
        
        # Perform configuration drift detection
        config_drift_details = _detect_configuration_drift(current_resource.config, desired_config)
        
        # Perform runtime drift detection
        runtime_drift_details = _detect_runtime_drift(current_resource)
        
        # Determine drift type and severity
        drift_type = _determine_drift_type(config_drift_details, runtime_drift_details)
        severity = _calculate_drift_severity(config_drift_details, runtime_drift_details, is_stale)
        
        # Calculate drift score (0-100)
        drift_score = _calculate_drift_score(config_drift_details, runtime_drift_details)
        
        # Generate suggested actions
        suggested_actions = _generate_drift_remediation_actions(
            drift_type, config_drift_details, runtime_drift_details
        )
        
        drift_detection = DriftDetection(
            resource_id=current_resource.resource_id,
            resource_type=current_resource.type.value,
            drift_type=drift_type,
            severity=severity,
            detected_at=datetime.now(),
            last_checked=datetime.now(),
            config_drift_details=config_drift_details,
            runtime_drift_details=runtime_drift_details,
            suggested_actions=suggested_actions,
            drift_score=drift_score
        )
        
        logger.debug(f"Drift detection completed for {current_resource.resource_id}: "
                    f"type={drift_type.value}, severity={severity.value}, score={drift_score}")
        
        return drift_detection
        
    except Exception as e:
        logger.error(f"Failed to detect drift for resource {current_resource.resource_id}: {e}")
        # Return a critical drift detection to indicate error
        return DriftDetection(
            resource_id=current_resource.resource_id,
            resource_type=current_resource.type.value,
            drift_type=DriftType.EXTERNAL_DRIFT,
            severity=DriftSeverity.CRITICAL,
            config_drift_details={"error": str(e)},
            suggested_actions=["Manual investigation required", "Check resource status"]
        )


def detect_state_drift(
    current_state: Dict[str, ModelResourceState],
    desired_state: Dict[str, Any],
    check_interval_minutes: int = 60
) -> List[DriftDetection]:
    """
    Perform comprehensive drift detection across all resources in the state.
    
    Args:
        current_state: Dictionary of current resource states
        desired_state: Dictionary of desired resource configurations
        check_interval_minutes: Interval for drift checking
        
    Returns:
        List[DriftDetection]: List of drift detections for all resources
    """
    try:
        logger.info(f"Starting comprehensive drift detection for {len(current_state)} resources")
        drift_detections = []
        
        # Check for drift in existing resources
        for resource_id, current_resource in current_state.items():
            # Find corresponding desired configuration
            desired_config = _find_desired_resource_config(resource_id, desired_state)
            
            if desired_config:
                drift_detection = detect_resource_drift(
                    current_resource, desired_config, check_interval_minutes
                )
                drift_detections.append(drift_detection)
            else:
                # Resource exists but is not in desired state - orphaned resource
                drift_detection = DriftDetection(
                    resource_id=resource_id,
                    resource_type=current_resource.type.value,
                    drift_type=DriftType.EXTERNAL_DRIFT,
                    severity=DriftSeverity.HIGH,
                    config_drift_details={"issue": "orphaned_resource", "description": "Resource exists but not in desired configuration"},
                    suggested_actions=["Review resource necessity", "Consider removing resource", "Add to desired state if needed"]
                )
                drift_detections.append(drift_detection)
        
        # Check for missing resources (in desired state but not current)
        for resource_type, resources in desired_state.items():
            if isinstance(resources, dict):
                for resource_name, config in resources.items():
                    resource_id = f"{resource_type}/{resource_name}"
                    if resource_id not in current_state:
                        drift_detection = DriftDetection(
                            resource_id=resource_id,
                            resource_type=resource_type,
                            drift_type=DriftType.CONFIGURATION_DRIFT,
                            severity=DriftSeverity.MEDIUM,
                            config_drift_details={"issue": "missing_resource", "description": "Resource in desired state but not deployed"},
                            suggested_actions=["Deploy missing resource", "Run clockwork apply"]
                        )
                        drift_detections.append(drift_detection)
        
        # Filter out NO_DRIFT detections for cleaner output
        significant_drifts = [d for d in drift_detections if d.drift_type != DriftType.NO_DRIFT]
        
        logger.info(f"Drift detection completed: {len(significant_drifts)} resources with drift detected out of {len(drift_detections)} checked")
        return drift_detections
        
    except Exception as e:
        logger.error(f"Failed to detect state drift: {e}")
        return []


def generate_drift_report(drift_detections: List[DriftDetection]) -> Dict[str, Any]:
    """
    Generate a comprehensive drift report from drift detections.
    
    Args:
        drift_detections: List of drift detections
        
    Returns:
        Dict containing the drift report
    """
    try:
        # Categorize drifts by severity and type
        by_severity = {}
        by_type = {}
        
        for detection in drift_detections:
            # Group by severity
            severity = detection.severity.value
            if severity not in by_severity:
                by_severity[severity] = []
            by_severity[severity].append(detection)
            
            # Group by type
            drift_type = detection.drift_type.value
            if drift_type not in by_type:
                by_type[drift_type] = []
            by_type[drift_type].append(detection)
        
        # Calculate statistics
        total_resources = len(drift_detections)
        resources_with_drift = len([d for d in drift_detections if d.drift_type != DriftType.NO_DRIFT])
        critical_drifts = len(by_severity.get('critical', []))
        high_drifts = len(by_severity.get('high', []))
        
        # Get resources requiring immediate attention
        immediate_attention = [
            d for d in drift_detections 
            if d.requires_immediate_action()
        ]
        
        # Calculate average drift score
        drift_scores = [d.drift_score for d in drift_detections if d.drift_score > 0]
        avg_drift_score = sum(drift_scores) / len(drift_scores) if drift_scores else 0
        
        report = {
            "summary": {
                "total_resources_checked": total_resources,
                "resources_with_drift": resources_with_drift,
                "drift_percentage": (resources_with_drift / total_resources * 100) if total_resources > 0 else 0,
                "average_drift_score": round(avg_drift_score, 2),
                "critical_drifts": critical_drifts,
                "high_priority_drifts": high_drifts,
                "immediate_attention_required": len(immediate_attention)
            },
            "by_severity": {
                severity: [
                    {
                        "resource_id": d.resource_id,
                        "resource_type": d.resource_type,
                        "drift_type": d.drift_type.value,
                        "drift_score": d.drift_score,
                        "detected_at": d.detected_at.isoformat(),
                        "suggested_actions": d.suggested_actions
                    }
                    for d in detections
                ]
                for severity, detections in by_severity.items()
            },
            "by_type": {
                drift_type: len(detections)
                for drift_type, detections in by_type.items()
            },
            "immediate_action_required": [
                {
                    "resource_id": d.resource_id,
                    "resource_type": d.resource_type,
                    "drift_type": d.drift_type.value,
                    "severity": d.severity.value,
                    "drift_score": d.drift_score,
                    "suggested_actions": d.suggested_actions,
                    "config_drift": d.config_drift_details,
                    "runtime_drift": d.runtime_drift_details
                }
                for d in immediate_attention
            ],
            "generated_at": datetime.now().isoformat()
        }
        
        logger.info(f"Generated drift report: {resources_with_drift}/{total_resources} resources with drift")
        return report
        
    except Exception as e:
        logger.error(f"Failed to generate drift report: {e}")
        return {
            "error": str(e),
            "summary": {"total_resources_checked": 0, "resources_with_drift": 0},
            "generated_at": datetime.now().isoformat()
        }


def _detect_configuration_drift(current_config: Dict[str, Any], desired_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Detect configuration drift between current and desired configurations.
    
    Args:
        current_config: Current resource configuration
        desired_config: Desired resource configuration
        
    Returns:
        Dict containing configuration drift details
    """
    drift_details = {
        "has_drift": False,
        "changed_fields": {},
        "added_fields": {},
        "removed_fields": {},
        "drift_count": 0
    }
    
    try:
        # Check for modified fields
        for key, desired_value in desired_config.items():
            current_value = current_config.get(key)
            if current_value != desired_value:
                drift_details["changed_fields"][key] = {
                    "current": current_value,
                    "desired": desired_value
                }
                drift_details["drift_count"] += 1
        
        # Check for removed fields (in current but not desired)
        for key in current_config.keys():
            if key not in desired_config:
                drift_details["removed_fields"][key] = current_config[key]
                drift_details["drift_count"] += 1
        
        # Check for added fields (in desired but not current)
        for key in desired_config.keys():
            if key not in current_config:
                drift_details["added_fields"][key] = desired_config[key]
                drift_details["drift_count"] += 1
        
        drift_details["has_drift"] = drift_details["drift_count"] > 0
        
    except Exception as e:
        logger.error(f"Error detecting configuration drift: {e}")
        drift_details["error"] = str(e)
    
    return drift_details


def _detect_runtime_drift(resource: ModelResourceState) -> Dict[str, Any]:
    """
    Detect runtime drift for a resource.
    
    Args:
        resource: Resource state to check
        
    Returns:
        Dict containing runtime drift details
    """
    drift_details = {
        "has_drift": False,
        "status_issues": [],
        "verification_stale": False,
        "error_conditions": []
    }
    
    try:
        # Check for status issues
        if resource.status in [ExecutionStatus.FAILED, ExecutionStatus.PENDING]:
            drift_details["status_issues"].append(f"Resource status is {resource.status.value}")
            drift_details["has_drift"] = True
        
        # Check if verification is stale (older than 1 hour)
        if resource.last_verified:
            cutoff_time = datetime.now() - timedelta(hours=1)
            if resource.last_verified < cutoff_time:
                drift_details["verification_stale"] = True
                drift_details["has_drift"] = True
        
        # Check for error conditions
        if resource.error_message:
            drift_details["error_conditions"].append(resource.error_message)
            drift_details["has_drift"] = True
        
        # Check if drift was previously detected
        if resource.drift_detected:
            drift_details["has_drift"] = True
            drift_details["status_issues"].append("Drift previously detected and not resolved")
    
    except Exception as e:
        logger.error(f"Error detecting runtime drift: {e}")
        drift_details["error"] = str(e)
        drift_details["has_drift"] = True
    
    return drift_details


def _determine_drift_type(config_drift: Dict[str, Any], runtime_drift: Dict[str, Any]) -> DriftType:
    """
    Determine the primary type of drift based on configuration and runtime analysis.
    
    Args:
        config_drift: Configuration drift details
        runtime_drift: Runtime drift details
        
    Returns:
        DriftType: The primary type of drift detected
    """
    has_config_drift = config_drift.get("has_drift", False)
    has_runtime_drift = runtime_drift.get("has_drift", False)
    
    if not has_config_drift and not has_runtime_drift:
        return DriftType.NO_DRIFT
    
    if has_config_drift and not has_runtime_drift:
        return DriftType.CONFIGURATION_DRIFT
    
    if not has_config_drift and has_runtime_drift:
        return DriftType.RUNTIME_DRIFT
    
    # Both types of drift
    return DriftType.EXTERNAL_DRIFT


def _calculate_drift_severity(
    config_drift: Dict[str, Any], 
    runtime_drift: Dict[str, Any], 
    is_stale: bool
) -> DriftSeverity:
    """
    Calculate the severity of detected drift.
    
    Args:
        config_drift: Configuration drift details
        runtime_drift: Runtime drift details
        is_stale: Whether the drift detection is stale
        
    Returns:
        DriftSeverity: Calculated severity level
    """
    drift_count = config_drift.get("drift_count", 0)
    has_runtime_drift = runtime_drift.get("has_drift", False)
    has_errors = bool(runtime_drift.get("error_conditions", []))
    
    # Critical conditions
    if has_errors or drift_count > 10:
        return DriftSeverity.CRITICAL
    
    # High priority conditions
    if has_runtime_drift and drift_count > 5:
        return DriftSeverity.HIGH
    
    # Medium priority conditions
    if drift_count > 2 or has_runtime_drift:
        return DriftSeverity.MEDIUM
    
    # Low priority conditions
    if drift_count > 0 or is_stale:
        return DriftSeverity.LOW
    
    return DriftSeverity.INFO


def _calculate_drift_score(config_drift: Dict[str, Any], runtime_drift: Dict[str, Any]) -> float:
    """
    Calculate a numeric drift score (0-100) indicating the amount of drift.
    
    Args:
        config_drift: Configuration drift details
        runtime_drift: Runtime drift details
        
    Returns:
        float: Drift score from 0 (no drift) to 100 (maximum drift)
    """
    score = 0.0
    
    # Configuration drift scoring
    drift_count = config_drift.get("drift_count", 0)
    score += min(drift_count * 5, 50)  # Max 50 points for config drift
    
    # Runtime drift scoring
    if runtime_drift.get("has_drift", False):
        score += 20  # Base runtime drift penalty
        
        if runtime_drift.get("error_conditions", []):
            score += 20  # Error conditions
        
        if runtime_drift.get("verification_stale", False):
            score += 10  # Stale verification
    
    return min(score, 100.0)


def _generate_drift_remediation_actions(
    drift_type: DriftType,
    config_drift: Dict[str, Any],
    runtime_drift: Dict[str, Any]
) -> List[str]:
    """
    Generate suggested remediation actions based on drift analysis.
    
    Args:
        drift_type: Type of drift detected
        config_drift: Configuration drift details
        runtime_drift: Runtime drift details
        
    Returns:
        List of suggested actions
    """
    actions = []
    
    if drift_type == DriftType.NO_DRIFT:
        actions.append("No action required - resource is in sync")
        return actions
    
    if drift_type == DriftType.CONFIGURATION_DRIFT:
        actions.extend([
            "Run 'clockwork apply' to sync configuration changes",
            "Review desired state configuration for accuracy",
            "Consider backup before applying changes"
        ])
        
        if config_drift.get("drift_count", 0) > 5:
            actions.append("Significant drift detected - review changes carefully")
    
    if drift_type == DriftType.RUNTIME_DRIFT:
        actions.extend([
            "Investigate runtime status and health",
            "Check resource logs for errors",
            "Verify resource connectivity and dependencies"
        ])
        
        if runtime_drift.get("error_conditions", []):
            actions.append("Address error conditions before proceeding")
    
    if drift_type == DriftType.EXTERNAL_DRIFT:
        actions.extend([
            "Full resource reconciliation required",
            "Run 'clockwork apply' with verification",
            "Monitor resource after remediation",
            "Consider manual intervention if issues persist"
        ])
    
    # Add verification action
    actions.append("Run 'clockwork verify' after remediation")
    
    return actions


def _find_desired_resource_config(resource_id: str, desired_state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Find the desired configuration for a resource ID in the desired state.
    
    Args:
        resource_id: Resource identifier (e.g., "services/web-app")
        desired_state: Desired state dictionary
        
    Returns:
        Dict with resource configuration if found, None otherwise
    """
    try:
        # Parse resource ID to extract type and name
        if '/' in resource_id:
            resource_type, resource_name = resource_id.split('/', 1)
        else:
            # Fallback - try to find in all resource types
            for rtype, resources in desired_state.items():
                if isinstance(resources, dict) and resource_id in resources:
                    return resources[resource_id]
            return None
        
        # Look for the resource in desired state
        if resource_type in desired_state:
            resources = desired_state[resource_type]
            if isinstance(resources, dict) and resource_name in resources:
                return resources[resource_name]
        
        return None
        
    except Exception as e:
        logger.warning(f"Failed to find desired config for resource {resource_id}: {e}")
        return None


# =============================================================================
# State Comparison Utilities
# =============================================================================

def compare_resource_states(
    resource1: ModelResourceState, 
    resource2: ModelResourceState,
    compare_timestamps: bool = False
) -> Dict[str, Any]:
    """
    Compare two ResourceState objects and return detailed comparison results.
    
    Args:
        resource1: First resource state to compare
        resource2: Second resource state to compare  
        compare_timestamps: Whether to include timestamp comparisons
        
    Returns:
        Dict containing comparison results and differences
    """
    try:
        comparison = {
            "are_identical": True,
            "differences": {},
            "diff_count": 0,
            "status_changed": False,
            "config_changed": False,
            "similarity_score": 100.0
        }
        
        # Compare basic properties
        if resource1.resource_id != resource2.resource_id:
            comparison["differences"]["resource_id"] = {
                "resource1": resource1.resource_id,
                "resource2": resource2.resource_id
            }
            comparison["diff_count"] += 1
            comparison["are_identical"] = False
        
        if resource1.type != resource2.type:
            comparison["differences"]["type"] = {
                "resource1": resource1.type.value,
                "resource2": resource2.type.value
            }
            comparison["diff_count"] += 1
            comparison["are_identical"] = False
        
        if resource1.status != resource2.status:
            comparison["differences"]["status"] = {
                "resource1": resource1.status.value,
                "resource2": resource2.status.value
            }
            comparison["diff_count"] += 1
            comparison["status_changed"] = True
            comparison["are_identical"] = False
        
        # Compare configurations
        config_diff = _deep_dict_compare(resource1.config, resource2.config)
        if config_diff["has_differences"]:
            comparison["differences"]["config"] = config_diff
            comparison["diff_count"] += config_diff["diff_count"]
            comparison["config_changed"] = True
            comparison["are_identical"] = False
        
        # Compare outputs
        outputs_diff = _deep_dict_compare(resource1.outputs, resource2.outputs)
        if outputs_diff["has_differences"]:
            comparison["differences"]["outputs"] = outputs_diff
            comparison["diff_count"] += outputs_diff["diff_count"]
            comparison["are_identical"] = False
        
        # Compare drift detection status
        if resource1.drift_detected != resource2.drift_detected:
            comparison["differences"]["drift_detected"] = {
                "resource1": resource1.drift_detected,
                "resource2": resource2.drift_detected
            }
            comparison["diff_count"] += 1
            comparison["are_identical"] = False
        
        # Compare error messages
        if resource1.error_message != resource2.error_message:
            comparison["differences"]["error_message"] = {
                "resource1": resource1.error_message,
                "resource2": resource2.error_message
            }
            comparison["diff_count"] += 1
            comparison["are_identical"] = False
        
        # Optional timestamp comparisons
        if compare_timestamps:
            if resource1.last_applied != resource2.last_applied:
                comparison["differences"]["last_applied"] = {
                    "resource1": resource1.last_applied.isoformat() if resource1.last_applied else None,
                    "resource2": resource2.last_applied.isoformat() if resource2.last_applied else None
                }
                comparison["diff_count"] += 1
                comparison["are_identical"] = False
            
            if resource1.last_verified != resource2.last_verified:
                comparison["differences"]["last_verified"] = {
                    "resource1": resource1.last_verified.isoformat() if resource1.last_verified else None,
                    "resource2": resource2.last_verified.isoformat() if resource2.last_verified else None
                }
                comparison["diff_count"] += 1
                comparison["are_identical"] = False
        
        # Calculate similarity score (0-100)
        comparison["similarity_score"] = _calculate_resource_similarity_score(comparison)
        
        logger.debug(f"Resource comparison completed: {comparison['diff_count']} differences found, "
                    f"similarity score: {comparison['similarity_score']}")
        
        return comparison
        
    except Exception as e:
        logger.error(f"Failed to compare resource states: {e}")
        return {
            "are_identical": False,
            "differences": {"error": str(e)},
            "diff_count": 1,
            "status_changed": False,
            "config_changed": False,
            "similarity_score": 0.0
        }


def calculate_state_diff_score(current_state: Dict[str, ModelResourceState], desired_state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate an overall diff score between current and desired states.
    
    Args:
        current_state: Current resource states
        desired_state: Desired state configuration
        
    Returns:
        Dict containing diff scoring analysis
    """
    try:
        analysis = {
            "total_resources_current": len(current_state),
            "total_resources_desired": 0,
            "resources_in_sync": 0,
            "resources_with_drift": 0,
            "missing_resources": 0,
            "orphaned_resources": 0,
            "overall_diff_score": 0.0,
            "sync_percentage": 0.0,
            "resource_scores": {}
        }
        
        # Count desired resources
        desired_resource_count = 0
        desired_resource_ids = set()
        for resource_type, resources in desired_state.items():
            if isinstance(resources, dict):
                for resource_name in resources.keys():
                    resource_id = f"{resource_type}/{resource_name}"
                    desired_resource_ids.add(resource_id)
                    desired_resource_count += 1
        
        analysis["total_resources_desired"] = desired_resource_count
        current_resource_ids = set(current_state.keys())
        
        # Calculate resource-level scores
        total_score = 0.0
        resource_count = 0
        
        # Check current resources against desired
        for resource_id, current_resource in current_state.items():
            if resource_id in desired_resource_ids:
                # Resource exists in both states - calculate drift score
                desired_config = _find_desired_resource_config(resource_id, desired_state)
                if desired_config:
                    config_drift = _detect_configuration_drift(current_resource.config, desired_config)
                    runtime_drift = _detect_runtime_drift(current_resource)
                    resource_score = 100.0 - _calculate_drift_score(config_drift, runtime_drift)
                    
                    analysis["resource_scores"][resource_id] = resource_score
                    total_score += resource_score
                    resource_count += 1
                    
                    if resource_score >= 95.0:
                        analysis["resources_in_sync"] += 1
                    else:
                        analysis["resources_with_drift"] += 1
            else:
                # Orphaned resource
                analysis["orphaned_resources"] += 1
                analysis["resource_scores"][resource_id] = 0.0  # Orphaned resources get 0 score
                resource_count += 1
        
        # Check for missing resources
        for resource_id in desired_resource_ids:
            if resource_id not in current_resource_ids:
                analysis["missing_resources"] += 1
                analysis["resource_scores"][resource_id] = 0.0  # Missing resources get 0 score
                resource_count += 1
        
        # Calculate overall metrics
        if resource_count > 0:
            analysis["overall_diff_score"] = total_score / resource_count
            analysis["sync_percentage"] = (analysis["resources_in_sync"] / resource_count) * 100
        
        logger.info(f"State diff score calculated: {analysis['overall_diff_score']:.2f}% overall sync, "
                   f"{analysis['sync_percentage']:.1f}% resources in sync")
        
        return analysis
        
    except Exception as e:
        logger.error(f"Failed to calculate state diff score: {e}")
        return {
            "error": str(e),
            "overall_diff_score": 0.0,
            "sync_percentage": 0.0
        }


def is_configuration_drift(current_resource: ModelResourceState, desired_config: Dict[str, Any]) -> bool:
    """
    Check if a resource has configuration drift compared to desired state.
    
    Args:
        current_resource: Current resource state
        desired_config: Desired configuration
        
    Returns:
        bool: True if configuration drift detected, False otherwise
    """
    try:
        config_drift = _detect_configuration_drift(current_resource.config, desired_config)
        return config_drift.get("has_drift", False)
    except Exception as e:
        logger.error(f"Failed to check configuration drift: {e}")
        return True  # Assume drift on error for safety


def is_runtime_drift(current_resource: ModelResourceState, max_age_hours: int = 1) -> bool:
    """
    Check if a resource has runtime drift (status, verification staleness, etc.).
    
    Args:
        current_resource: Current resource state
        max_age_hours: Maximum age in hours before verification is considered stale
        
    Returns:
        bool: True if runtime drift detected, False otherwise
    """
    try:
        runtime_drift = _detect_runtime_drift(current_resource)
        return runtime_drift.get("has_drift", False)
    except Exception as e:
        logger.error(f"Failed to check runtime drift: {e}")
        return True  # Assume drift on error for safety


def get_resource_drift_summary(current_resource: ModelResourceState, desired_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get a summary of drift for a single resource.
    
    Args:
        current_resource: Current resource state
        desired_config: Desired configuration
        
    Returns:
        Dict containing drift summary
    """
    try:
        config_drift = _detect_configuration_drift(current_resource.config, desired_config)
        runtime_drift = _detect_runtime_drift(current_resource)
        
        summary = {
            "resource_id": current_resource.resource_id,
            "resource_type": current_resource.type.value,
            "has_config_drift": config_drift.get("has_drift", False),
            "has_runtime_drift": runtime_drift.get("has_drift", False),
            "config_drift_count": config_drift.get("drift_count", 0),
            "drift_score": _calculate_drift_score(config_drift, runtime_drift),
            "status": current_resource.status.value,
            "last_verified": current_resource.last_verified.isoformat() if current_resource.last_verified else None,
            "error_message": current_resource.error_message
        }
        
        # Add specific drift details if present
        if config_drift.get("has_drift", False):
            summary["config_changes"] = {
                "changed_fields": list(config_drift.get("changed_fields", {}).keys()),
                "added_fields": list(config_drift.get("added_fields", {}).keys()),
                "removed_fields": list(config_drift.get("removed_fields", {}).keys())
            }
        
        if runtime_drift.get("has_drift", False):
            summary["runtime_issues"] = {
                "status_issues": runtime_drift.get("status_issues", []),
                "verification_stale": runtime_drift.get("verification_stale", False),
                "error_conditions": runtime_drift.get("error_conditions", [])
            }
        
        return summary
        
    except Exception as e:
        logger.error(f"Failed to get resource drift summary: {e}")
        return {
            "resource_id": current_resource.resource_id,
            "error": str(e),
            "has_config_drift": True,
            "has_runtime_drift": True,
            "drift_score": 100.0
        }


def _deep_dict_compare(dict1: Dict[str, Any], dict2: Dict[str, Any]) -> Dict[str, Any]:
    """
    Perform a deep comparison between two dictionaries.
    
    Args:
        dict1: First dictionary
        dict2: Second dictionary
        
    Returns:
        Dict containing comparison results
    """
    comparison = {
        "has_differences": False,
        "diff_count": 0,
        "changed_keys": {},
        "added_keys": {},
        "removed_keys": {}
    }
    
    try:
        # Check for changed values
        all_keys = set(dict1.keys()) | set(dict2.keys())
        
        for key in all_keys:
            value1 = dict1.get(key)
            value2 = dict2.get(key)
            
            if key in dict1 and key in dict2:
                # Key exists in both
                if value1 != value2:
                    comparison["changed_keys"][key] = {
                        "dict1": value1,
                        "dict2": value2
                    }
                    comparison["diff_count"] += 1
                    comparison["has_differences"] = True
            elif key in dict1 and key not in dict2:
                # Key removed
                comparison["removed_keys"][key] = value1
                comparison["diff_count"] += 1
                comparison["has_differences"] = True
            elif key not in dict1 and key in dict2:
                # Key added
                comparison["added_keys"][key] = value2
                comparison["diff_count"] += 1
                comparison["has_differences"] = True
        
    except Exception as e:
        logger.error(f"Error in deep dict comparison: {e}")
        comparison["error"] = str(e)
        comparison["has_differences"] = True
    
    return comparison


def _calculate_resource_similarity_score(comparison: Dict[str, Any]) -> float:
    """
    Calculate a similarity score based on resource comparison results.
    
    Args:
        comparison: Comparison results from compare_resource_states
        
    Returns:
        float: Similarity score from 0-100
    """
    try:
        if comparison["are_identical"]:
            return 100.0
        
        # Start with perfect score and deduct points for differences
        score = 100.0
        diff_count = comparison.get("diff_count", 0)
        
        # Deduct points based on type of differences
        if comparison.get("status_changed", False):
            score -= 20  # Status changes are significant
        
        if comparison.get("config_changed", False):
            score -= 30  # Config changes are very significant
        
        # Deduct points for each additional difference
        score -= min(diff_count * 5, 40)  # Max 40 points deduction for many diffs
        
        return max(score, 0.0)
        
    except Exception as e:
        logger.error(f"Error calculating similarity score: {e}")
        return 0.0