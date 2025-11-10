"""Network connection - creates Docker networks for container communication."""

import logging
from typing import Any

import pulumi
import pulumi_docker as docker
from pydantic import Field

from .base import Connection

logger = logging.getLogger(__name__)


class NetworkConnection(Connection):
    """Network connection that creates Docker networks for container communication.

    This connection automatically creates Docker networks and connects containers,
    enabling service discovery and isolation. The AI can generate network names
    if not provided.

    Attributes:
        network_name: Docker network name (AI generates if None and description provided)
        driver: Network driver - "bridge", "overlay", "host", or "macvlan"
        internal: Whether network is internal (no external access)
        enable_ipv6: Whether to enable IPv6
        subnet: Custom subnet in CIDR notation (e.g., "172.20.0.0/16")
        gateway: Custom gateway IP address

    Examples:
        # AI generates network name
        >>> db = DockerResource(name="postgres", image="postgres:15")
        >>> api = DockerResource(name="api", image="node:20")
        >>> connection = NetworkConnection(
        ...     description="backend network for API and database",
        ...     to_resource=db
        ... )
        >>> api.connect(connection)
        # AI generates: network_name="backend-network"

        # Manual network configuration
        >>> db = DockerResource(name="postgres", image="postgres:15")
        >>> api = DockerResource(name="api", image="node:20")
        >>> connection = NetworkConnection(
        ...     to_resource=db,
        ...     network_name="my-network",
        ...     driver="bridge",
        ...     internal=True
        ... )
        >>> api.connect(connection)
    """

    network_name: str | None = Field(
        None,
        description="Docker network name - AI generates if not provided",
        examples=["backend-network", "frontend-network", "app-network"],
    )
    driver: str = Field(
        default="bridge",
        description="Network driver type",
        examples=["bridge", "overlay", "host", "macvlan"],
    )
    internal: bool = Field(
        default=False,
        description="Whether network is internal (no external access)",
    )
    enable_ipv6: bool = Field(
        default=False,
        description="Whether to enable IPv6 on this network",
    )
    subnet: str | None = Field(
        None,
        description="Custom subnet in CIDR notation",
        examples=["172.20.0.0/16", "192.168.1.0/24"],
    )
    gateway: str | None = Field(
        None,
        description="Custom gateway IP address",
        examples=["172.20.0.1", "192.168.1.1"],
    )

    def needs_completion(self) -> bool:
        """Check if this connection needs AI completion.

        Returns True if description is provided but network_name is None.

        Returns:
            bool: True if network_name needs completion, False otherwise
        """
        return self.description is not None and self.network_name is None

    def to_pulumi(self) -> list[pulumi.Resource] | None:
        """Create Pulumi Docker Network resource and attach to containers.

        Creates the Docker network and modifies both from_resource and to_resource
        (if they are DockerResources) to:
        1. Add network to their networks list
        2. Inject hostname environment variables for service discovery

        Returns:
            list[pulumi.Resource]: List containing the network resource, or None if network_name not set

        Raises:
            ValueError: If network_name is not set after completion

        Example:
            >>> db = DockerResource(name="postgres", image="postgres:15")
            >>> api = DockerResource(name="api", image="node:20")
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

        # Build IPAM config if subnet or gateway is specified
        ipam_config = None
        if self.subnet or self.gateway:
            ipam_config_list = []
            config = {}
            if self.subnet:
                config["subnet"] = self.subnet
            if self.gateway:
                config["gateway"] = self.gateway
            ipam_config_list.append(docker.NetworkIpamConfigArgs(**config))
            ipam_config = docker.NetworkIpamArgs(configs=ipam_config_list)

        # Create the Docker network
        network = docker.Network(
            self.network_name,
            name=self.network_name,
            driver=self.driver,
            internal=self.internal,
            enable_ipv6=self.enable_ipv6,
            ipam=ipam_config,
        )

        # Store for later dependency tracking
        self._pulumi_resources = [network]

        # Modify from_resource if it's a DockerResource
        if self.from_resource is not None and self._is_docker_resource(
            self.from_resource
        ):
            # Add network to from_resource
            if self.network_name not in self.from_resource.networks:
                self.from_resource.networks.append(self.network_name)

            # Inject hostname env var for to_resource
            if self.to_resource is not None and self._is_docker_resource(
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

        # Modify to_resource if it's a DockerResource
        if self.to_resource is not None and self._is_docker_resource(
            self.to_resource
        ):
            # Add network to to_resource
            if self.network_name not in self.to_resource.networks:
                self.to_resource.networks.append(self.network_name)

            # Inject hostname env var for from_resource
            if self.from_resource is not None and self._is_docker_resource(
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

    def _is_docker_resource(self, resource: Any) -> bool:
        """Check if a resource is a DockerResource.

        Args:
            resource: Resource to check

        Returns:
            bool: True if resource is a DockerResource, False otherwise
        """
        return resource.__class__.__name__ == "DockerResource"

    def get_connection_context(self) -> dict[str, Any]:
        """Get connection context for AI completion.

        Returns context including network configuration that can be used
        by AI when completing this connection or other resources.

        Returns:
            dict: Context with network information

        Example:
            >>> conn = NetworkConnection(
            ...     network_name="backend-network",
            ...     driver="bridge",
            ...     internal=True
            ... )
            >>> conn.get_connection_context()
            {
                'type': 'NetworkConnection',
                'network_name': 'backend-network',
                'driver': 'bridge',
                'internal': True,
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

        context = {
            "type": "NetworkConnection",
            "network_name": self.network_name,
            "driver": self.driver,
            "from_resource": from_name,
            "to_resource": to_name,
        }

        # Add optional fields if they're set
        if self.internal:
            context["internal"] = self.internal
        if self.enable_ipv6:
            context["enable_ipv6"] = self.enable_ipv6
        if self.subnet:
            context["subnet"] = self.subnet
        if self.gateway:
            context["gateway"] = self.gateway

        return context
