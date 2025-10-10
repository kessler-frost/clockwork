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
        ports: Port mappings as list of strings (e.g., ["80:80", "443:443"])
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
        ...     ports=["80:80"]
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
        """Generate PyInfra shell operations for Apple Containers.

        Creates PyInfra operations that deploy the Apple Container with the
        specified configuration using the 'container' CLI. If the image was
        AI-generated, it will be retrieved from the artifacts dictionary.

        Args:
            artifacts: Dict mapping resource names to generated content.
                      For AppleContainerResource, should contain {"name": {"image": "image/name"}}

        Returns:
            str: PyInfra operation code as a string

        Example generated code:
            ```python
            server.shell(
                name="Deploy nginx",
                commands=[
                    "container run -d --name nginx -p 80:80 nginx:latest"
                ]
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

        # Build the container run command
        cmd_parts = ["container run -d"]

        # Add container name
        cmd_parts.append(f"--name {self.name}")

        # Add port mappings
        if self.ports:
            for port in self.ports:
                cmd_parts.append(f"-p {port}")

        # Add volume mounts
        if self.volumes:
            for volume in self.volumes:
                cmd_parts.append(f"-v {volume}")

        # Add environment variables
        if self.env_vars:
            for key, value in self.env_vars.items():
                cmd_parts.append(f"-e {key}={value}")

        # Add networks
        if self.networks:
            for network in self.networks:
                cmd_parts.append(f"--network {network}")

        # Add image
        cmd_parts.append(image)

        run_command = " ".join(cmd_parts)

        operations = []

        if self.present:
            if self.start:
                # Create and start the container
                operations.append(f'''
# Deploy Apple Container: {self.name}
server.shell(
    name="Deploy {self.name}",
    commands=[
        # Remove existing container if present
        "container rm -f {self.name} 2>/dev/null || true",
        # Run new container
        "{run_command}"
    ],
)
''')
            else:
                # Create but don't start (stopped state)
                stop_command = run_command.replace("container run -d", "container create")
                operations.append(f'''
# Create Apple Container (stopped): {self.name}
server.shell(
    name="Create {self.name} (stopped)",
    commands=[
        # Remove existing container if present
        "container rm -f {self.name} 2>/dev/null || true",
        # Create container without starting
        "{stop_command}"
    ],
)
''')
        else:
            # Container should not be present - handled in destroy
            operations.append(f'''
# Ensure Apple Container is removed: {self.name}
server.shell(
    name="Remove {self.name}",
    commands=[
        "container rm -f {self.name} 2>/dev/null || true"
    ],
)
''')

        return "\n".join(operations)

    def to_pyinfra_destroy_operations(self, artifacts: Dict[str, Any]) -> str:
        """Generate PyInfra operations code to destroy/remove the container.

        Creates PyInfra operations that remove the Apple Container using
        'container rm' command.

        Args:
            artifacts: Dict mapping resource names to generated content (unused for destroy)

        Returns:
            str: PyInfra operation code to remove the container

        Example generated code:
            ```python
            server.shell(
                name="Remove nginx",
                commands=[
                    "container rm -f nginx 2>/dev/null || true"
                ]
            )
            ```
        """
        return f'''
# Remove Apple Container: {self.name}
server.shell(
    name="Remove {self.name}",
    commands=[
        "container rm -f {self.name} 2>/dev/null || true"
    ],
)
'''

    def to_pyinfra_assert_operations(self, artifacts: Dict[str, Any]) -> str:
        """Generate PyInfra operations code for Apple Container assertions.

        Provides default assertions for AppleContainerResource:
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
            server.shell(
                name="Assert: Container nginx is running",
                commands=[
                    "container ls --filter name=^nginx$ --filter status=running ..."
                ]
            )
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
server.shell(
    name="Assert: Container {self.name} exists",
    commands=[
        "container ls -a --filter name=^{self.name}$ --format '{{{{.Names}}}}' | grep -q '^{self.name}$' || exit 1"
    ],
)
''')

            # Check if container should be running
            if self.start:
                operations.append(f'''
# Assert: Container is running
server.shell(
    name="Assert: Container {self.name} is running",
    commands=[
        "container ls --filter name=^{self.name}$ --filter status=running --format '{{{{.Names}}}}' | grep -q '^{self.name}$' || exit 1"
    ],
)
''')

        return "\n".join(operations)
