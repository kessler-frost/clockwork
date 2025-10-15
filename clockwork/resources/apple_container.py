"""Apple Container resource for running containers with optional AI-suggested images."""

from typing import Optional, Dict, Any, List
from .base import Resource
import pulumi


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
        present: Whether the container should exist (True) or be removed (False)
        start: Whether the container should be running (True) or stopped (False)

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

    description: str
    name: str | None = None
    image: str | None = None
    ports: List[str] | None = None
    volumes: List[str] = []  # Optional - defaults to empty
    env_vars: Dict[str, str] = {}  # Optional - defaults to empty
    networks: List[str] = []  # Optional - defaults to empty
    present: bool = True
    start: bool = True

    def needs_completion(self) -> bool:
        """Returns True if any critical field needs AI completion.

        Only critical fields (name, image, ports) trigger AI completion.
        Optional fields (volumes, env_vars, networks) default to empty.

        Returns:
            bool: True if any critical field needs completion, False otherwise
        """
        return (
            self.name is None or
            self.image is None or
            self.ports is None
        )

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
            present=self.present,
            start=self.start,
        )

        # Create and return the Pulumi resource
        return AppleContainer(
            resource_name=self.name,
            inputs=inputs,
            opts=pulumi.ResourceOptions(),
        )

    def get_connection_context(self) -> Dict[str, Any]:
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
