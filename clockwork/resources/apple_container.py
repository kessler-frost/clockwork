"""Apple Container resource for running containers with optional AI-suggested images."""

from typing import Optional, Dict, Any, List
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

    def needs_artifact_generation(self) -> bool:
        """Alias for needs_completion() for compatibility with base class.

        Returns:
            bool: True if any field needs AI completion
        """
        return self.needs_completion()

    def to_pyinfra_operations(self) -> str:
        """Generate PyInfra operations for Apple Containers.

        Creates PyInfra operations that deploy the Apple Container with the
        specified configuration using custom apple_containers operations.
        All fields should be populated by AI completion before this is called.

        Returns:
            str: PyInfra operation code as a string

        Example generated code:
            ```python
            apple_containers.container_run(
                name="Deploy nginx-server",
                image="nginx:alpine",
                container_name="nginx-server",
                ports=["80:80"],
                detach=True,
            )
            ```
        """
        # All fields should be populated by AI completion
        if self.name is None or self.image is None:
            raise ValueError(f"Resource fields not completed. name={self.name}, image={self.image}")

        operations = []

        if self.present:
            # First, remove existing container if present
            operations.append(f'''
# Remove existing container if present: {self.name}
apple_containers.container_remove(
    name="Remove existing {self.name}",
    container_id="{self.name}",
    force=True,
)
''')

            if self.start:
                # Create and start the container
                params = [
                    f'    image="{self.image}"',
                    f'    name="{self.name}"',
                    '    detach=True',
                ]

                if self.ports:
                    ports_str = ', '.join([f'"{p}"' for p in self.ports])
                    params.append(f'    ports=[{ports_str}]')

                if self.volumes:
                    volumes_str = ', '.join([f'"{v}"' for v in self.volumes])
                    params.append(f'    volumes=[{volumes_str}]')

                if self.env_vars:
                    env_items = ', '.join([f'"{k}": "{v}"' for k, v in self.env_vars.items()])
                    params.append(f'    env_vars={{{env_items}}}')

                if self.networks:
                    networks_str = ', '.join([f'"{n}"' for n in self.networks])
                    params.append(f'    networks=[{networks_str}]')

                operations.append(f'''
# Deploy Apple Container: {self.name}
apple_containers.container_run(
{',\n'.join(params)},
)
''')
            else:
                # Create but don't start (stopped state)
                params = [
                    f'    image="{self.image}"',
                    f'    name="{self.name}"',
                ]

                if self.ports:
                    ports_str = ', '.join([f'"{p}"' for p in self.ports])
                    params.append(f'    ports=[{ports_str}]')

                if self.volumes:
                    volumes_str = ', '.join([f'"{v}"' for v in self.volumes])
                    params.append(f'    volumes=[{volumes_str}]')

                if self.env_vars:
                    env_items = ', '.join([f'"{k}": "{v}"' for k, v in self.env_vars.items()])
                    params.append(f'    env_vars={{{env_items}}}')

                if self.networks:
                    networks_str = ', '.join([f'"{n}"' for n in self.networks])
                    params.append(f'    networks=[{networks_str}]')

                operations.append(f'''
# Create Apple Container (stopped): {self.name}
apple_containers.container_create(
{',\n'.join(params)},
)
''')
        else:
            # Container should not be present
            operations.append(f'''
# Ensure Apple Container is removed: {self.name}
apple_containers.container_remove(
    name="Remove {self.name}",
    container_id="{self.name}",
    force=True,
)
''')

        return "\n".join(operations)

    def to_pyinfra_destroy_operations(self) -> str:
        """Generate PyInfra operations code to destroy/remove the container.

        Creates PyInfra operations that remove the Apple Container using
        the custom apple_containers.container_remove operation.

        Returns:
            str: PyInfra operation code to remove the container

        Example generated code:
            ```python
            apple_containers.container_remove(
                name="Remove nginx-server",
                container_id="nginx-server",
                force=True,
            )
            ```
        """
        if self.name is None:
            raise ValueError("Resource name not completed")

        return f'''
# Remove Apple Container: {self.name}
apple_containers.container_remove(
    name="Remove {self.name}",
    container_id="{self.name}",
    force=True,
)
'''

    def to_pyinfra_assert_operations(self) -> str:
        """Generate PyInfra operations code for Apple Container assertions.

        Provides default assertions for AppleContainerResource using custom facts:
        - Container is running (if start=True)
        - Container exists (if present=True)

        These can be overridden by specifying custom assertions.

        Returns:
            str: PyInfra assertion operation code

        Example generated code:
            ```python
            # Default assertions for Apple Container: nginx-server
            from pyinfra.facts.server import Command

            status = host.get_fact(ContainerStatus, container_id="nginx-server")
            assert status is not None, "Container nginx-server does not exist"
            assert status.get("running"), "Container nginx-server is not running"
            ```
        """
        if self.name is None:
            raise ValueError("Resource name not completed")

        # If custom assertions are defined, use the base implementation
        if self.assertions:
            return super().to_pyinfra_assert_operations()

        operations = []
        operations.append(f"\n# Default assertions for Apple Container: {self.name}")

        # Check if container should be present
        if self.present:
            operations.append(f'''
# Assert: Container exists
from clockwork.pyinfra_facts.apple_containers import ContainerExists

container_exists = host.get_fact(ContainerExists, container_id="{self.name}")
if not container_exists:
    raise Exception("Container {self.name} does not exist")
''')

            # Check if container should be running
            if self.start:
                operations.append(f'''
# Assert: Container is running
from clockwork.pyinfra_facts.apple_containers import ContainerRunning

container_running = host.get_fact(ContainerRunning, container_id="{self.name}")
if not container_running:
    raise Exception("Container {self.name} is not running")
''')

        return "\n".join(operations)
