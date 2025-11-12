"""File connection for sharing files and volumes between resources."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import pulumi
import pulumi_docker as docker
from pydantic import Field

from .base import Connection

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class FileConnection(Connection):
    """File connection - shares files or volumes between resources.

    This connection enables file sharing between resources, typically for
    configuration files, shared data, or persistent storage. It can:
    - Mount host paths as bind mounts
    - Create and mount Docker volumes
    - Share FileResource outputs to containers

    The connection can be AI-completed to determine mount paths and volume names.

    Attributes:
        mount_path: Where to mount in from_resource (required for completion)
        source_path: Path in to_resource (if FileResource) or host path for bind mount
        volume_name: Docker volume name (can be AI-generated)
        read_only: Mount as read-only (default: False)
        create_volume: Auto-create Docker volume if it doesn't exist (default: True)
        volume_driver: Volume driver to use (default: "local")

    Examples:
        # Share a volume between containers (AI completes mount_path and volume_name)
        storage = AppleContainerResource(name="storage", description="storage container")
        app = AppleContainerResource(name="app", description="app container")
        connection = FileConnection(
            to_resource=storage,
            description="shared data volume"
        )
        app.connect(connection)

        # Mount a FileResource to a container
        config = FileResource(
            description="nginx config",
            directory="./config"
        )
        web = AppleContainerResource(name="nginx", image="nginx:alpine")
        connection = FileConnection(
            to_resource=config,
            mount_path="/etc/nginx/nginx.conf",
            read_only=True
        )
        web.connect(connection)

        # Bind mount with explicit paths
        app = AppleContainerResource(name="app", description="web app")
        connection = FileConnection(
            to_resource=None,  # No target resource for bind mounts
            mount_path="/data",
            source_path="/host/data",
            create_volume=False
        )
        app.connect(connection)
    """

    mount_path: str | None = Field(
        default=None,
        description="Target mount path in from_resource container",
        examples=["/data", "/etc/config", "/var/lib/postgres"],
    )
    source_path: str | None = Field(
        default=None,
        description="Source path - host path for bind mount or path in to_resource if FileResource",
    )
    volume_name: str | None = Field(
        default=None,
        description="Docker volume name - AI can generate based on context",
        examples=["app-data", "postgres-data", "shared-config"],
    )
    read_only: bool = Field(
        default=False,
        description="Mount as read-only",
    )
    create_volume: bool = Field(
        default=True,
        description="Auto-create Docker volume if it doesn't exist",
    )
    volume_driver: str = Field(
        default="local",
        description="Docker volume driver",
        examples=["local", "nfs", "cifs"],
    )

    def needs_completion(self) -> bool:
        """Check if this connection needs AI completion.

        Returns True if description is provided but mount_path is missing,
        or if we need to create a volume but volume_name is missing.

        Returns:
            bool: True if AI completion is needed, False otherwise
        """
        # If no description, no AI completion needed
        if not self.description:
            return False

        # Need completion if mount_path is missing or if we want a volume but don't have a name
        return self.mount_path is None or (
            self.create_volume
            and not self.source_path
            and self.volume_name is None
        )

    def to_pulumi(self) -> list[pulumi.Resource] | None:
        """Create Pulumi resources for the file connection.

        This method:
        1. Determines mount type (bind mount or volume)
        2. Creates Docker volume if needed
        3. Modifies from_resource to add volume mount
        4. Handles FileResource source files

        Returns:
            List of Pulumi resources created, or None if no resources needed
        """
        from clockwork.resources.apple_container import AppleContainerResource
        from clockwork.resources.file import FileResource

        resources = []

        # Validate mount_path is set
        if not self.mount_path:
            logger.warning(
                f"FileConnection for {getattr(self.from_resource, 'name', 'unknown')} "
                f"missing mount_path - skipping"
            )
            return None

        # Determine source for the mount
        mount_source = None

        # Case 1: FileResource as to_resource
        if isinstance(self.to_resource, FileResource):
            # Use the file's resolved path as source
            if self.to_resource.path:
                mount_source = self.to_resource.path
            elif self.to_resource.name and self.to_resource.directory:
                from pathlib import Path

                mount_source = str(
                    Path(self.to_resource.directory) / self.to_resource.name
                )
            else:
                logger.warning(
                    f"FileResource {self.to_resource.name} path cannot be determined"
                )
                return None

        # Case 2: Explicit source_path (bind mount)
        elif self.source_path:
            mount_source = self.source_path

        # Case 3: Docker volume
        elif self.volume_name:
            # Create volume if requested
            if self.create_volume:
                # Build dependency options
                opts = self._build_dependency_options()

                volume = docker.Volume(
                    self.volume_name,
                    driver=self.volume_driver,
                    name=self.volume_name,
                    opts=opts,
                )
                resources.append(volume)
                logger.info(f"Created Docker volume: {self.volume_name}")

            mount_source = self.volume_name
        else:
            logger.warning(
                "FileConnection has no source_path, volume_name, or FileResource - skipping"
            )
            return None

        # Add mount to from_resource if it's a AppleContainerResource
        if isinstance(self.from_resource, AppleContainerResource):
            # Determine mount type for logging
            mount_type = (
                "bind"
                if (
                    self.source_path
                    or isinstance(self.to_resource, FileResource)
                )
                else "volume"
            )

            # Modify the container's volumes list
            # Convert mount to volume string format: "source:target" or "source:target:ro"
            volume_str = f"{mount_source}:{self.mount_path}"
            if self.read_only:
                volume_str += ":ro"

            self.from_resource.volumes.append(volume_str)

            logger.info(
                f"Added {mount_type} mount to {self.from_resource.name}: "
                f"{mount_source} -> {self.mount_path}"
            )

        else:
            logger.warning(
                f"from_resource {getattr(self.from_resource, 'name', 'unknown')} "
                f"is not a AppleContainerResource - cannot add mount"
            )

        # Store created resources
        self._pulumi_resources = resources

        return resources if resources else None

    def get_connection_context(self) -> dict[str, Any]:
        """Get connection context for AI completion.

        Provides information about the file connection including mount paths,
        volume names, and mount type for AI to use when completing missing fields.

        Returns:
            Dict with connection details
        """
        context = super().get_connection_context()

        context.update(
            {
                "connection_type": "file",
                "mount_path": self.mount_path,
                "source_path": self.source_path,
                "volume_name": self.volume_name,
                "read_only": self.read_only,
                "create_volume": self.create_volume,
            }
        )

        # Add to_resource path if it's a FileResource
        if hasattr(self.to_resource, "path") and self.to_resource.path:
            context["file_path"] = self.to_resource.path

        return context
