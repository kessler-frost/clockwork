"""Apple Container resource for running containers with optional AI-suggested images."""

from typing import Optional, Dict, Any, List
from .base import Resource


class AppleContainerResource(Resource):
    """Apple Container resource - runs containers with AI-suggested images.

    This resource allows you to define Apple Containers declaratively. If no image
    is specified, the AI will suggest an appropriate image based on the description.

    Attributes:
        name: Container name (required)
        description: What the service does - used by AI for image suggestions (required)
        image: Container image to use (optional - AI will suggest if not provided)
        ports: Port mappings as list of strings (e.g., ["8080:80", "8443:443"])
        volumes: Volume mounts as list of strings (e.g., ["/host:/container"])
        env_vars: Environment variables as key-value pairs
        networks: Container networks to attach the container to
        present: Whether the container should exist (True) or be removed (False)
        start: Whether the container should be running (True) or stopped (False)

    Examples:
        # Basic usage with AI-suggested image:
        >>> nginx = AppleContainerResource(
        ...     name="nginx",
        ...     description="Web server for serving static content",
        ...     ports=["8080:80"]
        ... )

        # Explicit image specification:
        >>> redis = AppleContainerResource(
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
        suggest an appropriate container image to use.

        Returns:
            bool: True if image is None, False otherwise
        """
        return self.image is None

    def to_pyinfra_operations(self, artifacts: Dict[str, Any]) -> str:
        """Generate PyInfra operations for Apple Containers.

        Creates PyInfra operations that deploy the Apple Container with the
        specified configuration using custom apple_containers operations.
        If the image was AI-generated, it will be retrieved from the artifacts dictionary.

        Args:
            artifacts: Dict mapping resource names to generated content.
                      For AppleContainerResource, should contain {"name": {"image": "image/name"}}

        Returns:
            str: PyInfra operation code as a string

        Example generated code:
            ```python
            apple_containers.container_run(
                name="Deploy nginx",
                image="nginx:latest",
                container_name="nginx",
                ports=["8080:80"],
                detach=True,
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
                    f'    image="{image}"',
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
                    f'    image="{image}"',
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

    def to_pyinfra_destroy_operations(self, artifacts: Dict[str, Any]) -> str:
        """Generate PyInfra operations code to destroy/remove the container.

        Creates PyInfra operations that remove the Apple Container using
        the custom apple_containers.container_remove operation.

        Args:
            artifacts: Dict mapping resource names to generated content (unused for destroy)

        Returns:
            str: PyInfra operation code to remove the container

        Example generated code:
            ```python
            apple_containers.container_remove(
                name="Remove nginx",
                container_id="nginx",
                force=True,
            )
            ```
        """
        return f'''
# Remove Apple Container: {self.name}
apple_containers.container_remove(
    name="Remove {self.name}",
    container_id="{self.name}",
    force=True,
)
'''

    def to_pyinfra_assert_operations(self, artifacts: Dict[str, Any]) -> str:
        """Generate PyInfra operations code for Apple Container assertions.

        Provides default assertions for AppleContainerResource using custom facts:
        - Container is running (if start=True)
        - Container exists (if present=True)

        These can be overridden by specifying custom assertions.

        Args:
            artifacts: Dict mapping resource names to generated content

        Returns:
            str: PyInfra assertion operation code

        Example generated code:
            ```python
            # Default assertions for Apple Container: nginx
            from pyinfra.facts.server import Command

            status = host.get_fact(ContainerStatus, container_id="nginx")
            assert status is not None, "Container nginx does not exist"
            assert status.get("running"), "Container nginx is not running"
            ```
        """
        # If custom assertions are defined, use the base implementation
        if self.assertions:
            return super().to_pyinfra_assert_operations(artifacts)

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
