"""
Remediation Engine - Automatic resource remediation via prompt updates and re-application.

This module provides automatic remediation for failed resource deployments by:
1. Collecting diagnostics from failed resources
2. Enhancing AI completion prompts with error context
3. Re-completing resources with improved prompts
4. Re-applying resources individually
5. Validating fixes via assertions
"""

import logging
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..resources.base import Resource
from ..resource_completer import ResourceCompleter
from ..pyinfra_compiler import PyInfraCompiler
from ..settings import get_settings
from .models import ProjectState

logger = logging.getLogger(__name__)


# Utility functions for ProjectState manipulation
def increment_attempts(project_state: ProjectState, resource_name: str) -> int:
    """Increment and return the remediation attempt count for a resource.

    Args:
        project_state: The project state to update
        resource_name: Name of the resource

    Returns:
        Updated attempt count
    """
    current = project_state.remediation_attempts.get(resource_name, 0)
    project_state.remediation_attempts[resource_name] = current + 1
    return current + 1


def get_attempts(project_state: ProjectState, resource_name: str) -> int:
    """Get the current remediation attempt count for a resource.

    Args:
        project_state: The project state
        resource_name: Name of the resource

    Returns:
        Current attempt count (0 if no attempts yet)
    """
    return project_state.remediation_attempts.get(resource_name, 0)


def mark_failed(project_state: ProjectState, resource_name: str):
    """Mark a resource as failed in the project state.

    Args:
        project_state: The project state to update
        resource_name: Name of the resource
    """
    project_state.health_status[resource_name] = False


def mark_succeeded(project_state: ProjectState, resource_name: str):
    """Mark a resource as succeeded in the project state.

    Args:
        project_state: The project state to update
        resource_name: Name of the resource
    """
    project_state.health_status[resource_name] = True


class RemediationEngine:
    """Automatic remediation engine for failed resource deployments.

    This engine collects diagnostics from failed resources, enhances AI completion
    prompts with error context, and attempts to re-apply resources with corrected
    configurations.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None
    ):
        """Initialize the remediation engine.

        Args:
            api_key: API key for AI service (overrides settings/.env)
            model: Model to use for resource completion (overrides settings/.env)
            base_url: Base URL for API endpoint (overrides settings/.env)
        """
        settings = get_settings()

        self.resource_completer = ResourceCompleter(
            api_key=api_key or settings.api_key,
            model=model or settings.model,
            base_url=base_url or settings.base_url
        )

        self.pyinfra_compiler = PyInfraCompiler(
            output_dir=settings.pyinfra_output_dir
        )

        logger.info("RemediationEngine initialized")

    def collect_diagnostics(self, resource: Resource, project_state: ProjectState) -> Dict[str, Any]:
        """Collect diagnostic information from a failed resource.

        Args:
            resource: The resource that failed
            project_state: Current project state

        Returns:
            Dict with diagnostic information including errors, logs, status, etc.
        """
        diagnostics = {
            "resource_name": resource.name,
            "resource_type": resource.__class__.__name__,
            "attempt_count": get_attempts(project_state, resource.name),
        }

        resource_type = resource.__class__.__name__

        try:
            if resource_type in ["DockerResource", "AppleContainerResource"]:
                # Collect container diagnostics
                diagnostics.update(self._collect_container_diagnostics(resource))
            elif resource_type == "FileResource":
                # Collect file diagnostics
                diagnostics.update(self._collect_file_diagnostics(resource))
            elif resource_type == "GitRepoResource":
                # Collect git repo diagnostics
                diagnostics.update(self._collect_git_diagnostics(resource))
            else:
                # Generic diagnostics
                diagnostics["message"] = f"No specific diagnostics available for {resource_type}"

        except Exception as e:
            logger.warning(f"Failed to collect diagnostics for {resource.name}: {e}")
            diagnostics["error"] = str(e)

        return diagnostics

    def _collect_container_diagnostics(self, resource: Resource) -> Dict[str, Any]:
        """Collect diagnostics for container resources (Docker/AppleContainer).

        Args:
            resource: Container resource

        Returns:
            Dict with container-specific diagnostics
        """
        diagnostics = {}

        resource_type = resource.__class__.__name__

        # Determine command based on container type
        if resource_type == "DockerResource":
            cmd_prefix = "docker"
        else:  # AppleContainerResource
            cmd_prefix = "container"

        try:
            # Check if container exists
            result = subprocess.run(
                [cmd_prefix, "ps", "-a", "--filter", f"name={resource.name}", "--format", "{{.Names}}"],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0 and resource.name in result.stdout:
                diagnostics["container_exists"] = True

                # Get container status
                status_result = subprocess.run(
                    [cmd_prefix, "ps", "-a", "--filter", f"name={resource.name}", "--format", "{{.Status}}"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if status_result.returncode == 0:
                    diagnostics["status"] = status_result.stdout.strip()

                # Get last 50 lines of logs
                log_result = subprocess.run(
                    [cmd_prefix, "logs", "--tail", "50", resource.name],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if log_result.returncode == 0:
                    diagnostics["logs"] = log_result.stdout
                    if log_result.stderr:
                        diagnostics["logs_stderr"] = log_result.stderr
                else:
                    diagnostics["logs_error"] = log_result.stderr
            else:
                diagnostics["container_exists"] = False
                diagnostics["error"] = "Container does not exist or failed to start"

        except subprocess.TimeoutExpired:
            diagnostics["error"] = "Timeout while collecting container diagnostics"
        except Exception as e:
            diagnostics["error"] = f"Failed to collect container diagnostics: {e}"

        return diagnostics

    def _collect_file_diagnostics(self, resource: Resource) -> Dict[str, Any]:
        """Collect diagnostics for file resources.

        Args:
            resource: File resource

        Returns:
            Dict with file-specific diagnostics
        """
        diagnostics = {}

        try:
            # Resolve file path
            file_path, _ = resource._resolve_file_path()
            path = Path(file_path)

            diagnostics["path"] = str(path)
            diagnostics["exists"] = path.exists()

            if path.exists():
                # Get file info
                stat = path.stat()
                diagnostics["size"] = stat.st_size
                diagnostics["permissions"] = oct(stat.st_mode)[-3:]

                # Check if it's a file or directory
                diagnostics["is_file"] = path.is_file()
                diagnostics["is_directory"] = path.is_dir()
            else:
                diagnostics["error"] = f"File does not exist at {path}"

                # Check if parent directory exists
                parent = path.parent
                diagnostics["parent_exists"] = parent.exists()
                if not parent.exists():
                    diagnostics["error"] += f" (parent directory {parent} does not exist)"

        except Exception as e:
            diagnostics["error"] = f"Failed to collect file diagnostics: {e}"

        return diagnostics

    def _collect_git_diagnostics(self, resource: Resource) -> Dict[str, Any]:
        """Collect diagnostics for git repository resources.

        Args:
            resource: Git repository resource

        Returns:
            Dict with git-specific diagnostics
        """
        diagnostics = {}

        try:
            dest = getattr(resource, 'dest', None)
            if not dest:
                diagnostics["error"] = "No destination path specified"
                return diagnostics

            path = Path(dest)
            diagnostics["path"] = str(path)
            diagnostics["exists"] = path.exists()

            if path.exists():
                # Check if it's a git repository
                git_dir = path / ".git"
                diagnostics["is_git_repo"] = git_dir.exists()

                if git_dir.exists():
                    # Get git status
                    result = subprocess.run(
                        ["git", "-C", str(path), "status", "--short"],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if result.returncode == 0:
                        diagnostics["git_status"] = result.stdout

                    # Get current branch
                    result = subprocess.run(
                        ["git", "-C", str(path), "branch", "--show-current"],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if result.returncode == 0:
                        diagnostics["current_branch"] = result.stdout.strip()
                else:
                    diagnostics["error"] = f"Directory exists but is not a git repository"
            else:
                diagnostics["error"] = f"Repository not cloned at {path}"

        except Exception as e:
            diagnostics["error"] = f"Failed to collect git diagnostics: {e}"

        return diagnostics

    def enhance_completion_prompt(self, resource: Resource, diagnostics: Dict[str, Any]) -> str:
        """Build an enhanced completion prompt with diagnostic context.

        Args:
            resource: The resource to remediate
            diagnostics: Diagnostic information from collect_diagnostics()

        Returns:
            Enhanced prompt string with error context
        """
        prompt_parts = [
            "The previous deployment of this resource failed with the following issues:",
            ""
        ]

        # Add error information
        if "error" in diagnostics:
            prompt_parts.append(f"Error: {diagnostics['error']}")
            prompt_parts.append("")

        # Add container-specific info
        if diagnostics["resource_type"] in ["DockerResource", "AppleContainerResource"]:
            if "container_exists" in diagnostics:
                if diagnostics["container_exists"]:
                    prompt_parts.append(f"Container Status: {diagnostics.get('status', 'unknown')}")

                    if "logs" in diagnostics:
                        # Truncate logs if too long
                        logs = diagnostics["logs"]
                        if len(logs) > 1000:
                            logs = logs[-1000:]
                        prompt_parts.append(f"Recent Logs:\n{logs}")

                    if "logs_error" in diagnostics:
                        prompt_parts.append(f"Log Error: {diagnostics['logs_error']}")
                else:
                    prompt_parts.append("Container failed to start or does not exist")
            prompt_parts.append("")

        # Add file-specific info
        elif diagnostics["resource_type"] == "FileResource":
            if "exists" in diagnostics:
                if not diagnostics["exists"]:
                    prompt_parts.append(f"File does not exist at: {diagnostics.get('path', 'unknown')}")
                    if "parent_exists" in diagnostics and not diagnostics["parent_exists"]:
                        prompt_parts.append("Parent directory does not exist")
            prompt_parts.append("")

        # Add git-specific info
        elif diagnostics["resource_type"] == "GitRepoResource":
            if "is_git_repo" in diagnostics:
                if not diagnostics["is_git_repo"]:
                    prompt_parts.append("Repository not properly cloned or initialized")
            prompt_parts.append("")

        # Add remediation guidance
        prompt_parts.extend([
            f"Please fix the configuration for: {resource.description}",
            "",
            "Consider:",
        ])

        # Resource-specific considerations
        if diagnostics["resource_type"] in ["DockerResource", "AppleContainerResource"]:
            prompt_parts.extend([
                "- Checking if the image exists and is accessible",
                "- Validating port mappings and avoiding conflicts",
                "- Ensuring required environment variables are set correctly",
                "- Verifying volume paths are valid and accessible",
                "- Checking connection to dependencies (if any)",
            ])
        elif diagnostics["resource_type"] == "FileResource":
            prompt_parts.extend([
                "- Ensuring the directory path is valid",
                "- Checking file permissions are correct",
                "- Verifying the content is properly formatted",
            ])
        elif diagnostics["resource_type"] == "GitRepoResource":
            prompt_parts.extend([
                "- Verifying the repository URL is correct and accessible",
                "- Checking if the branch exists",
                "- Ensuring the destination path is valid",
            ])

        prompt_parts.append("")
        prompt_parts.append(f"Attempt: {diagnostics.get('attempt_count', 0) + 1}")

        return "\n".join(prompt_parts)

    async def remediate_resource(self, resource: Resource, project_state: ProjectState) -> bool:
        """Main remediation flow for a failed resource.

        Args:
            resource: The resource to remediate
            project_state: Current project state

        Returns:
            True if remediation succeeded, False otherwise
        """
        settings = get_settings()
        resource_name = resource.name or resource.__class__.__name__

        logger.warning(f"🚨 REMEDIATE_RESOURCE CALLED for {resource_name}")
        logger.info(f"Project: {project_state.project_id}")

        # Check if we've exceeded max attempts
        current_attempts = get_attempts(project_state, resource_name)
        logger.info(f"Current remediation attempts: {current_attempts}/{settings.service_max_remediation_attempts}")

        if current_attempts >= settings.service_max_remediation_attempts:
            logger.error(
                f"Resource {resource_name} has reached max remediation attempts "
                f"({settings.service_max_remediation_attempts}). Giving up."
            )
            return False

        logger.info(
            f"🔧 Starting remediation for {resource_name} "
            f"(attempt {current_attempts + 1}/{settings.service_max_remediation_attempts})"
        )

        # Increment attempt counter
        increment_attempts(project_state, resource_name)

        try:
            # Step 1: Collect diagnostics
            logger.info(f"Collecting diagnostics for {resource_name}")
            diagnostics = self.collect_diagnostics(resource, project_state)

            # Step 2: Enhance completion prompt
            logger.info(f"Enhancing completion prompt with diagnostic context")
            enhanced_prompt = self.enhance_completion_prompt(resource, diagnostics)

            # Step 3: Re-complete resource with enhanced prompt
            # Add enhanced prompt to resource description temporarily
            original_description = resource.description
            resource.description = f"{original_description}\n\n{enhanced_prompt}"

            logger.info(f"Re-completing resource {resource_name}")
            completed_resource = await self.resource_completer._complete_resource(resource)

            # Restore original description
            completed_resource.description = original_description

            # Step 4: Apply single resource
            logger.info(f"Applying remediated resource {resource_name}")
            apply_success = await self.apply_single_resource(completed_resource, project_state)

            if not apply_success:
                logger.warning(f"Failed to apply remediated resource {resource_name}")
                mark_failed(project_state, resource_name)
                return False

            # Step 5: Check if fixed (run assertions if available)
            if hasattr(completed_resource, 'assertions') and completed_resource.assertions:
                logger.info(f"Validating remediated resource {resource_name}")
                validation_success = await self._validate_resource(completed_resource, project_state)

                if validation_success:
                    logger.info(f"Successfully remediated {resource_name}")
                    mark_succeeded(project_state, resource_name)
                    return True
                else:
                    logger.warning(f"Resource {resource_name} still failing assertions")
                    mark_failed(project_state, resource_name)
                    return False
            else:
                # No assertions, assume success if apply succeeded
                logger.info(f"Successfully remediated {resource_name} (no assertions to validate)")
                mark_succeeded(project_state, resource_name)
                return True

        except Exception as e:
            logger.error(f"Remediation failed for {resource_name}: {e}")
            mark_failed(project_state, resource_name)
            return False

    async def apply_single_resource(self, resource: Resource, project_state: ProjectState) -> bool:
        """Apply a single resource without affecting other resources.

        Args:
            resource: The resource to apply
            project_state: Current project state

        Returns:
            True if application succeeded, False otherwise
        """
        try:
            # Generate PyInfra code for this resource only
            logger.info(f"Compiling single resource: {resource.name}")

            # Use a temporary directory for single-resource deployment
            import tempfile
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)

                # Set temporary output directory
                original_output_dir = self.pyinfra_compiler.output_dir
                self.pyinfra_compiler.output_dir = temp_path

                # Compile single resource
                pyinfra_dir = self.pyinfra_compiler.compile([resource])

                # Execute PyInfra
                result = self._execute_pyinfra(pyinfra_dir)

                # Restore original output directory
                self.pyinfra_compiler.output_dir = original_output_dir

                return result["success"]

        except Exception as e:
            logger.error(f"Failed to apply single resource {resource.name}: {e}")
            return False

    async def _validate_resource(self, resource: Resource, project_state: ProjectState) -> bool:
        """Validate a resource by running its assertions.

        Args:
            resource: The resource to validate
            project_state: Current project state

        Returns:
            True if all assertions passed, False otherwise
        """
        try:
            # Generate PyInfra assertion code for this resource only
            logger.info(f"Validating resource: {resource.name}")

            # Use a temporary directory for assertions
            import tempfile
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)

                # Set temporary output directory
                original_output_dir = self.pyinfra_compiler.output_dir
                self.pyinfra_compiler.output_dir = temp_path

                # Compile assertions
                pyinfra_dir = self.pyinfra_compiler.compile_assert([resource])

                # Execute PyInfra assertions
                result = self._execute_pyinfra(pyinfra_dir, deploy_file="assert.py")

                # Restore original output directory
                self.pyinfra_compiler.output_dir = original_output_dir

                return result["success"]

        except Exception as e:
            logger.error(f"Failed to validate resource {resource.name}: {e}")
            return False

    def _execute_pyinfra(self, pyinfra_dir: Path, deploy_file: str = "deploy.py") -> Dict[str, Any]:
        """Execute PyInfra deployment or assertion operation.

        Args:
            pyinfra_dir: Path to directory with inventory.py and deploy file
            deploy_file: Name of the deployment file (default: "deploy.py")

        Returns:
            Dict with execution results
        """
        operation_type = "destroy" if deploy_file == "destroy.py" else "deployment"
        if deploy_file == "assert.py":
            operation_type = "assertions"

        logger.debug(f"Executing PyInfra {operation_type} from: {pyinfra_dir}")

        # Run: pyinfra -y inventory.py <deploy_file> (auto-approve changes)
        cmd = ["pyinfra", "-y", "inventory.py", deploy_file]

        try:
            result = subprocess.run(
                cmd,
                cwd=pyinfra_dir,
                capture_output=True,
                text=True,
                check=True,
                timeout=300  # 5 minute timeout
            )

            logger.debug(f"PyInfra {operation_type} successful")
            return {
                "success": True,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode
            }

        except subprocess.CalledProcessError as e:
            logger.error(f"PyInfra {operation_type} failed: {e.stderr}")
            return {
                "success": False,
                "stdout": e.stdout,
                "stderr": e.stderr,
                "returncode": e.returncode
            }
        except subprocess.TimeoutExpired as e:
            logger.error(f"PyInfra {operation_type} timed out")
            return {
                "success": False,
                "stdout": "",
                "stderr": "Operation timed out after 5 minutes",
                "returncode": -1
            }
