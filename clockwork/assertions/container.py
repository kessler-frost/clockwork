"""Container-specific assertions for both Docker and Apple Containers."""

import subprocess
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

            # Determine if this is Docker or Apple Container based on resource type
            resource_type = resource.__class__.__name__

            if resource_type == "AppleContainerResource":
                cmd = ["container", "ps", "--filter", f"name={container_name}", "--format", "{{.Status}}"]
            else:
                # Default to Docker for DockerResource and others
                cmd = ["docker", "ps", "-a", "--filter", f"name={container_name}", "--format", "{{.Status}}"]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds
            )
            return "up" in result.stdout.lower()
        except Exception:
            return False
