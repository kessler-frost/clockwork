"""Docker container resource for cross-platform container management.

This module provides DockerResource, a cross-platform container resource
that works on Linux, macOS, and Windows wherever Docker is installed.
"""

from typing import Any

from pydantic import Field

from .base import Resource


class DockerResource(Resource):
    """Docker container resource - runs containers with intelligence completing all fields.

    This resource allows you to define Docker containers with just a description.
    Intelligence will complete all missing fields including name, image,
    ports, volumes, environment variables, and networks.

    Works on any platform with Docker installed (Linux, macOS, Windows).

    Attributes:
        description: What the service does - intelligence uses this to complete all fields (required)
        name: Container name (optional - intelligently generated if not provided)
        image: Container image to use (optional - intelligently suggested if not provided)
        ports: Port mappings as list of strings (optional - intelligently determined if not provided)
        volumes: Volume mounts as list of strings (optional - intelligently determined if not provided)
        env_vars: Environment variables as key-value pairs (optional - intelligently suggested if not provided)
        command: Command to run in the container (optional)
        networks: Container networks to attach (optional - intelligently determined if not provided)
        must_run: Whether the container must be running (True) or can be stopped (False)

    Examples:
        # Minimal - intelligence completes everything:
        >>> web = DockerResource(
        ...     description="lightweight nginx web server for testing"
        ... )
        # Intelligence generates: name="nginx-server", image="nginx:alpine", ports=["80:80"]

        # Advanced - override specific fields:
        >>> api = DockerResource(
        ...     description="lightweight web server for testing",
        ...     ports=["8090:80"]  # Override port
        ... )
        # Intelligence generates: name="nginx-server", image="nginx:alpine", volumes, env_vars
    """

    description: str | None = None
    name: str | None = Field(
        None,
        description="Container name - must be unique",
        examples=["nginx-server", "postgres-db", "redis-cache"],
    )
    image: str | None = Field(
        None,
        description="Container image with tag - prefer official, well-maintained images",
        examples=["nginx:alpine", "postgres:15-alpine", "redis:7-alpine"],
    )
    ports: list[str] | None = Field(
        None,
        description="Port mappings in 'host:container' format",
        examples=[["8080:80"], ["5432:5432", "5433:5432"]],
    )
    volumes: list[str] = Field(
        default_factory=list,
        description="Volume mounts in 'host:container' or 'host:container:ro' format",
        examples=[["./data:/data"], ["./config:/etc/nginx:ro"]],
    )
    env_vars: dict[str, str] = Field(
        default_factory=dict,
        description="Environment variables as key-value pairs",
        examples=[
            {"DEBUG": "1"},
            {
                "POSTGRES_PASSWORD": "secret",  # pragma: allowlist secret
                "POSTGRES_DB": "myapp",
            },
        ],
    )
    command: str | None = Field(
        None,
        description="Command to run in the container",
        examples=["nginx -g 'daemon off;'", "python app.py"],
    )
    networks: list[str] = Field(
        default_factory=list,
        description="Networks to attach container to",
        examples=[["backend"], ["frontend", "backend"]],
    )
    must_run: bool = Field(
        default=True,
        description="Whether the container must be running after creation",
    )

    def needs_completion(self) -> bool:
        """Returns True if any critical field needs intelligent completion.

        Only critical fields (name, image, ports) trigger intelligent completion.
        Optional fields (volumes, env_vars, networks, command) default to empty.

        Returns:
            bool: True if any critical field needs completion, False otherwise
        """
        return self.name is None or self.image is None or self.ports is None

    def to_pulumi(self):
        """Create Pulumi Docker container resource.

        Uses the DockerContainer dynamic provider to manage the container
        using the Docker CLI. All fields should be populated by
        intelligent completion before this is called.

        Returns:
            DockerContainer: Pulumi dynamic resource instance

        Raises:
            ValueError: If required fields are not completed

        Example:
            # After intelligent completion
            >>> resource.to_pulumi()
            <DockerContainer resource with container_id output>
        """
        from clockwork.pulumi_providers.docker_container import (
            DockerContainer,
            DockerContainerInputs,
        )

        # All fields should be populated by intelligent completion
        if self.name is None or self.image is None:
            raise ValueError(
                f"Resource fields not completed. name={self.name}, image={self.image}"
            )

        # Create inputs for the dynamic provider
        inputs = DockerContainerInputs(
            image=self.image,
            container_name=self.name,
            ports=self.ports or [],
            volumes=self.volumes,
            env_vars=self.env_vars,
            command=self.command,
            networks=self.networks,
            must_run=self.must_run,
        )

        # Check if we have temporary compile options (from _compile_with_opts)
        if hasattr(self, "_temp_compile_opts"):
            # Already contains merged parent + dependencies from _compile_with_opts()
            # Don't build or merge again - just use it directly
            opts = self._temp_compile_opts
        else:
            # Not in composite - build dependencies normally
            opts = self._build_dependency_options()

        # Create Pulumi resource
        container_resource = DockerContainer(
            resource_name=self.name,
            inputs=inputs,
            opts=opts,
        )

        # Store for dependency tracking
        self._pulumi_resource = container_resource

        return container_resource

    def get_connection_context(self) -> dict[str, Any]:
        """Get connection context for this Docker container resource.

        Returns shareable fields that other resources can use when connected.
        This includes container name, image, exposed ports, environment variables,
        and networks. Only non-None/non-empty fields are included.

        Returns:
            Dict with shareable fields:
                - name: Container name
                - type: Resource class name (DockerResource)
                - image: Container image (if set)
                - ports: Port mappings (if set)
                - env_vars: Environment variables (if set)
                - networks: Container networks (if set)
                - command: Container command (if set)

        Example:
            >>> container = DockerResource(
            ...     name="postgres",
            ...     image="postgres:15",
            ...     ports=["5432:5432"],
            ...     env_vars={"POSTGRES_PASSWORD": "testpass"}
            ... )
            >>> container.get_connection_context()
            {
                'name': 'postgres',
                'type': 'DockerResource',
                'image': 'postgres:15',
                'ports': ['5432:5432'],
                'env_vars': {'POSTGRES_PASSWORD': 'testpass'}
            }
        """
        context = {
            "name": self.name,
            "type": self.__class__.__name__,
            "image": self.image,
        }

        if self.ports:
            context["ports"] = self.ports
        if self.env_vars:
            context["env_vars"] = self.env_vars
        if self.networks:
            context["networks"] = self.networks
        if self.command:
            context["command"] = self.command

        return context
