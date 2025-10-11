"""Container-specific assertions for both Docker and Apple Containers."""

from typing import Any, Optional
from .base import BaseAssertion
from .utils import resolve_container_name, escape_shell_pattern


class ContainerRunningAssert(BaseAssertion):
    """Assert that a container is in running state.

    Checks if the specified container exists and is currently running.
    Automatically detects whether to use 'docker ps' or 'container ls' based on resource type.

    Attributes:
        container_name: Optional override for container name (defaults to resource.name)
        timeout_seconds: Maximum time to wait for check (default: 5)

    Example:
        >>> ContainerRunningAssert()  # Uses resource name
        >>> ContainerRunningAssert(container_name="my-container")
    """

    container_name: Optional[str] = None
    timeout_seconds: int = 5

    def to_pyinfra_operation(self, resource: Any) -> str:
        """Generate PyInfra operation to check container is running.

        Args:
            resource: Parent DockerResource or AppleContainerResource

        Returns:
            PyInfra server.shell operation that checks container status
        """
        container = resolve_container_name(self, resource)
        desc = self.description or f"Container {container} is running"

        # Detect resource type and use appropriate CLI command
        resource_type = type(resource).__name__
        if resource_type == "DockerResource":
            check_cmd = f"docker ps | grep -q {container} || exit 1"
        else:  # AppleContainerResource
            check_cmd = f"container ls | grep -q {container} || exit 1"

        return f'''
# Assert: {desc}
server.shell(
    name="Assert: {desc}",
    commands=[
        "{check_cmd}"
    ],
)
'''


class ContainerHealthyAssert(BaseAssertion):
    """Assert that a container reports healthy status.

    Checks the container's health check status. The container must have
    a HEALTHCHECK defined in its container image or configuration.
    Automatically detects whether to use 'docker inspect' or 'container inspect' based on resource type.

    Attributes:
        container_name: Optional override for container name (defaults to resource.name)
        timeout_seconds: Maximum time to wait for healthy state (default: 30)

    Example:
        >>> ContainerHealthyAssert()  # Uses resource name
        >>> ContainerHealthyAssert(container_name="postgres", timeout_seconds=60)
    """

    container_name: Optional[str] = None
    timeout_seconds: int = 30

    def to_pyinfra_operation(self, resource: Any) -> str:
        """Generate PyInfra operation to check container health.

        Args:
            resource: Parent DockerResource or AppleContainerResource

        Returns:
            PyInfra server.shell operation that inspects container health
        """
        container = resolve_container_name(self, resource)
        desc = self.description or f"Container {container} is healthy"

        # Detect resource type and use appropriate CLI command
        resource_type = type(resource).__name__
        if resource_type == "DockerResource":
            inspect_cmd = f"HEALTH=$(docker inspect --format='{{{{.State.Health.Status}}}}' {container} 2>/dev/null || echo 'none'); "
        else:  # AppleContainerResource
            inspect_cmd = f"HEALTH=$(container inspect --format='{{{{.State.Health.Status}}}}' {container} 2>/dev/null || echo 'none'); "

        return f'''
# Assert: {desc}
server.shell(
    name="Assert: {desc}",
    commands=[
        "{inspect_cmd}"
        "[ \"$HEALTH\" = 'healthy' ] || exit 1"
    ],
)
'''


class LogContainsAssert(BaseAssertion):
    """Assert that container logs contain a specific pattern.

    Searches the container's recent logs for a regex pattern. Useful for
    verifying successful startup messages or specific events.
    Automatically detects whether to use 'docker logs' or 'container logs' based on resource type.

    Attributes:
        pattern: Regular expression pattern to search for in logs
        lines: Number of log lines to check from the end (default: 100)
        container_name: Optional override for container name (defaults to resource.name)
        timeout_seconds: Maximum time to wait (default: 10)

    Example:
        >>> LogContainsAssert(
        ...     pattern="Server started on port 8080",
        ...     lines=50
        ... )
    """

    pattern: str
    lines: int = 100
    container_name: Optional[str] = None
    timeout_seconds: int = 10

    def to_pyinfra_operation(self, resource: Any) -> str:
        """Generate PyInfra operation to check container logs.

        Args:
            resource: Parent DockerResource or AppleContainerResource

        Returns:
            PyInfra server.shell operation that greps container logs
        """
        container = resolve_container_name(self, resource)
        desc = self.description or f"Logs for {container} contain '{self.pattern}'"

        # Escape single quotes in pattern for shell command
        escaped_pattern = escape_shell_pattern(self.pattern)

        # Detect resource type and use appropriate CLI command
        resource_type = type(resource).__name__
        if resource_type == "DockerResource":
            logs_cmd = f"docker logs --tail {self.lines} {container} 2>&1 | grep -q '{escaped_pattern}' || exit 1"
        else:  # AppleContainerResource
            logs_cmd = f"container logs -n {self.lines} {container} 2>&1 | grep -q '{escaped_pattern}' || exit 1"

        return f'''
# Assert: {desc}
server.shell(
    name="Assert: {desc}",
    commands=[
        "{logs_cmd}"
    ],
)
'''
