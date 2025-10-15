"""Container-specific assertions for both Docker and Apple Containers."""

from typing import Any, Optional
from .base import BaseAssertion
from .utils import resolve_container_name, escape_shell_pattern


class ContainerRunningAssert(BaseAssertion):
    """Assert that a container is in running state.

    Checks if the specified container exists and is currently running.

    Attributes:
        container_name: Optional override for container name (defaults to resource.name)
        timeout_seconds: Maximum time to wait for check (default: 5)

    Example:
        >>> ContainerRunningAssert()  # Uses resource name
        >>> ContainerRunningAssert(container_name="my-container")
    """

    container_name: Optional[str] = None
    timeout_seconds: int = 5


class ContainerHealthyAssert(BaseAssertion):
    """Assert that a container reports healthy status.

    Checks the container's health check status. The container must have
    a HEALTHCHECK defined in its container image or configuration.

    Attributes:
        container_name: Optional override for container name (defaults to resource.name)
        timeout_seconds: Maximum time to wait for healthy state (default: 30)

    Example:
        >>> ContainerHealthyAssert()  # Uses resource name
        >>> ContainerHealthyAssert(container_name="postgres", timeout_seconds=60)
    """

    container_name: Optional[str] = None
    timeout_seconds: int = 30


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
