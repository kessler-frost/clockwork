"""
Clockwork Daemon Loop - Main daemon implementation for continuous reconciliation.

This module implements the ClockworkDaemon class which provides:
- File system watching for .cw file changes
- Periodic drift detection and monitoring
- Auto-fix policy engine with safety controls
- Integration with core Clockwork pipeline (Intake → Assembly → Forge)
- Rate limiting and cooldown mechanisms
"""

import asyncio
import logging
import signal
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Set, Callable
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent, FileCreatedEvent

from ..core import ClockworkCore
from ..models import ClockworkConfig, ClockworkState, ResourceState, IR, ActionList, ArtifactBundle
from ..assembly.differ import detect_state_drift, DriftDetection, DriftSeverity
from .types import DaemonState, AutoFixPolicy, DaemonConfig, PatchType, FixDecision
from .patch_engine import PatchEngine
from .rate_limiter import RateLimiter, CooldownManager


logger = logging.getLogger(__name__)




class ClockworkFileHandler(FileSystemEventHandler):
    """File system event handler for .cw file changes."""
    
    def __init__(self, daemon: 'ClockworkDaemon'):
        super().__init__()
        self.daemon = daemon
        self.logger = logging.getLogger(__name__ + ".FileHandler")
    
    def on_modified(self, event):
        """Handle file modification events."""
        if not event.is_directory and self._should_process_file(event.src_path):
            self.logger.info(f"Detected modification: {event.src_path}")
            self.daemon._queue_file_change(Path(event.src_path))
    
    def on_created(self, event):
        """Handle file creation events."""
        if not event.is_directory and self._should_process_file(event.src_path):
            self.logger.info(f"Detected creation: {event.src_path}")
            self.daemon._queue_file_change(Path(event.src_path))
    
    def _should_process_file(self, file_path: str) -> bool:
        """Check if file should be processed based on patterns."""
        path = Path(file_path)
        
        # Check if file matches watch patterns
        for pattern in self.daemon.config.watch_file_patterns:
            if path.match(pattern):
                # Check if file matches ignore patterns
                for ignore_pattern in self.daemon.config.ignore_patterns:
                    if path.match(ignore_pattern):
                        return False
                return True
        
        return False


class ClockworkDaemon:
    """
    Main Clockwork daemon for continuous reconciliation and drift detection.
    
    The daemon provides:
    - File system watching for .cw configuration changes
    - Periodic drift detection and monitoring
    - Auto-fix policy engine with safety controls
    - Integration with core pipeline (Intake → Assembly → Forge)
    - Rate limiting and cooldown mechanisms
    """
    
    def __init__(self, core: ClockworkCore, config: DaemonConfig):
        """
        Initialize the Clockwork daemon.
        
        Args:
            core: ClockworkCore instance for pipeline execution
            config: DaemonConfig with daemon settings
        """
        self.core = core
        self.config = config
        self.state = DaemonState.STOPPED
        
        # Validate configuration
        config_issues = config.validate()
        if config_issues:
            raise ValueError(f"Invalid daemon configuration: {'; '.join(config_issues)}")
        
        # Initialize components
        self.patch_engine = PatchEngine(config.auto_fix_policy)
        self.rate_limiter = RateLimiter(
            max_operations=config.max_fixes_per_hour,
            time_window_hours=1
        )
        self.cooldown_manager = CooldownManager(config.cooldown_minutes)
        
        # File watching
        self.file_observer = Observer()
        self.file_handler = ClockworkFileHandler(self)
        self.pending_file_changes: Set[Path] = set()
        self.file_change_lock = threading.Lock()
        
        # Drift monitoring
        self.last_drift_check = datetime.now()
        self.consecutive_failures = 0
        
        # Control flags
        self._stop_event = threading.Event()
        self._main_loop_thread: Optional[threading.Thread] = None
        
        # Metrics and monitoring
        self.metrics = {
            "drift_checks_performed": 0,
            "fixes_applied": 0,
            "fixes_failed": 0,
            "files_processed": 0,
            "uptime_start": datetime.now()
        }
        
        logger.info(f"ClockworkDaemon initialized with {config.auto_fix_policy.value} policy")
    
    def start(self) -> None:
        """Start the daemon."""
        if self.state != DaemonState.STOPPED:
            raise RuntimeError(f"Cannot start daemon in state: {self.state}")
        
        logger.info("Starting Clockwork daemon...")
        self.state = DaemonState.STARTING
        
        try:
            # Setup signal handlers
            signal.signal(signal.SIGTERM, self._signal_handler)
            signal.signal(signal.SIGINT, self._signal_handler)
            
            # Start file watching
            self._start_file_watching()
            
            # Start main loop
            self._stop_event.clear()
            self._main_loop_thread = threading.Thread(
                target=self._main_loop,
                name="ClockworkDaemon-MainLoop",
                daemon=False
            )
            self._main_loop_thread.start()
            
            self.state = DaemonState.RUNNING
            logger.info("Clockwork daemon started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start daemon: {e}")
            self.state = DaemonState.ERROR
            raise
    
    def stop(self, timeout: int = 30) -> None:
        """Stop the daemon."""
        if self.state == DaemonState.STOPPED:
            return
        
        logger.info("Stopping Clockwork daemon...")
        self.state = DaemonState.STOPPING
        
        try:
            # Signal threads to stop
            self._stop_event.set()
            
            # Stop file watching
            self._stop_file_watching()
            
            # Wait for main loop to finish
            if self._main_loop_thread and self._main_loop_thread.is_alive():
                self._main_loop_thread.join(timeout=timeout)
                if self._main_loop_thread.is_alive():
                    logger.warning("Main loop thread did not stop within timeout")
            
            self.state = DaemonState.STOPPED
            logger.info("Clockwork daemon stopped")
            
        except Exception as e:
            logger.error(f"Error stopping daemon: {e}")
            self.state = DaemonState.ERROR
    
    def pause(self) -> None:
        """Pause daemon operations (keeps file watching active)."""
        if self.state == DaemonState.RUNNING:
            self.state = DaemonState.PAUSED
            logger.info("Daemon paused")
    
    def resume(self) -> None:
        """Resume daemon operations."""
        if self.state == DaemonState.PAUSED:
            self.state = DaemonState.RUNNING
            logger.info("Daemon resumed")
    
    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive daemon status."""
        uptime = datetime.now() - self.metrics["uptime_start"]
        
        return {
            "state": self.state.value,
            "uptime_seconds": int(uptime.total_seconds()),
            "config": {
                "auto_fix_policy": self.config.auto_fix_policy.value,
                "max_fixes_per_hour": self.config.max_fixes_per_hour,
                "check_interval": self.config.check_interval_seconds,
                "watch_paths": [str(p) for p in self.config.watch_paths]
            },
            "metrics": self.metrics.copy(),
            "rate_limiter": {
                "remaining_operations": self.rate_limiter.get_remaining_operations(),
                "reset_time": self.rate_limiter.get_reset_time().isoformat() if self.rate_limiter.get_reset_time() else None
            },
            "cooldown": {
                "in_cooldown": self.cooldown_manager.in_cooldown(),
                "cooldown_end": self.cooldown_manager.get_cooldown_end().isoformat() if self.cooldown_manager.in_cooldown() else None
            },
            "pending_changes": len(self.pending_file_changes),
            "consecutive_failures": self.consecutive_failures,
            "last_drift_check": self.last_drift_check.isoformat()
        }
    
    def trigger_manual_check(self) -> Dict[str, Any]:
        """Trigger a manual drift check and return results."""
        logger.info("Manual drift check triggered")
        return self._perform_drift_check()
    
    def _main_loop(self) -> None:
        """Main daemon loop."""
        logger.info("Daemon main loop started")
        
        while not self._stop_event.is_set():
            try:
                if self.state == DaemonState.RUNNING:
                    # Process any pending file changes
                    self._process_pending_file_changes()
                    
                    # Perform periodic drift check
                    if self._should_perform_drift_check():
                        self._perform_drift_check()
                    
                    # Reset consecutive failures on successful cycle
                    self.consecutive_failures = 0
                
                # Sleep for check interval
                self._stop_event.wait(timeout=self.config.check_interval_seconds)
                
            except Exception as e:
                logger.error(f"Error in daemon main loop: {e}")
                self.consecutive_failures += 1
                
                if self.consecutive_failures >= self.config.max_consecutive_failures:
                    logger.critical(f"Maximum consecutive failures ({self.config.max_consecutive_failures}) reached")
                    self.state = DaemonState.ERROR
                    break
                
                # Back off on failures
                time.sleep(min(30, self.config.check_interval_seconds * 2))
        
        logger.info("Daemon main loop stopped")
    
    def _start_file_watching(self) -> None:
        """Start file system watching."""
        logger.info("Starting file system watching...")
        
        for watch_path in self.config.watch_paths:
            if watch_path.exists():
                self.file_observer.schedule(
                    self.file_handler,
                    str(watch_path),
                    recursive=True
                )
                logger.debug(f"Watching path: {watch_path}")
            else:
                logger.warning(f"Watch path does not exist: {watch_path}")
        
        self.file_observer.start()
        logger.info("File system watching started")
    
    def _stop_file_watching(self) -> None:
        """Stop file system watching."""
        logger.info("Stopping file system watching...")
        
        if self.file_observer.is_alive():
            self.file_observer.stop()
            self.file_observer.join(timeout=5)
        
        logger.info("File system watching stopped")
    
    def _queue_file_change(self, file_path: Path) -> None:
        """Queue a file change for processing."""
        with self.file_change_lock:
            self.pending_file_changes.add(file_path)
            logger.debug(f"Queued file change: {file_path}")
    
    def _process_pending_file_changes(self) -> None:
        """Process all pending file changes."""
        if not self.pending_file_changes:
            return
        
        with self.file_change_lock:
            changes_to_process = self.pending_file_changes.copy()
            self.pending_file_changes.clear()
        
        if changes_to_process:
            logger.info(f"Processing {len(changes_to_process)} file changes")
            self._handle_configuration_changes(changes_to_process)
            self.metrics["files_processed"] += len(changes_to_process)
    
    def _handle_configuration_changes(self, changed_files: Set[Path]) -> None:
        """Handle configuration file changes by running the full pipeline."""
        try:
            logger.info(f"Configuration changes detected in {len(changed_files)} files")
            
            # Find the root configuration directory
            config_dirs = set()
            for file_path in changed_files:
                # Find .cw files and determine their directories
                if file_path.suffix == '.cw':
                    config_dirs.add(file_path.parent)
            
            if not config_dirs:
                logger.debug("No .cw files in changes, skipping pipeline execution")
                return
            
            # For each config directory, run the pipeline
            for config_dir in config_dirs:
                logger.info(f"Running pipeline for configuration directory: {config_dir}")
                
                try:
                    # Run full pipeline: Intake → Assembly → Forge
                    results = self.core.apply(config_dir, timeout_per_step=self.config.timeout_per_step)
                    
                    logger.info(f"Pipeline completed successfully for {config_dir}")
                    
                    # Optionally run verification
                    if self.config.enable_verification_after_fix:
                        action_list = self.core.plan(config_dir)
                        verify_results = self.core.verify_only(action_list)
                        logger.info(f"Verification completed for {config_dir}")
                    
                except Exception as e:
                    logger.error(f"Pipeline execution failed for {config_dir}: {e}")
                    raise
        
        except Exception as e:
            logger.error(f"Failed to handle configuration changes: {e}")
            raise
    
    def _should_perform_drift_check(self) -> bool:
        """Check if it's time to perform drift detection."""
        time_since_last_check = datetime.now() - self.last_drift_check
        return time_since_last_check.total_seconds() >= (self.config.drift_check_interval_minutes * 60)
    
    def _perform_drift_check(self) -> Dict[str, Any]:
        """Perform drift detection and apply auto-fixes if appropriate."""
        logger.info("Performing drift check...")
        self.last_drift_check = datetime.now()
        self.metrics["drift_checks_performed"] += 1
        
        try:
            # Detect drift using core functionality
            drift_report = self.core.detect_drift()
            
            if drift_report.get("error"):
                logger.error(f"Drift detection failed: {drift_report['error']}")
                return drift_report
            
            resources_with_drift = drift_report["summary"]["resources_with_drift"]
            
            if resources_with_drift == 0:
                logger.info("No drift detected")
                return drift_report
            
            logger.info(f"Detected drift in {resources_with_drift} resources")
            
            # Apply auto-fixes if enabled and safe
            if self.config.auto_fix_policy != AutoFixPolicy.DISABLED:
                self._apply_auto_fixes(drift_report)
            else:
                logger.info("Auto-fix disabled, manual intervention required")
            
            return drift_report
        
        except Exception as e:
            logger.error(f"Drift check failed: {e}")
            return {"error": str(e), "drift_detections": []}
    
    def _apply_auto_fixes(self, drift_report: Dict[str, Any]) -> None:
        """Apply auto-fixes based on policy and safety checks."""
        if self.cooldown_manager.in_cooldown():
            logger.info("In cooldown period, skipping auto-fixes")
            return
        
        if not self.rate_limiter.can_perform_operation():
            logger.info("Rate limit exceeded, skipping auto-fixes")
            return
        
        drift_detections = drift_report.get("drift_detections", [])
        immediate_attention = drift_report.get("immediate_action_required", [])
        
        fixes_applied = 0
        
        for drift_data in immediate_attention:
            if fixes_applied >= self.config.max_fixes_per_hour:
                logger.info("Maximum fixes per check reached")
                break
            
            try:
                # Convert drift data to proper format
                resource_id = drift_data["resource_id"]
                resource_type = drift_data["resource_type"]
                drift_type = drift_data["drift_type"]
                severity = drift_data["severity"]
                
                # Determine fix decision using patch engine
                fix_decision = self.patch_engine.determine_fix_decision(
                    resource_id=resource_id,
                    resource_type=resource_type,
                    drift_details=drift_data,
                    current_policy=self.config.auto_fix_policy
                )
                
                if fix_decision.should_auto_apply:
                    logger.info(f"Applying auto-fix for {resource_id}: {fix_decision.patch_type.value}")
                    
                    # Apply the fix
                    success = self._apply_fix(resource_id, fix_decision)
                    
                    if success:
                        fixes_applied += 1
                        self.metrics["fixes_applied"] += 1
                        self.rate_limiter.record_operation()
                        
                        # Start cooldown after successful fix
                        if self.config.cooldown_minutes > 0:
                            self.cooldown_manager.start_cooldown()
                    else:
                        self.metrics["fixes_failed"] += 1
                        logger.warning(f"Fix failed for {resource_id}")
                else:
                    logger.info(f"Fix for {resource_id} requires manual approval: {fix_decision.reason}")
            
            except Exception as e:
                logger.error(f"Error applying auto-fix: {e}")
                self.metrics["fixes_failed"] += 1
        
        if fixes_applied > 0:
            logger.info(f"Applied {fixes_applied} auto-fixes")
        else:
            logger.info("No auto-fixes applied")
    
    def _apply_fix(self, resource_id: str, fix_decision: FixDecision) -> bool:
        """Apply a specific fix based on the decision."""
        try:
            logger.info(f"Applying {fix_decision.patch_type.value} fix for {resource_id}")
            
            if fix_decision.patch_type == PatchType.ARTIFACT_PATCH:
                # Apply artifact-only patch (regenerate artifacts and re-execute)
                return self._apply_artifact_patch(resource_id, fix_decision)
            
            elif fix_decision.patch_type == PatchType.CONFIG_PATCH:
                # Apply configuration patch (modify .cw files)
                return self._apply_config_patch(resource_id, fix_decision)
            
            elif fix_decision.patch_type == PatchType.RUNBOOK:
                # Create runbook for manual intervention
                return self._create_runbook(resource_id, fix_decision)
            
            else:
                logger.error(f"Unknown patch type: {fix_decision.patch_type}")
                return False
        
        except Exception as e:
            logger.error(f"Failed to apply fix for {resource_id}: {e}")
            return False
    
    def _apply_artifact_patch(self, resource_id: str, fix_decision: FixDecision) -> bool:
        """Apply artifact-only patch by re-running pipeline."""
        try:
            # For artifact patches, we re-run the pipeline without changing .cw files
            # This is useful for fixing runtime issues, updating healthchecks, etc.
            
            # Find the configuration path for this resource
            config_path = self._find_config_path_for_resource(resource_id)
            if not config_path:
                logger.error(f"Could not find configuration path for resource {resource_id}")
                return False
            
            # Run the full pipeline
            results = self.core.apply(config_path, timeout_per_step=self.config.timeout_per_step)
            
            logger.info(f"Artifact patch applied successfully for {resource_id}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to apply artifact patch for {resource_id}: {e}")
            return False
    
    def _apply_config_patch(self, resource_id: str, fix_decision: FixDecision) -> bool:
        """Apply configuration patch by modifying .cw files."""
        try:
            # Configuration patches modify the .cw files and then re-run pipeline
            # This requires careful analysis of what needs to be changed
            
            # For now, log that this would require .cw file modification
            logger.info(f"Config patch for {resource_id} would modify .cw files")
            logger.info(f"Suggested changes: {fix_decision.suggested_changes}")
            
            # In a full implementation, this would:
            # 1. Parse the .cw files
            # 2. Apply the suggested configuration changes
            # 3. Write back the modified .cw files
            # 4. Run the pipeline
            
            # For safety, we'll skip actual .cw modification for now
            logger.warning("Config patch implementation is conservative - manual review required")
            return False
        
        except Exception as e:
            logger.error(f"Failed to apply config patch for {resource_id}: {e}")
            return False
    
    def _create_runbook(self, resource_id: str, fix_decision: FixDecision) -> bool:
        """Create a runbook for manual intervention."""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            runbook_path = Path(f".clockwork/runbooks/runbook_{resource_id.replace('/', '_')}_{timestamp}.md")
            runbook_path.parent.mkdir(parents=True, exist_ok=True)
            
            runbook_content = f"""# Manual Intervention Runbook

**Resource:** {resource_id}
**Generated:** {datetime.now().isoformat()}
**Reason:** {fix_decision.reason}

## Issue Description
{fix_decision.description}

## Suggested Actions
{chr(10).join(f"- {action}" for action in fix_decision.suggested_actions)}

## Risk Assessment
**Risk Level:** {fix_decision.risk_level}
**Reasons:** {', '.join(fix_decision.risk_factors)}

## Manual Steps Required
1. Review the drift details carefully
2. Verify the suggested changes are appropriate
3. Apply changes manually to .cw configuration files
4. Run `clockwork apply` to execute changes
5. Verify the fix with `clockwork verify`

## Additional Context
```json
{fix_decision.additional_context}
```
"""
            
            runbook_path.write_text(runbook_content)
            logger.info(f"Runbook created: {runbook_path}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to create runbook for {resource_id}: {e}")
            return False
    
    def _find_config_path_for_resource(self, resource_id: str) -> Optional[Path]:
        """Find the configuration path that contains the given resource."""
        # This is a simplified implementation
        # In practice, we'd need to track which .cw files define which resources
        
        for watch_path in self.config.watch_paths:
            if watch_path.exists() and watch_path.is_dir():
                # Look for .cw files in this directory
                cw_files = list(watch_path.glob("*.cw"))
                if cw_files:
                    return watch_path
        
        return None
    
    def _signal_handler(self, signum: int, frame) -> None:
        """Handle shutdown signals gracefully."""
        signal_name = signal.Signals(signum).name
        logger.info(f"Received signal {signal_name}, initiating graceful shutdown...")
        self.stop()
    
    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()


# =============================================================================
# Utility Functions
# =============================================================================

def create_default_daemon_config(watch_paths: List[Path]) -> DaemonConfig:
    """Create a default daemon configuration."""
    return DaemonConfig(
        watch_paths=watch_paths,
        auto_fix_policy=AutoFixPolicy.CONSERVATIVE
    )


def setup_daemon_logging(log_level: str = "INFO") -> None:
    """Setup logging for the daemon."""
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('.clockwork/daemon.log')
        ]
    )