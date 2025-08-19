"""
Enhanced Executor module for validating and executing generated artifacts safely.

This module provides functionality for running compiled artifacts in sandboxed
environments with proper logging, validation, security measures, timeout handling,
retry logic, and comprehensive path validation. Now integrated with the Runner
system for multi-environment execution support.
"""

import asyncio
import hashlib
import json
import logging
import os
import platform
import psutil
import re
import resource
import signal
import stat
import subprocess
import tempfile
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, Tuple
import shutil
import joblib

from ..models import ArtifactBundle, Artifact, ExecutionStep
from .runner import Runner, RunnerFactory, RunnerType, select_runner
from ..errors import ValidationError

logger = logging.getLogger(__name__)


def load_parallel_limit_from_config() -> int:
    """Load parallel_limit from development.json configuration."""
    config_paths = [
        "configs/development.json",
        "../configs/development.json", 
        "../../configs/development.json"
    ]
    
    for config_path in config_paths:
        try:
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    config = json.load(f)
                    return config.get("clockwork", {}).get("forge", {}).get("execution", {}).get("parallel_limit", 4)
        except (json.JSONDecodeError, FileNotFoundError, KeyError):
            continue
    
    # Fallback to environment variable or default
    return int(os.environ.get("CLOCKWORK_PARALLEL_LIMIT", 4))


class ExecutionStatus(Enum):
    """Status of artifact execution."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    RETRYING = "retrying"
    SKIPPED = "skipped"


class RuntimeType(Enum):
    """Supported runtime types for execution."""
    PYTHON3 = "python3"
    BASH = "bash"
    SH = "sh"
    NODE = "node"
    DENO = "deno"
    GO = "go"
    RUST = "rust"
    JAVA = "java"
    DOTNET = "dotnet"


@dataclass
class ExecutionResult:
    """Enhanced result of executing an artifact with detailed tracking."""
    artifact_name: str
    status: ExecutionStatus
    exit_code: Optional[int] = None
    stdout: str = ""
    stderr: str = ""
    execution_time: float = 0.0
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    retry_count: int = 0
    timeout_occurred: bool = False
    resource_usage: Dict[str, Any] = field(default_factory=dict)
    command: List[str] = field(default_factory=list)
    working_directory: Optional[str] = None
    environment_vars: Dict[str, str] = field(default_factory=dict)
    validation_warnings: List[str] = field(default_factory=list)
    security_violations: List[str] = field(default_factory=list)
    
    def is_success(self) -> bool:
        """Check if execution was successful."""
        return self.status == ExecutionStatus.SUCCESS and self.exit_code == 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "artifact_name": self.artifact_name,
            "status": self.status.value,
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "execution_time": self.execution_time,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "error_message": self.error_message,
            "metadata": self.metadata,
            "retry_count": self.retry_count,
            "timeout_occurred": self.timeout_occurred,
            "resource_usage": self.resource_usage,
            "command": self.command,
            "working_directory": self.working_directory,
            "environment_vars": self.environment_vars,
            "validation_warnings": self.validation_warnings,
            "security_violations": self.security_violations
        }


class ExecutionError(Exception):
    """Exception raised during artifact execution."""
    
    def __init__(self, message: str, result: Optional[ExecutionResult] = None):
        super().__init__(message)
        self.result = result


@dataclass
class SandboxConfig:
    """Enhanced configuration for sandbox environment with security controls."""
    max_memory_mb: int = 512
    max_cpu_percent: float = 50.0
    max_execution_time: int = 300
    allow_network: bool = False
    allow_file_write: bool = True
    allowed_directories: List[str] = field(default_factory=lambda: [".clockwork/build"])
    blocked_commands: List[str] = field(default_factory=lambda: [
        "rm", "rmdir", "del", "format", "fdisk", "mount", "umount",
        "chmod", "chown", "sudo", "su", "passwd", "useradd", "userdel",
        "iptables", "netstat", "ss", "tcpdump", "nmap"
    ])
    environment_vars: Dict[str, str] = field(default_factory=dict)
    max_retries: int = 3
    retry_delay_base: float = 1.0  # Base delay for exponential backoff
    retry_delay_max: float = 60.0  # Maximum retry delay
    allowed_runtimes: List[str] = field(default_factory=lambda: [
        "python3", "bash", "sh", "node", "deno", "go", "java"
    ])
    resource_limits: Dict[str, Any] = field(default_factory=lambda: {
        "max_open_files": 1024,
        "max_processes": 32,
        "max_file_size_mb": 100
    })
    build_directory: str = ".clockwork/build"
    parallel_limit: int = 4  # Maximum number of parallel executions




class RetryManager:
    """Manages retry logic with exponential backoff."""
    
    def __init__(self, max_retries: int, base_delay: float, max_delay: float):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
    
    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay for retry attempt using exponential backoff."""
        delay = self.base_delay * (2 ** attempt)
        return min(delay, self.max_delay)
    
    def should_retry(self, attempt: int, exception: Exception) -> bool:
        """Determine if we should retry based on attempt count and exception type."""
        if attempt >= self.max_retries:
            return False
        
        # Retry on specific exceptions
        retryable_exceptions = (
            subprocess.TimeoutExpired,
            OSError,
            ConnectionError,
            PermissionError
        )
        
        return isinstance(exception, retryable_exceptions)


@contextmanager
def resource_monitor(pid: int):
    """Context manager to monitor process resource usage."""
    try:
        process = psutil.Process(pid)
        start_time = time.time()
        start_memory = process.memory_info().rss / 1024 / 1024  # MB
        start_cpu_time = process.cpu_times()
        
        yield
        
    except psutil.NoSuchProcess:
        # Process finished before we could get final stats
        pass
    finally:
        try:
            end_time = time.time()
            if process.is_running():
                end_memory = process.memory_info().rss / 1024 / 1024  # MB
                end_cpu_time = process.cpu_times()
                
                return {
                    "wall_time": end_time - start_time,
                    "memory_peak_mb": end_memory,
                    "memory_start_mb": start_memory,
                    "cpu_time_user": end_cpu_time.user - start_cpu_time.user,
                    "cpu_time_system": end_cpu_time.system - start_cpu_time.system
                }
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        
        return {"wall_time": time.time() - start_time}


class ArtifactExecutor:
    """
    Enhanced executor for running artifacts in sandboxed environments.
    
    Provides functionality to validate and execute generated artifacts safely
    with proper sandboxing, logging, resource management, timeout handling,
    and retry logic. Now supports multiple execution environments via runners.
    """
    
    def __init__(self, sandbox_config: Optional[SandboxConfig] = None, runner: Optional[Runner] = None, 
                 execution_context: Optional[Dict[str, Any]] = None):
        """
        Initialize the enhanced executor.
        
        Args:
            sandbox_config: Configuration for sandbox environment
            runner: Specific runner to use, if None will auto-select
            execution_context: Context for runner selection
        """
        self.sandbox_config = sandbox_config or SandboxConfig()
        self.retry_manager = RetryManager(
            self.sandbox_config.max_retries,
            self.sandbox_config.retry_delay_base,
            self.sandbox_config.retry_delay_max
        )
        self.temp_dir = None
        self.build_dir = None
        
        # Setup runner
        if runner:
            self.runner = runner
        else:
            # Auto-select runner based on context
            execution_context = execution_context or {}
            runner_type = select_runner(execution_context)
            runner_config = execution_context.get("runner_config", {})
            self.runner = RunnerFactory.create_runner(runner_type, runner_config)
        
        # Ensure build directory exists
        self.build_dir = Path(self.sandbox_config.build_directory)
        self.build_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Initialized Enhanced ArtifactExecutor with build dir: {self.build_dir}")
        logger.info(f"Using runner: {self.runner.__class__.__name__}")
    
    def validate_bundle(self, bundle: ArtifactBundle) -> None:
        """
        Validate an artifact bundle before execution - simplified for Docker execution.
        
        Args:
            bundle: The bundle to validate
        """
        logger.debug(f"Validating artifact bundle with {len(bundle.artifacts)} artifacts")
        
        for artifact in bundle.artifacts:
            # Only check for empty content
            if not artifact.content.strip():
                raise ValidationError(f"Artifact {artifact.path} has empty content")
        
        logger.debug("Artifact bundle validation completed successfully")
    
    def execute_bundle(self, bundle: ArtifactBundle) -> List[ExecutionResult]:
        """
        Execute an entire artifact bundle using parallel execution for independent steps.
        
        Args:
            bundle: The bundle to execute
            
        Returns:
            List of execution results for each step
            
        Raises:
            ExecutionError: If bundle execution fails
        """
        try:
            logger.info(f"Starting execution of ArtifactBundle version {bundle.version}")
            logger.info(f"Bundle contains {len(bundle.artifacts)} artifacts and {len(bundle.steps)} steps")
            
            # Validate runner environment first
            if not self.runner.validate_environment():
                raise ExecutionError(f"Runner environment validation failed for {self.runner.__class__.__name__}")
            
            # Basic validation - just check for empty artifacts
            for artifact in bundle.artifacts:
                if not artifact.content.strip():
                    raise ExecutionError(f"Artifact {artifact.path} has empty content")
            
            # Prepare environment variables
            env_vars = {}
            env_vars.update(self.sandbox_config.environment_vars)
            env_vars.update(bundle.vars)
            
            # Use our new parallel execution method
            logger.info("Using parallel execution for artifact bundle")
            results = self.execute_steps(bundle.steps, bundle.artifacts, env_vars)
            
            # Generate execution summary
            successful_steps = sum(1 for r in results if r.is_success())
            total_time = sum(r.execution_time for r in results)
            
            logger.info(f"Bundle execution completed: {successful_steps}/{len(results)} steps successful, total time: {total_time:.2f}s")
            return results
            
        except Exception as e:
            logger.error(f"Bundle execution failed: {e}", exc_info=True)
            raise ExecutionError(f"Failed to execute bundle: {e}")
        finally:
            # Cleanup runner resources
            try:
                self.runner.cleanup()
            except Exception as e:
                logger.warning(f"Failed to cleanup runner: {e}")
    
    def _prepare_all_artifacts(self, artifacts: List[Artifact]) -> Dict[str, Path]:
        """Prepare and validate all artifacts for execution."""
        artifact_paths = {}
        
        for artifact in artifacts:
            logger.debug(f"Preparing artifact: {artifact.path}")
            
            # Validate artifact path
            is_valid, violations = self.validator.validate_artifact_path(artifact.path)
            if not is_valid:
                raise ExecutionError(f"Artifact path validation failed for {artifact.path}: {violations}")
            
            # Validate artifact content
            warnings, security_violations = self.validator.validate_artifact_content(artifact)
            if security_violations:
                raise ExecutionError(f"Security violations in artifact {artifact.path}: {security_violations}")
            
            if warnings:
                logger.warning(f"Validation warnings for {artifact.path}: {warnings}")
            
            # Prepare artifact file
            artifact_path = self._prepare_artifact_file(artifact)
            artifact_paths[artifact.path] = artifact_path
            
            logger.debug(f"Prepared artifact {artifact.path} at {artifact_path}")
        
        return artifact_paths
    
    def _prepare_artifact_file(self, artifact: Artifact) -> Path:
        """Prepare artifact file with proper permissions and validation."""
        # Create artifact file in temp directory
        artifact_filename = Path(artifact.path).name
        artifact_path = self.temp_dir / artifact_filename
        
        # Write artifact content
        with open(artifact_path, "w", encoding="utf-8") as f:
            f.write(artifact.content)
        
        # Set file permissions
        mode_int = int(artifact.mode, 8) if artifact.mode.startswith('0') else int(artifact.mode[-3:], 8)
        os.chmod(artifact_path, mode_int)
        
        # Validate permissions were set correctly
        is_valid, violations = self.validator.validate_file_permissions(artifact_path, artifact.mode)
        if not is_valid:
            logger.warning(f"Permission validation warnings for {artifact_path}: {violations}")
        
        return artifact_path
    
    def _execute_step(self, step: ExecutionStep, artifact_paths: Dict[str, Path], env: Dict[str, str]) -> ExecutionResult:
        """Execute a single step with retry logic and resource monitoring."""
        result = ExecutionResult(
            artifact_name=step.purpose,
            status=ExecutionStatus.PENDING
        )
        
        # Extract command from step
        if "cmd" not in step.run:
            result.status = ExecutionStatus.FAILED
            result.error_message = "Step run configuration missing 'cmd' key"
            return result
        
        base_command = step.run["cmd"]
        if not isinstance(base_command, list):
            result.status = ExecutionStatus.FAILED
            result.error_message = "Step command must be a list"
            return result
        
        # Skip runtime validation - Docker provides isolation
        
        # Replace artifact paths in command
        command = self._resolve_command_paths(base_command, artifact_paths)
        result.command = command
        
        # Execute with retry logic
        for attempt in range(self.sandbox_config.max_retries + 1):
            if attempt > 0:
                result.status = ExecutionStatus.RETRYING
                result.retry_count = attempt
                delay = self.retry_manager.calculate_delay(attempt - 1)
                logger.info(f"Retrying step {step.purpose} (attempt {attempt+1}) after {delay:.1f}s delay")
                time.sleep(delay)
            
            try:
                result.status = ExecutionStatus.RUNNING
                result.start_time = time.time()
                
                # Execute command with monitoring
                process_result = self._run_command_monitored(command, env, result)
                
                result.end_time = time.time()
                result.execution_time = result.end_time - result.start_time
                result.exit_code = process_result.returncode
                result.stdout = process_result.stdout
                result.stderr = process_result.stderr
                
                if process_result.returncode == 0:
                    result.status = ExecutionStatus.SUCCESS
                    logger.debug(f"Step {step.purpose} completed successfully")
                    break
                else:
                    result.status = ExecutionStatus.FAILED
                    result.error_message = f"Process exited with code {process_result.returncode}"
                    
                    # Check if we should retry
                    if attempt < self.sandbox_config.max_retries:
                        logger.warning(f"Step {step.purpose} failed with exit code {process_result.returncode}, will retry")
                        continue
                    else:
                        logger.error(f"Step {step.purpose} failed after {attempt+1} attempts")
                        break
                        
            except subprocess.TimeoutExpired as e:
                result.status = ExecutionStatus.TIMEOUT
                result.timeout_occurred = True
                result.error_message = f"Execution timed out after {self.sandbox_config.max_execution_time}s"
                result.end_time = time.time()
                result.execution_time = result.end_time - (result.start_time or 0)
                
                if not self.retry_manager.should_retry(attempt, e):
                    logger.error(f"Step {step.purpose} timed out and will not be retried")
                    break
                else:
                    logger.warning(f"Step {step.purpose} timed out, will retry")
                    continue
                    
            except Exception as e:
                result.status = ExecutionStatus.FAILED
                result.error_message = str(e)
                result.end_time = time.time()
                result.execution_time = result.end_time - (result.start_time or 0)
                
                if not self.retry_manager.should_retry(attempt, e):
                    logger.error(f"Step {step.purpose} failed with error: {e}")
                    break
                else:
                    logger.warning(f"Step {step.purpose} failed with error: {e}, will retry")
                    continue
        
        return result
    
    
    def _resolve_command_paths(self, command: List[str], artifact_paths: Dict[str, Path]) -> List[str]:
        """Resolve artifact paths in command arguments."""
        resolved_command = []
        
        for arg in command:
            # Check if argument is an artifact path
            if arg in artifact_paths:
                resolved_command.append(str(artifact_paths[arg]))
            else:
                resolved_command.append(arg)
        
        # Special handling for UV Python execution
        if len(resolved_command) >= 3 and resolved_command[0] == "uv" and resolved_command[1] == "run" and resolved_command[2] == "python":
            # Replace with full UV command
            resolved_command = ["uv", "run", "python"] + resolved_command[3:]
        
        return resolved_command
    
    def _run_command_monitored(self, command: List[str], env: Dict[str, str], result: ExecutionResult) -> subprocess.CompletedProcess:
        """Run command in Docker container for isolation."""
        logger.debug(f"Executing command in Docker: {' '.join(command)}")
        
        # Choose appropriate Docker image based on command
        docker_image = self._select_docker_image(command)
        
        # Wrap command in Docker execution
        docker_command = self._wrap_command_in_docker(command, env, docker_image)
        
        # Set working directory and environment for result tracking
        result.working_directory = str(self.temp_dir)
        result.environment_vars = {k: v for k, v in env.items() if not k.startswith("_")}
        
        # Execute Docker command
        process = subprocess.Popen(
            docker_command,
            cwd=str(self.temp_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        try:
            stdout, stderr = process.communicate(timeout=self.sandbox_config.max_execution_time)
            result.resource_usage = {}  # Docker handles resource monitoring
            
            return subprocess.CompletedProcess(
                args=command,  # Return original command for logging
                returncode=process.returncode,
                stdout=stdout,
                stderr=stderr
            )
            
        except subprocess.TimeoutExpired:
            # Kill Docker container
            try:
                process.terminate()
                time.sleep(2)
                if process.poll() is None:
                    process.kill()
            except:
                pass
            raise
    
    def _select_docker_image(self, command: List[str]) -> str:
        """Select appropriate Docker image based on command."""
        if not command:
            return "alpine:latest"
        
        runtime = command[0].lower()
        
        # Map runtime to appropriate Docker images
        image_map = {
            "python": "python:3.11-alpine",
            "python3": "python:3.11-alpine", 
            "bash": "alpine:latest",
            "sh": "alpine:latest",
            "node": "node:18-alpine",
            "npm": "node:18-alpine",
            "go": "golang:1.21-alpine",
            "java": "openjdk:17-alpine",
            "uv": "python:3.11-alpine"  # UV uses Python
        }
        
        return image_map.get(runtime, "alpine:latest")
    
    def _wrap_command_in_docker(self, command: List[str], env: Dict[str, str], image: str) -> List[str]:
        """Wrap command in Docker execution."""
        # Build Docker command
        docker_cmd = [
            "docker", "run", "--rm",
            "--network", "none",  # No network access for security
            "--user", "1000:1000",  # Non-root user
            "--workdir", "/workspace",
            "-v", f"{self.temp_dir}:/workspace"
        ]
        
        # Add environment variables
        for k, v in env.items():
            if not k.startswith("_"):
                docker_cmd.extend(["-e", f"{k}={v}"])
        
        # Add resource limits
        memory_limit = self.sandbox_config.resource_limits.get("max_memory_mb", 512)
        docker_cmd.extend(["--memory", f"{memory_limit}m"])
        docker_cmd.extend(["--cpus", "1.0"])
        
        # Add image and command
        docker_cmd.append(image)
        
        # Handle special cases for different runtimes
        if command[0] == "uv":
            # Install uv in the container first, then run command
            docker_cmd.extend([
                "sh", "-c", 
                f"pip install uv && {' '.join(command)}"
            ])
        elif command[0] in ["python", "python3"] and image.startswith("python"):
            docker_cmd.extend(command)
        elif command[0] in ["bash", "sh"]:
            docker_cmd.extend(command)
        else:
            # For other commands, try to run them directly
            docker_cmd.extend(command)
        
        logger.debug(f"Docker command: {' '.join(docker_cmd)}")
        return docker_cmd
    
    def save_results(self, results: List[ExecutionResult], output_file: Path) -> None:
        """
        Save execution results to a file with enhanced detail.
        
        Args:
            results: List of execution results
            output_file: Path to save results
        """
        # Calculate summary statistics
        total_steps = len(results)
        successful_steps = sum(1 for r in results if r.is_success())
        failed_steps = sum(1 for r in results if r.status == ExecutionStatus.FAILED)
        timeout_steps = sum(1 for r in results if r.status == ExecutionStatus.TIMEOUT)
        total_time = sum(r.execution_time for r in results)
        total_retries = sum(r.retry_count for r in results)
        
        output_data = {
            "execution_summary": {
                "total_steps": total_steps,
                "successful": successful_steps,
                "failed": failed_steps,
                "timeouts": timeout_steps,
                "total_time": total_time,
                "total_retries": total_retries,
                "success_rate": (successful_steps / total_steps * 100) if total_steps > 0 else 0,
                "execution_timestamp": time.time(),
                "executor_config": {
                    "max_retries": self.sandbox_config.max_retries,
                    "max_execution_time": self.sandbox_config.max_execution_time,
                    "max_memory_mb": self.sandbox_config.max_memory_mb,
                    "allowed_runtimes": self.sandbox_config.allowed_runtimes
                }
            },
            "step_results": [result.to_dict() for result in results]
        }
        
        with open(output_file, "w") as f:
            json.dump(output_data, f, indent=2)
        
        logger.info(f"Saved enhanced execution results to {output_file}")
        logger.info(f"Summary: {successful_steps}/{total_steps} successful, {total_retries} retries, {total_time:.2f}s total")
    
    def cleanup(self) -> None:
        """Clean up temporary resources."""
        if self.temp_dir and self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
            logger.debug("Cleaned up temporary directory")
    
    def _analyze_step_dependencies(self, steps: List[ExecutionStep], artifacts: List[Artifact]) -> Dict[str, List[str]]:
        """
        Analyze dependencies between execution steps.
        
        Args:
            steps: List of execution steps
            artifacts: List of artifacts
            
        Returns:
            Dictionary mapping step names to their dependencies
        """
        dependencies = {}
        artifact_map = {artifact.path: artifact for artifact in artifacts}
        
        for step in steps:
            step_deps = []
            
            # Check if step command references outputs from other steps
            if "cmd" in step.run and isinstance(step.run["cmd"], list):
                for arg in step.run["cmd"]:
                    if isinstance(arg, str):
                        # Look for file references that might be outputs from other steps
                        for other_step in steps:
                            if other_step != step and other_step.purpose in arg:
                                step_deps.append(other_step.purpose)
                        
                        # Check for artifact dependencies
                        for artifact_path in artifact_map:
                            if artifact_path in arg:
                                # Find which step creates this artifact
                                for other_step in steps:
                                    if other_step != step and other_step.purpose in artifact_path:
                                        step_deps.append(other_step.purpose)
            
            # Check explicit dependencies if defined in step metadata
            if hasattr(step, 'depends_on') and step.depends_on:
                step_deps.extend(step.depends_on)
            
            dependencies[step.purpose] = list(set(step_deps))  # Remove duplicates
        
        return dependencies
    
    def _group_independent_steps(self, steps: List[ExecutionStep], dependencies: Dict[str, List[str]]) -> List[List[ExecutionStep]]:
        """
        Group steps into batches of independent steps that can run in parallel.
        
        Args:
            steps: List of execution steps
            dependencies: Dictionary of step dependencies
            
        Returns:
            List of step batches, where each batch can be executed in parallel
        """
        step_map = {step.purpose: step for step in steps}
        remaining_steps = set(step.purpose for step in steps)
        completed_steps = set()
        batches = []
        
        while remaining_steps:
            # Find steps that have no unmet dependencies
            ready_steps = []
            for step_name in remaining_steps:
                deps = dependencies.get(step_name, [])
                if all(dep in completed_steps for dep in deps):
                    ready_steps.append(step_map[step_name])
            
            if not ready_steps:
                # Circular dependency or unresolvable dependency
                logger.warning(f"Circular or unresolvable dependencies detected. Remaining steps: {remaining_steps}")
                # Add remaining steps as a single batch to avoid infinite loop
                ready_steps = [step_map[name] for name in remaining_steps]
            
            batches.append(ready_steps)
            
            # Mark these steps as completed
            for step in ready_steps:
                completed_steps.add(step.purpose)
                remaining_steps.remove(step.purpose)
        
        return batches
    
    def execute_steps(self, steps: List[ExecutionStep], artifacts: List[Artifact], 
                     env_vars: Optional[Dict[str, str]] = None) -> List[ExecutionResult]:
        """
        Execute steps with parallel processing for independent steps.
        
        Args:
            steps: List of execution steps to execute
            artifacts: List of artifacts needed for execution
            env_vars: Environment variables for execution
            
        Returns:
            List of execution results
        """
        if not steps:
            return []
        
        env_vars = env_vars or {}
        results = []
        
        # Load parallel limit from configuration
        parallel_limit = load_parallel_limit_from_config()
        self.sandbox_config.parallel_limit = parallel_limit
        
        logger.info(f"Executing {len(steps)} steps with parallel limit: {parallel_limit}")
        
        # Setup temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            self.temp_dir = Path(temp_dir)
            
            try:
                # Prepare all artifacts
                artifact_paths = self._prepare_all_artifacts(artifacts)
                
                # Analyze dependencies
                dependencies = self._analyze_step_dependencies(steps, artifacts)
                logger.debug(f"Step dependencies: {dependencies}")
                
                # Group steps into independent batches
                step_batches = self._group_independent_steps(steps, dependencies)
                logger.info(f"Grouped steps into {len(step_batches)} batches for parallel execution")
                
                # Execute each batch in parallel
                for batch_idx, batch in enumerate(step_batches):
                    logger.info(f"Executing batch {batch_idx + 1}/{len(step_batches)} with {len(batch)} steps")
                    
                    if len(batch) == 1:
                        # Single step - execute directly
                        result = self._execute_step(batch[0], artifact_paths, env_vars)
                        results.append(result)
                    else:
                        # Multiple steps - execute in parallel
                        batch_results = self._execute_steps_parallel(batch, artifact_paths, env_vars)
                        results.extend(batch_results)
                    
                    # Check if any critical steps failed
                    failed_steps = [r for r in results[-len(batch):] if not r.is_success()]
                    if failed_steps:
                        logger.warning(f"Batch {batch_idx + 1} had {len(failed_steps)} failed steps")
                        # Continue with remaining batches unless it's a critical failure
                
                logger.info(f"Completed execution of all steps. Success rate: {sum(1 for r in results if r.is_success())}/{len(results)}")
                
            finally:
                # Reset temp_dir
                self.temp_dir = None
        
        return results
    
    def _execute_steps_parallel(self, steps: List[ExecutionStep], artifact_paths: Dict[str, Path], 
                               env_vars: Dict[str, str]) -> List[ExecutionResult]:
        """
        Execute multiple steps in parallel using joblib.
        
        Args:
            steps: List of execution steps to run in parallel
            artifact_paths: Map of artifact paths
            env_vars: Environment variables
            
        Returns:
            List of execution results
        """
        parallel_limit = min(self.sandbox_config.parallel_limit, len(steps))
        
        logger.debug(f"Executing {len(steps)} steps in parallel (limit: {parallel_limit})")
        
        # Use joblib.Parallel with threading backend for I/O-bound operations
        try:
            results = joblib.Parallel(
                n_jobs=parallel_limit,
                backend='threading',
                verbose=0
            )(
                joblib.delayed(self._execute_step)(step, artifact_paths, env_vars)
                for step in steps
            )
            
            return results
            
        except Exception as e:
            logger.error(f"Parallel execution failed: {e}")
            # Fallback to sequential execution
            logger.info("Falling back to sequential execution")
            results = []
            for step in steps:
                try:
                    result = self._execute_step(step, artifact_paths, env_vars)
                    results.append(result)
                except Exception as step_error:
                    logger.error(f"Step {step.purpose} failed: {step_error}")
                    error_result = ExecutionResult(
                        artifact_name=step.purpose,
                        status=ExecutionStatus.FAILED
                    )
                    error_result.error_message = str(step_error)
                    results.append(error_result)
            
            return results


def create_secure_executor(runner_type: Optional[str] = None, execution_context: Optional[Dict[str, Any]] = None) -> ArtifactExecutor:
    """Create a secure executor with restrictive sandbox configuration."""
    parallel_limit = load_parallel_limit_from_config()
    config = SandboxConfig(
        max_memory_mb=256,
        max_cpu_percent=25.0,
        max_execution_time=60,
        allow_network=False,
        allow_file_write=False,
        max_retries=2,
        retry_delay_base=2.0,
        blocked_commands=[
            "rm", "rmdir", "del", "format", "fdisk", "mount", "umount",
            "chmod", "chown", "sudo", "su", "passwd", "useradd", "userdel",
            "iptables", "netstat", "ss", "tcpdump", "nmap", "wget", "curl"
        ],
        allowed_runtimes=["python3", "bash", "sh", "uv"],
        resource_limits={
            "max_open_files": 512,
            "max_processes": 16,
            "max_file_size_mb": 50
        },
        parallel_limit=parallel_limit
    )
    
    # Setup execution context for secure environments
    context = execution_context or {}
    context.setdefault("requires_isolation", True)
    if runner_type:
        context["runner_type"] = runner_type
    
    return ArtifactExecutor(config, execution_context=context)


def create_development_executor(runner_type: Optional[str] = None, execution_context: Optional[Dict[str, Any]] = None) -> ArtifactExecutor:
    """Create a development executor with more permissive settings."""
    parallel_limit = load_parallel_limit_from_config()
    config = SandboxConfig(
        max_memory_mb=1024,
        max_cpu_percent=75.0,
        max_execution_time=300,
        allow_network=True,
        allow_file_write=True,
        max_retries=3,
        retry_delay_base=1.0,
        allowed_runtimes=["python3", "bash", "sh", "node", "deno", "go", "java", "uv"],
        resource_limits={
            "max_open_files": 2048,
            "max_processes": 64,
            "max_file_size_mb": 200
        },
        parallel_limit=parallel_limit
    )
    
    # Setup execution context
    context = execution_context or {}
    if runner_type:
        context["runner_type"] = runner_type
    
    return ArtifactExecutor(config, execution_context=context)


def create_executor_for_environment(environment: str, config_overrides: Optional[Dict[str, Any]] = None) -> ArtifactExecutor:
    """Create an executor optimized for a specific environment.
    
    Args:
        environment: Target environment ('local', 'docker', 'kubernetes', 'ssh')
        config_overrides: Optional configuration overrides
        
    Returns:
        Configured executor for the environment
    """
    config_overrides = config_overrides or {}
    
    if environment == "local":
        return create_development_executor("local", config_overrides)
    elif environment == "docker":
        context = {"runner_type": "docker", "requires_isolation": True}
        context.update(config_overrides)
        return create_secure_executor("docker", context)
    elif environment == "kubernetes":
        context = {"runner_type": "kubernetes", "requires_isolation": True}
        context.update(config_overrides)
        return create_secure_executor("kubernetes", context)
    elif environment == "ssh":
        context = {"runner_type": "ssh"}
        context.update(config_overrides)
        return create_development_executor("ssh", context)
    else:
        raise ValueError(f"Unsupported environment: {environment}")


def get_available_executors() -> Dict[str, bool]:
    """Get available executor environments on this system.
    
    Returns:
        Dictionary mapping environment names to availability
    """
    available_runners = RunnerFactory.get_available_runners()
    return {
        "local": "local" in available_runners,
        "docker": "docker" in available_runners,
        "podman": "podman" in available_runners,
        "kubernetes": "kubernetes" in available_runners,
        "ssh": "ssh" in available_runners
    }