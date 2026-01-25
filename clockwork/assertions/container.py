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
        import json

        try:
            container_name = resolve_container_name(self, resource)

            # Use Apple Container CLI (list --format json)
            cmd = ["container", "list", "--format", "json"]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
            )

            if result.returncode != 0:
                return False

            containers = json.loads(result.stdout) if result.stdout else []

            # Check if any container matches the name and is running
            for container in containers:
                # Check labels for clockwork.name
                labels = container.get("configuration", {}).get("labels", {})
                if labels.get("clockwork.name") == container_name:
                    return container.get("status") == "running"

            return False
        except Exception:
            return False
