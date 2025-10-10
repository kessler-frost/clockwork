"""PyInfra facts for Apple Containers CLI.

This module provides custom PyInfra facts for gathering information about
containers using the Apple Containers CLI (container command) on macOS.
"""

import json
from typing import Any, Dict, List, Optional

from pyinfra.api import FactBase


class ContainerList(FactBase):
    """Get list of all containers.

    Returns:
        List of container dictionaries with basic info

    Example:
        containers = host.get_fact(ContainerList)
        # Returns list of dicts with container info
    """

    command = "container ls --all --format json"

    def process(self, output: List[str]) -> List[Dict[str, Any]]:
        """Process the JSON output from container ls.

        Args:
            output: Raw command output lines

        Returns:
            List of container information dictionaries
        """
        if not output:
            return []

        try:
            # Join output lines and parse as JSON
            json_str = "".join(output)
            data = json.loads(json_str)

            # The output is an array of container objects
            if isinstance(data, list):
                return data
            return []
        except (json.JSONDecodeError, ValueError):
            # If JSON parsing fails, return empty list
            return []


class ContainerStatus(FactBase):
    """Get status of a specific container.

    Args:
        container_id: Container ID or name

    Returns:
        Dictionary with container status info, or None if not found

    Example:
        status = host.get_fact(ContainerStatus, container_id="nginx-web")
        if status and status.get("running"):
            print("Container is running")
    """

    def command(self, container_id: str) -> str:
        """Generate command to get container status.

        Args:
            container_id: Container ID or name

        Returns:
            Command string to execute
        """
        # First check if container exists in the list
        return f"container ls --all --format json | grep -q '{container_id}' && container inspect {container_id} || echo '{{}}'"

    def process(self, output: List[str]) -> Optional[Dict[str, Any]]:
        """Process the container inspect output.

        Args:
            output: Raw command output lines

        Returns:
            Container status dictionary or None if not found
        """
        if not output:
            return None

        try:
            json_str = "".join(output)
            data = json.loads(json_str)

            # Empty dict means container doesn't exist
            if not data or data == {}:
                return None

            # Extract relevant status information
            # The inspect output format may vary, so we handle it flexibly
            if isinstance(data, list) and len(data) > 0:
                container_info = data[0]
            elif isinstance(data, dict):
                container_info = data
            else:
                return None

            # Build a simplified status dict
            status = {
                "id": container_info.get("ID") or container_info.get("id"),
                "name": container_info.get("Name") or container_info.get("name"),
                "image": container_info.get("Image") or container_info.get("image"),
                "state": container_info.get("State", {}),
                "running": False,
            }

            # Check if container is running
            state = container_info.get("State", {})
            if isinstance(state, dict):
                status["running"] = state.get("Running", False) or state.get("running", False)
                status["status"] = state.get("Status", "unknown")
            elif isinstance(state, str):
                status["running"] = state.lower() in ("running", "up")
                status["status"] = state

            return status
        except (json.JSONDecodeError, ValueError, KeyError, AttributeError):
            return None


class ContainerInspect(FactBase):
    """Get detailed information about one or more containers.

    Args:
        container_id: Container ID or name

    Returns:
        Detailed container information dictionary

    Example:
        info = host.get_fact(ContainerInspect, container_id="nginx-web")
        print(info.get("Config", {}).get("Env"))
    """

    def command(self, container_id: str) -> str:
        """Generate command to inspect container.

        Args:
            container_id: Container ID or name

        Returns:
            Command string to execute
        """
        return f"container inspect {container_id}"

    def process(self, output: List[str]) -> Optional[Dict[str, Any]]:
        """Process the container inspect JSON output.

        Args:
            output: Raw command output lines

        Returns:
            Container inspection data or None if parsing fails
        """
        if not output:
            return None

        try:
            json_str = "".join(output)
            data = json.loads(json_str)

            # inspect returns an array with one element per container
            if isinstance(data, list) and len(data) > 0:
                return data[0]
            elif isinstance(data, dict):
                return data

            return None
        except (json.JSONDecodeError, ValueError):
            return None


class ContainerLogs(FactBase):
    """Get logs from a container.

    Args:
        container_id: Container ID or name
        tail: Number of lines to retrieve (default: all)

    Returns:
        List of log lines

    Example:
        logs = host.get_fact(ContainerLogs, container_id="nginx-web", tail=100)
        for line in logs:
            print(line)
    """

    def command(self, container_id: str, tail: Optional[int] = None) -> str:
        """Generate command to fetch container logs.

        Args:
            container_id: Container ID or name
            tail: Number of lines to retrieve

        Returns:
            Command string to execute
        """
        cmd = f"container logs {container_id}"
        if tail:
            cmd += f" --tail {tail}"
        return cmd

    def process(self, output: List[str]) -> List[str]:
        """Process log output.

        Args:
            output: Raw log lines

        Returns:
            List of log lines
        """
        return output if output else []


class ContainerRunning(FactBase):
    """Check if a specific container is running.

    Args:
        container_id: Container ID or name

    Returns:
        True if container is running, False otherwise

    Example:
        if host.get_fact(ContainerRunning, container_id="nginx-web"):
            print("Container is running")
    """

    def command(self, container_id: str) -> str:
        """Generate command to check if container is running.

        Args:
            container_id: Container ID or name

        Returns:
            Command string to execute
        """
        return f"container ls --format json | grep -q '{container_id}' && echo 'true' || echo 'false'"

    def process(self, output: List[str]) -> bool:
        """Process the running status.

        Args:
            output: Raw command output

        Returns:
            True if running, False otherwise
        """
        if not output:
            return False

        return "true" in "".join(output).lower()


class ContainerExists(FactBase):
    """Check if a container exists (running or stopped).

    Args:
        container_id: Container ID or name

    Returns:
        True if container exists, False otherwise

    Example:
        if host.get_fact(ContainerExists, container_id="nginx-web"):
            print("Container exists")
    """

    def command(self, container_id: str) -> str:
        """Generate command to check if container exists.

        Args:
            container_id: Container ID or name

        Returns:
            Command string to execute
        """
        return f"container ls --all --format json | grep -q '{container_id}' && echo 'true' || echo 'false'"

    def process(self, output: List[str]) -> bool:
        """Process the existence check.

        Args:
            output: Raw command output

        Returns:
            True if exists, False otherwise
        """
        if not output:
            return False

        return "true" in "".join(output).lower()


class ContainerImage(FactBase):
    """Get the image name used by a container.

    Args:
        container_id: Container ID or name

    Returns:
        Image name string or None if container not found

    Example:
        image = host.get_fact(ContainerImage, container_id="nginx-web")
        print(f"Container uses image: {image}")
    """

    def command(self, container_id: str) -> str:
        """Generate command to get container image.

        Args:
            container_id: Container ID or name

        Returns:
            Command string to execute
        """
        return f"container inspect {container_id}"

    def process(self, output: List[str]) -> Optional[str]:
        """Extract image name from inspect output.

        Args:
            output: Raw command output lines

        Returns:
            Image name or None
        """
        if not output:
            return None

        try:
            json_str = "".join(output)
            data = json.loads(json_str)

            if isinstance(data, list) and len(data) > 0:
                container_info = data[0]
            elif isinstance(data, dict):
                container_info = data
            else:
                return None

            # Try different possible fields
            return (
                container_info.get("Image")
                or container_info.get("image")
                or container_info.get("Config", {}).get("Image")
            )
        except (json.JSONDecodeError, ValueError, KeyError, AttributeError):
            return None


class ContainerPorts(FactBase):
    """Get port mappings for a container.

    Args:
        container_id: Container ID or name

    Returns:
        List of port mapping dictionaries or empty list

    Example:
        ports = host.get_fact(ContainerPorts, container_id="nginx-web")
        for mapping in ports:
            print(f"{mapping['host_port']} -> {mapping['container_port']}")
    """

    def command(self, container_id: str) -> str:
        """Generate command to get container port mappings.

        Args:
            container_id: Container ID or name

        Returns:
            Command string to execute
        """
        return f"container inspect {container_id}"

    def process(self, output: List[str]) -> List[Dict[str, Any]]:
        """Extract port mappings from inspect output.

        Args:
            output: Raw command output lines

        Returns:
            List of port mapping dictionaries
        """
        if not output:
            return []

        try:
            json_str = "".join(output)
            data = json.loads(json_str)

            if isinstance(data, list) and len(data) > 0:
                container_info = data[0]
            elif isinstance(data, dict):
                container_info = data
            else:
                return []

            # Try to extract port mappings
            # Format may vary, so we handle it flexibly
            ports_config = (
                container_info.get("NetworkSettings", {}).get("Ports")
                or container_info.get("HostConfig", {}).get("PortBindings")
                or {}
            )

            port_mappings = []
            if isinstance(ports_config, dict):
                for container_port, host_bindings in ports_config.items():
                    if host_bindings:
                        for binding in host_bindings:
                            port_mappings.append(
                                {
                                    "container_port": container_port,
                                    "host_ip": binding.get("HostIp", ""),
                                    "host_port": binding.get("HostPort", ""),
                                }
                            )

            return port_mappings
        except (json.JSONDecodeError, ValueError, KeyError, AttributeError):
            return []
