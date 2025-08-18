"""
State management module for tracking resource states and execution history.

This module provides fast joblib-based state management for tracking the state
of resources and maintaining execution history across artifact runs.
"""

import joblib
import logging
import time
import shutil
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import threading
from contextlib import contextmanager
from ..models import ClockworkState, ResourceState as ModelResourceState, ExecutionRecord

logger = logging.getLogger(__name__)


class ResourceStatus(Enum):
    """Status of a resource."""
    UNKNOWN = "unknown"
    CREATED = "created"
    UPDATED = "updated"
    DELETED = "deleted"
    ERROR = "error"


class ExecutionPhase(Enum):
    """Phase of execution."""
    PLANNING = "planning"
    COMPILATION = "compilation"
    VALIDATION = "validation"
    EXECUTION = "execution"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ResourceState:
    """Represents the state of a resource."""
    resource_id: str
    resource_type: str
    status: ResourceStatus
    properties: Dict[str, Any] = field(default_factory=dict)
    last_updated: float = field(default_factory=time.time)
    version: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def update(self, properties: Dict[str, Any], status: Optional[ResourceStatus] = None) -> None:
        """Update resource state."""
        self.properties.update(properties)
        if status:
            self.status = status
        self.last_updated = time.time()
        self.version += 1
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data["status"] = self.status.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ResourceState":
        """Create from dictionary."""
        data = data.copy()
        data["status"] = ResourceStatus(data["status"])
        return cls(**data)


@dataclass
class ExecutionHistoryEntry:
    """Represents a single execution history entry."""
    execution_id: str
    action_list_name: str
    phase: ExecutionPhase
    timestamp: float = field(default_factory=time.time)
    duration: Optional[float] = None
    success: Optional[bool] = None
    error_message: Optional[str] = None
    artifacts_generated: List[str] = field(default_factory=list)
    resources_affected: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data["phase"] = self.phase.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExecutionHistoryEntry":
        """Create from dictionary."""
        data = data.copy()
        data["phase"] = ExecutionPhase(data["phase"])
        return cls(**data)


@dataclass
class ExecutionHistory:
    """Collection of execution history entries."""
    entries: List[ExecutionHistoryEntry] = field(default_factory=list)
    
    def add_entry(self, entry: ExecutionHistoryEntry) -> None:
        """Add a new history entry."""
        self.entries.append(entry)
    
    def get_recent_entries(self, limit: int = 10) -> List[ExecutionHistoryEntry]:
        """Get recent history entries."""
        return sorted(self.entries, key=lambda e: e.timestamp, reverse=True)[:limit]
    
    def get_entries_for_action_list(self, action_list_name: str) -> List[ExecutionHistoryEntry]:
        """Get history entries for a specific action list."""
        return [e for e in self.entries if e.action_list_name == action_list_name]
    
    def get_failed_entries(self) -> List[ExecutionHistoryEntry]:
        """Get all failed execution entries."""
        return [e for e in self.entries if e.success is False]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {"entries": [entry.to_dict() for entry in self.entries]}
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExecutionHistory":
        """Create from dictionary."""
        entries = [ExecutionHistoryEntry.from_dict(e) for e in data.get("entries", [])]
        return cls(entries=entries)


class StateManagerError(Exception):
    """Exception raised by StateManager."""
    pass


class StateManager:
    """
    Enhanced joblib-based state manager for tracking ClockworkState with drift detection.
    
    Provides functionality to:
    - Track resource states across executions using ClockworkState model
    - Maintain execution history with versioning
    - Persist state to .clockwork/state.json (using joblib for fast serialization)
    - Handle concurrent access with locking
    - Backup and restore state with migration support
    - State versioning and automatic migration
    - Drift detection capabilities
    """
    
    def __init__(self, state_file: Union[str, Path], backup_dir: Optional[Path] = None):
        """
        Initialize the enhanced state manager.
        
        Args:
            state_file: Path to the state file (supports string or Path)
            backup_dir: Optional directory for state backups
        """
        # Handle string paths for backward compatibility
        if isinstance(state_file, str):
            self.state_file = Path(state_file)
        else:
            self.state_file = Path(state_file)
            
        # Setup backup directory
        if backup_dir:
            self.backup_dir = Path(backup_dir)
        else:
            self.backup_dir = self.state_file.parent / "backups"
            
        self._lock = threading.RLock()
        
        # Current ClockworkState
        self._clockwork_state: Optional[ClockworkState] = None
        
        # Legacy support - keep existing structure for backward compatibility
        self._resources: Dict[str, ResourceState] = {}
        self._execution_history = ExecutionHistory()
        self._metadata: Dict[str, Any] = {
            "created_at": time.time(),
            "version": "2.0",  # Updated version for ClockworkState support
            "last_backup": None,
            "schema_version": "2.0"
        }
        
        # Initialize state
        self._load_state()
        logger.info(f"Enhanced StateManager initialized with state file: {state_file}")
    
    @contextmanager
    def transaction(self):
        """Context manager for atomic state operations."""
        with self._lock:
            try:
                yield
                self._save_state()
            except Exception as e:
                logger.error(f"Transaction failed: {e}")
                raise StateManagerError(f"State transaction failed: {e}")
    
    def get_resource(self, resource_id: str) -> Optional[ResourceState]:
        """
        Get a resource by ID.
        
        Args:
            resource_id: The resource identifier
            
        Returns:
            ResourceState if found, None otherwise
        """
        with self._lock:
            return self._resources.get(resource_id)
    
    def set_resource(self, resource: ResourceState) -> None:
        """
        Set/update a resource state.
        
        Args:
            resource: The resource state to set
        """
        with self._lock:
            self._resources[resource.resource_id] = resource
            logger.debug(f"Updated resource: {resource.resource_id}")
    
    def delete_resource(self, resource_id: str) -> bool:
        """
        Delete a resource.
        
        Args:
            resource_id: The resource identifier
            
        Returns:
            True if resource was deleted, False if not found
        """
        with self._lock:
            if resource_id in self._resources:
                del self._resources[resource_id]
                logger.debug(f"Deleted resource: {resource_id}")
                return True
            return False
    
    def list_resources(
        self, 
        resource_type: Optional[str] = None,
        status: Optional[ResourceStatus] = None
    ) -> List[ResourceState]:
        """
        List resources with optional filtering.
        
        Args:
            resource_type: Filter by resource type
            status: Filter by status
            
        Returns:
            List of matching resources
        """
        with self._lock:
            resources = list(self._resources.values())
            
            if resource_type:
                resources = [r for r in resources if r.resource_type == resource_type]
            
            if status:
                resources = [r for r in resources if r.status == status]
            
            return resources
    
    def add_execution_entry(self, entry: ExecutionHistoryEntry) -> None:
        """
        Add an execution history entry.
        
        Args:
            entry: The history entry to add
        """
        with self._lock:
            self._execution_history.add_entry(entry)
            logger.debug(f"Added execution entry: {entry.execution_id}")
    
    def get_execution_history(self) -> ExecutionHistory:
        """Get the complete execution history."""
        with self._lock:
            return self._execution_history
    
    def create_execution_context(self, action_list_name: str) -> str:
        """
        Create a new execution context and return execution ID.
        
        Args:
            action_list_name: Name of the action list being executed
            
        Returns:
            Generated execution ID
        """
        execution_id = f"exec_{int(time.time() * 1000)}"
        
        entry = ExecutionHistoryEntry(
            execution_id=execution_id,
            action_list_name=action_list_name,
            phase=ExecutionPhase.PLANNING
        )
        
        self.add_execution_entry(entry)
        return execution_id
    
    def update_execution_phase(
        self,
        execution_id: str,
        phase: ExecutionPhase,
        success: Optional[bool] = None,
        error_message: Optional[str] = None,
        duration: Optional[float] = None,
        **metadata
    ) -> None:
        """
        Update execution phase and status.
        
        Args:
            execution_id: The execution ID
            phase: New execution phase
            success: Whether the phase was successful
            error_message: Error message if failed
            duration: Duration of the phase
            **metadata: Additional metadata
        """
        with self._lock:
            # Find the entry
            for entry in self._execution_history.entries:
                if entry.execution_id == execution_id:
                    entry.phase = phase
                    entry.timestamp = time.time()
                    if success is not None:
                        entry.success = success
                    if error_message:
                        entry.error_message = error_message
                    if duration is not None:
                        entry.duration = duration
                    entry.metadata.update(metadata)
                    break
            else:
                logger.warning(f"Execution ID not found: {execution_id}")
    
    def backup_state(self) -> Optional[Path]:
        """
        Create a backup of the current state.
        
        Returns:
            Path to backup file if successful, None otherwise
        """
        if not self.backup_dir:
            return None
        
        try:
            self.backup_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = self.backup_dir / f"state_backup_{timestamp}.json"
            
            with self._lock:
                # Create backup data
                backup_data = {
                    "resources": {k: v.to_dict() for k, v in self._resources.items()},
                    "execution_history": self._execution_history.to_dict(),
                    "metadata": self._metadata.copy(),
                    "backup_timestamp": time.time()
                }
                
                joblib.dump(backup_data, backup_file)
                
                self._metadata["last_backup"] = time.time()
            
            logger.info(f"Created state backup: {backup_file}")
            return backup_file
            
        except Exception as e:
            logger.error(f"Failed to create backup: {e}")
            return None
    
    def restore_from_backup(self, backup_file: Path) -> bool:
        """
        Restore state from backup file.
        
        Args:
            backup_file: Path to backup file
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Try joblib first for new format
            backup_data = joblib.load(backup_file)
            
            with self._lock:
                # Restore resources
                self._resources = {
                    k: ResourceState.from_dict(v) 
                    for k, v in backup_data.get("resources", {}).items()
                }
                
                # Restore execution history
                self._execution_history = ExecutionHistory.from_dict(
                    backup_data.get("execution_history", {"entries": []})
                )
                
                # Restore metadata
                self._metadata = backup_data.get("metadata", {})
                
                # Save restored state
                self._save_state()
            
            logger.info(f"Restored state from backup: {backup_file}")
            return True
            
        except Exception as joblib_error:
            # If joblib fails, try JSON fallback for legacy compatibility
            try:
                import json
                with open(backup_file, "r") as f:
                    backup_data = json.load(f)
                logger.info("Loaded legacy JSON backup file")
                
                with self._lock:
                    # Restore resources (same logic as above)
                    self._resources = {
                        k: ResourceState.from_dict(v) 
                        for k, v in backup_data.get("resources", {}).items()
                    }
                    
                    # Restore execution history
                    self._execution_history = ExecutionHistory.from_dict(
                        backup_data.get("execution_history", {"entries": []})
                    )
                    
                    # Restore metadata
                    self._metadata = backup_data.get("metadata", {})
                    
                    # Save restored state
                    self._save_state()
                
                logger.info(f"Restored state from legacy backup: {backup_file}")
                return True
                
            except Exception as json_error:
                logger.error(f"Failed to restore from backup with joblib: {joblib_error}")
                logger.error(f"Failed to restore from backup with JSON fallback: {json_error}")
                return False
    
    def cleanup_old_entries(self, max_entries: int = 1000, max_age_days: int = 30) -> int:
        """
        Clean up old execution history entries.
        
        Args:
            max_entries: Maximum number of entries to keep
            max_age_days: Maximum age in days
            
        Returns:
            Number of entries removed
        """
        cutoff_time = time.time() - (max_age_days * 24 * 3600)
        
        with self._lock:
            original_count = len(self._execution_history.entries)
            
            # Remove old entries
            self._execution_history.entries = [
                e for e in self._execution_history.entries
                if e.timestamp > cutoff_time
            ]
            
            # Keep only most recent entries if still too many
            if len(self._execution_history.entries) > max_entries:
                self._execution_history.entries.sort(key=lambda e: e.timestamp, reverse=True)
                self._execution_history.entries = self._execution_history.entries[:max_entries]
            
            removed_count = original_count - len(self._execution_history.entries)
            
            if removed_count > 0:
                logger.info(f"Cleaned up {removed_count} old execution entries")
        
        return removed_count
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get state manager statistics."""
        with self._lock:
            resource_stats = {}
            for resource in self._resources.values():
                resource_type = resource.resource_type
                resource_stats.setdefault(resource_type, {"count": 0, "statuses": {}})
                resource_stats[resource_type]["count"] += 1
                
                status = resource.status.value
                resource_stats[resource_type]["statuses"].setdefault(status, 0)
                resource_stats[resource_type]["statuses"][status] += 1
            
            execution_stats = {
                "total_executions": len(self._execution_history.entries),
                "successful_executions": sum(
                    1 for e in self._execution_history.entries if e.success is True
                ),
                "failed_executions": sum(
                    1 for e in self._execution_history.entries if e.success is False
                )
            }
            
            return {
                "total_resources": len(self._resources),
                "resource_breakdown": resource_stats,
                "execution_statistics": execution_stats,
                "state_file_size": self.state_file.stat().st_size if self.state_file.exists() else 0,
                "last_backup": self._metadata.get("last_backup"),
                "created_at": self._metadata.get("created_at")
            }
    
    def _load_state(self) -> None:
        """Load state from file with automatic migration support."""
        if not self.state_file.exists():
            logger.info("State file does not exist, starting with empty ClockworkState")
            self._initialize_empty_state()
            self._save_state()
            return
        
        try:
            # Try joblib first for new format
            data = joblib.load(self.state_file)
            
            # Check schema version and migrate if needed
            schema_version = data.get("metadata", {}).get("schema_version", "1.0")
            
            if schema_version == "1.0":
                logger.info("Migrating state from schema version 1.0 to 2.0")
                data = self._migrate_from_v1(data)
            
            # Load ClockworkState if present
            if "clockwork_state" in data:
                self._clockwork_state = ClockworkState.model_validate(data["clockwork_state"])
                logger.info(f"Loaded ClockworkState with {len(self._clockwork_state.current_resources)} resources")
            else:
                self._initialize_empty_state()
            
            # Load legacy data for backward compatibility
            self._resources = {
                k: ResourceState.from_dict(v) 
                for k, v in data.get("resources", {}).items()
            }
            
            self._execution_history = ExecutionHistory.from_dict(
                data.get("execution_history", {"entries": []})
            )
            
            # Load metadata
            self._metadata.update(data.get("metadata", {}))
            
            logger.info(f"Loaded state: {len(self._resources)} legacy resources, "
                       f"{len(self._execution_history.entries)} legacy history entries")
            
        except Exception as joblib_error:
            # If joblib fails, try JSON fallback for legacy compatibility
            try:
                import json
                with open(self.state_file, "r") as f:
                    data = json.load(f)
                logger.info("Loaded legacy JSON state file, will convert to joblib format on next save")
            except Exception as json_error:
                logger.error(f"Failed to load state with joblib: {joblib_error}")
                logger.error(f"Failed to load state with JSON fallback: {json_error}")
                raise StateManagerError(f"Could not load state file with either joblib or JSON: joblib={joblib_error}, json={json_error}")
    
    def _save_state(self) -> None:
        """Save state to file with ClockworkState support."""
        try:
            # Ensure parent directory exists
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Prepare data with ClockworkState
            data = {
                "clockwork_state": self._clockwork_state.model_dump() if self._clockwork_state else None,
                "resources": {k: v.to_dict() for k, v in self._resources.items()},
                "execution_history": self._execution_history.to_dict(),
                "metadata": self._metadata
            }
            
            # Write to temporary file first, then rename (atomic operation)
            temp_file = self.state_file.with_suffix(".tmp")
            joblib.dump(data, temp_file)
            
            temp_file.rename(self.state_file)
            logger.debug("Saved enhanced state to file")
            
        except Exception as e:
            logger.error(f"Failed to save state: {e}")
            raise StateManagerError(f"Could not save state file: {e}")


    def _initialize_empty_state(self) -> None:
        """Initialize empty ClockworkState."""
        self._clockwork_state = ClockworkState()
        logger.debug("Initialized empty ClockworkState")
    
    def _migrate_from_v1(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Migrate state data from version 1.0 to 2.0."""
        try:
            # Create new ClockworkState from legacy data
            clockwork_state = ClockworkState()
            
            # Migrate resources
            legacy_resources = data.get("resources", {})
            for resource_id, resource_data in legacy_resources.items():
                # Convert legacy ResourceState to model ResourceState
                model_resource = ModelResourceState(
                    resource_id=resource_id,
                    type=resource_data.get("resource_type", "service"),
                    status=resource_data.get("status", "unknown"),
                    config=resource_data.get("properties", {}),
                    last_applied=datetime.fromtimestamp(resource_data.get("last_updated", time.time())),
                    last_verified=datetime.fromtimestamp(resource_data.get("last_updated", time.time()))
                )
                clockwork_state.current_resources[resource_id] = model_resource
            
            # Migrate execution history
            legacy_history = data.get("execution_history", {}).get("entries", [])
            for entry_data in legacy_history:
                execution_record = ExecutionRecord(
                    run_id=entry_data.get("execution_id", f"migrated_{int(time.time())}"),
                    started_at=datetime.fromtimestamp(entry_data.get("timestamp", time.time())),
                    completed_at=datetime.fromtimestamp(entry_data.get("timestamp", time.time())),
                    status=entry_data.get("phase", "completed"),
                    action_list_checksum="",
                    artifact_bundle_checksum="",
                    logs=[entry_data.get("error_message", "")] if entry_data.get("error_message") else []
                )
                clockwork_state.execution_history.append(execution_record)
            
            # Update metadata
            data["metadata"]["schema_version"] = "2.0"
            data["clockwork_state"] = clockwork_state.model_dump()
            
            logger.info("Successfully migrated state from v1.0 to v2.0")
            return data
            
        except Exception as e:
            logger.error(f"Failed to migrate state: {e}")
            # Fall back to empty state
            data["clockwork_state"] = ClockworkState().model_dump()
            data["metadata"]["schema_version"] = "2.0"
            return data
    
    # =========================================================================
    # ClockworkState Management Methods
    # =========================================================================
    
    def load_clockwork_state(self) -> Optional[ClockworkState]:
        """
        Load the current ClockworkState.
        
        Returns:
            ClockworkState if available, None otherwise
        """
        with self._lock:
            return self._clockwork_state
    
    def save_clockwork_state(self, state: ClockworkState) -> None:
        """
        Save a ClockworkState.
        
        Args:
            state: ClockworkState to save
        """
        with self._lock:
            state.update_timestamp()
            self._clockwork_state = state
            self._save_state()
            logger.debug("Saved ClockworkState")
    
    def update_resource_state(self, resource_id: str, resource_state: ModelResourceState) -> None:
        """
        Update a specific resource in the ClockworkState.
        
        Args:
            resource_id: Resource identifier
            resource_state: New resource state
        """
        with self._lock:
            if not self._clockwork_state:
                self._initialize_empty_state()
            
            self._clockwork_state.current_resources[resource_id] = resource_state
            self._clockwork_state.update_timestamp()
            self._save_state()
            logger.debug(f"Updated resource state: {resource_id}")
    
    def add_execution_record(self, execution_record: ExecutionRecord) -> None:
        """
        Add an execution record to the ClockworkState.
        
        Args:
            execution_record: Execution record to add
        """
        with self._lock:
            if not self._clockwork_state:
                self._initialize_empty_state()
            
            self._clockwork_state.execution_history.append(execution_record)
            
            # Keep only last 100 records
            if len(self._clockwork_state.execution_history) > 100:
                self._clockwork_state.execution_history = self._clockwork_state.execution_history[-100:]
            
            self._clockwork_state.update_timestamp()
            self._save_state()
            logger.debug(f"Added execution record: {execution_record.run_id}")
    
    def get_resource_states(self, resource_type: Optional[str] = None) -> List[ModelResourceState]:
        """
        Get resource states from ClockworkState.
        
        Args:
            resource_type: Optional filter by resource type
            
        Returns:
            List of resource states
        """
        with self._lock:
            if not self._clockwork_state:
                return []
            
            resources = list(self._clockwork_state.current_resources.values())
            
            if resource_type:
                resources = [r for r in resources if r.type == resource_type]
            
            return resources
    
    def detect_resource_drift(self, resource_id: str) -> bool:
        """
        Check if a resource has detected drift.
        
        Args:
            resource_id: Resource identifier
            
        Returns:
            True if drift detected, False otherwise
        """
        with self._lock:
            if not self._clockwork_state or resource_id not in self._clockwork_state.current_resources:
                return False
            
            return self._clockwork_state.current_resources[resource_id].drift_detected
    
    def mark_resource_drift(self, resource_id: str, has_drift: bool = True) -> None:
        """
        Mark a resource as having drift or not.
        
        Args:
            resource_id: Resource identifier
            has_drift: Whether the resource has drift
        """
        with self._lock:
            if not self._clockwork_state:
                self._initialize_empty_state()
            
            if resource_id in self._clockwork_state.current_resources:
                self._clockwork_state.current_resources[resource_id].drift_detected = has_drift
                self._clockwork_state.update_timestamp()
                self._save_state()
                logger.debug(f"Marked resource drift: {resource_id} = {has_drift}")
    
    def get_execution_history_records(self, limit: Optional[int] = None) -> List[ExecutionRecord]:
        """
        Get execution history from ClockworkState.
        
        Args:
            limit: Optional limit on number of records
            
        Returns:
            List of execution records
        """
        with self._lock:
            if not self._clockwork_state:
                return []
            
            history = sorted(
                self._clockwork_state.execution_history,
                key=lambda r: r.started_at,
                reverse=True
            )
            
            if limit:
                history = history[:limit]
            
            return history
    
    def create_state_snapshot(self) -> Optional[Path]:
        """
        Create a snapshot of the current state.
        
        Returns:
            Path to snapshot file if successful, None otherwise
        """
        if not self._clockwork_state:
            return None
        
        try:
            self.backup_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            snapshot_file = self.backup_dir / f"state_snapshot_{timestamp}.json"
            
            joblib.dump(self._clockwork_state.model_dump(), snapshot_file)
            
            logger.info(f"Created state snapshot: {snapshot_file}")
            return snapshot_file
            
        except Exception as e:
            logger.error(f"Failed to create state snapshot: {e}")
            return None
    
    def restore_from_snapshot(self, snapshot_file: Path) -> bool:
        """
        Restore state from a snapshot file.
        
        Args:
            snapshot_file: Path to snapshot file
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Try joblib first for new format
            snapshot_data = joblib.load(snapshot_file)
            
            with self._lock:
                self._clockwork_state = ClockworkState.model_validate(snapshot_data)
                self._save_state()
            
            logger.info(f"Restored state from snapshot: {snapshot_file}")
            return True
            
        except Exception as joblib_error:
            # If joblib fails, try JSON fallback for legacy compatibility
            try:
                import json
                with open(snapshot_file, "r") as f:
                    snapshot_data = json.load(f)
                logger.info("Loaded legacy JSON snapshot file")
                
                with self._lock:
                    self._clockwork_state = ClockworkState.model_validate(snapshot_data)
                    self._save_state()
                
                logger.info(f"Restored state from legacy snapshot: {snapshot_file}")
                return True
                
            except Exception as json_error:
                logger.error(f"Failed to restore from snapshot with joblib: {joblib_error}")
                logger.error(f"Failed to restore from snapshot with JSON fallback: {json_error}")
                return False

    # =========================================================================
    # Core.py Integration Methods
    # =========================================================================
    
    def load_state(self) -> Optional[ClockworkState]:
        """
        Load the current ClockworkState - method expected by core.py.
        
        Returns:
            ClockworkState if available, None otherwise
        """
        return self.load_clockwork_state()
    
    def save_state(self, state: ClockworkState) -> None:
        """
        Save a ClockworkState - method expected by core.py.
        
        Args:
            state: ClockworkState to save
        """
        self.save_clockwork_state(state)


def create_default_state_manager(workspace_dir: Path) -> StateManager:
    """Create a state manager with default configuration."""
    workspace_dir = Path(workspace_dir)
    clockwork_dir = workspace_dir / ".clockwork"
    clockwork_dir.mkdir(parents=True, exist_ok=True)
    
    state_file = clockwork_dir / "state.json"
    backup_dir = clockwork_dir / "backups"
    
    return StateManager(state_file, backup_dir)