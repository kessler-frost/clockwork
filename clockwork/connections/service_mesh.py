"""Service mesh connection for service discovery and mesh configuration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import pulumi
from pydantic import Field

from .base import Connection

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class ServiceMeshConnection(Connection):
    """Configure service-to-service communication with service discovery.

    ServiceMeshConnection handles service discovery, optional TLS, health checks,
    and automatic URL injection for microservices. It discovers service ports
    from the target resource and injects service URLs into the source resource's
    environment variables.

    Attributes:
        protocol: Protocol (http, https, grpc, tcp)
        port: Service port (AI can discover from to_resource)
        tls_enabled: Enable TLS for service communication
        cert_path: Path to TLS certificate file
        key_path: Path to TLS private key file
        health_check_path: Health check endpoint (default: "/health")
        service_name: Service discovery name (defaults to to_resource.name)
        load_balancing: Load balancing strategy (default: "round_robin")

    Example:
        >>> from clockwork.resources import DockerResource
        >>> from clockwork.connections import ServiceMeshConnection
        >>>
        >>> # Create backend service
        >>> api = DockerResource(
        ...     name="api-server",
        ...     description="API backend",
        ...     ports=["8000:8000"]
        ... )
        >>>
        >>> # Create frontend that connects to backend
        >>> web = DockerResource(
        ...     name="web-frontend",
        ...     description="Web frontend"
        ... )
        >>>
        >>> # Connect with service mesh
        >>> mesh = ServiceMeshConnection(
        ...     to_resource=api,
        ...     protocol="http",
        ...     health_check_path="/health"
        ... )
        >>> web.connect(mesh)
        >>>
        >>> # Result: web.env_vars["API_SERVER_URL"] = "http://api-server:8000"
    """

    protocol: str = Field(
        default="http",
        description="Protocol for service communication (http, https, grpc, tcp)",
    )
    port: int | None = Field(
        default=None,
        description="Service port (will be discovered from to_resource if not set)",
    )
    tls_enabled: bool = Field(
        default=False,
        description="Enable TLS for service communication",
    )
    cert_path: str | None = Field(
        default=None,
        description="Path to TLS certificate file",
    )
    key_path: str | None = Field(
        default=None,
        description="Path to TLS private key file",
    )
    health_check_path: str | None = Field(
        default="/health",
        description="Health check endpoint path",
    )
    service_name: str | None = Field(
        default=None,
        description="Service discovery name (defaults to to_resource.name)",
    )
    load_balancing: str = Field(
        default="round_robin",
        description="Load balancing strategy",
    )

    def needs_completion(self) -> bool:
        """Check if this connection needs AI completion.

        Returns True if description is provided but port or service_name are missing.

        Returns:
            True if needs AI completion, False otherwise
        """
        return self.description is not None and (
            self.port is None or self.service_name is None
        )

    def _extract_port(self, port_mapping: str) -> int:
        """Extract port number from Docker port mapping string.

        Args:
            port_mapping: Port mapping in format "host:container" or "port"

        Returns:
            Container port number

        Example:
            >>> self._extract_port("8080:80")
            80
            >>> self._extract_port("8000")
            8000
        """
        if ":" in port_mapping:
            # Format: "host:container" -> extract container port
            return int(port_mapping.split(":")[-1])
        # Format: "port" -> use as-is
        return int(port_mapping)

    def _discover_port(self) -> None:
        """Discover port from to_resource if not explicitly set."""
        if self.port is not None:
            return

        # Try to extract port from DockerResource
        if hasattr(self.to_resource, "ports") and self.to_resource.ports:
            port_mapping = self.to_resource.ports[0]
            self.port = self._extract_port(port_mapping)
            logger.info(
                f"Discovered port {self.port} from {self.to_resource.name}"
            )

    def _set_service_name(self) -> None:
        """Set service_name to to_resource.name if not explicitly set."""
        if self.service_name is None and hasattr(self.to_resource, "name"):
            self.service_name = self.to_resource.name
            logger.info(f"Set service_name to {self.service_name}")

    def _inject_service_url(self) -> None:
        """Inject service URL into from_resource environment variables.

        Creates environment variable in format:
            {SERVICE_NAME}_URL={protocol}://{service_name}:{port}

        Example:
            API_SERVER_URL=http://api-server:8000
        """
        if not self.service_name or not self.port:
            logger.warning(
                "Cannot inject service URL: service_name or port missing"
            )
            return

        # Build service URL
        service_url = f"{self.protocol}://{self.service_name}:{self.port}"

        # Create environment variable name (uppercase, replace hyphens with underscores)
        env_var_name = f"{self.service_name.upper().replace('-', '_')}_URL"

        # Inject into from_resource
        if not hasattr(self.from_resource, "env_vars"):
            self.from_resource.env_vars = {}

        self.from_resource.env_vars[env_var_name] = service_url
        logger.info(f"Injected {env_var_name}={service_url}")

    def _add_health_check_assertion(self) -> None:
        """Add health check assertion if health_check_path is set."""
        if not self.health_check_path or not self.service_name or not self.port:
            return

        from clockwork.assertions import HealthcheckAssert

        health_url = (
            f"{self.protocol}://{self.service_name}:{self.port}"
            f"{self.health_check_path}"
        )

        health_check = HealthcheckAssert(url=health_url)

        if self.assertions is None:
            self.assertions = []

        self.assertions.append(health_check)
        logger.info(f"Added health check assertion for {health_url}")

    def _create_tls_certificates(self) -> None:
        """Create self-signed TLS certificates if TLS is enabled but no certs provided.

        Uses openssl to generate self-signed certificate and key files.
        Stores them as FileResources in setup_resources.
        """
        if not self.tls_enabled or self.cert_path:
            return

        from clockwork.resources import FileResource

        # Generate self-signed certificate using openssl
        cert_content = FileResource(
            name=f"{self.service_name}-tls-cert",
            description=f"Self-signed TLS certificate for {self.service_name}",
            path=f"/tmp/{self.service_name}-cert.pem",
        )

        key_content = FileResource(
            name=f"{self.service_name}-tls-key",
            description=f"Self-signed TLS private key for {self.service_name}",
            path=f"/tmp/{self.service_name}-key.pem",
        )

        self.setup_resources.extend([cert_content, key_content])
        self.cert_path = cert_content.path
        self.key_path = key_content.path

        logger.info(
            f"Created self-signed TLS certificate for {self.service_name}"
        )

    def to_pulumi(self) -> list[pulumi.Resource] | None:
        """Create Pulumi resources for service mesh connection.

        Performs the following steps:
        1. Discover port from to_resource if not provided
        2. Set service_name to to_resource.name if not provided
        3. Generate self-signed certificates if TLS enabled but no cert_path
        4. Inject service URL into from_resource environment variables
        5. Add health check assertion if health_check_path is set
        6. Deploy any setup resources (e.g., TLS certificates)

        Returns:
            List of Pulumi resources, or None if no setup resources
        """
        # Step 1: Discover port from to_resource
        self._discover_port()

        # Step 2: Set service_name to to_resource.name
        self._set_service_name()

        # Step 3: Generate TLS certificates if needed
        self._create_tls_certificates()

        # Step 4: Inject service URL into from_resource
        self._inject_service_url()

        # Step 5: Add health check assertion
        self._add_health_check_assertion()

        # Step 6: Deploy setup resources (e.g., TLS certificates)
        if not self.setup_resources:
            return None

        # Deploy setup resources
        pulumi_resources = []
        for resource in self.setup_resources:
            if hasattr(resource, "to_pulumi"):
                deployed = resource.to_pulumi()
                if deployed:
                    pulumi_resources.append(deployed)

        # Store for dependency tracking
        self._pulumi_resources = pulumi_resources

        return pulumi_resources if pulumi_resources else None

    def get_connection_context(self) -> dict[str, Any]:
        """Get context for AI completion.

        Returns connection details that can be used by AI when completing
        resources or other connections.

        Returns:
            Dict with service mesh connection details
        """
        context = super().get_connection_context()
        context.update(
            {
                "protocol": self.protocol,
                "port": self.port,
                "service_name": self.service_name,
                "tls_enabled": self.tls_enabled,
                "health_check_path": self.health_check_path,
                "load_balancing": self.load_balancing,
            }
        )
        return context
