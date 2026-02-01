"""Pulumi dynamic provider for Docker containers.

This module provides a Pulumi dynamic provider for managing containers using
the Docker CLI (docker command), available on Linux, macOS, and Windows.
"""

import asyncio
import json
import logging
import re
from typing import Any

import pulumi
from pulumi.dynamic import (
    CreateResult,
    DiffResult,
    ResourceProvider,
    UpdateResult,
)
from pydantic import BaseModel, Field, field_validator, model_validator

logger = logging.getLogger(__name__)


class DockerContainerInputs(BaseModel):
    """Input properties for DockerContainer resource.

    Attributes:
        image: Container image name (e.g., "nginx:latest")
        container_name: Logical container name for tracking
        ports: Port mappings in format ["host:container", ...]
        volumes: Volume mounts in format ["host:container", ...]
        env_vars: Environment variables as dict {"KEY": "value"}
        command: Command to run in the container
        networks: Networks to attach container to
        memory: Memory limit (e.g., "512m", "1g")
        cpus: Number of CPUs to allocate
        user: User to run as (format: "name|uid[:gid]")
        workdir: Working directory inside container
        labels: Labels to add to container {"key": "value"}
        must_run: Whether the container must be running (True) or can be stopped (False)
    """

    image: str = Field(
        ..., description="Container image name (e.g., 'nginx:latest')"
    )
    container_name: str = Field(
        ..., description="Logical container name for tracking"
    )
    ports: list[str] = Field(
        default_factory=list,
        description="Port mappings in format ['host:container', ...]",
    )
    volumes: list[str] = Field(
        default_factory=list,
        description="Volume mounts in format ['host:container', ...]",
    )
    env_vars: dict[str, str] = Field(
        default_factory=dict, description="Environment variables"
    )
    command: str | None = Field(None, description="Command to run in container")
    networks: list[str] = Field(
        default_factory=list, description="Networks to attach container to"
    )
    memory: str | None = Field(
        None, description="Memory limit (e.g., '512m', '1g')"
    )
    cpus: str | None = Field(None, description="Number of CPUs to allocate")
    user: str | None = Field(None, description="User to run as")
    workdir: str | None = Field(
        None, description="Working directory inside container"
    )
    labels: dict[str, str] = Field(
        default_factory=dict, description="Container labels"
    )
    must_run: bool = Field(
        True,
        description="Whether the container must be running (True) or can be stopped",
    )

    @field_validator("ports", mode="before")
    @classmethod
    def validate_ports(cls, v: list[str] | None) -> list[str]:
        """Validate port format is 'host:container'."""
        if v is None:
            return []
        for port in v:
            if ":" not in port:
                raise ValueError(
                    f"Port must be in 'host:container' format, got: {port}"
                )
        return v

    @field_validator("memory", mode="before")
    @classmethod
    def validate_memory(cls, v: str | None) -> str | None:
        """Validate memory format (e.g., '512m', '1g')."""
        if v and not re.match(r"^\d+[kmgb]?$", v, re.IGNORECASE):
            raise ValueError(
                f"Invalid memory format: {v}. Use format like '512m' or '1g'."
            )
        return v

    @model_validator(mode="after")
    def add_tracking_label(self) -> "DockerContainerInputs":
        """Add clockwork.name label for tracking."""
        if "clockwork.name" not in self.labels:
            # Create a new dict to avoid mutating the default
            self.labels = {**self.labels, "clockwork.name": self.container_name}
        return self


class DockerContainerProvider(ResourceProvider):
    """Pulumi dynamic provider for Docker containers.

    This provider manages containers using the Docker CLI (docker command)
    via subprocess calls. It supports create, update (via replace), delete, and diff
    operations.
    """

    async def _run_command(self, cmd: list[str]) -> dict[str, Any]:
        """Run a Docker CLI command and return the result.

        Args:
            cmd: Command parts to execute

        Returns:
            Dict with 'returncode', 'stdout', 'stderr'

        Raises:
            Exception: If command fails
        """
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout_bytes, stderr_bytes = await process.communicate()

            return {
                "returncode": process.returncode,
                "stdout": stdout_bytes.decode().strip(),
                "stderr": stderr_bytes.decode().strip(),
            }
        except Exception as e:
            raise Exception(
                f"Failed to run command {' '.join(cmd)}: {e!s}"
            ) from e

    async def _find_container_by_name(self, container_name: str) -> str | None:
        """Find container ID by name.

        Args:
            container_name: Container name

        Returns:
            Container ID if found, None otherwise
        """
        result = await self._run_command(
            [
                "docker",
                "ps",
                "-a",
                "--filter",
                f"name=^/{container_name}$",
                "--format",
                "{{.ID}}",
            ]
        )
        if result["returncode"] != 0:
            return None

        container_id = result["stdout"].strip()
        return container_id if container_id else None

    async def _find_container_by_label(self, container_name: str) -> str | None:
        """Find container ID by clockwork.name label.

        Args:
            container_name: Logical container name

        Returns:
            Container ID if found, None otherwise
        """
        result = await self._run_command(
            [
                "docker",
                "ps",
                "-a",
                "--filter",
                f"label=clockwork.name={container_name}",
                "--format",
                "{{.ID}}",
            ]
        )
        if result["returncode"] != 0:
            return None

        container_id = result["stdout"].strip()
        return container_id if container_id else None

    def _build_common_options(self, props: dict[str, Any]) -> list[str]:
        """Build common container options from properties.

        Args:
            props: Container properties

        Returns:
            Command options as list
        """
        options = []

        # Add container name
        if props.get("container_name"):
            options.extend(["--name", props["container_name"]])

        # Add resource limits
        if props.get("memory"):
            options.extend(["--memory", props["memory"]])
        if props.get("cpus"):
            options.extend(["--cpus", props["cpus"]])

        # Add user and workdir
        if props.get("user"):
            options.extend(["--user", props["user"]])
        if props.get("workdir"):
            options.extend(["--workdir", props["workdir"]])

        # Add port mappings
        for port in props.get("ports", []):
            options.extend(["-p", port])

        # Add volume mounts
        for volume in props.get("volumes", []):
            options.extend(["-v", volume])

        # Add environment variables
        for key, value in props.get("env_vars", {}).items():
            options.extend(["-e", f"{key}={value}"])

        # Add networks (only first one for run command, others added later)
        networks = props.get("networks", [])
        if networks:
            options.extend(["--network", networks[0]])

        # Add labels
        for key, value in props.get("labels", {}).items():
            options.extend(["--label", f"{key}={value}"])

        return options

    def _build_run_command(self, props: dict[str, Any]) -> list[str]:
        """Build docker run command from properties.

        Args:
            props: Container properties

        Returns:
            Command parts as list
        """
        cmd = ["docker", "run", "-d"]  # Always detached
        cmd.extend(self._build_common_options(props))
        cmd.append(props["image"])

        # Add command if specified
        if props.get("command"):
            # Split command into parts for shell execution
            cmd.extend(props["command"].split())

        return cmd

    async def _connect_additional_networks(
        self, container_id: str, networks: list[str]
    ) -> None:
        """Connect container to additional networks (beyond the first one).

        Args:
            container_id: Container ID
            networks: List of networks (first already connected via run)
        """
        # Skip first network (already connected via --network in run command)
        for network in networks[1:]:
            result = await self._run_command(
                ["docker", "network", "connect", network, container_id]
            )
            if result["returncode"] != 0:
                # Network might not exist, try to create it
                create_result = await self._run_command(
                    ["docker", "network", "create", network]
                )
                if create_result["returncode"] == 0:
                    # Retry connection
                    retry_result = await self._run_command(
                        ["docker", "network", "connect", network, container_id]
                    )
                    if retry_result["returncode"] != 0:
                        logger.warning(
                            f"Failed to connect container {container_id} to network {network}: "
                            f"{retry_result['stderr']}"
                        )
                else:
                    logger.warning(
                        f"Failed to create network {network}: {create_result['stderr']}"
                    )

    async def _create_async(self, props: dict[str, Any]) -> CreateResult:
        """Async implementation of create.

        Args:
            props: Container properties

        Returns:
            CreateResult with container ID

        Raises:
            Exception: If creation fails
        """
        container_name = props["container_name"]

        # Check if container already exists by name
        existing_id = await self._find_container_by_name(container_name)
        if not existing_id:
            # Try finding by label
            existing_id = await self._find_container_by_label(container_name)

        if existing_id:
            # Check if it's running
            inspect_result = await self._run_command(
                [
                    "docker",
                    "inspect",
                    existing_id,
                    "--format",
                    "{{.State.Running}}",
                ]
            )
            if inspect_result["returncode"] == 0:
                is_running = inspect_result["stdout"].strip().lower() == "true"
                if is_running and props.get("must_run", True):
                    # Already running, return existing ID
                    return CreateResult(id_=existing_id, outs=props)
                elif not props.get("must_run", True) and not is_running:
                    # Container exists and stopped, we don't want it running
                    return CreateResult(id_=existing_id, outs=props)

            # Remove existing container
            await self._run_command(["docker", "rm", "-f", existing_id])

        if props.get("must_run", True):
            # Create and start the container
            cmd = self._build_run_command(props)
            result = await self._run_command(cmd)

            if result["returncode"] != 0:
                raise Exception(
                    f"Failed to create container: {result['stderr']}"
                )

            # Container ID is in stdout
            container_id = result["stdout"].strip()

            # Connect to additional networks
            networks = props.get("networks", [])
            if len(networks) > 1:
                await self._connect_additional_networks(container_id, networks)

            return CreateResult(id_=container_id, outs=props)
        else:
            # Create but don't start (use docker create)
            cmd = ["docker", "create"]
            cmd.extend(self._build_common_options(props))
            cmd.append(props["image"])

            if props.get("command"):
                cmd.extend(props["command"].split())

            result = await self._run_command(cmd)

            if result["returncode"] != 0:
                raise Exception(
                    f"Failed to create container: {result['stderr']}"
                )

            container_id = result["stdout"].strip()
            return CreateResult(id_=container_id, outs=props)

    def create(self, props: dict[str, Any]) -> CreateResult:
        """Create a new container.

        Args:
            props: Container properties

        Returns:
            CreateResult with container ID

        Raises:
            Exception: If creation fails
        """
        return asyncio.run(self._create_async(props))

    async def _read_async(
        self, id: str, props: dict[str, Any]
    ) -> dict[str, Any]:
        """Async implementation of read.

        Args:
            id: Container ID
            props: Container properties

        Returns:
            Current container properties
        """
        container_name = props.get("container_name")

        # Try to find container by label first, then by name
        actual_id = id
        if container_name:
            found_id = await self._find_container_by_label(container_name)
            if not found_id:
                found_id = await self._find_container_by_name(container_name)
            if found_id:
                actual_id = found_id

        # Get container info
        result = await self._run_command(["docker", "inspect", actual_id])

        if result["returncode"] != 0:
            # Container doesn't exist
            return props

        try:
            data = json.loads(result["stdout"])
            if data and isinstance(data, list) and len(data) > 0:
                container_info = data[0]
                # Update props with actual values
                props["container_id"] = actual_id
                props["status"] = container_info.get("State", {}).get("Status")
        except json.JSONDecodeError as e:
            # Log but continue - Docker may have returned unexpected output
            logger.warning(
                f"Failed to parse docker inspect output for {actual_id}: {e}"
            )
        except KeyError as e:
            logger.warning(
                f"Unexpected docker inspect schema for {actual_id}: missing key {e}"
            )

        return props

    def read(self, id: str, props: dict[str, Any]) -> dict[str, Any]:
        """Read current container state.

        Args:
            id: Container ID
            props: Container properties

        Returns:
            Current container properties
        """
        return asyncio.run(self._read_async(id, props))

    async def _update_async(
        self, id: str, old_props: dict[str, Any], new_props: dict[str, Any]
    ) -> UpdateResult:
        """Async implementation of update.

        Args:
            id: Container ID
            old_props: Old properties
            new_props: New properties

        Returns:
            UpdateResult with new properties
        """
        # Delete the old container
        await self._delete_async(id, old_props)

        # Create new container
        create_result = await self._create_async(new_props)

        return UpdateResult(outs=create_result.outs)

    def update(
        self, id: str, old_props: dict[str, Any], new_props: dict[str, Any]
    ) -> UpdateResult:
        """Update a container by recreating it.

        Args:
            id: Container ID
            old_props: Old properties
            new_props: New properties

        Returns:
            UpdateResult with new properties
        """
        return asyncio.run(self._update_async(id, old_props, new_props))

    async def _delete_async(self, id: str, props: dict[str, Any]) -> None:
        """Async implementation of delete.

        Args:
            id: Container ID
            props: Container properties
        """
        container_name = props.get("container_name")

        # Try to find container by label first, then by name
        actual_id = id
        if container_name:
            found_id = await self._find_container_by_label(container_name)
            if not found_id:
                found_id = await self._find_container_by_name(container_name)
            if found_id:
                actual_id = found_id

        # Check if container exists
        inspect_result = await self._run_command(
            ["docker", "inspect", actual_id]
        )
        if inspect_result["returncode"] != 0:
            # Container doesn't exist, nothing to do
            return

        # Stop container first (if running)
        await self._run_command(["docker", "stop", actual_id])

        # Remove container
        result = await self._run_command(["docker", "rm", "-f", actual_id])

        if result["returncode"] != 0:
            raise Exception(f"Failed to delete container: {result['stderr']}")

    def delete(self, id: str, props: dict[str, Any]) -> None:
        """Delete a container.

        Args:
            id: Container ID
            props: Container properties
        """
        asyncio.run(self._delete_async(id, props))

    def diff(
        self, id: str, old_props: dict[str, Any], new_props: dict[str, Any]
    ) -> DiffResult:
        """Check what changed between old and new properties.

        Args:
            id: Container ID
            old_props: Old properties
            new_props: New properties

        Returns:
            DiffResult indicating if changes require replacement
        """
        # Compare key properties
        changes = []
        replaces = []

        # Fields that require replacement
        replacement_fields = [
            "image",
            "ports",
            "volumes",
            "env_vars",
            "command",
            "networks",
            "memory",
            "cpus",
            "user",
            "workdir",
            "labels",
            "must_run",
        ]

        for field in replacement_fields:
            old_val = old_props.get(field)
            new_val = new_props.get(field)
            if old_val != new_val:
                changes.append(field)
                replaces.append(field)

        # Any change requires replacement for containers
        return DiffResult(
            changes=len(changes) > 0,
            replaces=replaces,
            stables=[],
            delete_before_replace=True,  # Stop old container before starting new
        )


class DockerContainer(pulumi.dynamic.Resource):
    """Pulumi resource for managing Docker containers.

    This is a dynamic resource that wraps the DockerContainerProvider to manage
    containers using the Docker CLI.

    Attributes:
        container_id: The container ID (output)
        image: Container image name
        container_name: Logical container name
        ports: Port mappings
        volumes: Volume mounts
        env_vars: Environment variables
        command: Container command
        networks: Networks
    """

    container_id: pulumi.Output[str]
    image: pulumi.Output[str]
    container_name: pulumi.Output[str]
    ports: pulumi.Output[list[str]]
    volumes: pulumi.Output[list[str]]
    env_vars: pulumi.Output[dict[str, str]]
    command: pulumi.Output[str | None]
    networks: pulumi.Output[list[str]]

    def __init__(
        self,
        resource_name: str,
        inputs: DockerContainerInputs,
        opts: pulumi.ResourceOptions | None = None,
    ):
        """Initialize DockerContainer resource.

        Args:
            resource_name: Pulumi resource name
            inputs: Container input properties
            opts: Pulumi resource options
        """
        # Convert Pydantic model to dict for dynamic provider
        props = inputs.model_dump()

        super().__init__(
            DockerContainerProvider(),
            resource_name,
            props,
            opts,
        )
