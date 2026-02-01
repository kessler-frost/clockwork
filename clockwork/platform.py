"""Platform detection utilities for Clockwork.

This module provides utilities to detect available container runtimes
and platform capabilities.
"""

import shutil
import subprocess
from enum import Enum


class ContainerRuntime(Enum):
    """Available container runtimes."""

    DOCKER = "docker"
    APPLE_CONTAINERS = "apple_containers"
    NONE = "none"


def is_docker_available() -> bool:
    """Check if Docker CLI is available and working.

    Returns:
        True if docker CLI is available and daemon is running, False otherwise.

    Example:
        >>> if is_docker_available():
        ...     print("Docker is ready")
    """
    # Check if docker command exists
    if not shutil.which("docker"):
        return False

    # Check if docker daemon is running
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=10,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False


def is_apple_containers_available() -> bool:
    """Check if Apple Containers CLI is available and working.

    Returns:
        True if container CLI is available, False otherwise.

    Example:
        >>> if is_apple_containers_available():
        ...     print("Apple Containers is ready")
    """
    # Check if container command exists
    if not shutil.which("container"):
        return False

    # Check if it works
    try:
        result = subprocess.run(
            ["container", "list"],
            capture_output=True,
            timeout=10,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False


def get_container_runtime() -> ContainerRuntime:
    """Get the available container runtime.

    Checks for available container runtimes in order of preference:
    1. Docker (cross-platform)
    2. Apple Containers (macOS only)

    Returns:
        ContainerRuntime enum indicating available runtime.

    Example:
        >>> runtime = get_container_runtime()
        >>> if runtime == ContainerRuntime.DOCKER:
        ...     print("Using Docker")
        >>> elif runtime == ContainerRuntime.APPLE_CONTAINERS:
        ...     print("Using Apple Containers")
        >>> else:
        ...     print("No container runtime available")
    """
    if is_docker_available():
        return ContainerRuntime.DOCKER

    if is_apple_containers_available():
        return ContainerRuntime.APPLE_CONTAINERS

    return ContainerRuntime.NONE


def get_available_runtimes() -> list[ContainerRuntime]:
    """Get all available container runtimes.

    Returns:
        List of available ContainerRuntime values.

    Example:
        >>> runtimes = get_available_runtimes()
        >>> for runtime in runtimes:
        ...     print(f"Available: {runtime.value}")
    """
    runtimes = []

    if is_docker_available():
        runtimes.append(ContainerRuntime.DOCKER)

    if is_apple_containers_available():
        runtimes.append(ContainerRuntime.APPLE_CONTAINERS)

    return runtimes


def require_docker() -> None:
    """Ensure Docker is available, raise error if not.

    Raises:
        RuntimeError: If Docker is not available.

    Example:
        >>> require_docker()  # Raises if Docker not available
    """
    if not is_docker_available():
        raise RuntimeError(
            "Docker is required but not available. "
            "Please install Docker and ensure the daemon is running. "
            "See https://docs.docker.com/get-docker/"
        )


def require_apple_containers() -> None:
    """Ensure Apple Containers is available, raise error if not.

    Raises:
        RuntimeError: If Apple Containers is not available.

    Example:
        >>> require_apple_containers()  # Raises if not available
    """
    if not is_apple_containers_available():
        raise RuntimeError(
            "Apple Containers is required but not available. "
            "Apple Containers requires macOS 26 'Tahoe' (beta) or later. "
            "See https://developer.apple.com/documentation/Container"
        )


def require_any_container_runtime() -> ContainerRuntime:
    """Ensure at least one container runtime is available.

    Returns:
        The available ContainerRuntime (prefers Docker).

    Raises:
        RuntimeError: If no container runtime is available.

    Example:
        >>> runtime = require_any_container_runtime()
        >>> print(f"Using {runtime.value}")
    """
    runtime = get_container_runtime()

    if runtime == ContainerRuntime.NONE:
        raise RuntimeError(
            "No container runtime available. "
            "Please install Docker (https://docs.docker.com/get-docker/) "
            "or use macOS 26 'Tahoe' with Apple Containers."
        )

    return runtime
