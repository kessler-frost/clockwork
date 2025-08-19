"""
State management module for tracking resource states and execution history.

This module provides joblib-based state management using ClockworkState model
for tracking the state of resources and maintaining execution history.
"""

import joblib
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
import threading
from ..models import ClockworkState, ResourceState as ModelResourceState, ExecutionRecord

logger = logging.getLogger(__name__)


class StateManagerError(Exception):
    """Exception raised by StateManager operations."""
    pass


class StateManager:
    """
    Enhanced state manager for tracking ClockworkState.
    
    Features:
    - Load/save ClockworkState using joblib
    - Thread-safe operations
    - Resource state management
    - Execution history tracking
    """
    
    def __init__(self, state_file: Path, backup_dir: Optional[Path] = None):
        """
        Initialize StateManager.
        
        Args:
            state_file: Path to the state file
            backup_dir: Optional directory for state backups
        """
        self.state_file = Path(state_file)
        
        # Setup backup directory
        if backup_dir:
            self.backup_dir = Path(backup_dir)
        else:
            self.backup_dir = self.state_file.parent / "backups"
            
        self._lock = threading.RLock()
        
        # Current ClockworkState - this is the only state format we support
        self._clockwork_state: Optional[ClockworkState] = None
        
        # Initialize state
        self._load_state()
        logger.info(f"StateManager initialized with state file: {state_file}")
    
    def _load_state(self) -> None:
        """Load state from file."""
        if not self.state_file.exists():
            logger.info("State file does not exist, starting with empty ClockworkState")
            self._initialize_empty_state()
            return
        
        try:
            # Load using joblib
            data = joblib.load(self.state_file)
            
            # Load ClockworkState - only format we support
            if "clockwork_state" in data and data["clockwork_state"]:
                self._clockwork_state = ClockworkState.model_validate(data["clockwork_state"])
                logger.info(f"Loaded ClockworkState with {len(self._clockwork_state.current_resources)} resources")
            else:
                self._initialize_empty_state()
                
        except Exception as e:
            logger.error(f"Failed to load state: {e}")
            # Initialize empty state on load failure
            self._initialize_empty_state()
    
    def _save_state(self) -> None:
        """Save state to file."""
        try:
            # Ensure parent directory exists
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Prepare data with ClockworkState only
            data = {
                "clockwork_state": self._clockwork_state.model_dump() if self._clockwork_state else None,
            }
            
            # Write to temporary file first, then rename (atomic operation)
            temp_file = self.state_file.with_suffix(".tmp")
            joblib.dump(data, temp_file)
            
            temp_file.rename(self.state_file)
            logger.debug("Saved state to file")
            
        except Exception as e:
            logger.error(f"Failed to save state: {e}")
            raise StateManagerError(f"Could not save state file: {e}")
    
    def _initialize_empty_state(self) -> None:
        """Initialize empty ClockworkState."""
        self._clockwork_state = ClockworkState()
        logger.debug("Initialized empty ClockworkState")
    
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
            self._clockwork_state.update_timestamp()
            self._save_state()
            logger.debug(f"Added execution record: {execution_record.run_id}")
    
    def get_resource_states(self) -> Dict[str, ModelResourceState]:
        """
        Get resource states from ClockworkState.
        
        Returns:
            Dictionary of resource states
        """
        with self._lock:
            if not self._clockwork_state:
                return {}
            return self._clockwork_state.current_resources.copy()
    
    def get_execution_history(self) -> List[ExecutionRecord]:
        """
        Get execution history from ClockworkState.
        
        Returns:
            List of execution records
        """
        with self._lock:
            if not self._clockwork_state:
                return []
            return self._clockwork_state.execution_history.copy()
    
    def create_backup(self) -> str:
        """
        Create a backup of the current state.
        
        Returns:
            Path to the backup file
        """
        with self._lock:
            if not self._clockwork_state:
                logger.warning("No state to backup")
                return ""
            
            # Ensure backup directory exists
            self.backup_dir.mkdir(parents=True, exist_ok=True)
            
            # Create timestamped backup
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            backup_file = self.backup_dir / f"state_backup_{timestamp}.joblib"
            
            try:
                data = {
                    "clockwork_state": self._clockwork_state.model_dump(),
                    "backup_timestamp": time.time()
                }
                joblib.dump(data, backup_file)
                logger.info(f"Created backup: {backup_file}")
                return str(backup_file)
                
            except Exception as e:
                logger.error(f"Failed to create backup: {e}")
                return ""
    
    def restore_from_backup(self, backup_file: Path) -> bool:
        """
        Restore state from a backup file.
        
        Args:
            backup_file: Path to backup file
            
        Returns:
            True if restore succeeded, False otherwise
        """
        try:
            backup_data = joblib.load(backup_file)
            
            with self._lock:
                if "clockwork_state" in backup_data:
                    self._clockwork_state = ClockworkState.model_validate(backup_data["clockwork_state"])
                    self._save_state()
                    logger.info(f"Restored state from backup: {backup_file}")
                    return True
                else:
                    logger.error("Invalid backup file format")
                    return False
                    
        except Exception as e:
            logger.error(f"Failed to restore from backup: {e}")
            return False
    
    # =========================================================================
    # Public Interface Methods (Expected by core.py)
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