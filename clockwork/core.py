"""
Clockwork Core - Simplified pyinfra-based pipeline orchestration.

This module contains the ClockworkCore class that coordinates the simplified two-phase pipeline:
1. Parse: Convert .cw files directly to pyinfra operations
2. Execute: Run pyinfra operations on target infrastructure

This replaces the old Intake → Assembly → Forge three-phase architecture.
"""

import logging
import json
import hashlib
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
import tempfile
import subprocess

from .models import ClockworkConfig, ClockworkState, ExecutionStatus, ExecutionRecord, ResourceState, ResourceType
from .errors import ClockworkError, ConfigurationError, create_error_context
from .parser import PyInfraParser, PyInfraParserError
from .state_manager import EnhancedStateManager

logger = logging.getLogger(__name__)


class ClockworkCore:
    """
    Main orchestrator for the simplified Clockwork pipeline.

    Provides the core interface for executing the two-phase pipeline:
    Parse → Execute
    """

    def __init__(self, config_path: Optional[Path] = None, config: Optional[ClockworkConfig] = None):
        """
        Initialize ClockworkCore.

        Args:
            config_path: Path to configuration directory (defaults to current directory)
            config: Optional ClockworkConfig object (will be loaded from environment if not provided)
        """
        self.config_path = config_path or Path(".")
        self.config = config or self._load_config()

        # Initialize core components
        self.parser = PyInfraParser(default_host="localhost")
        self.state_manager = self._init_state_manager()

        # Setup logging
        logging.basicConfig(
            level=getattr(logging, self.config.log_level),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

        logger.info(f"ClockworkCore initialized for project: {self.config.project_name}")

    def _load_config(self) -> ClockworkConfig:
        """Load configuration from environment variables and .env file."""
        return ClockworkConfig()

    def _init_state_manager(self):
        """Initialize enhanced state manager with pyinfra integration."""
        state_file = self.config_path / ".clockwork" / "state.json"
        return EnhancedStateManager(state_file, self.config)

    # =========================================================================
    # Phase 1: Parse - Convert .cw files to pyinfra code
    # =========================================================================

    def parse(self, path: Path, variables: Optional[Dict[str, Any]] = None, targets: Optional[List[str]] = None) -> str:
        """
        Parse phase: Convert .cw files to executable pyinfra Python code.

        Args:
            path: Path to .cw configuration files
            variables: Optional variable overrides (not implemented yet)
            targets: Optional list of target hosts for pyinfra

        Returns:
            Generated pyinfra Python code as string

        Raises:
            ClockworkError: If parsing fails
        """
        logger.info(f"Starting parse phase for path: {path}")

        try:
            # Parse .cw files in directory
            logger.debug("Parsing .cw configuration files...")

            # Use targets or default to localhost
            if targets is None:
                targets = ["localhost"]

            if path.is_file():
                python_code = self.parser.parse_file(path, targets)
            else:
                python_code = self.parser.parse_directory(path, targets)

            # Apply variable overrides if provided
            if variables:
                logger.debug(f"Applying variable overrides: {variables}")
                # TODO: Implement variable substitution in generated code
                # This would involve replacing placeholders in the code with actual values
                pass

            logger.info(f"Parse phase completed: Generated {len(python_code.splitlines())} lines of pyinfra code")
            return python_code

        except PyInfraParserError as e:
            logger.error(f"Parse phase failed: {e}")
            raise ClockworkError(
                f"Failed to parse .cw files: {e.message}",
                context=create_error_context(
                    file_path=str(path),
                    component="parser",
                    operation="parse_and_translate"
                )
            ) from e
        except Exception as e:
            logger.error(f"Parse phase failed: {e}")
            raise ClockworkError(
                f"Failed to parse .cw files: {e}",
                context=create_error_context(
                    file_path=str(path),
                    component="parser",
                    operation="parse_and_translate"
                )
            ) from e

    # =========================================================================
    # Phase 2: Execute - Run pyinfra code
    # =========================================================================

    def execute(self, python_code: str, targets: Optional[List[str]] = None, timeout_per_step: int = 300) -> List[Dict[str, Any]]:
        """
        Execute phase: Run generated pyinfra Python code with enhanced state tracking.

        Args:
            python_code: Generated pyinfra Python code from parse phase
            targets: Optional list of target hosts (defaults to localhost)
            timeout_per_step: Timeout for execution in seconds

        Returns:
            List of execution results

        Raises:
            ClockworkError: If execution fails
        """
        if targets is None:
            targets = ["localhost"]

        logger.info(f"Starting execute phase with pyinfra on {len(targets)} target(s): {targets}")

        try:
            # Create pyinfra inventory for fact collection
            from pyinfra.api.inventory import Inventory
            inventory = self._create_pyinfra_inventory(targets)

            # Collect pre-execution facts for drift detection
            logger.debug("Collecting pre-execution facts...")
            pre_facts = self.state_manager.collect_pre_execution_facts(inventory)

            # Create temporary file for the pyinfra script
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(python_code)
                script_path = f.name

            try:
                # Execute pyinfra command
                logger.debug(f"Executing pyinfra script: {script_path}")

                # Build pyinfra command
                target_string = ",".join(targets)
                cmd = ["uv", "run", "pyinfra", target_string, script_path, "-v", "-y"]

                # Run pyinfra
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=timeout_per_step,
                    cwd=self.config_path
                )

                # Collect post-execution facts
                logger.debug("Collecting post-execution facts...")
                post_facts = self.state_manager.collect_post_execution_facts(inventory)

                # Process results
                execution_results = [{
                    "command": " ".join(cmd),
                    "success": result.returncode == 0,
                    "exit_code": result.returncode,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "targets": targets
                }]

                # Update state with enhanced fact tracking
                logger.debug("Updating state with fact tracking...")
                self._update_state_from_results_with_facts(
                    python_code, execution_results, inventory, pre_facts, post_facts
                )

                logger.info(f"Execute phase completed: exit code {result.returncode}")
                return execution_results

            finally:
                # Clean up temporary file
                try:
                    Path(script_path).unlink()
                except:
                    pass

        except subprocess.TimeoutExpired as e:
            logger.error(f"Execute phase timed out after {timeout_per_step} seconds")
            raise ClockworkError(
                f"Execution timed out after {timeout_per_step} seconds",
                context=create_error_context(
                    component="executor",
                    operation="execute_pyinfra",
                    targets=targets,
                    timeout=timeout_per_step
                )
            ) from e
        except subprocess.CalledProcessError as e:
            logger.error(f"Execute phase failed with exit code {e.returncode}")
            raise ClockworkError(
                f"Pyinfra execution failed with exit code {e.returncode}",
                context=create_error_context(
                    component="executor",
                    operation="execute_pyinfra",
                    targets=targets,
                    exit_code=e.returncode
                )
            ) from e
        except Exception as e:
            logger.error(f"Execute phase failed: {e}")
            raise ClockworkError(
                f"Failed to execute pyinfra code: {e}",
                context=create_error_context(
                    component="executor",
                    operation="execute_pyinfra",
                    targets=targets
                )
            ) from e

    # =========================================================================
    # Convenience Methods
    # =========================================================================

    def plan(self, path: Path, variables: Optional[Dict[str, Any]] = None, targets: Optional[List[str]] = None) -> Dict[str, Any]:
        """Generate execution plan showing what changes would be made."""
        targets = targets or ["@local"]
        python_code = self.parse(path, variables, targets)
        desired_resources = self._extract_desired_resources_from_config(path, variables)
        current_state = self.state_manager.load_state()

        plan_changes = self._compare_states({}, current_state, desired_resources, targets)

        return {
            "targets": targets,
            "config_file": str(path),
            "timestamp": datetime.now().isoformat(),
            "changes": plan_changes,
            "generated_code": python_code,
            "has_changes": len(plan_changes.get("create", [])) > 0,
            "summary": {
                "create": len(plan_changes.get("create", [])),
                "update": len(plan_changes.get("update", [])),
                "delete": len(plan_changes.get("delete", [])),
                "no_change": len(plan_changes.get("no_change", []))
            }
        }

    def apply(self, path: Path, variables: Optional[Dict[str, Any]] = None,
              targets: Optional[List[str]] = None, timeout_per_step: int = 300) -> List[Dict[str, Any]]:
        """
        Run complete pipeline: parse → execute.

        Args:
            path: Path to .cw configuration files
            variables: Optional variable overrides
            targets: Optional list of target hosts
            timeout_per_step: Timeout for execution in seconds

        Returns:
            List of execution results
        """
        logger.info("Running complete pipeline: parse → execute")

        # Parse .cw files to pyinfra code
        python_code = self.parse(path, variables, targets)

        # Execute pyinfra code
        return self.execute(python_code, targets, timeout_per_step)

    def verify_only(self, path: Path, targets: Optional[List[str]] = None, timeout: int = 60) -> List[Dict[str, Any]]:
        """
        Run only verification operations.

        Args:
            path: Path to .cw configuration files
            targets: Optional list of target hosts
            timeout: Timeout for verification operations

        Returns:
            List of verification results
        """
        logger.info("Running verification operations only")

        try:
            # Parse configuration
            python_code = self.parse(path, targets=targets)

            # For now, execute all operations since pyinfra doesn't support filtering easily
            # TODO: In the future, modify the parser to generate only verification operations
            logger.warning("Currently running all operations; targeted verification filtering not yet implemented")

            return self.execute(python_code, targets, timeout)

        except Exception as e:
            logger.error(f"Verification failed: {e}")
            raise ClockworkError(f"Verification failed: {e}") from e

    def plan_destroy(self, path: Path, variables: Optional[Dict[str, Any]] = None, targets: Optional[List[str]] = None) -> str:
        """
        Generate a destroy plan (parse only) without executing.

        Args:
            path: Path to .cw configuration files
            variables: Optional variable overrides
            targets: Optional list of target hosts

        Returns:
            Generated pyinfra Python code that would be executed for destruction
        """
        logger.info("Generating destroy plan (parse only)")

        try:
            # Load the .cw file content
            if path.is_file():
                config_files = [path]
            else:
                config_files = list(path.glob("*.cw"))

            if not config_files:
                raise ConfigurationError(f"No .cw files found in {path}")

            # For now, just use the first .cw file
            config_file = config_files[0]
            logger.info(f"Parsing destroy plan from: {config_file}")

            # Generate destroy operations
            destroy_code = self.parser.parse_file_for_destroy(config_file, targets)

            logger.info("Destroy plan generated successfully")
            return destroy_code

        except PyInfraParserError as e:
            logger.error(f"Failed to parse configuration for destroy: {e}")
            raise ConfigurationError(f"Configuration parsing failed: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error generating destroy plan: {e}")
            raise ClockworkError(f"Failed to generate destroy plan: {e}") from e

    def destroy(self, path: Path, variables: Optional[Dict[str, Any]] = None,
                targets: Optional[List[str]] = None, timeout_per_step: int = 300) -> List[Dict[str, Any]]:
        """
        Run complete destroy pipeline: parse → execute destroy operations.

        Args:
            path: Path to .cw configuration files
            variables: Optional variable overrides
            targets: Optional list of target hosts
            timeout_per_step: Timeout for execution in seconds

        Returns:
            List of execution results from destroy operations
        """
        logger.info("Running complete destroy pipeline: parse → execute")

        # Generate destroy plan
        destroy_code = self.plan_destroy(path, variables, targets)

        # Execute destroy operations
        results = self.execute(destroy_code, targets, timeout_per_step)

        # Update state to reflect destroyed resources
        self._update_state_after_destroy(path, results)

        logger.info("Destroy pipeline completed")
        return results

    def _update_state_after_destroy(self, path, results):
        """
        Update state after destroy operations to remove destroyed resources.

        Args:
            path: Path to configuration files
            results: Results from destroy operations
        """
        try:
            current_state = self.state_manager.load_state()
            if not current_state:
                logger.warning("No current state found to update after destroy")
                return

            # Create a new execution record for the destroy operation
            execution_record = ExecutionRecord(
                run_id=f"destroy_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                started_at=datetime.now(),
                completed_at=datetime.now(),
                status=ExecutionStatus.SUCCESS,
                action_list_checksum="destroy",  # Simplified for destroy operations
                artifact_bundle_checksum="destroy",  # Simplified for destroy operations
                error_message=None
            )

            # Update state to mark resources as destroyed
            # For now, just add the execution record
            current_state.execution_history.append(execution_record)

            # Save updated state
            self.state_manager.save_state(current_state)
            logger.info("State updated after destroy operations")

        except Exception as e:
            logger.error(f"Failed to update state after destroy: {e}")
            # Don't raise here since the destroy operation itself succeeded

    # =========================================================================
    # State Management
    # =========================================================================

    def get_current_state(self) -> Optional[ClockworkState]:
        """Get current state."""
        return self.state_manager.load_state()

    def get_state_health(self) -> Dict[str, Any]:
        """
        Get overall health status of the current state.

        Returns:
            Dict containing health summary
        """
        try:
            current_state = self.state_manager.load_state()
            if not current_state:
                return {
                    "error": "No current state found",
                    "health_score": 0.0
                }

            # Calculate basic health metrics
            total_resources = len(current_state.current_resources)
            if total_resources == 0:
                return {"health_score": 100.0, "total_resources": 0, "healthy_resources": 0}

            healthy_resources = sum(
                1 for resource in current_state.current_resources.values()
                if resource.status == ExecutionStatus.SUCCESS
            )

            health_score = (healthy_resources / total_resources) * 100.0

            # Add execution history info
            last_execution = None
            if current_state.execution_history:
                latest_execution = max(current_state.execution_history, key=lambda x: x.started_at)
                last_execution = {
                    "run_id": latest_execution.run_id,
                    "started_at": latest_execution.started_at.isoformat(),
                    "status": latest_execution.status.value,
                    "completed_at": latest_execution.completed_at.isoformat() if latest_execution.completed_at else None
                }

            return {
                "health_score": health_score,
                "total_resources": total_resources,
                "healthy_resources": healthy_resources,
                "last_execution": last_execution,
                "state_version": current_state.version
            }

        except Exception as e:
            logger.error(f"Failed to get state health: {e}")
            return {
                "error": str(e),
                "health_score": 0.0
            }

    def _create_pyinfra_inventory(self, targets: List[str]):
        """Create pyinfra inventory from target list."""
        from pyinfra.api.inventory import Inventory

        # Simple inventory creation - can be enhanced later
        hosts = targets
        host_data = {target: {} for target in targets}

        return Inventory((hosts, host_data))

    def _update_state_from_results_with_facts(self, python_code: str, results: List[Dict[str, Any]],
                                            inventory, pre_facts: Dict, post_facts: Dict):
        """Update state with enhanced fact tracking."""
        try:
            # Load or create state
            state = self.state_manager.load_state() or ClockworkState()

            # Generate run ID
            run_id = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            # Create execution record with fact snapshots
            execution_record = self.state_manager.create_execution_record_with_facts(
                run_id, python_code, results, inventory, pre_facts, post_facts
            )

            # Create resource states from results (enhanced)
            resource_states = {}
            for i, result in enumerate(results):
                try:
                    # Create a resource ID based on execution result
                    resource_id = f"pyinfra_execution_{i}"

                    # Determine resource type (simplified)
                    resource_type = ResourceType.CUSTOM

                    # Create resource state
                    resource_state = ResourceState(
                        resource_id=resource_id,
                        type=resource_type,
                        status=ExecutionStatus.SUCCESS if result.get("success", False) else ExecutionStatus.FAILED,
                        last_applied=datetime.now(),
                        last_verified=datetime.now(),
                        error_message=result.get("stderr") if not result.get("success", False) else None
                    )

                    resource_states[resource_id] = resource_state
                    state.current_resources[resource_id] = resource_state

                except Exception as e:
                    logger.error(f"Failed to create resource state for result {i}: {e}")

            # Detect drift using fact comparison
            drifted_resources = self.state_manager.detect_drift(inventory, resource_states)
            if drifted_resources:
                logger.warning(f"Drift detected in {len(drifted_resources)} resources")

            # Add execution record
            state.execution_history.append(execution_record)

            # Keep only last 100 execution records
            if len(state.execution_history) > 100:
                state.execution_history = state.execution_history[-100:]

            # Update timestamp and save
            state.update_timestamp()
            self.state_manager.save_state(state)

            logger.debug("Enhanced state updated successfully")

        except Exception as e:
            logger.warning(f"Failed to update enhanced state: {e}")
            # Fallback to simple state update
            self._update_state_from_results_simple(python_code, results)

    def _update_state_from_results_simple(self, python_code: str, results: List[Dict[str, Any]]):
        """Simple fallback state update method."""
        try:
            # Load or create state
            state = self.state_manager.load_state() or ClockworkState()

            # Create execution record
            code_checksum = hashlib.sha256(python_code.encode()).hexdigest()

            # Determine overall execution status
            success_count = sum(1 for r in results if r.get("success", False))
            total_count = len(results)
            overall_success = success_count == total_count and total_count > 0

            execution_record = ExecutionRecord(
                run_id=f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                started_at=datetime.now(),
                completed_at=datetime.now(),
                status=ExecutionStatus.SUCCESS if overall_success else ExecutionStatus.FAILED,
                action_list_checksum=code_checksum,
                artifact_bundle_checksum=code_checksum,  # Same as code for simplified pipeline
                logs=[str(r) for r in results]
            )

            # Create basic resource states from results
            for i, result in enumerate(results):
                try:
                    # Create a resource ID based on execution result
                    resource_id = f"pyinfra_execution_{i}"

                    # Determine resource type (simplified)
                    resource_type = ResourceType.CUSTOM

                    # Create resource state
                    resource_state = ResourceState(
                        resource_id=resource_id,
                        type=resource_type,
                        status=ExecutionStatus.SUCCESS if result.get("success", False) else ExecutionStatus.FAILED,
                        last_applied=datetime.now(),
                        last_verified=datetime.now(),
                        error_message=result.get("stderr") if not result.get("success", False) else None
                    )

                    state.current_resources[resource_id] = resource_state

                except Exception as e:
                    logger.error(f"Failed to create resource state for result {i}: {e}")

            # Add execution record
            state.execution_history.append(execution_record)

            # Keep only last 100 execution records
            if len(state.execution_history) > 100:
                state.execution_history = state.execution_history[-100:]

            # Update timestamp and save
            state.update_timestamp()
            self.state_manager.save_state(state)

            logger.debug("Simple state updated successfully")

        except Exception as e:
            logger.warning(f"Failed to update simple state: {e}")

    # =========================================================================
    # Plan Helper Methods
    # =========================================================================

    def _extract_desired_resources_from_config(self, path: Path, variables=None) -> Dict[str, Any]:
        """Extract desired resources from configuration files."""
        config_content = path.read_text() if path.is_file() else (path / "main.cw").read_text()

        resources = {}
        lines = config_content.split('\n')
        current_resource = None

        for line in lines:
            line = line.strip()
            if line.startswith('resource '):
                parts = line.split()
                resource_type = parts[1].strip('"')
                resource_name = parts[2].strip('"')
                current_resource = {"type": resource_type, "name": resource_name, "config": {}}
                resources[f"{resource_type}.{resource_name}"] = current_resource
            elif current_resource and "=" in line and not line.startswith('#'):
                key, value = line.split('=', 1)
                current_resource["config"][key.strip()] = value.strip().strip('"').strip("'")

        return resources

    def _compare_states(self, current_facts, current_state: Optional[ClockworkState],
                       desired_resources: Dict[str, Any], targets) -> Dict[str, List[Dict[str, Any]]]:
        """Compare current state with desired state to generate plan changes."""
        changes = {"create": [], "update": [], "delete": [], "no_change": []}
        current_resources = current_state.current_resources if current_state else {}

        for resource_id, desired_resource in desired_resources.items():
            if resource_id not in current_resources:
                changes["create"].append({
                    "resource_id": resource_id,
                    "action": "create",
                    "resource_type": desired_resource["type"],
                    "resource_name": desired_resource["name"],
                    "config": desired_resource["config"],
                    "reason": "Resource does not exist"
                })

        return changes

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def cleanup(self):
        """Cleanup temporary files and resources."""
        logger.info("Cleaning up...")

        # Clean build directory if it exists
        build_dir = Path(self.config.build_dir)
        if build_dir.exists():
            import shutil
            shutil.rmtree(build_dir)
            logger.debug(f"Removed build directory: {build_dir}")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, *args):
        """Context manager exit with cleanup."""
        self.cleanup()


# =============================================================================
# Utility Functions
# =============================================================================

def create_default_config(path: Path, project_name: str) -> ClockworkConfig:
    """Create a default configuration using environment variables and .env file."""
    # Create .env file with project name if it doesn't exist
    env_file = path / ".env"
    if not env_file.exists():
        env_file.write_text(f"CLOCKWORK_PROJECT_NAME={project_name}\n")

    return ClockworkConfig()


def discover_cw_files(path: Path) -> List[Path]:
    """Discover all .cw files in a directory tree."""
    cw_files = []
    for file_path in path.rglob("*.cw"):
        if not any(part.startswith('.') for part in file_path.parts):
            cw_files.append(file_path)

    return sorted(cw_files)