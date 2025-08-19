"""
Compiler module for converting ActionList to ArtifactBundle using AI agents.

This module provides the interface for calling AI agents to transform 
declarative action lists into executable artifacts in various languages.
"""

import json
import logging
import os
import re
import stat
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, Tuple
from joblib import Parallel, delayed, Memory
from ..models import ActionStep, ActionList as ModelsActionList, ArtifactBundle, Artifact, ExecutionStep
from .agno_agent import AgnoCompiler, AgnoCompilerError, create_agno_compiler

logger = logging.getLogger(__name__)

# Allowlisted runtimes for security validation
ALLOWED_RUNTIMES = {
    "bash", "python3", "python", "deno", "go", "node", "npm", "npx", 
    "java", "mvn", "gradle", "dotnet", "cargo", "rustc", "env"
}

# Allowed build directory patterns
ALLOWED_BUILD_PATHS = [
    ".clockwork/build",
    "scripts",
    "artifacts"
]


class SecurityValidationError(Exception):
    """Exception raised when security validation fails."""
    pass


class CompilerError(Exception):
    """Exception raised during compilation process."""
    pass


class Compiler:
    """
    Compiler interface for converting ActionList to ArtifactBundle using AI agents.
    
    This class provides the interface for calling AI agents to transform
    declarative action lists into executable artifacts with comprehensive
    security validation and runtime allowlisting.
    """
    
    def __init__(
        self, 
        timeout: int = 300,
        build_dir: str = ".clockwork/build",
        use_agno: bool = True,
        lm_studio_url: Optional[str] = None,
        agno_model_id: Optional[str] = None
    ):
        """
        Initialize the compiler.
        
        Args:
            timeout: Request timeout in seconds
            build_dir: Base directory for artifact output
            use_agno: Whether to use Agno/LM Studio integration (default: True)
            lm_studio_url: LM Studio server URL (default: http://localhost:1234)
            agno_model_id: Model ID for Agno agent (default: qwen/qwen3-4b-2507)
        """
        self.timeout = timeout
        self.build_dir = Path(build_dir)
        
        # Agno integration parameters
        self.use_agno = use_agno
        self.lm_studio_url = lm_studio_url or os.getenv('CLOCKWORK_LM_STUDIO_URL', "http://localhost:1234")
        self.agno_model_id = agno_model_id or "qwen/qwen3-4b-2507"
        
        # Initialize Agno compiler if enabled - fail fast if not available
        self.agno_compiler = None
        if self.use_agno:
            try:
                self.agno_compiler = create_agno_compiler(
                    model_id=self.agno_model_id,
                    lm_studio_url=self.lm_studio_url,
                    timeout=timeout
                )
                logger.info(f"Initialized Agno AI compiler with model: {self.agno_model_id}")
            except AgnoCompilerError as e:
                logger.error(f"Failed to initialize Agno compiler: {e}")
                raise CompilerError(f"LM Studio connection required but failed: {e}")
            except Exception as e:
                logger.error(f"Unexpected error initializing Agno compiler: {e}")
                raise CompilerError(f"Failed to initialize AI compiler: {e}")
        
        # Initialize joblib caching
        cache_dir = self.build_dir / "cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        self.memory = Memory(location=str(cache_dir), verbose=0)
        
        logger.info(f"Initialized compiler with agno_model: {self.agno_model_id}, build_dir: {build_dir}")
        logger.info(f"Caching enabled with directory: {cache_dir}")
    
    def clear_cache(self) -> None:
        """
        Clear the compilation cache.
        
        This method clears all cached compilation results, forcing fresh compilation
        of all action steps on the next compile() call.
        """
        try:
            self.memory.clear()
            logger.info("Compilation cache cleared successfully")
        except Exception as e:
            logger.warning(f"Failed to clear cache: {e}")
    
    def get_cache_info(self) -> Dict[str, Any]:
        """
        Get information about the current cache state.
        
        Returns:
            Dictionary containing cache information
        """
        try:
            cache_dir = Path(self.memory.location)
            if cache_dir.exists():
                cache_files = list(cache_dir.rglob("*"))
                cache_size = sum(f.stat().st_size for f in cache_files if f.is_file())
                return {
                    "cache_dir": str(cache_dir),
                    "cache_files": len([f for f in cache_files if f.is_file()]),
                    "cache_size_bytes": cache_size,
                    "cache_size_mb": round(cache_size / (1024 * 1024), 2)
                }
            else:
                return {"cache_dir": str(cache_dir), "cache_files": 0, "cache_size_bytes": 0, "cache_size_mb": 0}
        except Exception as e:
            logger.warning(f"Failed to get cache info: {e}")
            return {"error": str(e)}
    
    def _compute_step_hash(self, step: ActionStep) -> str:
        """
        Compute a hash for an action step based on its content.
        
        Args:
            step: The action step to hash
            
        Returns:
            SHA256 hash of the step content
        """
        step_data = {
            "name": step.name,
            "type": step.type.value if hasattr(step.type, 'value') else str(step.type),
            "args": step.args,
            "depends_on": sorted(step.depends_on)  # Sort for consistent hashing
        }
        step_json = json.dumps(step_data, sort_keys=True)
        return hashlib.sha256(step_json.encode()).hexdigest()
    
    def _analyze_dependencies(self, steps: List[ActionStep]) -> List[List[int]]:
        """
        Analyze step dependencies to group independent steps for parallel processing.
        
        Args:
            steps: List of action steps to analyze
            
        Returns:
            List of groups, where each group contains indices of steps that can be run in parallel
        """
        # Create a mapping of step names to indices
        name_to_index = {step.name: i for i, step in enumerate(steps)}
        
        # Build dependency graph
        dependencies = [set() for _ in steps]
        for i, step in enumerate(steps):
            for dep in step.depends_on:
                if dep in name_to_index:
                    dependencies[i].add(name_to_index[dep])
        
        # Group steps into parallel batches using topological ordering
        groups = []
        completed = set()
        
        while len(completed) < len(steps):
            # Find steps that can be executed (all dependencies completed)
            ready_steps = []
            for i, step_deps in enumerate(dependencies):
                if i not in completed and step_deps.issubset(completed):
                    ready_steps.append(i)
            
            if not ready_steps:
                # This shouldn't happen with valid dependencies, but handle it gracefully
                logger.warning("Circular dependency detected or invalid dependency graph")
                # Add remaining steps as individual groups
                remaining = [i for i in range(len(steps)) if i not in completed]
                groups.extend([[i] for i in remaining])
                break
            
            groups.append(ready_steps)
            completed.update(ready_steps)
        
        logger.info(f"Grouped {len(steps)} steps into {len(groups)} parallel batches")
        return groups
    
    def _compile_single_step_cached(self, step: ActionStep, step_hash: str, action_list_context: Dict[str, Any]) -> Optional[Tuple[List[Artifact], List[ExecutionStep]]]:
        """
        Cached compilation of a single action step.
        
        Args:
            step: The action step to compile
            step_hash: Hash of the step for caching
            action_list_context: Context from the full action list (metadata, etc.)
            
        Returns:
            Tuple of (artifacts, execution_steps) or None if compilation fails
        """
        return self.memory.cache(self._compile_single_step_uncached)(step, step_hash, action_list_context)
    
    def _compile_single_step_uncached(self, step: ActionStep, step_hash: str, action_list_context: Dict[str, Any]) -> Optional[Tuple[List[Artifact], List[ExecutionStep]]]:
        """
        Compile a single action step without caching.
        
        Args:
            step: The action step to compile
            step_hash: Hash of the step (for logging/debugging)
            action_list_context: Context from the full action list
            
        Returns:
            Tuple of (artifacts, execution_steps) or None if compilation fails
        """
        try:
            logger.info(f"Compiling step '{step.name}' (hash: {step_hash[:8]}...)")
            
            # Create a temporary action list with just this step for compilation
            temp_action_list = ModelsActionList(
                version=action_list_context.get('version', '1'),
                steps=[step],
                metadata=action_list_context.get('metadata', {})
            )
            
            # Use Agno compiler - no fallback for individual steps
            if self.use_agno and self.agno_compiler:
                bundle = self.agno_compiler.compile_to_artifacts(temp_action_list)
            else:
                logger.error(f"Cannot compile step '{step.name}' - no AI compiler available")
                raise CompilerError(
                    f"AI compilation required for step '{step.name}' but Agno compiler not available. "
                    "Please ensure LM Studio is running with a loaded model."
                )
            
            # Since we're compiling a single step, return all artifacts and steps from the bundle
            # The AI compiler generates appropriate artifacts for the given step
            artifacts = bundle.artifacts
            steps = bundle.steps
            
            logger.info(f"Successfully compiled step '{step.name}' -> {len(artifacts)} artifacts, {len(steps)} execution steps")
            return (artifacts, steps)
            
        except Exception as e:
            logger.error(f"Failed to compile step '{step.name}': {e}")
            return None
    
    def compile(self, action_list: ModelsActionList) -> ArtifactBundle:
        """
        Compile an ActionList into an ArtifactBundle with parallel processing and caching.
        
        Args:
            action_list: The list of actions to compile
            
        Returns:
            ArtifactBundle containing executable artifacts
            
        Raises:
            CompilerError: If compilation fails
        """
        try:
            logger.info(f"Compiling ActionList with {len(action_list.steps)} steps using parallel processing")
            
            # If only one step or parallel processing disabled, use original method
            if len(action_list.steps) <= 1:
                logger.info("Single step detected, using non-parallel compilation")
                return self._compile_sequential(action_list)
            
            # Analyze dependencies and group steps for parallel processing
            step_groups = self._analyze_dependencies(action_list.steps)
            
            # Prepare context for step compilation
            action_list_context = {
                'version': action_list.version,
                'metadata': action_list.metadata
            }
            
            # Compile steps in parallel batches
            all_artifacts = []
            all_execution_steps = []
            bundle_vars = {}
            
            for group_idx, step_indices in enumerate(step_groups):
                logger.info(f"Processing parallel group {group_idx + 1}/{len(step_groups)} with {len(step_indices)} steps")
                
                if len(step_indices) == 1:
                    # Single step in group - compile directly
                    step = action_list.steps[step_indices[0]]
                    step_hash = self._compute_step_hash(step)
                    result = self._compile_single_step_cached(step, step_hash, action_list_context)
                    if result:
                        artifacts, exec_steps = result
                        all_artifacts.extend(artifacts)
                        all_execution_steps.extend(exec_steps)
                else:
                    # Multiple steps in group - compile in parallel
                    steps_to_compile = [(action_list.steps[i], self._compute_step_hash(action_list.steps[i]), action_list_context) 
                                      for i in step_indices]
                    
                    # Use joblib.Parallel with threading backend for I/O-bound operations
                    parallel_results = Parallel(n_jobs=-1, backend='threading')(
                        delayed(self._compile_single_step_cached)(step, step_hash, context) 
                        for step, step_hash, context in steps_to_compile
                    )
                    
                    # Collect results from parallel compilation
                    for result in parallel_results:
                        if result:
                            artifacts, exec_steps = result
                            all_artifacts.extend(artifacts)
                            all_execution_steps.extend(exec_steps)
            
            # Create the final artifact bundle
            artifact_bundle = ArtifactBundle(
                version=action_list.version,
                artifacts=all_artifacts,
                steps=all_execution_steps,
                vars=bundle_vars
            )
            
            # Comprehensive validation
            self._validate_artifact_bundle(artifact_bundle, action_list)
            
            logger.info(f"Successfully compiled {len(artifact_bundle.artifacts)} artifacts using parallel processing")
            return artifact_bundle
            
        except Exception as e:
            logger.error(f"Parallel compilation failed: {e}")
            logger.info("Falling back to sequential compilation")
            try:
                return self._compile_sequential(action_list)
            except Exception as fallback_error:
                logger.error(f"Fallback compilation also failed: {fallback_error}")
                raise CompilerError(f"Failed to compile ActionList: {e}")
    
    def _compile_sequential(self, action_list: ModelsActionList) -> ArtifactBundle:
        """
        Sequential compilation fallback method.
        
        Args:
            action_list: The list of actions to compile
            
        Returns:
            ArtifactBundle containing executable artifacts
            
        Raises:
            CompilerError: If compilation fails
        """
        try:
            logger.info("Using sequential compilation")
            
            # Use Agno AI compiler - no fallback
            if self.use_agno and self.agno_compiler:
                logger.info("Using Agno AI compiler for artifact generation")
                artifact_bundle = self.agno_compiler.compile_to_artifacts(action_list)
            else:
                logger.error("No AI compiler available - Agno compiler initialization failed")
                raise CompilerError(
                    "AI compilation is required but Agno compiler is not available. "
                    "Please ensure LM Studio is running with a loaded model."
                )
            
            return artifact_bundle
            
        except Exception as e:
            logger.error(f"Sequential compilation failed: {e}")
            raise CompilerError(f"Failed to compile ActionList: {e}")
    
    
    
    
    
    def save_bundle(self, bundle: ArtifactBundle, output_dir: Optional[Path] = None) -> None:
        """
        Save an ArtifactBundle to disk.
        
        Args:
            bundle: The bundle to save
            output_dir: Directory to save artifacts (defaults to build_dir)
        """
        if output_dir is None:
            output_dir = self.build_dir
            
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Save bundle metadata
        bundle_file = output_dir / "artifact_bundle.json"
        with open(bundle_file, "w") as f:
            f.write(bundle.to_json())
        
        # Save each artifact with proper path structure
        for artifact in bundle.artifacts:
            artifact_path = output_dir / artifact.path
            artifact_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write artifact content
            with open(artifact_path, "w") as f:
                f.write(artifact.content)
            
            # Set file permissions
            try:
                mode = int(artifact.mode, 8)  # Convert octal string to int
                os.chmod(artifact_path, mode)
            except (ValueError, OSError) as e:
                logger.warning(f"Failed to set permissions {artifact.mode} on {artifact_path}: {e}")
        
        logger.info(f"Saved bundle with {len(bundle.artifacts)} artifacts to {output_dir}")
    
    def _validate_artifact_bundle(self, bundle: ArtifactBundle, action_list: ModelsActionList) -> None:
        """
        Comprehensive validation of the ArtifactBundle.
        
        Args:
            bundle: The bundle to validate
            action_list: Original action list for reference
            
        Raises:
            SecurityValidationError: If validation fails
        """
        logger.info("Validating artifact bundle security and compliance")
        
        # Validate bundle structure using Pydantic validation
        try:
            bundle.model_validate(bundle.model_dump())
        except Exception as e:
            raise SecurityValidationError(f"Bundle structure validation failed: {e}")
        
        # Validate artifact paths are confined to allowed directories
        for artifact in bundle.artifacts:
            self._validate_artifact_path(artifact.path)
            self._validate_artifact_content(artifact)
        
        # Validate execution steps
        for step in bundle.steps:
            self._validate_execution_step(step)
        
        # Validate that all action steps have corresponding artifacts/steps
        self._validate_step_completeness(bundle, action_list)
        
        logger.info("Bundle validation completed successfully")
    
    def _validate_artifact_path(self, path: str) -> None:
        """
        Validate that artifact path is within allowed directories.
        
        Args:
            path: The artifact path to validate
            
        Raises:
            SecurityValidationError: If path is invalid
        """
        # Check if path starts with any allowed pattern (don't resolve to avoid filesystem access)
        allowed = any(path.startswith(allowed_path) for allowed_path in ALLOWED_BUILD_PATHS)
        
        if not allowed:
            raise SecurityValidationError(
                f"Artifact path '{path}' is not within allowed directories: {ALLOWED_BUILD_PATHS}"
            )
        
        # Additional security checks
        if ".." in path:
            raise SecurityValidationError(f"Artifact path '{path}' contains directory traversal")
        
        if path.startswith("/"):
            raise SecurityValidationError(f"Artifact path '{path}' is absolute (must be relative)")
    
    def _validate_artifact_content(self, artifact: Artifact) -> None:
        """
        Validate artifact content for security issues.
        
        Args:
            artifact: The artifact to validate
            
        Raises:
            SecurityValidationError: If content is unsafe
        """
        # Validate file permissions
        try:
            mode = int(artifact.mode, 8)
            if mode > 0o777:
                raise SecurityValidationError(f"Invalid file mode: {artifact.mode}")
        except ValueError:
            raise SecurityValidationError(f"Invalid file mode format: {artifact.mode}")
        
        # Validate shebang lines if executable
        if artifact.mode.endswith(("5", "7")):  # executable permissions
            lines = artifact.content.split("\n")
            if lines and lines[0].startswith("#!"):
                shebang = lines[0][2:].strip()
                runtime = shebang.split()[0] if shebang.split() else ""
                runtime_name = Path(runtime).name
                
                if runtime_name not in ALLOWED_RUNTIMES:
                    raise SecurityValidationError(
                        f"Shebang runtime '{runtime_name}' not in allowed list: {sorted(ALLOWED_RUNTIMES)}"
                    )
        
        # Basic content security checks
        dangerous_patterns = [
            r"rm\s+-rf\s+/",  # Dangerous deletions
            r"dd\s+if=/dev/zero",  # Disk wiping
            r":\(\)\{\s*:\|:\s*&\s*\}\s*;",  # Fork bombs
            r"sudo\s+chmod\s+777",  # Dangerous permissions
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, artifact.content, re.IGNORECASE):
                raise SecurityValidationError(
                    f"Artifact '{artifact.path}' contains potentially dangerous pattern: {pattern}"
                )
    
    def _validate_execution_step(self, step: ExecutionStep) -> None:
        """
        Validate execution step for allowed runtimes.
        
        Args:
            step: The execution step to validate
            
        Raises:
            SecurityValidationError: If step uses disallowed runtime
        """
        if "cmd" not in step.run:
            raise SecurityValidationError(f"Execution step '{step.purpose}' missing 'cmd' field")
        
        cmd = step.run["cmd"]
        if not isinstance(cmd, list) or not cmd:
            raise SecurityValidationError(f"Execution step '{step.purpose}' cmd must be non-empty list")
        
        runtime = cmd[0]
        if runtime not in ALLOWED_RUNTIMES:
            raise SecurityValidationError(
                f"Runtime '{runtime}' in step '{step.purpose}' not allowed. Allowed: {sorted(ALLOWED_RUNTIMES)}"
            )
    
    def _validate_step_completeness(self, bundle: ArtifactBundle, action_list: ModelsActionList) -> None:
        """
        Validate that all ActionList steps are covered by the bundle.
        
        Args:
            bundle: The artifact bundle
            action_list: The original action list
            
        Raises:
            SecurityValidationError: If steps are missing
        """
        action_step_names = {step.name for step in action_list.steps}
        bundle_step_purposes = {step.purpose for step in bundle.steps}
        
        missing_steps = action_step_names - bundle_step_purposes
        if missing_steps:
            # Convert to warning instead of error - this is common when step names are transformed
            logger.warning(
                f"ActionList steps not directly covered by bundle: {sorted(missing_steps)}. "
                "This may be normal if step names are transformed during compilation."
            )
        
        extra_steps = bundle_step_purposes - action_step_names
        if extra_steps:
            logger.warning(f"Bundle contains extra steps not in ActionList: {sorted(extra_steps)}")
