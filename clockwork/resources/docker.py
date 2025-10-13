"""Docker resource for running containers using PyInfra's native docker.container operation."""

from typing import Optional, Dict, Any, List
from .base import Resource


class DockerResource(Resource):
    """Docker resource - runs containers with AI completing all fields.

    This resource allows you to define Docker containers with just a description.
    The AI will intelligently complete all missing fields including name, image,
    ports, volumes, environment variables, and networks. Uses PyInfra's native
    docker.container operation for cross-platform Docker support.

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
    name: Optional[str] = None
    image: Optional[str] = None
    ports: Optional[List[str]] = None
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

    def to_pyinfra_operations(self) -> str:
        """Generate PyInfra operations for Docker containers.

        Creates PyInfra operations that deploy the Docker container with the
        specified configuration using PyInfra's native docker.container operation.
        All fields should be populated by AI completion before this is called.

        Returns:
            str: PyInfra operation code as a string

        Example generated code:
            ```python
            docker.container(
                name="Deploy nginx-server",
                container="nginx-server",
                image="nginx:alpine",
                ports=["80:80"],
                present=True,
                start=True,
                force=True,
            )
            ```
        """
        # All fields should be populated by AI completion
        if self.name is None or self.image is None:
            raise ValueError(f"Resource fields not completed. name={self.name}, image={self.image}")

        if not self.present:
            # Container should not be present
            return f'''
# Ensure Docker container is removed: {self.name}
docker.container(
    name="Remove {self.name}",
    container="{self.name}",
    present=False,
)
'''

        # Build parameters list
        params = [
            f'    name="Deploy {self.name}"',
            f'    container="{self.name}"',
            f'    image="{self.image}"',
            f'    present={self.present}',
            f'    start={self.start}',
            '    force=True',  # Remove existing container with same name
        ]

        if self.ports:
            ports_str = ', '.join([f'"{p}"' for p in self.ports])
            params.append(f'    ports=[{ports_str}]')

        if self.volumes:
            volumes_str = ', '.join([f'"{v}"' for v in self.volumes])
            params.append(f'    volumes=[{volumes_str}]')

        if self.env_vars:
            # PyInfra docker.container expects env_vars as list of "KEY=VALUE" strings
            env_list = [f'"{k}={v}"' for k, v in self.env_vars.items()]
            env_str = ', '.join(env_list)
            params.append(f'    env_vars=[{env_str}]')

        if self.networks:
            networks_str = ', '.join([f'"{n}"' for n in self.networks])
            params.append(f'    networks=[{networks_str}]')

        return f'''
# Deploy Docker container: {self.name}
docker.container(
{',\n'.join(params)},
)
'''

    def to_pyinfra_destroy_operations(self) -> str:
        """Generate PyInfra operations code to destroy/remove the container.

        Creates PyInfra operations that remove the Docker container using
        PyInfra's native docker.container operation with present=False.

        Returns:
            str: PyInfra operation code to remove the container

        Example generated code:
            ```python
            docker.container(
                name="Remove nginx-server",
                container="nginx-server",
                present=False,
            )
            ```
        """
        if self.name is None:
            raise ValueError("Resource name not completed")

        return f'''
# Remove Docker container: {self.name}
docker.container(
    name="Remove {self.name}",
    container="{self.name}",
    present=False,
)
'''

    def get_connection_context(self) -> Dict[str, Any]:
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

    def to_pyinfra_assert_operations(self) -> str:
        """Generate PyInfra operations code for Docker container assertions.

        Uses the base implementation which processes assertion objects.
        If no assertions are defined, returns empty string (no default assertions).

        Returns:
            str: PyInfra assertion operation code
        """
        if self.name is None:
            raise ValueError("Resource name not completed")

        # Use the base implementation (processes assertion objects only)
        return super().to_pyinfra_assert_operations()
