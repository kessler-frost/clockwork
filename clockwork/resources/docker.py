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
    volumes: Optional[List[str]] = None
    env_vars: Optional[Dict[str, str]] = None
    networks: Optional[List[str]] = None
    present: bool = True
    start: bool = True

    def needs_completion(self) -> bool:
        """Returns True if any field needs AI completion.

        When any of the key fields are None, the AI will analyze the description
        and intelligently suggest appropriate values for all missing fields.

        Returns:
            bool: True if any field needs completion, False otherwise
        """
        return (
            self.name is None or
            self.image is None or
            self.ports is None or
            self.volumes is None or
            self.env_vars is None or
            self.networks is None
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

    def to_pyinfra_assert_operations(self) -> str:
        """Generate PyInfra operations code for Docker container assertions.

        Provides default assertions for DockerResource using PyInfra facts:
        - Container exists (if present=True)
        - Container is running (if start=True)

        These can be overridden by specifying custom assertions.

        Returns:
            str: PyInfra assertion operation code

        Example generated code:
            ```python
            # Default assertions for Docker container: nginx-server
            from pyinfra.facts.docker import DockerContainer

            containers = host.get_fact(DockerContainer)
            container = containers.get("nginx-server")
            assert container is not None, "Container nginx-server does not exist"
            assert container.get("running"), "Container nginx-server is not running"
            ```
        """
        if self.name is None:
            raise ValueError("Resource name not completed")

        # If custom assertions are defined, use the base implementation
        if self.assertions:
            return super().to_pyinfra_assert_operations()

        operations = []
        operations.append(f"\n# Default assertions for Docker container: {self.name}")

        # Check if container should be present
        if self.present:
            operations.append(f'''
# Assert: Container exists
from pyinfra.api import host
from pyinfra.facts.docker import DockerContainer

containers = host.get_fact(DockerContainer)
container = containers.get("{self.name}")
if container is None:
    raise Exception("Container {self.name} does not exist")
''')

            # Check if container should be running
            if self.start:
                operations.append(f'''
# Assert: Container is running
if not container.get("running"):
    raise Exception("Container {self.name} is not running")
''')

        return "\n".join(operations)
