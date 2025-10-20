"""Pulumi dynamic provider for Apple Containers CLI.

This module provides a Pulumi dynamic provider for managing containers using
the Apple Containers CLI (container command) available on macOS.
"""

import asyncio
import json
from typing import Any

import pulumi
from pulumi.dynamic import (
    CreateResult,
    DiffResult,
    ResourceProvider,
    UpdateResult,
)


class AppleContainerInputs:
    """Input properties for AppleContainer resource.

    Attributes:
        image: Container image name (e.g., "nginx:latest")
        container_name: Logical container name for tracking
        ports: Port mappings in format ["host:container", ...]
        volumes: Volume mounts in format ["host:container", ...]
        env_vars: Environment variables as dict {"KEY": "value"}
        networks: Networks to attach container to
        memory: Memory limit (e.g., "512M", "1G")
        cpus: Number of CPUs to allocate
        user: User to run as (format: "name|uid[:gid]")
        workdir: Working directory inside container
        labels: Labels to add to container {"key": "value"}
        must_run: Whether the container must be running (True) or can be stopped (False)
    """

    def __init__(
        self,
        image: str,
        container_name: str,
        ports: list[str] | None = None,
        volumes: list[str] | None = None,
        env_vars: dict[str, str] | None = None,
        networks: list[str] | None = None,
        memory: str | None = None,
        cpus: str | None = None,
        user: str | None = None,
        workdir: str | None = None,
        labels: dict[str, str] | None = None,
        must_run: bool = True,
    ):
        """Initialize AppleContainerInputs.

        Args:
            image: Container image name
            container_name: Logical container name
            ports: Port mappings (optional)
            volumes: Volume mounts (optional)
            env_vars: Environment variables (optional)
            networks: Networks to attach to (optional)
            memory: Memory limit (optional)
            cpus: Number of CPUs (optional)
            user: User to run as (optional)
            workdir: Working directory (optional)
            labels: Container labels (optional)
            must_run: Whether container must be running (default: True)
        """
        self.image = image
        self.container_name = container_name
        self.ports = ports or []
        self.volumes = volumes or []
        self.env_vars = env_vars or {}
        self.networks = networks or []
        self.memory = memory
        self.cpus = cpus
        self.user = user
        self.workdir = workdir
        self.labels = labels or {}
        self.must_run = must_run

        # Add clockwork.name label for tracking
        self.labels["clockwork.name"] = container_name


class AppleContainerProvider(ResourceProvider):
    """Pulumi dynamic provider for Apple Containers.

    This provider manages containers using the Apple Containers CLI (container command)
    via subprocess calls. It supports create, update (via replace), delete, and diff
    operations.
    """

    async def _run_command(self, cmd: list[str]) -> dict[str, Any]:
        """Run a container CLI command and return the result.

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

    async def _find_container_by_label(self, container_name: str) -> str | None:
        """Find container ID by clockwork.name label.

        Args:
            container_name: Logical container name

        Returns:
            Container ID if found, None otherwise
        """
        result = await self._run_command(
            ["container", "ls", "--all", "--format", "json"]
        )
        if result["returncode"] != 0:
            return None

        try:
            containers = (
                json.loads(result["stdout"]) if result["stdout"] else []
            )
            for container in containers:
                labels = container.get("configuration", {}).get("labels", {})
                if labels.get("clockwork.name") == container_name:
                    return container.get("configuration", {}).get("id")
        except (json.JSONDecodeError, KeyError):
            pass

        return None

    def _build_common_options(self, props: dict[str, Any]) -> list[str]:
        """Build common container options from properties.

        Args:
            props: Container properties

        Returns:
            Command options as list
        """
        options = []

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

        # Add networks
        for network in props.get("networks", []):
            options.extend(["--network", network])

        # Add labels
        for key, value in props.get("labels", {}).items():
            options.extend(["-l", f"{key}={value}"])

        return options

    def _build_run_command(self, props: dict[str, Any]) -> list[str]:
        """Build container run command from properties.

        Args:
            props: Container properties

        Returns:
            Command parts as list
        """
        cmd = ["container", "run", "-d"]  # Always detached
        cmd.extend(self._build_common_options(props))
        cmd.append(props["image"])
        return cmd

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

        # Check if container already exists
        existing_id = await self._find_container_by_label(container_name)
        if existing_id:
            # Check if it's running
            inspect_result = await self._run_command(
                ["container", "inspect", existing_id]
            )
            if inspect_result["returncode"] == 0:
                try:
                    data = json.loads(inspect_result["stdout"])
                    if data and isinstance(data, list) and len(data) > 0:
                        status = data[0].get("status")
                        if status == "running" and props.get("must_run", True):
                            # Already running, return existing ID
                            return CreateResult(id_=existing_id, outs=props)
                        elif not props.get("must_run", True):
                            # Container exists and we don't want it running
                            return CreateResult(id_=existing_id, outs=props)
                except (json.JSONDecodeError, KeyError):
                    pass

            # Remove existing container
            await self._run_command(["container", "rm", "-f", existing_id])

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
            return CreateResult(id_=container_id, outs=props)
        else:
            # Create but don't start (use container create)
            cmd = ["container", "create"]
            cmd.extend(self._build_common_options(props))
            cmd.append(props["image"])

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

        # Try to find container by label first
        actual_id = id
        if container_name:
            found_id = await self._find_container_by_label(container_name)
            if found_id:
                actual_id = found_id

        # Check if container exists
        inspect_result = await self._run_command(
            ["container", "inspect", actual_id]
        )
        if inspect_result["returncode"] != 0:
            # Container doesn't exist, nothing to do
            return

        # Remove container (force to stop if running)
        result = await self._run_command(["container", "rm", "-f", actual_id])

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


class AppleContainer(pulumi.dynamic.Resource):
    """Pulumi resource for managing Apple Containers.

    This is a dynamic resource that wraps the AppleContainerProvider to manage
    containers using the Apple Containers CLI.

    Attributes:
        container_id: The container ID (output)
        image: Container image name
        container_name: Logical container name
        ports: Port mappings
        volumes: Volume mounts
        env_vars: Environment variables
        networks: Networks
    """

    container_id: pulumi.Output[str]
    image: pulumi.Output[str]
    container_name: pulumi.Output[str]
    ports: pulumi.Output[list[str]]
    volumes: pulumi.Output[list[str]]
    env_vars: pulumi.Output[dict[str, str]]
    networks: pulumi.Output[list[str]]

    def __init__(
        self,
        resource_name: str,
        inputs: AppleContainerInputs,
        opts: pulumi.ResourceOptions | None = None,
    ):
        """Initialize AppleContainer resource.

        Args:
            resource_name: Pulumi resource name
            inputs: Container input properties
            opts: Pulumi resource options
        """
        # Convert inputs to dict for dynamic provider
        props = {
            "image": inputs.image,
            "container_name": inputs.container_name,
            "ports": inputs.ports,
            "volumes": inputs.volumes,
            "env_vars": inputs.env_vars,
            "networks": inputs.networks,
            "memory": inputs.memory,
            "cpus": inputs.cpus,
            "user": inputs.user,
            "workdir": inputs.workdir,
            "labels": inputs.labels,
            "must_run": inputs.must_run,
        }

        super().__init__(
            AppleContainerProvider(),
            resource_name,
            props,
            opts,
        )
