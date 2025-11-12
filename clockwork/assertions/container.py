"""Container-specific assertions for Apple Containers."""

import subprocess
from typing import TYPE_CHECKING

from .base import BaseAssertion
from .utils import resolve_container_name

if TYPE_CHECKING:
    from clockwork.resources.base import Resource


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

    container_name: str | None = None
    timeout_seconds: int = 5

    async def check(self, resource: "Resource") -> bool:
        """Check if the container is running.

        Args:
            resource: The resource to validate

        Returns:
            True if container is running, False otherwise
        """
        try:
            container_name = resolve_container_name(self, resource)

            # Use Apple Container CLI
            cmd = [
                "container",
                "ps",
                "--filter",
                f"name={container_name}",
                "--format",
                "{{.Status}}",
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
            )
            return "up" in result.stdout.lower()
        except Exception:
            return False
