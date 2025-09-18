"""
Enhanced State Management for Clockwork with PyInfra Integration

This module provides sophisticated state management capabilities by leveraging
pyinfra's native fact collection and state tracking mechanisms.

Features:
- PyInfra fact collection before/after execution
- State drift detection using fact comparison
- Resource dependency tracking
- State versioning and history
- State visualization and reporting
"""

import json
import logging
import hashlib
from pathlib import Path
from typing import Dict, List, Any, Optional, Set, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass

from pyinfra.api import State, Config
from pyinfra.api.facts import get_facts
from pyinfra.api.inventory import Inventory
from pyinfra.api.host import Host
from pyinfra.facts.server import Os, Hostname, Users, Groups, Date
from pyinfra.facts.files import File, Directory, FindFiles
from pyinfra.facts.systemd import SystemdStatus
from pyinfra.facts.docker import DockerContainers

from .models import (
    ClockworkState, ResourceState, ExecutionRecord, ExecutionStatus,
    ResourceType, ClockworkConfig
)
from .errors import ClockworkError

logger = logging.getLogger(__name__)


@dataclass
class FactSnapshot:
    """Snapshot of pyinfra facts at a point in time."""
    timestamp: datetime
    host: str
    facts: Dict[str, Any]
    checksum: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "host": self.host,
            "facts": self.facts,
            "checksum": self.checksum
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FactSnapshot':
        """Create from dictionary."""
        return cls(
            timestamp=datetime.fromisoformat(data["timestamp"]),
            host=data["host"],
            facts=data["facts"],
            checksum=data["checksum"]
        )


@dataclass
class StateDiff:
    """Represents differences between two states."""
    added_resources: List[str]
    removed_resources: List[str]
    modified_resources: List[str]
    drift_detected: List[str]
    fact_changes: Dict[str, Dict[str, Any]]

    def has_changes(self) -> bool:
        """Check if there are any changes."""
        return bool(
            self.added_resources or
            self.removed_resources or
            self.modified_resources or
            self.drift_detected or
            self.fact_changes
        )


class PyInfraFactCollector:
    """Collector for pyinfra facts with caching and filtering."""

    def __init__(self, config: ClockworkConfig):
        self.config = config
        self._fact_cache: Dict[str, FactSnapshot] = {}

    def collect_facts(self, inventory: Inventory, fact_types: Optional[List[str]] = None) -> Dict[str, FactSnapshot]:
        """
        Collect facts from all hosts in inventory.

        Args:
            inventory: PyInfra inventory
            fact_types: Specific fact types to collect (defaults to all)

        Returns:
            Dictionary mapping host names to fact snapshots
        """
        snapshots = {}

        # Default fact types for comprehensive state tracking
        if fact_types is None:
            fact_types = [
                'server.Os', 'server.Hostname', 'server.Users', 'server.Groups',
                'server.Date', 'files.Directory', 'systemd.SystemdStatus',
                'docker.DockerContainers'
            ]

        try:
            # Create pyinfra state for fact collection
            state = State(inventory, Config())

            for host in inventory:
                host_facts = {}

                logger.debug(f"Collecting facts from host: {host.name}")

                # Collect each fact type
                for fact_type in fact_types:
                    try:
                        fact_class = self._get_fact_class(fact_type)
                        if fact_class:
                            fact_data = get_facts(state, fact_class, host)
                            host_facts[fact_type] = fact_data
                        else:
                            logger.warning(f"Unknown fact type: {fact_type}")
                    except Exception as e:
                        logger.warning(f"Failed to collect fact {fact_type} from {host.name}: {e}")
                        host_facts[fact_type] = None

                # Create snapshot
                timestamp = datetime.now()
                facts_json = json.dumps(host_facts, default=str, sort_keys=True)
                checksum = hashlib.sha256(facts_json.encode()).hexdigest()

                snapshot = FactSnapshot(
                    timestamp=timestamp,
                    host=host.name,
                    facts=host_facts,
                    checksum=checksum
                )

                snapshots[host.name] = snapshot
                self._fact_cache[host.name] = snapshot

                logger.debug(f"Collected {len(host_facts)} fact types from {host.name}")

        except Exception as e:
            logger.error(f"Failed to collect facts: {e}")
            raise ClockworkError(f"Fact collection failed: {e}") from e

        return snapshots

    def _get_fact_class(self, fact_type: str):
        """Get pyinfra fact class from string identifier."""
        fact_mapping = {
            'server.Os': Os,
            'server.Hostname': Hostname,
            'server.Users': Users,
            'server.Groups': Groups,
            'server.Date': Date,
            'files.Directory': Directory,
            'files.File': File,
            'files.FindFiles': FindFiles,
            'systemd.SystemdStatus': SystemdStatus,
            'docker.DockerContainers': DockerContainers,
        }

        return fact_mapping.get(fact_type)

    def compare_snapshots(self, before: FactSnapshot, after: FactSnapshot) -> Dict[str, Any]:
        """
        Compare two fact snapshots to detect changes.

        Args:
            before: Snapshot before operation
            after: Snapshot after operation

        Returns:
            Dictionary of detected changes
        """
        changes = {}

        # Compare each fact type
        for fact_type in set(before.facts.keys()) | set(after.facts.keys()):
            before_fact = before.facts.get(fact_type)
            after_fact = after.facts.get(fact_type)

            if before_fact != after_fact:
                changes[fact_type] = {
                    'before': before_fact,
                    'after': after_fact,
                    'changed': True
                }

        return changes


class EnhancedStateManager:
    """
    Enhanced state manager with pyinfra integration.

    Provides sophisticated state management including:
    - Fact collection and storage
    - Drift detection
    - State comparison and diffing
    - Resource dependency tracking
    - State versioning
    """

    def __init__(self, state_file: Path, config: ClockworkConfig):
        self.state_file = state_file
        self.config = config
        self.fact_collector = PyInfraFactCollector(config)

        # Create state directories
        self.state_dir = state_file.parent
        self.facts_dir = self.state_dir / "facts"
        self.snapshots_dir = self.state_dir / "snapshots"

        for directory in [self.state_dir, self.facts_dir, self.snapshots_dir]:
            directory.mkdir(parents=True, exist_ok=True)

    def load_state(self) -> Optional[ClockworkState]:
        """Load current state from file."""
        try:
            if self.state_file.exists():
                with open(self.state_file, 'r') as f:
                    state_data = json.load(f)
                return ClockworkState.model_validate(state_data)
            return None
        except Exception as e:
            logger.warning(f"Failed to load state: {e}")
            return None

    def save_state(self, state: ClockworkState):
        """Save state to file with versioning."""
        try:
            # Create backup of current state
            if self.state_file.exists():
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                backup_file = self.snapshots_dir / f"state_{timestamp}.json"
                self.state_file.rename(backup_file)
                logger.debug(f"Backed up previous state to {backup_file}")

            # Save new state
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.state_file, 'w') as f:
                json.dump(state.model_dump(), f, default=str, indent=2)

            logger.debug(f"Saved state with {len(state.current_resources)} resources")

        except Exception as e:
            logger.warning(f"Failed to save state: {e}")

    def collect_pre_execution_facts(self, inventory: Inventory) -> Dict[str, FactSnapshot]:
        """Collect facts before execution for drift detection."""
        logger.info("Collecting pre-execution facts for drift detection")
        return self.fact_collector.collect_facts(inventory)

    def collect_post_execution_facts(self, inventory: Inventory) -> Dict[str, FactSnapshot]:
        """Collect facts after execution to track changes."""
        logger.info("Collecting post-execution facts to track changes")
        return self.fact_collector.collect_facts(inventory)

    def detect_drift(self, inventory: Inventory, resource_states: Dict[str, ResourceState]) -> List[str]:
        """
        Detect configuration drift by comparing current facts with expected state.

        Args:
            inventory: PyInfra inventory
            resource_states: Current resource states

        Returns:
            List of resource IDs with detected drift
        """
        logger.info("Detecting configuration drift")

        drifted_resources = []

        try:
            # Collect current facts
            current_facts = self.fact_collector.collect_facts(inventory)

            # Load last known good facts
            last_facts = self._load_last_facts()

            for host_name, current_snapshot in current_facts.items():
                if host_name in last_facts:
                    last_snapshot = last_facts[host_name]

                    # Compare snapshots
                    changes = self.fact_collector.compare_snapshots(last_snapshot, current_snapshot)

                    if changes:
                        logger.warning(f"Drift detected on {host_name}: {len(changes)} fact changes")

                        # Mark affected resources as drifted
                        for resource_id, resource_state in resource_states.items():
                            if self._resource_affected_by_changes(resource_state, changes):
                                drifted_resources.append(resource_id)
                                resource_state.drift_detected = True
                                resource_state.mark_verified(has_drift=True)

                        # Save drift details
                        self._save_drift_report(host_name, changes)

            # Save current facts as new baseline
            self._save_facts(current_facts)

        except Exception as e:
            logger.error(f"Drift detection failed: {e}")

        return drifted_resources

    def generate_state_diff(self, before_state: Optional[ClockworkState],
                          after_state: ClockworkState) -> StateDiff:
        """
        Generate a comprehensive diff between two states.

        Args:
            before_state: Previous state (None if first run)
            after_state: Current state

        Returns:
            StateDiff object with detailed changes
        """
        if before_state is None:
            # First run - all resources are new
            return StateDiff(
                added_resources=list(after_state.current_resources.keys()),
                removed_resources=[],
                modified_resources=[],
                drift_detected=[],
                fact_changes={}
            )

        before_resources = set(before_state.current_resources.keys())
        after_resources = set(after_state.current_resources.keys())

        added = list(after_resources - before_resources)
        removed = list(before_resources - after_resources)

        # Check for modifications in common resources
        modified = []
        drifted = []

        for resource_id in before_resources & after_resources:
            before_resource = before_state.current_resources[resource_id]
            after_resource = after_state.current_resources[resource_id]

            # Check for configuration changes
            if before_resource.config != after_resource.config:
                modified.append(resource_id)

            # Check for drift
            if after_resource.drift_detected and not before_resource.drift_detected:
                drifted.append(resource_id)

        return StateDiff(
            added_resources=added,
            removed_resources=removed,
            modified_resources=modified,
            drift_detected=drifted,
            fact_changes={}  # Will be populated with fact comparison details
        )

    def create_execution_record_with_facts(self, run_id: str, python_code: str,
                                         results: List[Dict[str, Any]],
                                         inventory: Inventory,
                                         pre_facts: Dict[str, FactSnapshot],
                                         post_facts: Dict[str, FactSnapshot]) -> ExecutionRecord:
        """
        Create execution record with fact snapshots.

        Args:
            run_id: Unique run identifier
            python_code: Executed pyinfra code
            results: Execution results
            inventory: PyInfra inventory
            pre_facts: Facts before execution
            post_facts: Facts after execution

        Returns:
            ExecutionRecord with fact changes
        """
        code_checksum = hashlib.sha256(python_code.encode()).hexdigest()

        # Determine overall execution status
        success_count = sum(1 for r in results if r.get("success", False))
        total_count = len(results)
        overall_success = success_count == total_count and total_count > 0

        # Analyze fact changes
        fact_changes = {}
        for host_name in set(pre_facts.keys()) | set(post_facts.keys()):
            if host_name in pre_facts and host_name in post_facts:
                changes = self.fact_collector.compare_snapshots(
                    pre_facts[host_name],
                    post_facts[host_name]
                )
                if changes:
                    fact_changes[host_name] = changes

        execution_record = ExecutionRecord(
            run_id=run_id,
            started_at=datetime.now(),
            completed_at=datetime.now(),
            status=ExecutionStatus.SUCCESS if overall_success else ExecutionStatus.FAILED,
            action_list_checksum=code_checksum,
            artifact_bundle_checksum=code_checksum,
            logs=[str(r) for r in results]
        )

        # Save fact snapshots
        self._save_execution_facts(run_id, pre_facts, post_facts, fact_changes)

        return execution_record

    def get_state_summary(self) -> Dict[str, Any]:
        """Get comprehensive state summary including health metrics."""
        state = self.load_state()
        if not state:
            return {"error": "No state found"}

        summary = state.get_health_summary()

        # Add additional metrics
        summary.update({
            "state_file_size": self.state_file.stat().st_size if self.state_file.exists() else 0,
            "last_execution": None,
            "fact_snapshots_count": len(list(self.facts_dir.glob("*.json"))),
            "state_backups_count": len(list(self.snapshots_dir.glob("state_*.json")))
        })

        # Get last execution info
        if state.execution_history:
            latest = max(state.execution_history, key=lambda x: x.started_at)
            summary["last_execution"] = {
                "run_id": latest.run_id,
                "status": latest.status.value,
                "started_at": latest.started_at.isoformat(),
                "completed_at": latest.completed_at.isoformat() if latest.completed_at else None
            }

        return summary

    def cleanup_old_snapshots(self, keep_days: int = 30):
        """Clean up old state snapshots and fact files."""
        cutoff_date = datetime.now() - timedelta(days=keep_days)

        cleaned_count = 0

        # Clean old state snapshots
        for snapshot_file in self.snapshots_dir.glob("state_*.json"):
            try:
                # Extract timestamp from filename
                timestamp_str = snapshot_file.stem.replace("state_", "")
                file_date = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")

                if file_date < cutoff_date:
                    snapshot_file.unlink()
                    cleaned_count += 1

            except (ValueError, OSError) as e:
                logger.warning(f"Failed to process snapshot {snapshot_file}: {e}")

        # Clean old fact files
        for fact_file in self.facts_dir.glob("facts_*.json"):
            try:
                file_stat = fact_file.stat()
                file_date = datetime.fromtimestamp(file_stat.st_mtime)

                if file_date < cutoff_date:
                    fact_file.unlink()
                    cleaned_count += 1

            except OSError as e:
                logger.warning(f"Failed to process fact file {fact_file}: {e}")

        logger.info(f"Cleaned up {cleaned_count} old files")

    def _load_last_facts(self) -> Dict[str, FactSnapshot]:
        """Load the most recent fact snapshots."""
        facts = {}

        try:
            # Find the most recent facts file
            fact_files = sorted(self.facts_dir.glob("facts_*.json"), reverse=True)

            if fact_files:
                latest_facts_file = fact_files[0]

                with open(latest_facts_file, 'r') as f:
                    facts_data = json.load(f)

                for host_name, snapshot_data in facts_data.items():
                    facts[host_name] = FactSnapshot.from_dict(snapshot_data)

        except Exception as e:
            logger.warning(f"Failed to load last facts: {e}")

        return facts

    def _save_facts(self, facts: Dict[str, FactSnapshot]):
        """Save fact snapshots to file."""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            facts_file = self.facts_dir / f"facts_{timestamp}.json"

            facts_data = {
                host_name: snapshot.to_dict()
                for host_name, snapshot in facts.items()
            }

            with open(facts_file, 'w') as f:
                json.dump(facts_data, f, indent=2, default=str)

            logger.debug(f"Saved facts for {len(facts)} hosts to {facts_file}")

        except Exception as e:
            logger.warning(f"Failed to save facts: {e}")

    def _save_execution_facts(self, run_id: str, pre_facts: Dict[str, FactSnapshot],
                            post_facts: Dict[str, FactSnapshot],
                            fact_changes: Dict[str, Dict[str, Any]]):
        """Save execution-specific fact information."""
        try:
            execution_facts = {
                "run_id": run_id,
                "timestamp": datetime.now().isoformat(),
                "pre_facts": {h: s.to_dict() for h, s in pre_facts.items()},
                "post_facts": {h: s.to_dict() for h, s in post_facts.items()},
                "changes": fact_changes
            }

            facts_file = self.facts_dir / f"execution_{run_id}.json"

            with open(facts_file, 'w') as f:
                json.dump(execution_facts, f, indent=2, default=str)

        except Exception as e:
            logger.warning(f"Failed to save execution facts: {e}")

    def _save_drift_report(self, host_name: str, changes: Dict[str, Any]):
        """Save drift detection report."""
        try:
            drift_report = {
                "host": host_name,
                "detected_at": datetime.now().isoformat(),
                "changes": changes
            }

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            drift_file = self.state_dir / f"drift_{host_name}_{timestamp}.json"

            with open(drift_file, 'w') as f:
                json.dump(drift_report, f, indent=2, default=str)

            logger.info(f"Saved drift report to {drift_file}")

        except Exception as e:
            logger.warning(f"Failed to save drift report: {e}")

    def _resource_affected_by_changes(self, resource: ResourceState,
                                    changes: Dict[str, Any]) -> bool:
        """
        Determine if a resource is affected by detected fact changes.

        This is a heuristic that maps fact changes to resource types.
        """
        # Simple heuristic - can be made more sophisticated
        if resource.type == ResourceType.SERVICE:
            return 'systemd.SystemdStatus' in changes
        elif resource.type == ResourceType.FILE:
            return any('files.' in change for change in changes.keys())
        elif resource.type == ResourceType.DIRECTORY:
            return 'files.Directory' in changes
        elif resource.type in [ResourceType.IMAGE, ResourceType.SERVICE]:
            return 'docker.DockerContainers' in changes

        # Default: assume all resources might be affected
        return True