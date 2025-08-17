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

from ..models import ArtifactBundle, Artifact, ExecutionStep
from .runner import Runner, RunnerFactory, RunnerType, select_runner
from ..errors import ValidationError

logger = logging.getLogger(__name__)


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


class ArtifactPathValidator:
    """Enhanced validator for artifact paths and security."""
    
    def __init__(self, build_directory: str = ".clockwork/build"):
        self.build_directory = Path(build_directory).resolve()
        self.dangerous_patterns = {
            "python": [
                "__import__", "exec(", "eval(", "compile(",
                "os.system", "subprocess.call", "subprocess.run",
                "open(", "file(", "input(", "raw_input(",
                "import os", "import sys", "import subprocess"
            ],
            "bash": [
                "rm -rf", ":(){ :|:& };:", "dd if=", "mkfs",
                "> /dev/", "curl", "wget", "nc ", "netcat",
                "chmod 777", "sudo", "su -", "/etc/passwd"
            ],
            "javascript": [
                "require(", "import(", "eval(", "Function(",
                "document.", "window.", "global.", "process.exit",
                "fs.unlink", "child_process"
            ],
            "sh": [
                "rm -rf", "dd if=", "mkfs", "> /dev/",
                "chmod 777", "chown", "sudo", "su"
            ]
        }
        
    def validate_artifact_path(self, artifact_path: str) -> Tuple[bool, List[str]]:
        """Validate artifact path for security compliance.
        
        Args:
            artifact_path: Path to validate
            
        Returns:
            Tuple of (is_valid, list_of_violations)
        """
        violations = []
        
        try:
            # Resolve the path and check if it's within build directory
            resolved_path = Path(artifact_path).resolve()
            
            # Check for directory traversal attacks
            if ".." in str(artifact_path) or "../" in str(artifact_path):
                violations.append("Directory traversal attack detected: contains '..'")
            
            # Ensure path is within build directory
            try:
                resolved_path.relative_to(self.build_directory)
            except ValueError:
                violations.append(f"Path outside allowed directory: {artifact_path} not in {self.build_directory}")
            
            # Check for dangerous path components
            dangerous_components = ["/etc/", "/usr/", "/bin/", "/sbin/", "/root/", "/home/", "/var/", "/tmp/"]
            for component in dangerous_components:
                if component in str(resolved_path):
                    violations.append(f"Dangerous path component detected: {component}")
            
            # Check for special files
            if resolved_path.exists():
                if resolved_path.is_symlink():
                    violations.append("Symbolic links not allowed for security")
                # Check if it's a device file (requires stat module)
                file_stat = resolved_path.stat()
                if stat.S_ISBLK(file_stat.st_mode) or stat.S_ISCHR(file_stat.st_mode):
                    violations.append("Device files not allowed")
                    
        except Exception as e:
            violations.append(f"Path validation error: {str(e)}")
            
        return len(violations) == 0, violations
    
    def validate_file_permissions(self, file_path: Path, expected_mode: str) -> Tuple[bool, List[str]]:
        """Validate file permissions match expected mode.
        
        Args:
            file_path: Path to file
            expected_mode: Expected mode in format '0755'
            
        Returns:
            Tuple of (is_valid, list_of_violations)
        """
        violations = []
        
        if not file_path.exists():
            violations.append(f"File does not exist: {file_path}")
            return False, violations
            
        try:
            # Get current file mode
            current_mode = oct(file_path.stat().st_mode)[-3:]
            expected_mode_digits = expected_mode[-3:] if expected_mode.startswith('0') else expected_mode
            
            if current_mode != expected_mode_digits:
                violations.append(f"File mode mismatch: expected {expected_mode_digits}, got {current_mode}")
                
            # Check for overly permissive permissions
            mode_int = int(expected_mode_digits, 8)
            if mode_int & 0o002:  # World writable
                violations.append("World-writable permissions detected - security risk")
            if mode_int & 0o001 and mode_int & 0o004:  # World readable and executable
                violations.append("World-executable permissions on readable file - potential security risk")
                
        except Exception as e:
            violations.append(f"Permission validation error: {str(e)}")
            
        return len(violations) == 0, violations
    
    def validate_artifact_content(self, artifact: Artifact) -> Tuple[List[str], List[str]]:
        """
        Enhanced validation of artifact content for security issues.
        
        Args:
            artifact: The artifact to validate
            
        Returns:
            Tuple of (warnings, security_violations)
        """
        warnings = []
        violations = []
        
        # Check for dangerous patterns
        language = artifact.lang.lower() if hasattr(artifact, 'lang') else 'unknown'
        dangerous_patterns = self.dangerous_patterns.get(language, [])
        
        for pattern in dangerous_patterns:
            if pattern in artifact.content:
                violations.append(f"Dangerous pattern detected: {pattern}")
        
        # Check content length
        if len(artifact.content) > 1000000:  # 1MB limit
            warnings.append("Artifact content is unusually large (>1MB)")
        elif len(artifact.content) > 100000:  # 100KB warning
            warnings.append("Artifact content is large (>100KB)")
        
        # Check for empty content
        if not artifact.content.strip():
            violations.append("Artifact content is empty")
        
        # Language-specific validation
        if language == "python":
            warnings.extend(self._validate_python_content(artifact.content))
        elif language in ["bash", "sh"]:
            warnings.extend(self._validate_bash_content(artifact.content))
        elif language in ["javascript", "js"]:
            warnings.extend(self._validate_js_content(artifact.content))
        
        # Check for potential injection patterns
        injection_patterns = [
            r'\$\([^)]*\)',  # Command substitution
            r'`[^`]*`',      # Backticks
            r';\s*rm\s',     # Dangerous commands
            r'\|\s*sh\s',    # Pipe to shell
            r'eval\s*\(',    # Eval functions
        ]
        
        for pattern in injection_patterns:
            if re.search(pattern, artifact.content):
                violations.append(f"Potential injection pattern: {pattern}")
        
        return warnings, violations
    
    def _validate_python_content(self, content: str) -> List[str]:
        """Validate Python-specific security concerns."""
        warnings = []
        
        # Check for dangerous imports
        dangerous_imports = [
            "os", "sys", "subprocess", "socket", "urllib", "requests",
            "shutil", "tempfile", "pickle", "marshal", "importlib"
        ]
        for imp in dangerous_imports:
            if re.search(rf'\bimport\s+{imp}\b', content) or re.search(rf'\bfrom\s+{imp}\b', content):
                warnings.append(f"Potentially dangerous import: {imp}")
        
        # Check for dangerous functions
        dangerous_funcs = ["exec", "eval", "compile", "__import__", "getattr", "setattr"]
        for func in dangerous_funcs:
            if re.search(rf'\b{func}\s*\(', content):
                warnings.append(f"Dangerous function call: {func}()")
        
        return warnings
    
    def _validate_bash_content(self, content: str) -> List[str]:
        """Validate Bash-specific security concerns."""
        warnings = []
        
        # Check for dangerous commands
        dangerous_commands = [
            r"rm\s+-rf", r"dd\s+if=", "mkfs", "format", "fdisk",
            r"chmod\s+777", "chown", "sudo", r"su\s+", "passwd"
        ]
        for cmd in dangerous_commands:
            if re.search(cmd, content):
                warnings.append(f"Dangerous command detected: {cmd}")
        
        # Check for network operations
        network_commands = ["curl", "wget", "nc", "netcat", "telnet", "ssh"]
        for cmd in network_commands:
            if re.search(rf'\b{cmd}\b', content):
                warnings.append(f"Network command detected: {cmd}")
        
        return warnings
    
    def _validate_js_content(self, content: str) -> List[str]:
        """Validate JavaScript-specific security concerns."""
        warnings = []
        
        # Check for dangerous functions
        dangerous_patterns = [
            r"eval\s*\(", r"Function\s*\(", r"setTimeout\s*\(", r"setInterval\s*\(",
            r"document\.", r"window\.", r"global\.", r"process\."
        ]
        for pattern in dangerous_patterns:
            if re.search(pattern, content):
                warnings.append(f"Potentially dangerous JS pattern: {pattern}")
        
        return warnings


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
        self.validator = ArtifactPathValidator(self.sandbox_config.build_directory)
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
        Validate an artifact bundle before execution.
        
        Args:
            bundle: The bundle to validate
            
        Raises:
            ValidationError: If validation fails
        """
        logger.debug(f"Validating artifact bundle with {len(bundle.artifacts)} artifacts")
        
        for artifact in bundle.artifacts:
            # Validate artifact content
            violations, warnings = self.validator.validate_artifact_content(artifact)
            
            if violations:
                raise ValidationError(f"Artifact {artifact.path} validation failed: {'; '.join(violations)}")
            
            if warnings:
                logger.warning(f"Artifact {artifact.path} validation warnings: {'; '.join(warnings)}")
        
        logger.debug("Artifact bundle validation completed successfully")
    
    def execute_bundle(self, bundle: ArtifactBundle) -> List[ExecutionResult]:
        """
        Execute an entire artifact bundle using the configured runner.
        
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
            logger.info(f"Using runner: {self.runner.__class__.__name__}")
            
            # Validate runner environment first
            if not self.runner.validate_environment():
                raise ExecutionError(f"Runner environment validation failed for {self.runner.__class__.__name__}")
            
            # Validate artifacts first
            for artifact in bundle.artifacts:
                is_valid, violations = self.validator.validate_artifact_path(artifact.path)
                if not is_valid:
                    raise ExecutionError(f"Artifact path validation failed for {artifact.path}: {violations}")
                
                warnings, security_violations = self.validator.validate_artifact_content(artifact)
                if security_violations:
                    raise ExecutionError(f"Security violations in artifact {artifact.path}: {security_violations}")
                
                if warnings:
                    logger.warning(f"Validation warnings for {artifact.path}: {warnings}")
            
            # Use the runner to execute the bundle
            results = self.runner.execute_bundle(bundle)
            
            # Convert runner results to our ExecutionResult format if needed
            converted_results = []
            for result in results:
                if hasattr(result, 'to_dict'):
                    # It's already our ExecutionResult format
                    converted_results.append(result)
                else:
                    # Convert from runner's result format
                    exec_result = ExecutionResult(
                        artifact_name=result.artifact_name,
                        status=ExecutionStatus(result.status) if isinstance(result.status, str) else result.status
                    )
                    # Copy other attributes
                    for attr in ['exit_code', 'stdout', 'stderr', 'execution_time', 'start_time', 
                                'end_time', 'error_message', 'metadata', 'retry_count', 'timeout_occurred',
                                'resource_usage', 'command', 'working_directory', 'environment_vars']:
                        if hasattr(result, attr):
                            setattr(exec_result, attr, getattr(result, attr))
                    converted_results.append(exec_result)
            
            # Generate execution summary
            successful_steps = sum(1 for r in converted_results if r.is_success())
            total_time = sum(r.execution_time for r in converted_results)
            
            logger.info(f"Bundle execution completed: {successful_steps}/{len(converted_results)} steps successful, total time: {total_time:.2f}s")
            return converted_results
            
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
        
        # Validate runtime
        runtime = base_command[0] if base_command else None
        if not self._validate_runtime(runtime):
            result.status = ExecutionStatus.FAILED
            result.error_message = f"Runtime '{runtime}' not allowed"
            return result
        
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
    
    def _validate_runtime(self, runtime: str) -> bool:
        """Validate that the runtime is allowed."""
        if not runtime:
            return False
        
        # Handle 'uv run python' case
        if runtime == "uv":
            return True
        
        return runtime in self.sandbox_config.allowed_runtimes
    
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
        """Run command with resource monitoring and security controls."""
        logger.debug(f"Executing command: {' '.join(command)}")
        
        # Set resource limits (only on Linux, as macOS has different behavior)
        def preexec_fn():
            try:
                # Set file descriptor limit (usually works on most systems)
                max_files = self.sandbox_config.resource_limits.get("max_open_files", 1024)
                resource.setrlimit(resource.RLIMIT_NOFILE, (max_files, max_files))
                
                # Set process limit (may not work on all systems)
                try:
                    max_processes = self.sandbox_config.resource_limits.get("max_processes", 32)
                    resource.setrlimit(resource.RLIMIT_NPROC, (max_processes, max_processes))
                except (OSError, ValueError):
                    pass  # Ignore if not supported
                
                # Memory limit (may not work on macOS)
                try:
                    memory_limit = self.sandbox_config.max_memory_mb * 1024 * 1024
                    resource.setrlimit(resource.RLIMIT_AS, (memory_limit, memory_limit))
                except (OSError, ValueError):
                    pass  # Ignore if not supported
                    
            except Exception:
                pass  # Continue execution even if resource limits fail
        
        # Set working directory and environment
        result.working_directory = str(self.temp_dir)
        result.environment_vars = {k: v for k, v in env.items() if not k.startswith("_")}
        
        # Execute with timeout and monitoring
        process = subprocess.Popen(
            command,
            cwd=self.temp_dir,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            preexec_fn=preexec_fn if platform.system() != "Windows" else None
        )
        
        try:
            # Monitor resource usage
            with resource_monitor(process.pid) as monitor:
                stdout, stderr = process.communicate(timeout=self.sandbox_config.max_execution_time)
                result.resource_usage = monitor or {}
            
            return subprocess.CompletedProcess(
                args=command,
                returncode=process.returncode,
                stdout=stdout,
                stderr=stderr
            )
            
        except subprocess.TimeoutExpired:
            # Kill process tree on timeout
            try:
                parent = psutil.Process(process.pid)
                children = parent.children(recursive=True)
                for child in children:
                    child.terminate()
                parent.terminate()
                
                # Wait for graceful termination
                time.sleep(1)
                
                # Force kill if still running
                for child in children:
                    if child.is_running():
                        child.kill()
                if parent.is_running():
                    parent.kill()
                    
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
            
            raise
    
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


def create_secure_executor(runner_type: Optional[str] = None, execution_context: Optional[Dict[str, Any]] = None) -> ArtifactExecutor:
    """Create a secure executor with restrictive sandbox configuration."""
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
        }
    )
    
    # Setup execution context for secure environments
    context = execution_context or {}
    context.setdefault("requires_isolation", True)
    if runner_type:
        context["runner_type"] = runner_type
    
    return ArtifactExecutor(config, execution_context=context)


def create_development_executor(runner_type: Optional[str] = None, execution_context: Optional[Dict[str, Any]] = None) -> ArtifactExecutor:
    """Create a development executor with more permissive settings."""
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
        }
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