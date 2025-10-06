"""Docker service resource for running containers with optional AI-suggested images."""

from typing import Optional, Dict, Any, List
from .base import Resource


class DockerServiceResource(Resource):
    """Docker service resource - runs containers with AI-suggested images.

    This resource allows you to define Docker containers declaratively. If no image
    is specified, the AI will suggest an appropriate image based on the description.

    Attributes:
        name: Container name (required)
        description: What the service does - used by AI for image suggestions (required)
        image: Docker image to use (optional - AI will suggest if not provided)
        ports: Port mappings as list of strings (e.g., ["80:80", "443:443"])
        volumes: Volume mounts as list of strings (e.g., ["/host:/container"])
        env_vars: Environment variables as key-value pairs
        networks: Docker networks to attach the container to
        present: Whether the container should exist (True) or be removed (False)
        start: Whether the container should be running (True) or stopped (False)

    Examples:
        # Basic usage with AI-suggested image:
        >>> nginx = DockerServiceResource(
        ...     name="nginx",
        ...     description="Web server for serving static content",
        ...     ports=["80:80"]
        ... )

        # Explicit image specification:
        >>> redis = DockerServiceResource(
        ...     name="redis",
        ...     description="Redis cache server",
        ...     image="redis:7-alpine",
        ...     ports=["6379:6379"],
        ...     volumes=["/data:/data"]
        ... )
    """

    name: str
    description: str
    image: Optional[str] = None
    ports: Optional[List[str]] = None
    volumes: Optional[List[str]] = None
    env_vars: Optional[Dict[str, str]] = None
    networks: Optional[List[str]] = None
    present: bool = True
    start: bool = True

    def needs_artifact_generation(self) -> bool:
        """Returns True if image needs to be AI-suggested.

        When no image is specified, the AI will analyze the description and
        suggest an appropriate Docker image to use.

        Returns:
            bool: True if image is None, False otherwise
        """
        return self.image is None

    def to_pyinfra_operations(self, artifacts: Dict[str, Any]) -> str:
        """Generate PyInfra docker.container operation code.

        Creates a PyInfra operation that deploys the Docker container with the
        specified configuration. If the image was AI-generated, it will be
        retrieved from the artifacts dictionary.

        Args:
            artifacts: Dict mapping resource names to generated content.
                      For DockerServiceResource, should contain {"name": {"image": "docker/image"}}

        Returns:
            str: PyInfra operation code as a string

        Example generated code:
            ```python
            docker.container(
                name="Deploy nginx",
                container="nginx",
                image="nginx:latest",
                ports=["80:80"],
                volumes=[],
                env_vars={},
                networks=[],
                present=True,
                start=True,
            )
            ```
        """
        # Get image from artifacts if not provided
        image = self.image
        if image is None:
            artifact_data = artifacts.get(self.name, {})
            image = artifact_data.get("image") if isinstance(artifact_data, dict) else artifact_data

        # Use empty string as fallback (should not happen in practice)
        image = image or ""

        # Convert None values to empty defaults
        ports = self.ports or []
        volumes = self.volumes or []
        env_vars = self.env_vars or {}
        networks = self.networks or []

        # Format ports, volumes, and networks as Python lists
        ports_str = repr(ports)
        volumes_str = repr(volumes)
        networks_str = repr(networks)
        env_vars_str = repr(env_vars)

        return f'''
# Deploy Docker container: {self.name}
docker.container(
    name="Deploy {self.name}",
    container="{self.name}",
    image="{image}",
    ports={ports_str},
    volumes={volumes_str},
    env_vars={env_vars_str},
    networks={networks_str},
    present={self.present},
    start={self.start},
)
'''

    def to_pyinfra_destroy_operations(self, artifacts: Dict[str, Any]) -> str:
        """Generate PyInfra operations code to destroy/remove the container.

        Creates a PyInfra operation that removes the Docker container by setting
        present=False. This stops and removes the container.

        Args:
            artifacts: Dict mapping resource names to generated content (unused for destroy)

        Returns:
            str: PyInfra operation code to remove the container

        Example generated code:
            ```python
            docker.container(
                name="Remove nginx",
                container="nginx",
                present=False,
            )
            ```
        """
        return f'''
# Remove Docker container: {self.name}
docker.container(
    name="Remove {self.name}",
    container="{self.name}",
    present=False,
)
'''
