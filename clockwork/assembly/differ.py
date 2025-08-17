"""
Differ module for computing state differences in the clockwork system.

This module provides functionality to compare desired state vs current state
and compute what changes need to be made to achieve the desired configuration.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union
import logging
from copy import deepcopy


logger = logging.getLogger(__name__)


class DiffType(Enum):
    """Enumeration of types of differences that can be detected."""
    
    CREATE = "create"      # Resource needs to be created
    UPDATE = "update"      # Resource needs to be updated
    DELETE = "delete"      # Resource needs to be deleted
    NO_CHANGE = "no_change"  # No changes needed


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
    """
    
    resource_type: str
    resource_name: str
    diff_type: DiffType
    current_value: Optional[Dict[str, Any]] = None
    desired_value: Optional[Dict[str, Any]] = None
    field_diffs: Dict[str, Any] = field(default_factory=dict)
    priority: int = 100
    
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