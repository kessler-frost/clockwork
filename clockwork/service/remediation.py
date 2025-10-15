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
from ..pulumi_compiler import PulumiCompiler
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
        base_url: Optional[str] = None,
        project_dir: Optional[Path] = None
    ):
        """Initialize the remediation engine.

        Args:
            api_key: API key for AI service (overrides settings/.env)
            model: Model to use for resource completion (overrides settings/.env)
            base_url: Base URL for API endpoint (overrides settings/.env)
            project_dir: Base directory for the project (defaults to current directory)
        """
        settings = get_settings()

        self.resource_completer = ResourceCompleter(
            api_key=api_key or settings.api_key,
            model=model or settings.model,
            base_url=base_url or settings.base_url
        )

        self.pulumi_compiler = PulumiCompiler(
            project_dir=project_dir
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
        """Apply a single resource using Pulumi Automation API.

        Creates an inline Pulumi program that deploys only this resource,
        allowing surgical remediation without affecting other resources.

        Args:
            resource: The resource to apply
            project_state: Current project state

        Returns:
            True if application succeeded, False otherwise
        """
        try:
            logger.info(f"Applying single resource with Pulumi: {resource.name}")

            # Import Pulumi Automation API
            from pulumi import automation as auto

            # Create inline program for single resource
            def single_resource_program():
                """Pulumi program that deploys only the remediated resource."""
                try:
                    if hasattr(resource, "to_pulumi"):
                        resource.to_pulumi()
                        logger.debug(f"Created Pulumi resource: {resource.name}")
                    else:
                        logger.error(
                            f"Resource {resource.name} does not implement to_pulumi()"
                        )
                        raise ValueError(f"Resource {resource.name} missing to_pulumi() method")
                except Exception as e:
                    logger.error(f"Failed to create Pulumi resource {resource.name}: {e}")
                    raise

            # Create or select stack
            project_name = "clockwork"
            stack_name = "dev"

            stack = auto.create_or_select_stack(
                stack_name=stack_name,
                project_name=project_name,
                program=single_resource_program,
            )
            logger.info(f"Using stack: {stack_name} for single resource deployment")

            # Perform up operation
            logger.info(f"Running Pulumi up for {resource.name}...")
            up_result = stack.up(on_output=lambda msg: logger.debug(msg))

            # Check result
            success = up_result.summary.result == "succeeded"

            if success:
                logger.info(
                    f"Successfully applied resource {resource.name} "
                    f"(changes: +{up_result.summary.resource_changes.get('create', 0)} "
                    f"~{up_result.summary.resource_changes.get('update', 0)})"
                )
            else:
                logger.error(f"Failed to apply resource {resource.name}: {up_result.summary.result}")

            return success

        except Exception as e:
            logger.error(f"Failed to apply single resource {resource.name}: {e}")
            return False

    async def _validate_resource(self, resource: Resource, project_state: ProjectState) -> bool:
        """Validate a resource by querying Pulumi state and running assertions.

        First checks if the resource exists in Pulumi state, then runs any
        defined assertions as additional validation.

        Args:
            resource: The resource to validate
            project_state: Current project state

        Returns:
            True if resource is valid and all assertions passed, False otherwise
        """
        try:
            logger.info(f"Validating resource: {resource.name}")

            # Import Pulumi Automation API
            from pulumi import automation as auto

            # Query Pulumi state to verify resource exists
            project_name = "clockwork"
            stack_name = "dev"

            try:
                # Create empty program for state query
                def empty_program():
                    pass

                # Select existing stack
                stack = auto.select_stack(
                    stack_name=stack_name,
                    project_name=project_name,
                    program=empty_program,
                )

                # Export stack state
                state = stack.export_stack()

                # Find resource in state
                resource_state = self._find_resource_in_state(state, resource.name)

                if not resource_state:
                    logger.warning(
                        f"Resource {resource.name} not found in Pulumi state after remediation"
                    )
                    return False

                logger.debug(f"Found resource {resource.name} in Pulumi state")

            except Exception as e:
                logger.error(f"Failed to query Pulumi state for {resource.name}: {e}")
                return False

            # If resource has assertions, run them as additional validation
            if hasattr(resource, 'assertions') and resource.assertions:
                logger.debug(f"Running assertions for {resource.name}")
                try:
                    # Import assertion runner
                    from clockwork.core import ClockworkCore
                    core = ClockworkCore()
                    assertion_results = await core.assert_resources([resource])

                    # Check if all assertions passed
                    if not assertion_results.get('success', False):
                        logger.warning(f"Assertions failed for {resource.name}")
                        return False

                    logger.debug(f"All assertions passed for {resource.name}")

                except Exception as e:
                    logger.error(f"Failed to run assertions for {resource.name}: {e}")
                    return False

            return True

        except Exception as e:
            logger.error(f"Failed to validate resource {resource.name}: {e}")
            return False

    def _find_resource_in_state(self, state: Dict[str, Any], resource_name: str) -> Optional[Dict[str, Any]]:
        """Find a resource in Pulumi stack state by name.

        Searches the exported stack state for a resource matching the given name.
        The Pulumi state structure contains a 'deployment' key with 'resources' array.

        Args:
            state: Exported Pulumi stack state (from stack.export_stack())
            resource_name: Name of the resource to find

        Returns:
            Resource state dict if found, None otherwise
        """
        try:
            # Pulumi state structure: state['deployment']['resources']
            deployment = state.get('deployment', {})
            resources = deployment.get('resources', [])

            # Search for resource by URN or name
            for res in resources:
                # Check URN for resource name
                urn = res.get('urn', '')
                if resource_name in urn:
                    return res

                # Also check the 'id' field which may contain the resource name
                res_id = res.get('id', '')
                if resource_name in res_id:
                    return res

            return None

        except Exception as e:
            logger.warning(f"Error searching Pulumi state for {resource_name}: {e}")
            return None

