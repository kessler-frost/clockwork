"""Docker resource for running containers using Pulumi Docker provider."""

from typing import Any

import pulumi
import pulumi_docker as docker
from pydantic import Field

from .base import Resource


class DockerResource(Resource):
    """Docker resource - runs containers with AI completing all fields.

    This resource allows you to define Docker containers with just a description.
    The AI will intelligently complete all missing fields including name, image,
    ports, volumes, environment variables, and networks. Uses Pulumi Docker provider
    for cross-platform Docker support.

    Attributes:
        description: What the service does - AI uses this to complete all fields (required)
        name: Container name (optional - AI generates if not provided)
        image: Container image to use (optional - AI suggests if not provided)
        ports: Port mappings as list of strings (optional - AI determines if not provided)
        volumes: Volume mounts as list of strings (optional - AI determines if not provided)
        env_vars: Environment variables as key-value pairs (optional - AI suggests if not provided)
        networks: Container networks to attach (optional - AI determines if not provided)
        restart_policy: Container restart policy - "unless-stopped", "always", "on-failure", "no"
        must_run: Whether the container must be running (True) or can be stopped (False)

    Note:
        Images must have a proper CMD or ENTRYPOINT. Use images like nginx, postgres,
        redis, or build custom images beforehand. Base images like python:3.11-slim
        without CMD will exit immediately.

    Examples:
        # Minimal - AI completes everything:
        >>> web = DockerResource(
        ...     description="lightweight nginx web server for testing"
        ... )
        # AI generates: name="nginx-server", image="nginx:alpine", ports=["80:80"]

        # Advanced - override specific fields:
        >>> api = DockerResource(
        ...     description="lightweight web server for testing",
        ...     ports=["8090:80"]  # Override port
        ... )
        # AI generates: name="nginx-server", image="nginx:alpine", volumes, env_vars
    """

    description: str
    name: str | None = Field(
        None,
        description="Container name - must be unique",
        examples=["nginx-server", "postgres-db", "redis-cache"],
    )
    image: str | None = Field(
        None,
        description="Docker image with tag - prefer official, well-maintained images",
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
        description="Docker networks to attach container to",
        examples=[["backend"], ["frontend", "backend"]],
    )
    restart_policy: str = Field(
        default="unless-stopped",
        description="Container restart policy: 'unless-stopped', 'always', 'on-failure', 'no'",
        examples=["unless-stopped", "always", "no"],
    )
    must_run: bool = Field(
        default=True,
        description="Whether the container must be running after creation",
    )

    # Store Pulumi resource for dependency tracking
    _pulumi_resource: pulumi.Resource | None = None

    def needs_completion(self) -> bool:
        """Returns True if any critical field needs AI completion.

        Only critical fields (name, image, ports) trigger AI completion.
        Optional fields (volumes, env_vars, networks) default to empty.

        Returns:
            bool: True if any critical field needs completion, False otherwise
        """
        return self.name is None or self.image is None or self.ports is None

    def to_pulumi(self) -> pulumi.Resource:
        """Convert to Pulumi Docker Container resource.

        Creates a Pulumi Docker Container resource with all configured parameters.
        All required fields should be populated by AI completion before this is called.

        Returns:
            pulumi.Resource: Pulumi Docker Container resource

        Raises:
            ValueError: If required fields (name, image) are not completed

        Example:
            >>> container = DockerResource(
            ...     name="nginx",
            ...     image="nginx:alpine",
            ...     ports=["8080:80"],
            ...     volumes=["data:/data"],
            ...     env_vars={"DEBUG": "1"}
            ... )
            >>> pulumi_container = container.to_pulumi()
        """
        # Validate required fields
        if self.name is None or self.image is None:
            raise ValueError(
                f"Resource not completed: name={self.name}, image={self.image}"
            )

        # Parse port mappings: ["8080:80"] -> ContainerPortArgs
        ports = []
        if self.ports:
            for port_mapping in self.ports:
                # Format: "external:internal" or "internal"
                parts = port_mapping.split(":")
                if len(parts) == 2:
                    external, internal = parts
                    ports.append(
                        docker.ContainerPortArgs(
                            internal=int(internal),
                            external=int(external),
                            protocol="tcp",
                        )
                    )
                elif len(parts) == 1:
                    # Just internal port, let Docker assign external
                    ports.append(
                        docker.ContainerPortArgs(
                            internal=int(parts[0]), protocol="tcp"
                        )
                    )

        # Parse volume mappings: ["host:/container"] -> ContainerVolumeArgs
        volumes = []
        if self.volumes:
            for volume_mapping in self.volumes:
                # Format: "host_path:container_path" or "host_path:container_path:ro"
                parts = volume_mapping.split(":")
                if len(parts) >= 2:
                    host_path = parts[0]
                    container_path = parts[1]
                    read_only = len(parts) == 3 and parts[2] == "ro"
                    volumes.append(
                        docker.ContainerVolumeArgs(
                            host_path=host_path,
                            container_path=container_path,
                            read_only=read_only,
                        )
                    )

        # Convert env_vars dict to list of "KEY=VALUE" strings
        envs = (
            [f"{k}={v}" for k, v in self.env_vars.items()]
            if self.env_vars
            else []
        )

        # Convert networks to ContainerNetworksAdvancedArgs
        networks_advanced = []
        if self.networks:
            for network_name in self.networks:
                networks_advanced.append(
                    docker.ContainerNetworksAdvancedArgs(name=network_name)
                )

        # Build resource options for dependencies
        dep_opts = self._build_dependency_options()

        # Check if we have temporary compile options (from _compile_with_opts)
        # This allows this resource to be a child in a composite
        if hasattr(self, "_temp_compile_opts"):
            # Merge with dependency options
            opts = self._merge_resource_options(
                self._temp_compile_opts, dep_opts
            )
        else:
            opts = dep_opts

        # Create Pulumi Docker Container resource
        container = docker.Container(
            self.name,
            image=self.image,
            name=self.name,
            ports=ports if ports else None,
            volumes=volumes if volumes else None,
            envs=envs if envs else None,
            networks_advanced=networks_advanced if networks_advanced else None,
            restart=self.restart_policy,
            must_run=self.must_run,
            opts=opts,
        )

        # Store for dependency tracking
        self._pulumi_resource = container

        return container

    def get_connection_context(self) -> dict[str, Any]:
        """Get connection context for this Docker resource.

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

        Example:
            >>> container = DockerResource(
            ...     name="postgres",
            ...     image="postgres:15",
            ...     ports=["5432:5432"],
            ...     env_vars={"POSTGRES_PASSWORD": "secret"}
            ... )
            >>> container.get_connection_context()
            {
                'name': 'postgres',
                'type': 'DockerResource',
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
