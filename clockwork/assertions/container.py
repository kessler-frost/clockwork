"""Container-specific assertions for Docker services."""

from typing import Any, Optional
from .base import BaseAssertion
from .utils import resolve_container_name, escape_shell_pattern


class ContainerRunningAssert(BaseAssertion):
    """Assert that a Docker container is in running state.

    Checks if the specified container exists and is currently running.
    Uses 'docker ps' to verify container status.

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
            resource: Parent DockerServiceResource

        Returns:
            PyInfra server.shell operation that checks docker ps output
        """
        container = resolve_container_name(self, resource)
        desc = self.description or f"Container {container} is running"

        return f'''
# Assert: {desc}
server.shell(
    name="Assert: {desc}",
    commands=[
        "docker ps --filter name=^{container}$ --filter status=running --format '{{{{.Names}}}}' | grep -q '^{container}$' || exit 1"
    ],
)
'''


class ContainerHealthyAssert(BaseAssertion):
    """Assert that a Docker container reports healthy status.

    Checks the container's health check status. The container must have
    a HEALTHCHECK defined in its Dockerfile or docker-compose configuration.

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
            resource: Parent DockerServiceResource

        Returns:
            PyInfra server.shell operation that inspects container health
        """
        container = resolve_container_name(self, resource)
        desc = self.description or f"Container {container} is healthy"

        return f'''
# Assert: {desc}
server.shell(
    name="Assert: {desc}",
    commands=[
        "HEALTH=$(docker inspect --format='{{{{.State.Health.Status}}}}' {container} 2>/dev/null || echo 'none'); "
        "[ \"$HEALTH\" = 'healthy' ] || exit 1"
    ],
)
'''


class LogContainsAssert(BaseAssertion):
    """Assert that container logs contain a specific pattern.

    Searches the container's recent logs for a regex pattern. Useful for
    verifying successful startup messages or specific events.

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
            resource: Parent DockerServiceResource

        Returns:
            PyInfra server.shell operation that greps container logs
        """
        container = resolve_container_name(self, resource)
        desc = self.description or f"Logs for {container} contain '{self.pattern}'"

        # Escape single quotes in pattern for shell command
        escaped_pattern = escape_shell_pattern(self.pattern)

        return f'''
# Assert: {desc}
server.shell(
    name="Assert: {desc}",
    commands=[
        "docker logs --tail {self.lines} {container} 2>&1 | grep -q '{escaped_pattern}' || exit 1"
    ],
)
'''
