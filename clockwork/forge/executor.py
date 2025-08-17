"""
Executor module for validating and executing generated artifacts safely.

This module provides functionality for running compiled artifacts in sandboxed
environments with proper logging, validation, and security measures.
"""

import json
import logging
import os
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import shutil

from .compiler import Artifact, ArtifactBundle, LanguageType

logger = logging.getLogger(__name__)


class ExecutionStatus(Enum):
    """Status of artifact execution."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


@dataclass
class ExecutionResult:
    """Result of executing an artifact."""
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
            "metadata": self.metadata
        }


class ExecutionError(Exception):
    """Exception raised during artifact execution."""
    
    def __init__(self, message: str, result: Optional[ExecutionResult] = None):
        super().__init__(message)
        self.result = result


@dataclass
class SandboxConfig:
    """Configuration for sandbox environment."""
    max_memory_mb: int = 512
    max_cpu_percent: float = 50.0
    max_execution_time: int = 300
    allow_network: bool = False
    allow_file_write: bool = True
    allowed_directories: List[str] = field(default_factory=list)
    blocked_commands: List[str] = field(default_factory=lambda: [
        "rm", "rmdir", "del", "format", "fdisk", "mount", "umount"
    ])
    environment_vars: Dict[str, str] = field(default_factory=dict)


class ArtifactValidator:
    """Validates artifacts before execution."""
    
    def __init__(self):
        self.dangerous_patterns = {
            LanguageType.PYTHON: [
                "__import__", "exec(", "eval(", "compile(",
                "os.system", "subprocess.call", "subprocess.run",
                "open(", "file(", "input(", "raw_input("
            ],
            LanguageType.BASH: [
                "rm -rf", ":(){ :|:& };:", "dd if=", "mkfs",
                "> /dev/", "curl", "wget", "nc ", "netcat"
            ],
            LanguageType.JAVASCRIPT: [
                "require(", "import(", "eval(", "Function(",
                "document.", "window.", "global.", "process.exit"
            ]
        }
    
    def validate_artifact(self, artifact: Artifact) -> List[str]:
        """
        Validate an artifact for security issues.
        
        Args:
            artifact: The artifact to validate
            
        Returns:
            List of validation warnings/errors
        """
        warnings = []
        
        # Check for dangerous patterns
        dangerous_patterns = self.dangerous_patterns.get(artifact.language, [])
        for pattern in dangerous_patterns:
            if pattern in artifact.code:
                warnings.append(f"Potentially dangerous pattern detected: {pattern}")
        
        # Check code length
        if len(artifact.code) > 100000:  # 100KB limit
            warnings.append("Artifact code is unusually large")
        
        # Language-specific validation
        if artifact.language == LanguageType.PYTHON:
            warnings.extend(self._validate_python(artifact))
        elif artifact.language == LanguageType.BASH:
            warnings.extend(self._validate_bash(artifact))
        
        return warnings
    
    def _validate_python(self, artifact: Artifact) -> List[str]:
        """Validate Python-specific security concerns."""
        warnings = []
        
        # Check for imports that could be dangerous
        dangerous_imports = ["os", "sys", "subprocess", "socket", "urllib"]
        for imp in dangerous_imports:
            if f"import {imp}" in artifact.code or f"from {imp}" in artifact.code:
                warnings.append(f"Potentially dangerous import: {imp}")
        
        return warnings
    
    def _validate_bash(self, artifact: Artifact) -> List[str]:
        """Validate Bash-specific security concerns."""
        warnings = []
        
        # Check for shell injection patterns
        injection_patterns = ["|", ";", "&", "`", "$()"]
        for pattern in injection_patterns:
            if pattern in artifact.code:
                warnings.append(f"Potential shell injection pattern: {pattern}")
        
        return warnings


class ArtifactExecutor:
    """
    Executor for running artifacts in sandboxed environments.
    
    Provides functionality to validate and execute generated artifacts safely
    with proper sandboxing, logging, and resource management.
    """
    
    def __init__(self, sandbox_config: Optional[SandboxConfig] = None):
        """
        Initialize the executor.
        
        Args:
            sandbox_config: Configuration for sandbox environment
        """
        self.sandbox_config = sandbox_config or SandboxConfig()
        self.validator = ArtifactValidator()
        self.temp_dir = None
        
        logger.info("Initialized ArtifactExecutor")
    
    def execute_bundle(self, bundle: ArtifactBundle) -> List[ExecutionResult]:
        """
        Execute an entire artifact bundle.
        
        Args:
            bundle: The bundle to execute
            
        Returns:
            List of execution results for each artifact
            
        Raises:
            ExecutionError: If bundle execution fails
        """
        try:
            bundle.validate()
            logger.info(f"Executing bundle: {bundle.name}")
            
            results = []
            
            # Create temporary workspace
            with tempfile.TemporaryDirectory() as temp_dir:
                self.temp_dir = Path(temp_dir)
                
                # Prepare artifacts
                artifact_map = {artifact.name: artifact for artifact in bundle.artifacts}
                
                # Execute in specified order
                for artifact_name in bundle.execution_order:
                    if artifact_name not in artifact_map:
                        raise ExecutionError(f"Artifact not found: {artifact_name}")
                    
                    artifact = artifact_map[artifact_name]
                    result = self.execute_artifact(artifact)
                    results.append(result)
                    
                    # Stop execution if an artifact fails
                    if not result.is_success():
                        logger.error(f"Execution stopped due to failure in {artifact_name}")
                        break
            
            logger.info(f"Bundle execution completed. Results: {len(results)}")
            return results
            
        except Exception as e:
            logger.error(f"Bundle execution failed: {e}")
            raise ExecutionError(f"Failed to execute bundle: {e}")
    
    def execute_artifact(self, artifact: Artifact) -> ExecutionResult:
        """
        Execute a single artifact.
        
        Args:
            artifact: The artifact to execute
            
        Returns:
            ExecutionResult containing execution details
        """
        result = ExecutionResult(
            artifact_name=artifact.name,
            status=ExecutionStatus.PENDING
        )
        
        try:
            # Validate artifact
            warnings = self.validator.validate_artifact(artifact)
            if warnings:
                logger.warning(f"Validation warnings for {artifact.name}: {warnings}")
                result.metadata["validation_warnings"] = warnings
            
            # Prepare execution environment
            artifact_path = self._prepare_artifact(artifact)
            
            # Execute artifact
            result.status = ExecutionStatus.RUNNING
            result.start_time = time.time()
            
            process_result = self._run_artifact(artifact, artifact_path)
            
            result.end_time = time.time()
            result.execution_time = result.end_time - result.start_time
            result.exit_code = process_result.returncode
            result.stdout = process_result.stdout
            result.stderr = process_result.stderr
            
            if process_result.returncode == 0:
                result.status = ExecutionStatus.SUCCESS
                logger.info(f"Successfully executed {artifact.name}")
            else:
                result.status = ExecutionStatus.FAILED
                result.error_message = f"Process exited with code {process_result.returncode}"
                logger.error(f"Execution failed for {artifact.name}: {result.error_message}")
            
        except subprocess.TimeoutExpired:
            result.status = ExecutionStatus.TIMEOUT
            result.error_message = "Execution timed out"
            result.end_time = time.time()
            result.execution_time = result.end_time - (result.start_time or 0)
            logger.error(f"Timeout executing {artifact.name}")
            
        except Exception as e:
            result.status = ExecutionStatus.FAILED
            result.error_message = str(e)
            result.end_time = time.time()
            result.execution_time = result.end_time - (result.start_time or 0)
            logger.error(f"Error executing {artifact.name}: {e}")
        
        return result
    
    def _prepare_artifact(self, artifact: Artifact) -> Path:
        """
        Prepare artifact for execution by writing to temporary file.
        
        Args:
            artifact: The artifact to prepare
            
        Returns:
            Path to the prepared artifact file
        """
        if not self.temp_dir:
            raise ExecutionError("Temporary directory not initialized")
        
        # Get file extension
        extensions = {
            LanguageType.PYTHON: ".py",
            LanguageType.BASH: ".sh",
            LanguageType.JAVASCRIPT: ".js",
            LanguageType.TYPESCRIPT: ".ts",
            LanguageType.GO: ".go",
            LanguageType.RUST: ".rs"
        }
        
        ext = extensions.get(artifact.language, ".txt")
        artifact_path = self.temp_dir / f"{artifact.name}{ext}"
        
        # Write artifact code
        with open(artifact_path, "w") as f:
            f.write(artifact.code)
        
        # Make executable if needed
        if artifact.language in [LanguageType.BASH]:
            os.chmod(artifact_path, 0o755)
        
        logger.debug(f"Prepared artifact at {artifact_path}")
        return artifact_path
    
    def _run_artifact(self, artifact: Artifact, artifact_path: Path) -> subprocess.CompletedProcess:
        """
        Run the artifact using appropriate interpreter/runtime.
        
        Args:
            artifact: The artifact to run
            artifact_path: Path to the artifact file
            
        Returns:
            CompletedProcess result
        """
        # Prepare command based on language
        if artifact.language == LanguageType.PYTHON:
            cmd = ["python3", str(artifact_path)]
        elif artifact.language == LanguageType.BASH:
            cmd = ["bash", str(artifact_path)]
        elif artifact.language == LanguageType.JAVASCRIPT:
            cmd = ["node", str(artifact_path)]
        elif artifact.language == LanguageType.TYPESCRIPT:
            cmd = ["ts-node", str(artifact_path)]
        elif artifact.language == LanguageType.GO:
            cmd = ["go", "run", str(artifact_path)]
        elif artifact.language == LanguageType.RUST:
            # Rust requires compilation first
            exe_path = artifact_path.with_suffix("")
            subprocess.run(["rustc", str(artifact_path), "-o", str(exe_path)], check=True)
            cmd = [str(exe_path)]
        else:
            raise ExecutionError(f"Unsupported language: {artifact.language}")
        
        # Prepare environment
        env = os.environ.copy()
        env.update(self.sandbox_config.environment_vars)
        env.update(artifact.environment_vars)
        
        # Set restricted environment for security
        if not self.sandbox_config.allow_network:
            env["NO_PROXY"] = "*"
        
        # Execute with timeout and capture output
        logger.debug(f"Executing: {' '.join(cmd)}")
        
        return subprocess.run(
            cmd,
            cwd=self.temp_dir,
            env=env,
            capture_output=True,
            text=True,
            timeout=self.sandbox_config.max_execution_time
        )
    
    def save_results(self, results: List[ExecutionResult], output_file: Path) -> None:
        """
        Save execution results to a file.
        
        Args:
            results: List of execution results
            output_file: Path to save results
        """
        output_data = {
            "execution_summary": {
                "total_artifacts": len(results),
                "successful": sum(1 for r in results if r.is_success()),
                "failed": sum(1 for r in results if not r.is_success()),
                "total_time": sum(r.execution_time for r in results)
            },
            "results": [result.to_dict() for result in results]
        }
        
        with open(output_file, "w") as f:
            json.dump(output_data, f, indent=2)
        
        logger.info(f"Saved execution results to {output_file}")
    
    def cleanup(self) -> None:
        """Clean up temporary resources."""
        if self.temp_dir and self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
            logger.debug("Cleaned up temporary directory")


def create_secure_executor() -> ArtifactExecutor:
    """Create a secure executor with restrictive sandbox configuration."""
    config = SandboxConfig(
        max_memory_mb=256,
        max_cpu_percent=25.0,
        max_execution_time=60,
        allow_network=False,
        allow_file_write=False,
        blocked_commands=[
            "rm", "rmdir", "del", "format", "fdisk", "mount", "umount",
            "chmod", "chown", "sudo", "su", "passwd", "useradd", "userdel"
        ]
    )
    return ArtifactExecutor(config)