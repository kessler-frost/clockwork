"""State checkers for querying actual system state of deployed resources.

Each checker inspects the real system state for a specific resource type
and returns structured status information.
"""

import json
import logging
import subprocess
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from clockwork.resources.base import Resource

logger = logging.getLogger(__name__)


class ResourceStatus(Enum):
    """Enumeration of possible resource states."""

    RUNNING = "running"
    STOPPED = "stopped"
    EXISTS = "exists"
    MISSING = "missing"
    ERROR = "error"
    UNKNOWN = "unknown"
    CLONED = "cloned"
    NOT_A_REPO = "not_a_repo"
    COMPOSITE = "composite"


@dataclass
class ResourceState:
    """Represents the actual state of a deployed resource.

    Attributes:
        name: Resource name
        resource_type: Resource type (e.g., "AppleContainerResource")
        status: Status string (e.g., "running", "stopped", "exists", "missing")
        details: Additional status details as key-value pairs
        error: Error message if state check failed
    """

    name: str
    resource_type: str
    status: str
    details: dict[str, Any]
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            "name": self.name,
            "type": self.resource_type,
            "status": self.status,
            "details": self.details,
        }
        if self.error:
            result["error"] = self.error
        return result


class BaseStateChecker(ABC):
    """Base class for state checkers.

    State checkers query actual system state for specific resource types.
    """

    @abstractmethod
    async def check(self, resource: "Resource") -> ResourceState:
        """Check the actual state of a resource.

        Args:
            resource: The resource to check

        Returns:
            ResourceState with current system state
        """
        raise NotImplementedError

    @abstractmethod
    def can_check(self, resource: "Resource") -> bool:
        """Determine if this checker can handle the given resource.

        Args:
            resource: The resource to check

        Returns:
            True if this checker can handle the resource type
        """
        raise NotImplementedError

    # Error message formatters for different exception types
    _ERROR_FORMATTERS: ClassVar[dict[type, Callable[[Exception], str]]] = {
        PermissionError: lambda e: f"Permission denied: {e}. Try running with elevated privileges.",
        subprocess.TimeoutExpired: lambda e: f"Command timed out after {e.timeout}s",
        json.JSONDecodeError: lambda e: f"Failed to parse output: {e.msg}",
    }

    def _handle_check_error(
        self, e: Exception, resource_name: str, resource_type: str
    ) -> ResourceState:
        """Create error ResourceState with appropriate context.

        Args:
            e: The exception that occurred
            resource_name: Name of the resource being checked
            resource_type: Type of the resource being checked

        Returns:
            ResourceState with error status and descriptive error message
        """
        # Get formatter for this exception type, or use default
        formatter = self._ERROR_FORMATTERS.get(
            type(e), lambda e: f"{type(e).__name__}: {e}"
        )
        error_msg = formatter(e)

        # Log the error for debugging
        logger.error(
            f"State check failed for {resource_name} ({resource_type}): {error_msg}"
        )

        return ResourceState(
            name=resource_name,
            resource_type=resource_type,
            status=ResourceStatus.ERROR.value,
            details={},
            error=error_msg,
        )


class ContainerStateChecker(BaseStateChecker):
    """State checker for Apple Container resources.

    Queries the Apple Container CLI to get container status.
    """

    def can_check(self, resource: "Resource") -> bool:
        """Check if resource is an AppleContainerResource."""
        return resource.__class__.__name__ == "AppleContainerResource"

    async def check(self, resource: "Resource") -> ResourceState:
        """Check if an Apple Container is running.

        Uses `container list --format json` to query container status.

        Args:
            resource: AppleContainerResource to check

        Returns:
            ResourceState with container status
        """
        resource_name = resource.name or "unknown"
        resource_type = resource.__class__.__name__

        try:
            # Query Apple Container CLI
            cmd = ["container", "list", "--format", "json"]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode != 0:
                return ResourceState(
                    name=resource_name,
                    resource_type=resource_type,
                    status=ResourceStatus.ERROR.value,
                    details={},
                    error=f"container list failed: {result.stderr}",
                )

            containers = json.loads(result.stdout) if result.stdout else []

            # Find container by clockwork.name label
            for container in containers:
                labels = container.get("configuration", {}).get("labels", {})
                if labels.get("clockwork.name") == resource_name:
                    status = container.get("status", "unknown")

                    # Extract details
                    details: dict[str, Any] = {}

                    # Get ports from resource (since container list doesn't show them)
                    if hasattr(resource, "ports") and resource.ports:
                        details["ports"] = ", ".join(resource.ports)

                    # Get image
                    image = container.get("configuration", {}).get("image", "")
                    if image:
                        details["image"] = image

                    # Get container ID
                    container_id = container.get("id", "")
                    if container_id:
                        details["container_id"] = container_id[:12]

                    return ResourceState(
                        name=resource_name,
                        resource_type=resource_type,
                        status=status,
                        details=details,
                    )

            # Container not found
            return ResourceState(
                name=resource_name,
                resource_type=resource_type,
                status=ResourceStatus.MISSING.value,
                details={},
            )

        except FileNotFoundError:
            logger.error(f"Container CLI not found for {resource_name}")
            return ResourceState(
                name=resource_name,
                resource_type=resource_type,
                status=ResourceStatus.ERROR.value,
                details={},
                error="container CLI not found",
            )
        except (
            subprocess.TimeoutExpired,
            json.JSONDecodeError,
            PermissionError,
        ) as e:
            return self._handle_check_error(e, resource_name, resource_type)
        except Exception as e:
            # Log full traceback for unexpected errors
            logger.exception(
                f"Unexpected error checking state for {resource_name}: {e}"
            )
            return self._handle_check_error(e, resource_name, resource_type)


class FileStateChecker(BaseStateChecker):
    """State checker for File resources.

    Checks if file exists and gathers file metadata.
    """

    def can_check(self, resource: "Resource") -> bool:
        """Check if resource is a FileResource."""
        return resource.__class__.__name__ == "FileResource"

    async def check(self, resource: "Resource") -> ResourceState:
        """Check if a file exists and gather metadata.

        Args:
            resource: FileResource to check

        Returns:
            ResourceState with file status
        """
        resource_name = resource.name or "unknown"
        resource_type = resource.__class__.__name__

        try:
            # Resolve file path
            file_path = self._resolve_path(resource)

            if file_path is None:
                return ResourceState(
                    name=resource_name,
                    resource_type=resource_type,
                    status=ResourceStatus.UNKNOWN.value,
                    details={},
                    error="Could not resolve file path",
                )

            path = Path(file_path)

            if not path.exists():
                return ResourceState(
                    name=resource_name,
                    resource_type=resource_type,
                    status=ResourceStatus.MISSING.value,
                    details={"path": str(path)},
                )

            # File exists - gather metadata
            stat = path.stat()
            details: dict[str, Any] = {
                "path": str(path),
                "size": self._format_size(stat.st_size),
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            }

            # Check permissions
            mode = oct(stat.st_mode)[-3:]
            details["mode"] = mode

            return ResourceState(
                name=resource_name,
                resource_type=resource_type,
                status=ResourceStatus.EXISTS.value,
                details=details,
            )

        except PermissionError as e:
            return self._handle_check_error(e, resource_name, resource_type)
        except Exception as e:
            # Log full traceback for unexpected errors
            logger.exception(
                f"Unexpected error checking state for {resource_name}: {e}"
            )
            return self._handle_check_error(e, resource_name, resource_type)

    def _resolve_path(self, resource: "Resource") -> str | None:
        """Resolve file path from resource.

        Args:
            resource: FileResource with path information

        Returns:
            Resolved absolute file path or None
        """
        # Try explicit path first
        if hasattr(resource, "path") and resource.path:
            path = Path(resource.path)
            if not path.is_absolute():
                path = Path.cwd() / path
            return str(path)

        # Try directory + name
        if (
            hasattr(resource, "directory")
            and hasattr(resource, "name")
            and resource.directory
            and resource.name
        ):
            directory = Path(resource.directory)
            if not directory.is_absolute():
                directory = Path.cwd() / directory
            return str(directory / resource.name)

        # Try just name
        if hasattr(resource, "name") and resource.name:
            return str(Path.cwd() / resource.name)

        return None

    def _format_size(self, size: int) -> str:
        """Format file size in human-readable format.

        Args:
            size: Size in bytes

        Returns:
            Human-readable size string
        """
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.1f}{unit}" if unit != "B" else f"{size}B"
            size //= 1024
        return f"{size}TB"


class GitRepoStateChecker(BaseStateChecker):
    """State checker for Git repository resources.

    Checks repository status including branch, last commit, and dirty state.
    """

    def can_check(self, resource: "Resource") -> bool:
        """Check if resource is a GitRepoResource."""
        return resource.__class__.__name__ == "GitRepoResource"

    async def check(self, resource: "Resource") -> ResourceState:
        """Check Git repository status.

        Args:
            resource: GitRepoResource to check

        Returns:
            ResourceState with repository status
        """
        resource_name = resource.name or "unknown"
        resource_type = resource.__class__.__name__

        try:
            # Get destination path
            dest = getattr(resource, "dest", None)
            if not dest:
                return ResourceState(
                    name=resource_name,
                    resource_type=resource_type,
                    status=ResourceStatus.UNKNOWN.value,
                    details={},
                    error="No destination path specified",
                )

            repo_path = Path(dest)
            if not repo_path.is_absolute():
                repo_path = Path.cwd() / repo_path

            # Check if directory exists
            if not repo_path.exists():
                return ResourceState(
                    name=resource_name,
                    resource_type=resource_type,
                    status=ResourceStatus.MISSING.value,
                    details={"path": str(repo_path)},
                )

            # Check if it's a git repo
            git_dir = repo_path / ".git"
            if not git_dir.exists():
                return ResourceState(
                    name=resource_name,
                    resource_type=resource_type,
                    status=ResourceStatus.NOT_A_REPO.value,
                    details={"path": str(repo_path)},
                )

            details: dict[str, Any] = {"path": str(repo_path)}

            # Get current branch
            branch_result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if branch_result.returncode == 0:
                details["branch"] = branch_result.stdout.strip()

            # Get last commit info
            log_result = subprocess.run(
                ["git", "log", "-1", "--format=%h %s"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if log_result.returncode == 0:
                commit_info = log_result.stdout.strip()
                if commit_info:
                    details["last_commit"] = commit_info[:50]

            # Check if dirty
            status_result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if status_result.returncode == 0:
                is_dirty = bool(status_result.stdout.strip())
                details["dirty"] = is_dirty

            return ResourceState(
                name=resource_name,
                resource_type=resource_type,
                status=ResourceStatus.CLONED.value,
                details=details,
            )

        except FileNotFoundError:
            logger.error(f"Git CLI not found for {resource_name}")
            return ResourceState(
                name=resource_name,
                resource_type=resource_type,
                status=ResourceStatus.ERROR.value,
                details={},
                error="git CLI not found",
            )
        except (subprocess.TimeoutExpired, PermissionError) as e:
            return self._handle_check_error(e, resource_name, resource_type)
        except Exception as e:
            # Log full traceback for unexpected errors
            logger.exception(
                f"Unexpected error checking state for {resource_name}: {e}"
            )
            return self._handle_check_error(e, resource_name, resource_type)


class BlankStateChecker(BaseStateChecker):
    """State checker for Blank (composite) resources.

    Blank resources are containers for other resources,
    so their status is derived from children.
    """

    def can_check(self, resource: "Resource") -> bool:
        """Check if resource is a BlankResource."""
        return resource.__class__.__name__ == "BlankResource"

    async def check(self, resource: "Resource") -> ResourceState:
        """Check BlankResource status.

        Args:
            resource: BlankResource to check

        Returns:
            ResourceState showing composite status
        """
        resource_name = resource.name or "unknown"
        resource_type = resource.__class__.__name__

        children_count = len(resource._children) if resource._children else 0

        return ResourceState(
            name=resource_name,
            resource_type=resource_type,
            status=ResourceStatus.COMPOSITE.value,
            details={"children": children_count},
        )


# Registry of all state checkers
STATE_CHECKERS: list[BaseStateChecker] = [
    ContainerStateChecker(),
    FileStateChecker(),
    GitRepoStateChecker(),
    BlankStateChecker(),
]


def get_checker_for_resource(resource: "Resource") -> BaseStateChecker | None:
    """Get the appropriate state checker for a resource.

    Args:
        resource: Resource to find checker for

    Returns:
        Matching state checker or None
    """
    for checker in STATE_CHECKERS:
        if checker.can_check(resource):
            return checker
    return None


async def check_resource_state(resource: "Resource") -> ResourceState:
    """Check the state of a single resource.

    Args:
        resource: Resource to check

    Returns:
        ResourceState with current system state
    """
    checker = get_checker_for_resource(resource)

    if checker is None:
        return ResourceState(
            name=resource.name or "unknown",
            resource_type=resource.__class__.__name__,
            status=ResourceStatus.UNKNOWN.value,
            details={},
            error=f"No state checker for {resource.__class__.__name__}",
        )

    return await checker.check(resource)


async def check_all_resources_state(
    resources: list["Resource"],
) -> list[ResourceState]:
    """Check the state of multiple resources.

    Args:
        resources: List of resources to check

    Returns:
        List of ResourceState objects
    """
    states = []
    for resource in resources:
        state = await check_resource_state(resource)
        states.append(state)
    return states
