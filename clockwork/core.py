"""
Clockwork Core - Main pipeline orchestration for Intake → Assembly → Forge.

This module contains the ClockworkCore class that coordinates the three main phases:
1. Intake: Parse .cw files into IR (Intermediate Representation)
2. Assembly: Convert IR into ActionList with dependencies and ordering
3. Forge: Compile ActionList to ArtifactBundle and execute
"""

import logging
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

from .models import (
    IR, ActionList, ArtifactBundle, ClockworkState, ClockworkConfig,
    Environment, ValidationResult, ExecutionRecord, ResourceState
)
from .intake import Parser, Validator
from .assembly import convert_ir_to_actions, compute_state_diff
from .forge import Compiler, ArtifactExecutor, StateManager


logger = logging.getLogger(__name__)


class ClockworkCore:
    """
    Main orchestrator for the Clockwork pipeline.
    
    Provides the core interface for executing the three-phase pipeline:
    Intake → Assembly → Forge
    """
    
    def __init__(self, config_path: Optional[Path] = None, config: Optional[ClockworkConfig] = None):
        """
        Initialize ClockworkCore.
        
        Args:
            config_path: Path to configuration directory (defaults to current directory)
            config: Optional ClockworkConfig object (will be loaded from file if not provided)
        """
        self.config_path = config_path or Path(".")
        self.config = config or self._load_config()
        
        # Initialize components
        self.parser = Parser()
        self.validator = Validator()
        self.state_manager = StateManager(self.config.state_file)
        self.compiler = Compiler(self.config.agent_config)
        self.executor = ArtifactExecutor()
        
        # Setup logging
        logging.basicConfig(
            level=getattr(logging, self.config.log_level),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        logger.info(f"ClockworkCore initialized for project: {self.config.project_name}")

    def _load_config(self) -> ClockworkConfig:
        """Load configuration from file or create default."""
        config_file = self.config_path / "clockwork.json"
        
        if config_file.exists():
            try:
                with open(config_file) as f:
                    config_data = json.load(f)
                return ClockworkConfig(**config_data)
            except Exception as e:
                logger.warning(f"Failed to load config from {config_file}: {e}")
        
        # Create default config
        return ClockworkConfig(
            project_name=self.config_path.name or "clockwork-project"
        )

    # =========================================================================
    # Phase 1: Intake - Parse .cw files into IR
    # =========================================================================

    def intake(self, path: Path, variables: Optional[Dict[str, Any]] = None) -> IR:
        """
        Intake phase: Parse .cw files into validated IR.
        
        Args:
            path: Path to .cw configuration files
            variables: Optional variable overrides
            
        Returns:
            Validated IR object
            
        Raises:
            Exception: If parsing or validation fails
        """
        logger.info(f"Starting intake phase for path: {path}")
        
        try:
            # Parse .cw files
            logger.debug("Parsing .cw files...")
            ir = self.parser.parse_directory(path)
            
            # Apply variable overrides
            if variables:
                logger.debug(f"Applying variable overrides: {variables}")
                for key, value in variables.items():
                    if key in ir.variables:
                        ir.variables[key].default = value
                    else:
                        # Add new variable
                        from .models import Variable
                        ir.variables[key] = Variable(name=key, default=value)
            
            # Validate IR
            logger.debug("Validating IR...")
            validation_result = self.validator.validate_ir(ir)
            
            if not validation_result.valid:
                error_messages = [issue.message for issue in validation_result.errors]
                raise Exception(f"Validation failed: {'; '.join(error_messages)}")
            
            # Log warnings if any
            for warning in validation_result.warnings:
                logger.warning(f"Validation warning: {warning.message}")
            
            logger.info("Intake phase completed successfully")
            return ir
            
        except Exception as e:
            logger.error(f"Intake phase failed: {e}")
            raise

    # =========================================================================
    # Phase 2: Assembly - Convert IR to ActionList
    # =========================================================================

    def assembly(self, ir: IR) -> ActionList:
        """
        Assembly phase: Convert IR into ActionList with proper ordering.
        
        Args:
            ir: Validated IR from intake phase
            
        Returns:
            ActionList with ordered steps
            
        Raises:
            Exception: If planning fails
        """
        logger.info("Starting assembly phase")
        
        try:
            # Load current state for diffing
            current_state = self.state_manager.load_state()
            
            # Convert IR to actions
            logger.debug("Converting IR to actions...")
            action_list = convert_ir_to_actions(ir)
            
            # Compute state differences if we have current state
            if current_state and current_state.current_resources:
                logger.debug("Computing state differences...")
                # This would integrate with the differ to optimize actions
                # For now, we'll use the action list as-is
                pass
            
            logger.info(f"Assembly phase completed: {len(action_list.steps)} actions planned")
            return action_list
            
        except Exception as e:
            logger.error(f"Assembly phase failed: {e}")
            raise

    # =========================================================================
    # Phase 3: Forge - Compile and Execute
    # =========================================================================

    def forge_compile(self, action_list: ActionList) -> ArtifactBundle:
        """
        Forge compilation: Convert ActionList to ArtifactBundle using agent.
        
        Args:
            action_list: ActionList from assembly phase
            
        Returns:
            ArtifactBundle with executable artifacts
            
        Raises:
            Exception: If compilation fails
        """
        logger.info("Starting forge compilation phase")
        
        try:
            # Call compiler agent
            logger.debug("Calling compiler agent...")
            artifact_bundle = self.compiler.compile_actions(action_list)
            
            # Validate artifact bundle
            logger.debug("Validating artifact bundle...")
            self.executor.validate_bundle(artifact_bundle)
            
            logger.info(f"Forge compilation completed: {len(artifact_bundle.artifacts)} artifacts generated")
            return artifact_bundle
            
        except Exception as e:
            logger.error(f"Forge compilation failed: {e}")
            raise

    def forge_execute(self, artifact_bundle: ArtifactBundle, timeout_per_step: int = 300) -> List[Dict[str, Any]]:
        """
        Forge execution: Execute ArtifactBundle and update state.
        
        Args:
            artifact_bundle: ArtifactBundle from compilation
            timeout_per_step: Timeout for each step in seconds
            
        Returns:
            List of execution results
            
        Raises:
            Exception: If execution fails
        """
        logger.info("Starting forge execution phase")
        
        try:
            # Execute artifacts
            logger.debug("Executing artifact bundle...")
            results = self.executor.execute_bundle(artifact_bundle, timeout=timeout_per_step)
            
            # Update state
            logger.debug("Updating state...")
            self._update_state_from_results(artifact_bundle, results)
            
            logger.info("Forge execution completed successfully")
            return results
            
        except Exception as e:
            logger.error(f"Forge execution failed: {e}")
            raise

    # =========================================================================
    # Convenience Methods
    # =========================================================================

    def plan(self, path: Path, variables: Optional[Dict[str, Any]] = None) -> ActionList:
        """
        Run intake and assembly phases to generate a plan.
        
        Args:
            path: Path to .cw configuration files
            variables: Optional variable overrides
            
        Returns:
            ActionList showing planned actions
        """
        ir = self.intake(path, variables)
        return self.assembly(ir)

    def apply(self, path: Path, variables: Optional[Dict[str, Any]] = None, 
              timeout_per_step: int = 300) -> List[Dict[str, Any]]:
        """
        Run complete pipeline: intake → assembly → forge (compile + execute).
        
        Args:
            path: Path to .cw configuration files
            variables: Optional variable overrides
            timeout_per_step: Timeout for each step in seconds
            
        Returns:
            List of execution results
        """
        # Generate plan
        action_list = self.plan(path, variables)
        
        # Compile and execute
        artifact_bundle = self.forge_compile(action_list)
        return self.forge_execute(artifact_bundle, timeout_per_step)

    def verify_only(self, action_list: ActionList, timeout: int = 60) -> List[Dict[str, Any]]:
        """
        Run only verification actions from the action list.
        
        Args:
            action_list: ActionList to filter for verification steps
            timeout: Timeout for verification in seconds
            
        Returns:
            List of verification results
        """
        logger.info("Running verification steps only")
        
        try:
            # Filter for verification actions
            verify_actions = [
                action for action in action_list.steps 
                if action.type.value in ["verify_http", "verify_service", "health_check"]
            ]
            
            if not verify_actions:
                logger.warning("No verification actions found in action list")
                return []
            
            # Create temporary action list with only verify actions
            from .models import ActionList as AL
            verify_action_list = AL(steps=verify_actions)
            
            # Compile and execute verification steps
            artifact_bundle = self.forge_compile(verify_action_list)
            results = self.executor.execute_bundle(artifact_bundle, timeout=timeout)
            
            logger.info(f"Verification completed: {len(results)} checks run")
            return results
            
        except Exception as e:
            logger.error(f"Verification failed: {e}")
            raise

    # =========================================================================
    # State Management
    # =========================================================================

    def get_current_state(self) -> Optional[ClockworkState]:
        """Get current state."""
        return self.state_manager.load_state()

    def save_artifacts(self, artifact_bundle: ArtifactBundle, build_dir: Path):
        """Save artifact bundle to build directory."""
        build_dir.mkdir(parents=True, exist_ok=True)
        
        # Save each artifact
        for artifact in artifact_bundle.artifacts:
            artifact_path = build_dir / artifact.path
            artifact_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write content
            artifact_path.write_text(artifact.content)
            
            # Set permissions
            if artifact.mode:
                import stat
                mode = int(artifact.mode, 8)  # Convert octal string to int
                artifact_path.chmod(mode)
        
        # Save bundle metadata
        bundle_file = build_dir / "bundle.json"
        bundle_file.write_text(artifact_bundle.to_json())
        
        logger.info(f"Artifacts saved to {build_dir}")

    def _update_state_from_results(self, artifact_bundle: ArtifactBundle, results: List[Dict[str, Any]]):
        """Update state based on execution results."""
        try:
            # Load or create state
            state = self.state_manager.load_state() or ClockworkState()
            
            # Create execution record
            execution_record = ExecutionRecord(
                run_id=f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                started_at=datetime.now(),
                completed_at=datetime.now(),
                status="success" if all(r.get("success", False) for r in results) else "failed",
                action_list_checksum="",  # TODO: Calculate actual checksums
                artifact_bundle_checksum="",
                logs=[str(r) for r in results]
            )
            
            # Update resource states based on results
            for i, result in enumerate(results):
                if i < len(artifact_bundle.steps):
                    step = artifact_bundle.steps[i]
                    resource_id = step.purpose
                    
                    resource_state = ResourceState(
                        resource_id=resource_id,
                        type="service",  # TODO: Determine actual type
                        status="success" if result.get("success") else "failed",
                        last_applied=datetime.now(),
                        last_verified=datetime.now()
                    )
                    
                    state.current_resources[resource_id] = resource_state
            
            # Add execution record
            state.execution_history.append(execution_record)
            
            # Keep only last 100 execution records
            if len(state.execution_history) > 100:
                state.execution_history = state.execution_history[-100:]
            
            # Update timestamp and save
            state.update_timestamp()
            self.state_manager.save_state(state)
            
            logger.debug("State updated successfully")
            
        except Exception as e:
            logger.warning(f"Failed to update state: {e}")

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

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with cleanup."""
        self.cleanup()


# =============================================================================
# Utility Functions
# =============================================================================

def create_default_config(path: Path, project_name: str) -> ClockworkConfig:
    """Create a default configuration file."""
    config = ClockworkConfig(project_name=project_name)
    
    config_file = path / "clockwork.json"
    with open(config_file, 'w') as f:
        json.dump(config.dict(), f, indent=2, default=str)
    
    return config


def discover_cw_files(path: Path) -> List[Path]:
    """Discover all .cw files in a directory tree."""
    cw_files = []
    for file_path in path.rglob("*.cw"):
        if not any(part.startswith('.') for part in file_path.parts):
            cw_files.append(file_path)
    
    return sorted(cw_files)