"""PyInfra operations for Apple Containers CLI.

This module provides custom PyInfra operations for managing containers using
the Apple Containers CLI (container command) available on macOS.
"""

from typing import Any, Dict, List, Optional

from pyinfra import host
from pyinfra.api import operation
from pyinfra.api.exceptions import OperationError

from ..pyinfra_facts.apple_containers import ContainerStatus


@operation()
def container_run(
    image: str,
    name: Optional[str] = None,
    command: Optional[List[str]] = None,
    detach: bool = True,
    ports: Optional[List[str]] = None,
    volumes: Optional[List[str]] = None,
    env_vars: Optional[Dict[str, str]] = None,
    networks: Optional[List[str]] = None,
    remove: bool = False,
    memory: Optional[str] = None,
    cpus: Optional[str] = None,
    user: Optional[str] = None,
    workdir: Optional[str] = None,
    labels: Optional[Dict[str, str]] = None,
    interactive: bool = False,
    tty: bool = False,
    entrypoint: Optional[str] = None,
    **kwargs: Any,
):
    """Run a container using Apple Containers CLI.

    Args:
        image: Container image name (e.g., "nginx:latest")
        name: Container name/ID to use
        command: Command and arguments to run in container
        detach: Run container in detached mode (default: True)
        ports: Port mappings in format ["host:container", ...]
        volumes: Volume mounts in format ["host:container", ...]
        env_vars: Environment variables as dict {"KEY": "value"}
        networks: Networks to attach container to
        remove: Remove container after it stops
        memory: Memory limit (e.g., "512M", "1G")
        cpus: Number of CPUs to allocate
        user: User to run as (format: "name|uid[:gid]")
        workdir: Working directory inside container
        labels: Labels to add to container {"key": "value"}
        interactive: Keep stdin open
        tty: Allocate a pseudo-TTY
        entrypoint: Override image entrypoint
        **kwargs: Additional global operation arguments (_sudo, etc.)

    Returns:
        Operation result with container ID in stdout

    Example:
        container_run(
            name="nginx-web",
            image="nginx:latest",
            ports=["8080:80"],
            volumes=["./html:/usr/share/nginx/html"],
            env_vars={"ENV": "production"},
            detach=True,
        )
    """
    # Check if container already exists
    if name:
        status = host.get_fact(ContainerStatus, container_id=name)
        if status:
            # Container exists, check if running
            if status.get("running"):
                host.noop(f"Container {name} is already running")
                return
            # Container exists but not running - start it instead
            yield f"container start {name}"
            return

    # Build container run command
    cmd_parts = ["container", "run"]

    # Add flags
    if detach:
        cmd_parts.append("-d")
    if interactive:
        cmd_parts.append("-i")
    if tty:
        cmd_parts.append("-t")
    if remove:
        cmd_parts.append("--rm")

    # Add named arguments
    if name:
        cmd_parts.extend(["--name", name])

    if memory:
        cmd_parts.extend(["--memory", memory])

    if cpus:
        cmd_parts.extend(["--cpus", cpus])

    if user:
        cmd_parts.extend(["--user", user])

    if workdir:
        cmd_parts.extend(["--workdir", workdir])

    if entrypoint:
        cmd_parts.extend(["--entrypoint", entrypoint])

    # Add port mappings
    if ports:
        for port in ports:
            cmd_parts.extend(["-p", port])

    # Add volume mounts
    if volumes:
        for volume in volumes:
            cmd_parts.extend(["-v", volume])

    # Add environment variables
    if env_vars:
        for key, value in env_vars.items():
            cmd_parts.extend(["-e", f"{key}={value}"])

    # Add networks
    if networks:
        for network in networks:
            cmd_parts.extend(["--network", network])

    # Add labels
    if labels:
        for key, value in labels.items():
            cmd_parts.extend(["-l", f"{key}={value}"])

    # Add image
    cmd_parts.append(image)

    # Add command if specified
    if command:
        cmd_parts.extend(command)

    # Join and yield the command
    yield " ".join(cmd_parts)


@operation()
def container_stop(
    container_id: str,
    signal: Optional[str] = None,
    time: Optional[int] = None,
    **kwargs: Any,
):
    """Stop a running container.

    Args:
        container_id: Container ID or name
        signal: Signal to send (default: SIGTERM)
        time: Seconds to wait before killing (default: 5)
        **kwargs: Additional global operation arguments

    Example:
        container_stop(
            container_id="nginx-web",
            time=10,
        )
    """
    # Check if container exists and is running
    status = host.get_fact(ContainerStatus, container_id=container_id)
    if not status:
        raise OperationError(f"Container {container_id} does not exist")

    if not status.get("running"):
        host.noop(f"Container {container_id} is not running")
        return

    # Build stop command
    cmd_parts = ["container", "stop"]

    if signal:
        cmd_parts.extend(["--signal", signal])

    if time is not None:
        cmd_parts.extend(["--time", str(time)])

    cmd_parts.append(container_id)

    yield " ".join(cmd_parts)


@operation()
def container_remove(
    container_id: str,
    force: bool = False,
    **kwargs: Any,
):
    """Remove a container.

    Args:
        container_id: Container ID or name
        force: Force removal of running container
        **kwargs: Additional global operation arguments

    Example:
        container_remove(
            container_id="nginx-web",
            force=True,
        )
    """
    # Check if container exists
    status = host.get_fact(ContainerStatus, container_id=container_id)
    if not status:
        host.noop(f"Container {container_id} does not exist")
        return

    # Stop container first if running and not forcing
    if status.get("running") and not force:
        yield from container_stop._inner(container_id=container_id)

    # Build remove command
    cmd_parts = ["container", "rm"]

    cmd_parts.append(container_id)

    yield " ".join(cmd_parts)


@operation()
def container_exec(
    container_id: str,
    command: List[str],
    user: Optional[str] = None,
    workdir: Optional[str] = None,
    env_vars: Optional[Dict[str, str]] = None,
    interactive: bool = False,
    tty: bool = False,
    **kwargs: Any,
):
    """Execute a command in a running container.

    Args:
        container_id: Container ID or name
        command: Command and arguments to execute
        user: User to run as
        workdir: Working directory
        env_vars: Environment variables
        interactive: Keep stdin open
        tty: Allocate a pseudo-TTY
        **kwargs: Additional global operation arguments

    Example:
        container_exec(
            container_id="nginx-web",
            command=["nginx", "-t"],
        )
    """
    # Check if container is running
    status = host.get_fact(ContainerStatus, container_id=container_id)
    if not status:
        raise OperationError(f"Container {container_id} does not exist")

    if not status.get("running"):
        raise OperationError(f"Container {container_id} is not running")

    # Build exec command
    cmd_parts = ["container", "exec"]

    if interactive:
        cmd_parts.append("-i")

    if tty:
        cmd_parts.append("-t")

    if user:
        cmd_parts.extend(["--user", user])

    if workdir:
        cmd_parts.extend(["--workdir", workdir])

    if env_vars:
        for key, value in env_vars.items():
            cmd_parts.extend(["-e", f"{key}={value}"])

    cmd_parts.append(container_id)
    cmd_parts.extend(command)

    yield " ".join(cmd_parts)


@operation()
def container_create(
    image: str,
    name: Optional[str] = None,
    command: Optional[List[str]] = None,
    ports: Optional[List[str]] = None,
    volumes: Optional[List[str]] = None,
    env_vars: Optional[Dict[str, str]] = None,
    networks: Optional[List[str]] = None,
    memory: Optional[str] = None,
    cpus: Optional[str] = None,
    user: Optional[str] = None,
    workdir: Optional[str] = None,
    labels: Optional[Dict[str, str]] = None,
    entrypoint: Optional[str] = None,
    **kwargs: Any,
):
    """Create a container without starting it.

    Args:
        image: Container image name
        name: Container name/ID
        command: Command and arguments
        ports: Port mappings
        volumes: Volume mounts
        env_vars: Environment variables
        networks: Networks to attach to
        memory: Memory limit
        cpus: Number of CPUs
        user: User to run as
        workdir: Working directory
        labels: Container labels
        entrypoint: Override entrypoint
        **kwargs: Additional global operation arguments

    Example:
        container_create(
            name="nginx-web",
            image="nginx:latest",
            ports=["8080:80"],
        )
    """
    # Check if container already exists
    if name:
        status = host.get_fact(ContainerStatus, container_id=name)
        if status:
            host.noop(f"Container {name} already exists")
            return

    # Build container create command
    cmd_parts = ["container", "create"]

    if name:
        cmd_parts.extend(["--name", name])

    if memory:
        cmd_parts.extend(["--memory", memory])

    if cpus:
        cmd_parts.extend(["--cpus", cpus])

    if user:
        cmd_parts.extend(["--user", user])

    if workdir:
        cmd_parts.extend(["--workdir", workdir])

    if entrypoint:
        cmd_parts.extend(["--entrypoint", entrypoint])

    if ports:
        for port in ports:
            cmd_parts.extend(["-p", port])

    if volumes:
        for volume in volumes:
            cmd_parts.extend(["-v", volume])

    if env_vars:
        for key, value in env_vars.items():
            cmd_parts.extend(["-e", f"{key}={value}"])

    if networks:
        for network in networks:
            cmd_parts.extend(["--network", network])

    if labels:
        for key, value in labels.items():
            cmd_parts.extend(["-l", f"{key}={value}"])

    cmd_parts.append(image)

    if command:
        cmd_parts.extend(command)

    yield " ".join(cmd_parts)


@operation()
def container_start(
    container_id: str,
    **kwargs: Any,
):
    """Start a stopped container.

    Args:
        container_id: Container ID or name
        **kwargs: Additional global operation arguments

    Example:
        container_start(container_id="nginx-web")
    """
    # Check if container exists
    status = host.get_fact(ContainerStatus, container_id=container_id)
    if not status:
        raise OperationError(f"Container {container_id} does not exist")

    if status.get("running"):
        host.noop(f"Container {container_id} is already running")
        return

    yield f"container start {container_id}"


@operation()
def container_kill(
    container_id: str,
    signal: str = "SIGKILL",
    **kwargs: Any,
):
    """Kill a running container.

    Args:
        container_id: Container ID or name
        signal: Signal to send (default: SIGKILL)
        **kwargs: Additional global operation arguments

    Example:
        container_kill(container_id="nginx-web", signal="SIGTERM")
    """
    # Check if container is running
    status = host.get_fact(ContainerStatus, container_id=container_id)
    if not status:
        raise OperationError(f"Container {container_id} does not exist")

    if not status.get("running"):
        host.noop(f"Container {container_id} is not running")
        return

    cmd_parts = ["container", "kill", "--signal", signal, container_id]
    yield " ".join(cmd_parts)
