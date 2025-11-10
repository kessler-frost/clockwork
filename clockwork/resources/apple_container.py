"""Apple Container resource for running containers with optional AI-suggested images."""

from typing import Any

from pydantic import Field

from .base import Resource


class AppleContainerResource(Resource):
    """Apple Container resource - runs containers with AI completing all fields.

    This resource allows you to define Apple Containers with just a description.
    The AI will intelligently complete all missing fields including name, image,
    ports, volumes, environment variables, and networks.

    Attributes:
        description: What the service does - AI uses this to complete all fields (required)
        name: Container name (optional - AI generates if not provided)
        image: Container image to use (optional - AI suggests if not provided)
        ports: Port mappings as list of strings (optional - AI determines if not provided)
        volumes: Volume mounts as list of strings (optional - AI determines if not provided)
        env_vars: Environment variables as key-value pairs (optional - AI suggests if not provided)
        networks: Container networks to attach (optional - AI determines if not provided)
        must_run: Whether the container must be running (True) or can be stopped (False)

    Examples:
        # Minimal - AI completes everything:
        >>> web = AppleContainerResource(
        ...     description="lightweight nginx web server for testing"
        ... )
        # AI generates: name="nginx-server", image="nginx:alpine", ports=["80:80"]

        # Advanced - override specific fields:
        >>> api = AppleContainerResource(
        ...     description="lightweight web server for testing",
        ...     ports=["8090:80"]  # Override port
        ... )
        # AI generates: name="nginx-server", image="nginx:alpine", volumes, env_vars
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
            {"POSTGRES_PASSWORD": "secret", "POSTGRES_DB": "myapp"},
        ],
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
        """Returns True if any critical field needs AI completion.

        Only critical fields (name, image, ports) trigger AI completion.
        Optional fields (volumes, env_vars, networks) default to empty.

        Returns:
            bool: True if any critical field needs completion, False otherwise
        """
        return self.name is None or self.image is None or self.ports is None

    def to_pulumi(self):
        """Create Pulumi AppleContainer resource.

        Uses the AppleContainer dynamic provider to manage the container
        using the Apple Containers CLI. All fields should be populated by
        AI completion before this is called.

        Returns:
            AppleContainer: Pulumi dynamic resource instance

        Raises:
            ValueError: If required fields are not completed

        Example:
            # After AI completion
            >>> resource.to_pulumi()
            <AppleContainer resource with container_id output>
        """
        from clockwork.pulumi_providers.apple_container import (
            AppleContainer,
            AppleContainerInputs,
        )

        # All fields should be populated by AI completion
        if self.name is None or self.image is None:
            raise ValueError(
                f"Resource fields not completed. name={self.name}, image={self.image}"
            )

        # Create inputs for the dynamic provider
        inputs = AppleContainerInputs(
            image=self.image,
            container_name=self.name,
            ports=self.ports or [],
            volumes=self.volumes,
            env_vars=self.env_vars,
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
        container_resource = AppleContainer(
            resource_name=self.name,
            inputs=inputs,
            opts=opts,
        )

        # Store for dependency tracking
        self._pulumi_resource = container_resource

        return container_resource

    def get_connection_context(self) -> dict[str, Any]:
        """Get connection context for this Apple Container resource.

        Returns shareable fields that other resources can use when connected.
        This includes container name, image, exposed ports, environment variables,
        and networks. Only non-None/non-empty fields are included.

        Returns:
            Dict with shareable fields:
                - name: Container name
                - type: Resource class name (AppleContainerResource)
                - image: Container image (if set)
                - ports: Port mappings (if set)
                - env_vars: Environment variables (if set)
                - networks: Container networks (if set)

        Example:
            >>> container = AppleContainerResource(
            ...     name="postgres",
            ...     image="postgres:15",
            ...     ports=["5432:5432"],
            ...     env_vars={"POSTGRES_PASSWORD": "secret"}
            ... )
            >>> container.get_connection_context()
            {
                'name': 'postgres',
                'type': 'AppleContainerResource',
                'image': 'postgres:15',
                'ports': ['5432:5432'],
                'env_vars': {'POSTGRES_PASSWORD': 'secret'}
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

        return context
