"""
Clockwork Docker Compose Operations

PyInfra operations for managing Docker Compose applications with idempotent
deployment, scaling, and lifecycle management capabilities.
"""

import json
import logging
from typing import Dict, List, Optional, Union

from pyinfra import host
from pyinfra.api import operation, OperationError
from pyinfra.api.command import StringCommand
from pyinfra.facts.server import Command

logger = logging.getLogger(__name__)


@operation()
def compose_up(
    compose_file: str = "docker-compose.yml",
    project_name: Optional[str] = None,
    services: Optional[List[str]] = None,
    detach: bool = True,
    build: bool = False,
    force_recreate: bool = False,
    no_recreate: bool = False,
    remove_orphans: bool = True,
    scale: Optional[Dict[str, int]] = None,
    env_file: Optional[str] = None,
    profiles: Optional[List[str]] = None,
):
    """
    Start Docker Compose services using docker-compose up.

    Args:
        compose_file: Path to docker-compose.yml file
        project_name: Project name override
        services: List of specific services to start
        detach: Run in detached mode
        build: Build images before starting
        force_recreate: Force recreate containers
        no_recreate: Don't recreate existing containers
        remove_orphans: Remove orphaned containers
        scale: Dictionary of service:replica_count for scaling
        env_file: Environment file path
        profiles: List of profiles to enable

    Example:
        compose_up(
            compose_file="/app/docker-compose.yml",
            project_name="myapp",
            services=["web", "db"],
            build=True
        )
    """
    # Check if compose file exists
    file_check = host.get_fact(Command, command=f"test -f {compose_file}")
    if file_check.return_code != 0:
        raise OperationError(f"Compose file not found: {compose_file}")

    # Build docker-compose command
    cmd_parts = ["docker-compose", "-f", compose_file]

    if project_name:
        cmd_parts.extend(["-p", project_name])

    if env_file:
        cmd_parts.extend(["--env-file", env_file])

    if profiles:
        for profile in profiles:
            cmd_parts.extend(["--profile", profile])

    cmd_parts.append("up")

    if detach:
        cmd_parts.append("-d")
    if build:
        cmd_parts.append("--build")
    if force_recreate:
        cmd_parts.append("--force-recreate")
    if no_recreate:
        cmd_parts.append("--no-recreate")
    if remove_orphans:
        cmd_parts.append("--remove-orphans")

    # Add scaling options
    if scale:
        for service, count in scale.items():
            cmd_parts.extend(["--scale", f"{service}={count}"])

    # Add specific services
    if services:
        cmd_parts.extend(services)

    yield StringCommand(" ".join(cmd_parts))


@operation()
def compose_down(
    compose_file: str = "docker-compose.yml",
    project_name: Optional[str] = None,
    remove_orphans: bool = True,
    volumes: bool = False,
    images: Optional[str] = None,
    timeout: Optional[int] = None,
):
    """
    Stop and remove Docker Compose services using docker-compose down.

    Args:
        compose_file: Path to docker-compose.yml file
        project_name: Project name override
        remove_orphans: Remove orphaned containers
        volumes: Remove named volumes
        images: Remove images (all, local)
        timeout: Timeout for container stop

    Example:
        compose_down(
            compose_file="/app/docker-compose.yml",
            project_name="myapp",
            volumes=True
        )
    """
    # Check if any containers are running for this project
    ps_cmd_parts = ["docker-compose", "-f", compose_file]
    if project_name:
        ps_cmd_parts.extend(["-p", project_name])
    ps_cmd_parts.extend(["ps", "-q"])

    running_containers = host.get_fact(Command, command=" ".join(ps_cmd_parts))

    # Only run down if there are containers
    if running_containers.stdout:
        # Build docker-compose down command
        cmd_parts = ["docker-compose", "-f", compose_file]

        if project_name:
            cmd_parts.extend(["-p", project_name])

        cmd_parts.append("down")

        if remove_orphans:
            cmd_parts.append("--remove-orphans")
        if volumes:
            cmd_parts.append("--volumes")
        if images:
            cmd_parts.extend(["--rmi", images])
        if timeout:
            cmd_parts.extend(["-t", str(timeout)])

        yield StringCommand(" ".join(cmd_parts))


@operation()
def compose_build(
    compose_file: str = "docker-compose.yml",
    project_name: Optional[str] = None,
    services: Optional[List[str]] = None,
    no_cache: bool = False,
    pull: bool = False,
    parallel: bool = True,
    build_args: Optional[Dict[str, str]] = None,
):
    """
    Build Docker Compose services using docker-compose build.

    Args:
        compose_file: Path to docker-compose.yml file
        project_name: Project name override
        services: List of specific services to build
        no_cache: Don't use cache when building
        pull: Always pull newer versions of base images
        parallel: Build images in parallel
        build_args: Build arguments as key-value pairs

    Example:
        compose_build(
            compose_file="/app/docker-compose.yml",
            services=["web"],
            no_cache=True,
            build_args={"VERSION": "1.0.0"}
        )
    """
    # Build docker-compose build command
    cmd_parts = ["docker-compose", "-f", compose_file]

    if project_name:
        cmd_parts.extend(["-p", project_name])

    cmd_parts.append("build")

    if no_cache:
        cmd_parts.append("--no-cache")
    if pull:
        cmd_parts.append("--pull")
    if parallel:
        cmd_parts.append("--parallel")

    # Add build arguments
    if build_args:
        for key, value in build_args.items():
            cmd_parts.extend(["--build-arg", f"{key}={value}"])

    # Add specific services
    if services:
        cmd_parts.extend(services)

    yield StringCommand(" ".join(cmd_parts))


@operation()
def compose_pull(
    compose_file: str = "docker-compose.yml",
    project_name: Optional[str] = None,
    services: Optional[List[str]] = None,
    ignore_pull_failures: bool = False,
    parallel: bool = True,
    quiet: bool = False,
):
    """
    Pull Docker Compose service images using docker-compose pull.

    Args:
        compose_file: Path to docker-compose.yml file
        project_name: Project name override
        services: List of specific services to pull
        ignore_pull_failures: Continue if pull fails for some images
        parallel: Pull images in parallel
        quiet: Suppress progress output

    Example:
        compose_pull(
            compose_file="/app/docker-compose.yml",
            services=["web", "db"],
            parallel=True
        )
    """
    # Build docker-compose pull command
    cmd_parts = ["docker-compose", "-f", compose_file]

    if project_name:
        cmd_parts.extend(["-p", project_name])

    cmd_parts.append("pull")

    if ignore_pull_failures:
        cmd_parts.append("--ignore-pull-failures")
    if parallel:
        cmd_parts.append("--parallel")
    if quiet:
        cmd_parts.append("--quiet")

    # Add specific services
    if services:
        cmd_parts.extend(services)

    yield StringCommand(" ".join(cmd_parts))


@operation()
def compose_logs(
    compose_file: str = "docker-compose.yml",
    project_name: Optional[str] = None,
    services: Optional[List[str]] = None,
    follow: bool = False,
    tail: Optional[Union[str, int]] = None,
    timestamps: bool = False,
    since: Optional[str] = None,
    until: Optional[str] = None,
):
    """
    View Docker Compose service logs using docker-compose logs.

    Args:
        compose_file: Path to docker-compose.yml file
        project_name: Project name override
        services: List of specific services to show logs for
        follow: Follow log output
        tail: Number of lines to show from end (or "all")
        timestamps: Show timestamps
        since: Show logs since timestamp
        until: Show logs until timestamp

    Example:
        compose_logs(
            compose_file="/app/docker-compose.yml",
            services=["web"],
            tail=100,
            timestamps=True
        )
    """
    # Build docker-compose logs command
    cmd_parts = ["docker-compose", "-f", compose_file]

    if project_name:
        cmd_parts.extend(["-p", project_name])

    cmd_parts.append("logs")

    if follow:
        cmd_parts.append("--follow")
    if tail is not None:
        cmd_parts.extend(["--tail", str(tail)])
    if timestamps:
        cmd_parts.append("--timestamps")
    if since:
        cmd_parts.extend(["--since", since])
    if until:
        cmd_parts.extend(["--until", until])

    # Add specific services
    if services:
        cmd_parts.extend(services)

    yield StringCommand(" ".join(cmd_parts))


@operation()
def compose_ps(
    compose_file: str = "docker-compose.yml",
    project_name: Optional[str] = None,
    services: Optional[List[str]] = None,
    quiet: bool = False,
    all_containers: bool = False,
    format: str = "table",
):
    """
    List Docker Compose containers using docker-compose ps.

    Args:
        compose_file: Path to docker-compose.yml file
        project_name: Project name override
        services: List of specific services to list
        quiet: Only show container IDs
        all_containers: Show all containers (default shows only running)
        format: Output format (table, json)

    Example:
        compose_ps(
            compose_file="/app/docker-compose.yml",
            services=["web", "db"],
            format="json"
        )
    """
    # Build docker-compose ps command
    cmd_parts = ["docker-compose", "-f", compose_file]

    if project_name:
        cmd_parts.extend(["-p", project_name])

    cmd_parts.append("ps")

    if quiet:
        cmd_parts.append("--quiet")
    if all_containers:
        cmd_parts.append("--all")
    if format != "table":
        cmd_parts.extend(["--format", format])

    # Add specific services
    if services:
        cmd_parts.extend(services)

    yield StringCommand(" ".join(cmd_parts))


@operation()
def compose_restart(
    compose_file: str = "docker-compose.yml",
    project_name: Optional[str] = None,
    services: Optional[List[str]] = None,
    timeout: Optional[int] = None,
):
    """
    Restart Docker Compose services using docker-compose restart.

    Args:
        compose_file: Path to docker-compose.yml file
        project_name: Project name override
        services: List of specific services to restart
        timeout: Timeout for container stop

    Example:
        compose_restart(
            compose_file="/app/docker-compose.yml",
            services=["web"],
            timeout=30
        )
    """
    # Build docker-compose restart command
    cmd_parts = ["docker-compose", "-f", compose_file]

    if project_name:
        cmd_parts.extend(["-p", project_name])

    cmd_parts.append("restart")

    if timeout:
        cmd_parts.extend(["-t", str(timeout)])

    # Add specific services
    if services:
        cmd_parts.extend(services)

    yield StringCommand(" ".join(cmd_parts))


@operation()
def compose_stop(
    compose_file: str = "docker-compose.yml",
    project_name: Optional[str] = None,
    services: Optional[List[str]] = None,
    timeout: Optional[int] = None,
):
    """
    Stop Docker Compose services using docker-compose stop.

    Args:
        compose_file: Path to docker-compose.yml file
        project_name: Project name override
        services: List of specific services to stop
        timeout: Timeout for container stop

    Example:
        compose_stop(
            compose_file="/app/docker-compose.yml",
            services=["web"],
            timeout=30
        )
    """
    # Build docker-compose stop command
    cmd_parts = ["docker-compose", "-f", compose_file]

    if project_name:
        cmd_parts.extend(["-p", project_name])

    cmd_parts.append("stop")

    if timeout:
        cmd_parts.extend(["-t", str(timeout)])

    # Add specific services
    if services:
        cmd_parts.extend(services)

    yield StringCommand(" ".join(cmd_parts))


@operation()
def compose_exec(
    service: str,
    command: str,
    compose_file: str = "docker-compose.yml",
    project_name: Optional[str] = None,
    detach: bool = False,
    interactive: bool = True,
    tty: bool = True,
    user: Optional[str] = None,
    workdir: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
):
    """
    Execute commands in Docker Compose service containers using docker-compose exec.

    Args:
        service: Service name to execute command in
        command: Command to execute
        compose_file: Path to docker-compose.yml file
        project_name: Project name override
        detach: Run in detached mode
        interactive: Keep stdin open
        tty: Allocate a pseudo-TTY
        user: User to run command as
        workdir: Working directory for command
        env: Environment variables as key-value pairs

    Example:
        compose_exec(
            service="web",
            command="python manage.py migrate",
            compose_file="/app/docker-compose.yml",
            user="app"
        )
    """
    # Check if service is running
    ps_cmd_parts = ["docker-compose", "-f", compose_file]
    if project_name:
        ps_cmd_parts.extend(["-p", project_name])
    ps_cmd_parts.extend(["ps", "-q", service])

    running_container = host.get_fact(Command, command=" ".join(ps_cmd_parts))

    if not running_container.stdout:
        raise OperationError(f"Service '{service}' is not running")

    # Build docker-compose exec command
    cmd_parts = ["docker-compose", "-f", compose_file]

    if project_name:
        cmd_parts.extend(["-p", project_name])

    cmd_parts.append("exec")

    if detach:
        cmd_parts.append("-d")
    if not interactive:
        cmd_parts.append("-T")
    if user:
        cmd_parts.extend(["--user", user])
    if workdir:
        cmd_parts.extend(["--workdir", workdir])

    # Add environment variables
    if env:
        for key, value in env.items():
            cmd_parts.extend(["-e", f"{key}={value}"])

    cmd_parts.extend([service, command])

    yield StringCommand(" ".join(cmd_parts))


@operation()
def compose_config(
    compose_file: str = "docker-compose.yml",
    project_name: Optional[str] = None,
    resolve_image_digests: bool = False,
    quiet: bool = False,
    services: bool = False,
    volumes: bool = False,
    hash_services: Optional[List[str]] = None,
):
    """
    Validate and view Docker Compose configuration using docker-compose config.

    Args:
        compose_file: Path to docker-compose.yml file
        project_name: Project name override
        resolve_image_digests: Pin image tags to digests
        quiet: Only validate configuration
        services: Print service names
        volumes: Print volume names
        hash_services: Print hash for specified services

    Example:
        compose_config(
            compose_file="/app/docker-compose.yml",
            quiet=True  # Just validate
        )
    """
    # Build docker-compose config command
    cmd_parts = ["docker-compose", "-f", compose_file]

    if project_name:
        cmd_parts.extend(["-p", project_name])

    cmd_parts.append("config")

    if resolve_image_digests:
        cmd_parts.append("--resolve-image-digests")
    if quiet:
        cmd_parts.append("--quiet")
    if services:
        cmd_parts.append("--services")
    if volumes:
        cmd_parts.append("--volumes")

    # Add hash for specific services
    if hash_services:
        for service in hash_services:
            cmd_parts.extend(["--hash", service])

    yield StringCommand(" ".join(cmd_parts))