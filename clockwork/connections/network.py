"""Network connection - creates Apple Container networks for container communication."""

import logging
from typing import Any

import pulumi
import pulumi_command as command
from pydantic import Field

from .base import Connection

logger = logging.getLogger(__name__)


class NetworkConnection(Connection):
    """Network connection that creates Apple Container networks for container communication.

    This connection automatically creates Apple Container networks and connects containers,
    enabling service discovery and isolation. The AI can generate network names
    if not provided.

    Note: Apple Container networking (v0.1.0) supports network names for basic
    connectivity. Advanced features like custom drivers, subnets, and gateways are not
    currently available in this version.

    Attributes:
        network_name: Apple Container network name (AI generates if None and description provided)

    Examples:
        # AI generates network name
        >>> db = AppleContainerResource(name="postgres", image="postgres:15")
        >>> api = AppleContainerResource(name="api", image="node:20")
        >>> connection = NetworkConnection(
        ...     description="backend network for API and database",
        ...     to_resource=db
        ... )
        >>> api.connect(connection)
        # AI generates: network_name="backend-network"

        # Manual network configuration
        >>> db = AppleContainerResource(name="postgres", image="postgres:15")
        >>> api = AppleContainerResource(name="api", image="node:20")
        >>> connection = NetworkConnection(
        ...     to_resource=db,
        ...     network_name="my-network"
        ... )
        >>> api.connect(connection)
    """

    network_name: str | None = Field(
        None,
        description="Apple Container network name - AI generates if not provided",
        examples=["backend-network", "frontend-network", "app-network"],
    )

    def needs_completion(self) -> bool:
        """Check if this connection needs AI completion.

        Returns True if description is provided but network_name is None.

        Returns:
            bool: True if network_name needs completion, False otherwise
        """
        return self.description is not None and self.network_name is None

    def to_pulumi(self) -> list[pulumi.Resource] | None:
        """Create Apple Container network via CLI and attach to containers.

        Creates the Apple Container network using `container network create` and modifies
        both from_resource and to_resource (if they are AppleContainerResources) to:
        1. Add network to their networks list
        2. Inject hostname environment variables for service discovery

        Returns:
            list[pulumi.Resource]: List containing the network command resource, or None if network_name not set

        Raises:
            ValueError: If network_name is not set after completion

        Example:
            >>> db = AppleContainerResource(name="postgres", image="postgres:15")
            >>> api = AppleContainerResource(name="api", image="node:20")
            >>> conn = NetworkConnection(
            ...     from_resource=api,
            ...     to_resource=db,
            ...     network_name="backend-network"
            ... )
            >>> resources = conn.to_pulumi()
            # Creates network and injects POSTGRES_HOST=postgres into api
        """
        if self.network_name is None:
            raise ValueError(
                "network_name must be set before calling to_pulumi()"
            )

        # Create the Apple Container network using CLI
        network = command.local.Command(
            f"network-{self.network_name}",
            create=f"container network create {self.network_name}",
            delete=f"container network rm {self.network_name} || true",
        )

        # Store for later dependency tracking
        self._pulumi_resources = [network]

        # Modify from_resource if it's a AppleContainerResource
        if self.from_resource is not None and self._is_container_resource(
            self.from_resource
        ):
            # Add network to from_resource
            if self.network_name not in self.from_resource.networks:
                self.from_resource.networks.append(self.network_name)

            # Inject hostname env var for to_resource
            if self.to_resource is not None and self._is_container_resource(
                self.to_resource
            ):
                hostname_key = (
                    f"{self.to_resource.name.upper().replace('-', '_')}_HOST"
                )
                self.from_resource.env_vars[hostname_key] = (
                    self.to_resource.name
                )
                logger.info(
                    f"Injected {hostname_key}={self.to_resource.name} into {self.from_resource.name}"
                )

        # Modify to_resource if it's a AppleContainerResource
        if self.to_resource is not None and self._is_container_resource(
            self.to_resource
        ):
            # Add network to to_resource
            if self.network_name not in self.to_resource.networks:
                self.to_resource.networks.append(self.network_name)

            # Inject hostname env var for from_resource
            if self.from_resource is not None and self._is_container_resource(
                self.from_resource
            ):
                hostname_key = (
                    f"{self.from_resource.name.upper().replace('-', '_')}_HOST"
                )
                self.to_resource.env_vars[hostname_key] = (
                    self.from_resource.name
                )
                logger.info(
                    f"Injected {hostname_key}={self.from_resource.name} into {self.to_resource.name}"
                )

        return self._pulumi_resources

    def _is_container_resource(self, resource: Any) -> bool:
        """Check if a resource is a AppleContainerResource.

        Args:
            resource: Resource to check

        Returns:
            bool: True if resource is a AppleContainerResource, False otherwise
        """
        return resource.__class__.__name__ == "AppleContainerResource"

    def get_connection_context(self) -> dict[str, Any]:
        """Get connection context for AI completion.

        Returns context including network configuration that can be used
        by AI when completing this connection or other resources.

        Returns:
            dict: Context with network information

        Example:
            >>> conn = NetworkConnection(
            ...     network_name="backend-network"
            ... )
            >>> conn.get_connection_context()
            {
                'type': 'NetworkConnection',
                'network_name': 'backend-network',
                'from_resource': None,
                'to_resource': None
            }
        """
        from_name = None
        to_name = None

        if self.from_resource is not None:
            from_name = getattr(self.from_resource, "name", None)

        if self.to_resource is not None:
            to_name = getattr(self.to_resource, "name", None)

        return {
            "type": "NetworkConnection",
            "network_name": self.network_name,
            "from_resource": from_name,
            "to_resource": to_name,
        }
