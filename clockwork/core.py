"""
Clockwork Core - Main pipeline orchestration for Intake → Assembly → Forge.

This module contains the ClockworkCore class that coordinates the three main phases:
1. Intake: Parse .cw task definitions into IR (Intermediate Representation)
2. Assembly: Convert IR into ActionList with dependencies and ordering
3. Forge: Compile ActionList to ArtifactBundle and execute tasks
"""

import logging
import json
import hashlib
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
from joblib import Parallel, delayed

from .models import (
    IR, ActionList, ArtifactBundle, ClockworkState, ClockworkConfig,
    Environment, ValidationResult, ExecutionRecord, ResourceState,
    ActionType, ResourceType, ExecutionStatus
)
from .errors import (
    ClockworkError, IntakeError, AssemblyError, ForgeError, 
    ConfigurationError, StateError, DaemonError, RunnerError,
    format_error_chain, wrap_external_error, create_user_friendly_error,
    create_error_context
)
from .intake import Parser
from .intake.validator import EnhancedValidator
from .intake.resolver import Resolver, resolve_references, ResolutionError
from .assembly import convert_ir_to_actions, compute_state_diff
from .assembly.differ import detect_state_drift, generate_drift_report, calculate_state_diff_score
from .forge import Compiler, ArtifactExecutor, StateManager
from .forge.runner import RunnerFactory, select_runner
# Daemon imports moved to avoid circular imports - imported dynamically when needed


logger = logging.getLogger(__name__)


class ClockworkCore:
    """
    Main orchestrator for the Clockwork pipeline.
    
    Provides the core interface for executing the three-phase pipeline:
    Intake → Assembly → Forge
    """
    
    def __init__(self, config_path: Optional[Path] = None, config: Optional[ClockworkConfig] = None, runner_type: Optional[str] = None):
        """
        Initialize ClockworkCore.
        
        Args:
            config_path: Path to configuration directory (defaults to current directory)
            config: Optional ClockworkConfig object (will be loaded from file if not provided)
            runner_type: Optional runner type override (local, docker, podman, ssh, kubernetes)
        """
        self.config_path = config_path or Path(".")
        self.config = config or self._load_config()
        self.runner_type = runner_type
        
        # Initialize core components
        self.parser = Parser(resolve_references=True)
        self.validator = EnhancedValidator()
        self.resolver = Resolver(cache_dir=str(self.config_path / ".clockwork" / "cache"))
        self.state_manager = StateManager(self.config.state_file)
        self.compiler = Compiler(
            timeout=self.config.default_timeout,
            build_dir=self.config.build_dir,
            use_agno=self.config.use_agno,
            lm_studio_url=self.config.lm_studio_url,
            agno_model_id=self.config.lm_studio_model
        )
        self.executor = ArtifactExecutor()
        
        # Initialize runner factory and get available runners
        self.runner_factory = RunnerFactory()
        self.available_runners = self.runner_factory.get_available_runners()
        
        # Initialize daemon (optional - can be None if not needed)
        self.daemon = None
        
        # Setup logging
        logging.basicConfig(
            level=getattr(logging, self.config.log_level),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        logger.info(f"ClockworkCore initialized for project: {self.config.project_name}")
        logger.info(f"Available runners: {', '.join(self.available_runners)}")

    def _load_config(self) -> ClockworkConfig:
        """Load configuration from environment variables and .env file."""
        return ClockworkConfig()

    # =========================================================================
    # Phase 1: Intake - Parse .cw files into IR
    # =========================================================================

    def intake(self, path: Path, variables: Optional[Dict[str, Any]] = None, resolve_deps: bool = True) -> IR:
        """
        Intake phase: Parse .cw files into validated IR with dependency resolution.
        
        Args:
            path: Path to .cw configuration files
            variables: Optional variable overrides
            resolve_deps: Whether to resolve module and provider dependencies
            
        Returns:
            Validated IR object
            
        Raises:
            Exception: If parsing, validation, or resolution fails
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
            
            # Resolve module and provider dependencies if requested
            if resolve_deps and (ir.modules or ir.providers):
                logger.debug("Resolving module and provider dependencies...")
                try:
                    ir = resolve_references(ir, self.resolver)
                    logger.info("Dependency resolution completed")
                except ResolutionError as e:
                    logger.warning(f"Dependency resolution failed: {e}")
                    # Continue with validation but mark resolution as incomplete
                    ir.metadata["resolution_failed"] = True
                    ir.metadata["resolution_error"] = str(e)
            
            # Validate IR
            logger.debug("Validating IR...")
            validation_result = self.validator.validate_ir(ir)
            
            # Extract validation results using current format
            is_valid = validation_result.valid
            errors = validation_result.errors if hasattr(validation_result, 'errors') else []
            warnings = validation_result.warnings if hasattr(validation_result, 'warnings') else []
            
            if not is_valid:
                if errors and hasattr(errors[0], 'message'):
                    error_messages = [error.message for error in errors]
                else:
                    error_messages = [str(error) for error in errors]
                
                raise IntakeError(
                    f"IR validation failed: {'; '.join(error_messages)}",
                    context=create_error_context(
                        file_path=str(path),
                        component="validator",
                        operation="validate_ir",
                        error_count=len(errors)
                    ),
                    suggestions=[
                        "Check your .cw files for syntax errors",
                        "Verify that all required fields are present", 
                        "Run 'clockwork validate' for detailed validation info"
                    ]
                )
            
            # Log warnings if any
            for warning in warnings:
                if hasattr(warning, 'message'):
                    logger.warning(f"Validation warning: {warning.message}")
                else:
                    logger.warning(f"Validation warning: {warning}")
            
            logger.info("Intake phase completed successfully")
            return ir
            
        except IntakeError:
            # Re-raise IntakeError as-is
            raise
        except ResolutionError as e:
            # Already handled above, but just in case
            raise IntakeError(
                f"Dependency resolution failed: {e}",
                context=create_error_context(
                    file_path=str(path),
                    component="resolver", 
                    operation="resolve_references"
                )
            ) from e
        except Exception as e:
            # Wrap any other unexpected errors
            logger.error(f"Intake phase failed: {e}")
            raise wrap_external_error(
                e, 
                IntakeError,
                f"Unexpected error during intake phase: {e}",
                context=create_error_context(
                    file_path=str(path),
                    component="intake",
                    operation="parse_and_validate"
                )
            )

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
            
            # Convert IR to actions (convert Pydantic model to dict format expected by planner)
            logger.debug("Converting IR to actions...")
            ir_dict = self._convert_ir_to_planner_format(ir)
            action_list = convert_ir_to_actions(ir_dict)
            
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
            raise wrap_external_error(
                e,
                AssemblyError,
                f"Failed to convert IR to ActionList: {e}",
                context=create_error_context(
                    component="assembly",
                    operation="convert_ir_to_actions",
                    resource_count=len(ir.resources) if ir else 0
                ),
                suggestions=[
                    "Check that all resource dependencies are valid",
                    "Verify that there are no circular dependencies",
                    "Review the IR structure for completeness"
                ]
            )

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
            artifact_bundle = self.compiler.compile(action_list)
            
            # Validate artifact bundle
            logger.debug("Validating artifact bundle...")
            self.executor.validate_bundle(artifact_bundle)
            
            logger.info(f"Forge compilation completed: {len(artifact_bundle.artifacts)} artifacts generated")
            return artifact_bundle
            
        except Exception as e:
            logger.error(f"Forge compilation failed: {e}")
            raise wrap_external_error(
                e,
                ForgeError,
                f"Failed to compile ActionList to ArtifactBundle: {e}",
                context=create_error_context(
                    component="forge",
                    operation="compile_action_list",
                    action_count=len(action_list.steps) if action_list else 0
                ),
                suggestions=[
                    "Check that the ActionList is well-formed",
                    "Verify that the AI agent configuration is correct",
                    "Review the compilation logs for detailed error information"
                ]
            )

    def forge_execute(self, artifact_bundle: ArtifactBundle, timeout_per_step: int = 300, execution_context: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Forge execution: Execute ArtifactBundle using appropriate runner and update state.
        
        Args:
            artifact_bundle: ArtifactBundle from compilation
            timeout_per_step: Timeout for each step in seconds
            execution_context: Context for runner selection and configuration
            
        Returns:
            List of execution results
            
        Raises:
            Exception: If execution fails
        """
        logger.info("Starting forge execution phase")
        
        try:
            # Determine execution runner
            context = execution_context or {}
            if self.runner_type:
                selected_runner_type = self.runner_type
            else:
                selected_runner_type = select_runner(context)
            
            logger.info(f"Using runner: {selected_runner_type}")
            
            # Create and configure runner
            runner_config = context.get("runner_config", {})
            runner_config["timeout"] = timeout_per_step
            
            runner = self.runner_factory.create_runner(selected_runner_type, runner_config)
            
            # Validate runner environment
            if not runner.validate_environment():
                logger.warning(f"Runner {selected_runner_type} environment validation failed, falling back to local")
                runner = self.runner_factory.create_runner("local", {"timeout": timeout_per_step})
            
            # Execute artifacts using runner
            logger.debug(f"Executing artifact bundle with {selected_runner_type} runner...")
            execution_results = runner.execute_bundle(artifact_bundle)
            
            # Convert runner results to expected format
            results = []
            for exec_result in execution_results:
                if hasattr(exec_result, 'to_dict'):
                    result_dict = exec_result.to_dict()
                    # Ensure proper naming instead of "unknown"
                    if result_dict.get('artifact_name') == 'unknown' or not result_dict.get('artifact_name'):
                        # Use the artifact purpose if available
                        if hasattr(exec_result, 'artifact_name'):
                            result_dict['artifact_name'] = exec_result.artifact_name
                        # Add step name for identification
                        result_dict['step'] = result_dict.get('artifact_name', 'unknown')
                    results.append(result_dict)
                else:
                    results.append(exec_result)
            
            # Update state
            logger.debug("Updating state...")
            self._update_state_from_results(artifact_bundle, results)
            
            # Cleanup runner resources
            runner.cleanup()
            
            logger.info("Forge execution completed successfully")
            return results
            
        except RunnerError:
            # Re-raise RunnerError as-is
            raise
        except Exception as e:
            logger.error(f"Forge execution failed: {e}")
            
            # Determine if this is a runner issue or execution issue
            error_context = create_error_context(
                component="forge",
                operation="execute_artifact_bundle",
                runner_type=selected_runner_type if 'selected_runner_type' in locals() else "unknown",
                artifact_count=len(artifact_bundle.artifacts) if artifact_bundle else 0
            )
            
            # Check if it's a runner environment issue
            if "not available" in str(e).lower() or "not found" in str(e).lower():
                raise RunnerError(
                    f"Runner environment issue: {e}",
                    runner_type=selected_runner_type if 'selected_runner_type' in locals() else None,
                    context=error_context,
                    suggestions=[
                        f"Verify that {selected_runner_type if 'selected_runner_type' in locals() else 'the selected runner'} is properly installed",
                        "Check runner configuration and permissions",
                        "Try using a different runner type"
                    ]
                ) from e
            else:
                # General execution error
                raise wrap_external_error(
                    e,
                    ForgeError,
                    f"Artifact execution failed: {e}",
                    context=error_context,
                    suggestions=[
                        "Check that artifacts are valid and executable",
                        "Verify environment dependencies are available",
                        "Review execution logs for specific failure details"
                    ]
                )

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
              timeout_per_step: int = 300, execution_context: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Run complete pipeline: intake → assembly → forge (compile + execute).
        
        Args:
            path: Path to .cw configuration files
            variables: Optional variable overrides
            timeout_per_step: Timeout for each step in seconds
            execution_context: Context for runner selection and configuration
            
        Returns:
            List of execution results
        """
        # Generate plan
        action_list = self.plan(path, variables)
        
        # Compile and execute
        artifact_bundle = self.forge_compile(action_list)
        return self.forge_execute(artifact_bundle, timeout_per_step, execution_context)

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
                if hasattr(action, 'type') and (
                    action.type in [ActionType.VERIFY_HTTP, ActionType.VERIFY_CHECK] or
                    str(action.type).lower() in ["verify_http", "verify_service", "health_check", "verification", "verify_check", "check"]
                ) or
                "verify" in action.name.lower() or "check" in action.name.lower()
            ]
            
            if not verify_actions:
                logger.warning("No verification actions found in action list")
                return []
            
            # Create temporary action list with only verify actions
            from .models import ActionList as AL
            verify_action_list = AL(steps=verify_actions)
            
            # Compile and execute verification steps using runner
            artifact_bundle = self.forge_compile(verify_action_list)

            # Use runner to execute with timeout support
            runner = self.runner_factory.create_runner("local", {"timeout": timeout})
            if not runner.validate_environment():
                logger.warning("Local runner environment validation failed")
                return []

            execution_results = runner.execute_bundle(artifact_bundle)

            # Convert runner results to expected format
            results = []
            for exec_result in execution_results:
                results.append(exec_result.to_dict() if hasattr(exec_result, 'to_dict') else exec_result)

            # Cleanup runner resources
            runner.cleanup()
            
            logger.info(f"Verification completed: {len(results)} checks run")
            return results
            
        except Exception as e:
            logger.error(f"Verification failed: {e}")
            raise

    # =========================================================================
    # State Management and Drift Detection
    # =========================================================================

    def get_current_state(self) -> Optional[ClockworkState]:
        """Get current state."""
        return self.state_manager.load_state()
    
    def detect_drift(self, desired_ir: Optional[IR] = None, check_interval_minutes: int = 60) -> Dict[str, Any]:
        """
        Detect drift between current state and desired state.
        
        Args:
            desired_ir: Desired IR state (if None, tries to load from current state)
            check_interval_minutes: Interval for drift checking
            
        Returns:
            Dict containing drift detection report
        """
        try:
            logger.info("Starting drift detection")
            
            # Load current state
            current_state = self.state_manager.load_state()
            if not current_state:
                return {
                    "error": "No current state found",
                    "drift_detections": [],
                    "summary": {"total_resources_checked": 0, "resources_with_drift": 0}
                }
            
            # Use provided IR or load from current state
            if desired_ir is None:
                desired_ir = current_state.last_applied_ir
                if desired_ir is None:
                    return {
                        "error": "No desired state available for comparison",
                        "drift_detections": [],
                        "summary": {"total_resources_checked": 0, "resources_with_drift": 0}
                    }
            
            # Convert IR to desired state format
            desired_state = self._ir_to_desired_state(desired_ir)
            
            # Perform drift detection
            drift_detections = detect_state_drift(
                current_state.current_resources,
                desired_state,
                check_interval_minutes
            )
            
            # Generate comprehensive report
            report = generate_drift_report(drift_detections)
            report["drift_detections"] = [
                {
                    "resource_id": d.resource_id,
                    "resource_type": d.resource_type,
                    "drift_type": d.drift_type.value,
                    "severity": d.severity.value,
                    "drift_score": d.drift_score,
                    "detected_at": d.detected_at.isoformat(),
                    "suggested_actions": d.suggested_actions,
                    "config_drift_details": d.config_drift_details,
                    "runtime_drift_details": d.runtime_drift_details
                }
                for d in drift_detections
            ]
            
            logger.info(f"Drift detection completed: {report['summary']['resources_with_drift']} resources with drift")
            return report
            
        except Exception as e:
            logger.error(f"Drift detection failed: {e}")
            return {
                "error": str(e),
                "drift_detections": [],
                "summary": {"total_resources_checked": 0, "resources_with_drift": 0}
            }
    
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
            
            health_summary = current_state.get_health_summary()
            
            # Add additional context
            health_summary["state_file"] = str(self.state_manager.state_file)
            health_summary["state_version"] = current_state.version
            health_summary["last_execution"] = None
            
            if current_state.execution_history:
                latest_execution = max(current_state.execution_history, key=lambda x: x.started_at)
                health_summary["last_execution"] = {
                    "run_id": latest_execution.run_id,
                    "started_at": latest_execution.started_at.isoformat(),
                    "status": latest_execution.status.value,
                    "completed_at": latest_execution.completed_at.isoformat() if latest_execution.completed_at else None
                }
            
            logger.debug(f"State health calculated: {health_summary['health_score']}% healthy")
            return health_summary
            
        except Exception as e:
            logger.error(f"Failed to get state health: {e}")
            return {
                "error": str(e),
                "health_score": 0.0
            }
    
    def calculate_drift_score(self, desired_ir: Optional[IR] = None) -> Dict[str, Any]:
        """
        Calculate detailed drift scoring between current and desired state.
        
        Args:
            desired_ir: Desired IR state
            
        Returns:
            Dict containing drift score analysis
        """
        try:
            current_state = self.state_manager.load_state()
            if not current_state:
                return {"error": "No current state found", "overall_diff_score": 0.0}
            
            if desired_ir is None:
                desired_ir = current_state.last_applied_ir
                if desired_ir is None:
                    return {"error": "No desired state available", "overall_diff_score": 0.0}
            
            desired_state = self._ir_to_desired_state(desired_ir)
            
            score_analysis = calculate_state_diff_score(
                current_state.current_resources,
                desired_state
            )
            
            logger.info(f"Drift score calculated: {score_analysis.get('overall_diff_score', 0):.2f}%")
            return score_analysis
            
        except Exception as e:
            logger.error(f"Failed to calculate drift score: {e}")
            return {"error": str(e), "overall_diff_score": 0.0}
    
    def remediate_drift(self, path: Path, variables: Optional[Dict[str, Any]] = None, 
                       timeout_per_step: int = 300, dry_run: bool = False) -> Dict[str, Any]:
        """
        Remediate detected drift by re-applying the configuration.
        
        Args:
            path: Path to .cw configuration files
            variables: Optional variable overrides
            timeout_per_step: Timeout for each step
            dry_run: If True, only plan without executing
            
        Returns:
            Dict containing remediation results
        """
        try:
            logger.info(f"Starting drift remediation (dry_run={dry_run})")
            
            # First detect current drift
            drift_report = self.detect_drift()
            if drift_report.get("error"):
                return {"error": f"Drift detection failed: {drift_report['error']}"}
            
            resources_with_drift = drift_report["summary"]["resources_with_drift"]
            if resources_with_drift == 0:
                return {
                    "action": "no_remediation_needed",
                    "message": "No drift detected, remediation not needed",
                    "drift_report": drift_report
                }
            
            logger.info(f"Detected {resources_with_drift} resources with drift")
            
            if dry_run:
                # Plan only
                action_list = self.plan(path, variables)
                return {
                    "action": "dry_run_completed",
                    "planned_actions": len(action_list.steps),
                    "action_list": action_list.model_dump(),
                    "drift_report": drift_report
                }
            
            # Execute full remediation
            results = self.apply(path, variables, timeout_per_step)
            
            # Verify drift after remediation
            post_drift_report = self.detect_drift()
            
            return {
                "action": "remediation_completed",
                "execution_results": results,
                "pre_remediation_drift": drift_report,
                "post_remediation_drift": post_drift_report,
                "drift_reduction": {
                    "before": drift_report["summary"]["resources_with_drift"],
                    "after": post_drift_report["summary"]["resources_with_drift"]
                }
            }
            
        except Exception as e:
            logger.error(f"Drift remediation failed: {e}")
            return {"error": str(e)}
    
    def _is_result_successful(self, result: Dict[str, Any]) -> bool:
        """
        Check if an execution result indicates success.

        Args:
            result: Execution result dictionary from runner

        Returns:
            True if the result indicates success, False otherwise
        """
        # Handle ExecutionResult objects that have been converted to dict
        if isinstance(result, dict):
            # Check status field first (from ExecutionResult.to_dict())
            if "status" in result:
                return result["status"] == "success"
            # Check success field as fallback
            if "success" in result:
                return result["success"] is True
            # Check exit_code as another indicator
            if "exit_code" in result:
                return result["exit_code"] == 0
            # If none of the above, consider it failed
            return False

        # Handle ExecutionResult objects directly
        if hasattr(result, 'is_success'):
            return result.is_success()
        if hasattr(result, 'status'):
            return result.status == "success"

        # Default to failure if we can't determine success
        return False

    def _ir_to_desired_state(self, ir: IR) -> Dict[str, Any]:
        """
        Convert IR to desired state format for drift detection.
        
        Args:
            ir: Intermediate representation
            
        Returns:
            Dict representing desired state
        """
        try:
            desired_state = {}
            
            # Convert resources from IR to desired state format
            for resource_id, resource in ir.resources.items():
                resource_type = f"{resource.type.value}s"  # pluralize
                if resource_type not in desired_state:
                    desired_state[resource_type] = {}
                
                desired_state[resource_type][resource.name] = {
                    "type": resource.type.value,
                    "config": resource.config,
                    "tags": resource.tags,
                    "depends_on": resource.depends_on
                }
            
            return desired_state
            
        except Exception as e:
            logger.warning(f"Failed to convert IR to desired state: {e}")
            return {}

    def save_artifacts(self, artifact_bundle: ArtifactBundle, build_dir: Path):
        """Save artifact bundle to build directory."""
        build_dir.mkdir(parents=True, exist_ok=True)
        
        def _save_single_artifact(artifact):
            """Save a single artifact - used for parallel processing."""
            try:
                artifact_path = build_dir / artifact.path
                artifact_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Write content
                artifact_path.write_text(artifact.content)
                
                # Set permissions
                if artifact.mode:
                    import stat
                    mode = int(artifact.mode, 8)  # Convert octal string to int
                    artifact_path.chmod(mode)
                    
                return {"success": True, "path": str(artifact_path)}
            except Exception as e:
                logger.error(f"Failed to save artifact {artifact.path}: {e}")
                return {"success": False, "path": artifact.path, "error": str(e)}
        
        # Parallelize artifact saving when there are multiple artifacts
        if len(artifact_bundle.artifacts) > 1:
            logger.debug(f"Saving {len(artifact_bundle.artifacts)} artifacts in parallel")
            try:
                results = Parallel(n_jobs=-1, backend='threading')(
                    delayed(_save_single_artifact)(artifact)
                    for artifact in artifact_bundle.artifacts
                )
                
                # Check for any failures
                failed_saves = [r for r in results if not r["success"]]
                if failed_saves:
                    logger.warning(f"Failed to save {len(failed_saves)} artifacts")
                    for failure in failed_saves:
                        logger.error(f"Artifact save failed: {failure['path']} - {failure['error']}")
            except Exception as e:
                logger.warning(f"Parallel artifact saving failed, falling back to sequential: {e}")
                # Fallback to sequential processing
                for artifact in artifact_bundle.artifacts:
                    _save_single_artifact(artifact)
        else:
            # For single artifact, save directly
            if artifact_bundle.artifacts:
                _save_single_artifact(artifact_bundle.artifacts[0])
        
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
            # Calculate checksums - use artifact bundle steps as proxy for action list since we don't have access to it
            artifact_bundle_str = json.dumps([step.model_dump() for step in artifact_bundle.steps], sort_keys=True)
            artifact_bundle_checksum = hashlib.sha256(artifact_bundle_str.encode()).hexdigest()
            
            # Use artifact bundle checksum for action list checksum since action_list is not available
            action_list_checksum = artifact_bundle_checksum
            
            # Properly evaluate execution status from results
            success_count = sum(1 for r in results if self._is_result_successful(r))
            total_count = len(results)
            overall_success = success_count == total_count and total_count > 0

            execution_record = ExecutionRecord(
                run_id=f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                started_at=datetime.now(),
                completed_at=datetime.now(),
                status=ExecutionStatus.SUCCESS if overall_success else ExecutionStatus.FAILED,
                action_list_checksum=action_list_checksum,
                artifact_bundle_checksum=artifact_bundle_checksum,
                logs=[str(r) for r in results]
            )
            
            def _create_resource_state(result_data):
                """Create resource state from result data - used for parallel processing."""
                i, result = result_data
                try:
                    if i < len(artifact_bundle.steps):
                        step = artifact_bundle.steps[i]
                        resource_id = step.purpose
                        
                        # Determine resource type from action step type
                        step_type = getattr(step, 'type', ActionType.CUSTOM)
                        if isinstance(step_type, str):
                            step_type = ActionType(step_type) if step_type in [e.value for e in ActionType] else ActionType.CUSTOM
                        
                        # Map action types to resource types
                        action_to_resource_mapping = {
                            ActionType.ENSURE_SERVICE: ResourceType.SERVICE,
                            ActionType.BUILD_IMAGE: ResourceType.IMAGE,
                            ActionType.CREATE_NAMESPACE: ResourceType.CONFIG,
                            ActionType.APPLY_CONFIG: ResourceType.CONFIG,
                            ActionType.COPY_FILES: ResourceType.FILE,
                            ActionType.VERIFY_HTTP: ResourceType.VERIFICATION,
                            ActionType.FILE_OPERATION: ResourceType.FILE,
                            ActionType.CREATE_DIRECTORY: ResourceType.DIRECTORY,
                            ActionType.VERIFY_CHECK: ResourceType.CHECK,
                        }
                        resource_type = action_to_resource_mapping.get(step_type, ResourceType.CUSTOM)
                        
                        # Determine status using proper success evaluation
                        is_successful = self._is_result_successful(result)
                        status = ExecutionStatus.SUCCESS if is_successful else ExecutionStatus.FAILED

                        resource_state = ResourceState(
                            resource_id=resource_id,
                            type=resource_type,
                            status=status,
                            last_applied=datetime.now(),
                            last_verified=datetime.now(),
                            error_message=result.get("error_message") or result.get("stderr") if not is_successful else None
                        )
                        
                        return (resource_id, resource_state)
                    return None
                except Exception as e:
                    logger.error(f"Failed to create resource state for result {i}: {e}")
                    return None
            
            # Parallelize resource state updates when there are multiple results
            if len(results) > 1:
                logger.debug(f"Processing {len(results)} resource state updates in parallel")
                try:
                    resource_states = Parallel(n_jobs=-1, backend='threading')(
                        delayed(_create_resource_state)((i, result))
                        for i, result in enumerate(results)
                    )
                    
                    # Update state with results
                    for resource_data in resource_states:
                        if resource_data:
                            resource_id, resource_state = resource_data
                            state.current_resources[resource_id] = resource_state
                            
                except Exception as e:
                    logger.warning(f"Parallel state update failed, falling back to sequential: {e}")
                    # Fallback to sequential processing
                    for i, result in enumerate(results):
                        resource_data = _create_resource_state((i, result))
                        if resource_data:
                            resource_id, resource_state = resource_data
                            state.current_resources[resource_id] = resource_state
            else:
                # For single result, process directly
                if results:
                    resource_data = _create_resource_state((0, results[0]))
                    if resource_data:
                        resource_id, resource_state = resource_data
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
    # Helper Methods
    # =========================================================================
    
    def _convert_ir_to_planner_format(self, ir: IR) -> Dict[str, Any]:
        """Convert IR Pydantic model to dictionary format expected by planner."""
        ir_dict = {
            "config": {},
            "services": {},
            "repositories": {},
            "files": {},
            "directories": {},
            "verifications": {},
            "checks": {}
        }
        
        # Extract config from metadata or resources
        if ir.metadata.get("namespace"):
            ir_dict["config"]["namespace"] = ir.metadata["namespace"]
        
        def _process_single_resource(resource_item):
            """Process a single resource - used for parallel processing."""
            resource_name, resource = resource_item
            try:
                resource_type = resource.type.value if hasattr(resource.type, 'value') else str(resource.type)
                logger.debug(f"Processing resource {resource_name} of type {resource_type}")
                
                if resource_type == "service":
                    service_config = {
                        "name": resource.name,
                        "image": resource.config.get("image", "nginx:latest"),
                    }
                    
                    # Add ports if specified
                    if "ports" in resource.config:
                        service_config["ports"] = resource.config["ports"]
                    elif "port" in resource.config:
                        # Convert single port to ports array
                        service_config["ports"] = [{"external": resource.config["port"], "internal": 80}]
                    
                    # Add environment variables
                    if "environment" in resource.config:
                        service_config["environment"] = resource.config["environment"]
                    
                    # Add health check if specified (handle both dict and list[dict] from HCL parsing)
                    if "health_check" in resource.config:
                        health_check = resource.config["health_check"]
                        if isinstance(health_check, list) and len(health_check) > 0:
                            # HCL parser returns list, take first item
                            service_config["health_check"] = health_check[0]
                        else:
                            service_config["health_check"] = health_check
                    
                    # Add dependencies if specified
                    if resource.depends_on:
                        service_config["depends_on"] = resource.depends_on
                    
                    return ("services", resource.name, service_config)
                    
                elif resource_type == "file":
                    file_config = {
                        "name": resource.name,
                        "path": resource.config.get("path", ""),
                        "type": resource.config.get("type", "file"),  # file, directory
                        "mode": resource.config.get("mode", "644"),
                    }
                    
                    # Add content if specified
                    if "content" in resource.config:
                        file_config["content"] = resource.config["content"]
                    
                    # Add dependencies if specified
                    if resource.depends_on:
                        file_config["depends_on"] = resource.depends_on
                    
                    return ("files", resource.name, file_config)
                    
                elif resource_type == "verification":
                    verification_config = {
                        "name": resource.config.get("name", resource.name),
                        "checks": resource.config.get("checks", []),
                    }

                    # Add dependencies if specified
                    if resource.depends_on:
                        verification_config["depends_on"] = resource.depends_on

                    return ("verifications", resource.name, verification_config)

                elif resource_type == "check":
                    check_config = {
                        "name": resource.config.get("name", resource.name),
                        "description": resource.config.get("description", "Check resource verification"),
                        "type": resource.config.get("type", "file_exists"),
                        "target": resource.config.get("target", ""),
                    }

                    # Add dependencies if specified
                    if resource.depends_on:
                        check_config["depends_on"] = resource.depends_on

                    return ("checks", resource.name, check_config)

                elif resource_type == "directory":
                    directory_config = {
                        "name": resource.name,
                        "path": resource.config.get("path", ""),
                        "mode": resource.config.get("mode", "755"),
                        "description": resource.config.get("description", "Directory resource"),
                    }

                    # Add dependencies if specified
                    if resource.depends_on:
                        directory_config["depends_on"] = resource.depends_on

                    return ("directories", resource.name, directory_config)

                return None
            except Exception as e:
                logger.error(f"Failed to process resource {resource_name}: {e}")
                return None
        
        def _process_single_module(module_item):
            """Process a single module - used for parallel processing."""
            module_name, module = module_item
            try:
                if module.source.startswith(("http", "git")):
                    return (module_name, {
                        "url": module.source,
                        "branch": module.inputs.get("branch", "main")
                    })
                return None
            except Exception as e:
                logger.error(f"Failed to process module {module_name}: {e}")
                return None
        
        # Parallelize resource conversion when there are multiple resources
        if len(ir.resources) > 1:
            logger.debug(f"Converting {len(ir.resources)} resources from IR in parallel")
            try:
                resource_results = Parallel(n_jobs=-1, backend='threading')(
                    delayed(_process_single_resource)(item)
                    for item in ir.resources.items()
                )
                
                # Add processed resources to ir_dict
                for result in resource_results:
                    if result:
                        resource_category, resource_name, resource_config = result
                        ir_dict[resource_category][resource_name] = resource_config
                        
            except Exception as e:
                logger.warning(f"Parallel resource processing failed, falling back to sequential: {e}")
                # Fallback to sequential processing
                for resource_name, resource in ir.resources.items():
                    result = _process_single_resource((resource_name, resource))
                    if result:
                        resource_category, resource_name, resource_config = result
                        ir_dict[resource_category][resource_name] = resource_config
        else:
            # For single resource, process directly
            if ir.resources:
                resource_name, resource = next(iter(ir.resources.items()))
                result = _process_single_resource((resource_name, resource))
                if result:
                    resource_category, resource_name, resource_config = result
                    ir_dict[resource_category][resource_name] = resource_config
        
        # Parallelize module conversion when there are multiple modules
        if len(ir.modules) > 1:
            logger.debug(f"Converting {len(ir.modules)} modules from IR in parallel")
            try:
                module_results = Parallel(n_jobs=-1, backend='threading')(
                    delayed(_process_single_module)(item)
                    for item in ir.modules.items()
                )
                
                # Add processed modules to ir_dict
                for result in module_results:
                    if result:
                        module_name, module_config = result
                        ir_dict["repositories"][module_name] = module_config
                        
            except Exception as e:
                logger.warning(f"Parallel module processing failed, falling back to sequential: {e}")
                # Fallback to sequential processing
                for module_name, module in ir.modules.items():
                    result = _process_single_module((module_name, module))
                    if result:
                        module_name, module_config = result
                        ir_dict["repositories"][module_name] = module_config
        else:
            # For single module, process directly
            if ir.modules:
                module_name, module = next(iter(ir.modules.items()))
                result = _process_single_module((module_name, module))
                if result:
                    module_name, module_config = result
                    ir_dict["repositories"][module_name] = module_config
        
        return ir_dict

    # =========================================================================
    # Utility Methods
    # =========================================================================

    # =========================================================================
    # Daemon Integration
    # =========================================================================
    
    def start_daemon(self, daemon_config = None, config_path: Optional[Path] = None):
        """
        Start the Clockwork daemon for continuous monitoring and drift detection.
        
        Args:
            daemon_config: Optional daemon configuration
            config_path: Path to watch for configuration changes
            
        Returns:
            Running ClockworkDaemon instance
            
        Raises:
            DaemonError: If daemon fails to start
        """
        try:
            # Import daemon dynamically to avoid circular imports
            from .daemon import ClockworkDaemon, DaemonConfig
            
            if hasattr(self, 'daemon') and self.daemon and self.daemon.is_running():
                logger.warning("Daemon is already running")
                return self.daemon
            
            watch_path = config_path or self.config_path
            
            # Validate watch path exists
            if not watch_path.exists():
                from .errors import DaemonError
                raise DaemonError(
                    f"Watch path does not exist: {watch_path}",
                    context=create_error_context(
                        file_path=str(watch_path),
                        component="daemon",
                        operation="start"
                    ),
                    suggestions=[
                        "Ensure the configuration path exists",
                        "Create the directory if it doesn't exist"
                    ]
                )
            
            # Create default daemon config if not provided
            if not daemon_config:
                daemon_config = DaemonConfig(
                    watch_paths=[str(watch_path)],
                    check_interval_seconds=60,
                    auto_fix_enabled=False,  # Conservative default
                    drift_check_enabled=True
                )
            
            # Initialize daemon with ClockworkCore reference
            self.daemon = ClockworkDaemon(
                config=daemon_config,
                clockwork_core=self
            )
            
            logger.info(f"Starting Clockwork daemon for path: {watch_path}")
            self.daemon.start()
            return self.daemon
            
        except DaemonError:
            raise
        except Exception as e:
            raise wrap_external_error(
                e,
                DaemonError,
                f"Failed to start daemon: {e}",
                context=create_error_context(
                    component="daemon",
                    operation="start",
                    watch_path=str(watch_path) if 'watch_path' in locals() else None
                ),
                suggestions=[
                    "Check that the daemon configuration is valid",
                    "Verify filesystem permissions for watch paths",
                    "Ensure no other daemon is already running"
                ]
            )
    
    def stop_daemon(self):
        """Stop the running daemon."""
        if self.daemon:
            logger.info("Stopping Clockwork daemon")
            self.daemon.stop()
            self.daemon = None
        else:
            logger.warning("No daemon running")
    
    def daemon_status(self) -> Dict[str, Any]:
        """Get daemon status information."""
        if not self.daemon:
            return {"running": False, "error": "No daemon instance"}
        
        return self.daemon.get_status()
    
    # =========================================================================
    # Runner Management
    # =========================================================================
    
    def get_runner_capabilities(self, runner_type: Optional[str] = None) -> Dict[str, Any]:
        """Get capabilities of available or specific runner."""
        if runner_type:
            if runner_type not in self.available_runners:
                return {"error": f"Runner {runner_type} not available"}
            
            runner = self.runner_factory.create_runner(runner_type)
            return runner.get_capabilities()
        else:
            # Return capabilities for all available runners
            capabilities = {}
            for runner_type in self.available_runners:
                try:
                    runner = self.runner_factory.create_runner(runner_type)
                    capabilities[runner_type] = runner.get_capabilities()
                except Exception as e:
                    capabilities[runner_type] = {"error": str(e)}
            return capabilities
    
    def test_runner(self, runner_type: str, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Test a specific runner environment."""
        try:
            runner = self.runner_factory.create_runner(runner_type, config)
            is_valid = runner.validate_environment()
            capabilities = runner.get_capabilities()
            
            return {
                "runner_type": runner_type,
                "valid": is_valid,
                "capabilities": capabilities,
                "config": config or {}
            }
        except Exception as e:
            return {
                "runner_type": runner_type,
                "valid": False,
                "error": str(e)
            }

    # =========================================================================
    # Cache Management
    # =========================================================================
    
    def clear_resolver_cache(self):
        """Clear the resolver cache."""
        logger.info("Clearing resolver cache...")
        self.resolver.clear_cache()
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get resolver cache statistics."""
        return self.resolver.get_cache_stats()

    def cleanup(self):
        """Cleanup temporary files and resources."""
        logger.info("Cleaning up...")
        
        # Stop daemon if running
        if self.daemon:
            self.stop_daemon()
        
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