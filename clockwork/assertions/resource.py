"""Resource usage assertions for monitoring system resources."""

from typing import Any, Optional
from .base import BaseAssertion


class MemoryUsageAssert(BaseAssertion):
    """Assert that memory usage is below a threshold.

    Checks available system memory or container memory usage against a
    maximum threshold in megabytes.

    Attributes:
        max_mb: Maximum memory usage in megabytes
        container_name: If specified, check container memory instead of system memory
        timeout_seconds: Maximum time to wait (default: 5)

    Example:
        >>> # System memory
        >>> MemoryUsageAssert(max_mb=1024)
        >>>
        >>> # Container memory
        >>> MemoryUsageAssert(max_mb=512, container_name="my-app")
    """

    max_mb: int
    container_name: Optional[str] = None
    timeout_seconds: int = 5

    def to_pyinfra_operation(self, resource: Any) -> str:
        """Generate PyInfra operation to check memory usage.

        Args:
            resource: Parent resource (could be any resource type)

        Returns:
            PyInfra server.shell operation that checks memory usage
        """
        if self.container_name:
            desc = self.description or f"Container {self.container_name} memory < {self.max_mb}MB"
            container = self.container_name

            return f'''
# Assert: {desc}
server.shell(
    name="Assert: {desc}",
    commands=[
        "MEM_BYTES=$(container stats --no-stream --format '{{{{.MemUsage}}}}' {container} | awk '{{print $1}}' | sed 's/[^0-9.]//g'); "
        "MEM_MB=$(echo \"$MEM_BYTES\" | awk '{{printf \"%d\", $1}}'); "
        "[ $MEM_MB -le {self.max_mb} ] || exit 1"
    ],
)
'''
        else:
            desc = self.description or f"System memory usage < {self.max_mb}MB"

            return f'''
# Assert: {desc}
server.shell(
    name="Assert: {desc}",
    commands=[
        "MEM_USED=$(free -m | awk 'NR==2{{print $3}}'); "
        "[ $MEM_USED -le {self.max_mb} ] || exit 1"
    ],
)
'''


class CpuUsageAssert(BaseAssertion):
    """Assert that CPU usage is below a threshold.

    Checks current CPU usage percentage against a maximum threshold.
    For containers, monitors the specific container's CPU usage.

    Attributes:
        max_percent: Maximum CPU usage as percentage (0-100)
        container_name: If specified, check container CPU instead of system CPU
        timeout_seconds: Maximum time to wait (default: 5)

    Example:
        >>> # System CPU
        >>> CpuUsageAssert(max_percent=80)
        >>>
        >>> # Container CPU
        >>> CpuUsageAssert(max_percent=50, container_name="my-app")
    """

    max_percent: float
    container_name: Optional[str] = None
    timeout_seconds: int = 5

    def to_pyinfra_operation(self, resource: Any) -> str:
        """Generate PyInfra operation to check CPU usage.

        Args:
            resource: Parent resource (could be any resource type)

        Returns:
            PyInfra server.shell operation that checks CPU usage
        """
        if self.container_name:
            desc = self.description or f"Container {self.container_name} CPU < {self.max_percent}%"
            container = self.container_name

            return f'''
# Assert: {desc}
server.shell(
    name="Assert: {desc}",
    commands=[
        "CPU=$(container stats --no-stream --format '{{{{.CPUPerc}}}}' {container} | sed 's/%//'); "
        "[ \"$(echo \"$CPU < {self.max_percent}\" | bc)\" -eq 1 ] || exit 1"
    ],
)
'''
        else:
            desc = self.description or f"System CPU usage < {self.max_percent}%"

            return f'''
# Assert: {desc}
server.shell(
    name="Assert: {desc}",
    commands=[
        "CPU=$(top -bn1 | grep 'Cpu(s)' | awk '{{print $2}}' | sed 's/%us,//'); "
        "[ \"$(echo \"$CPU < {self.max_percent}\" | bc)\" -eq 1 ] || exit 1"
    ],
)
'''


class DiskUsageAssert(BaseAssertion):
    """Assert that disk usage is below a threshold.

    Checks disk usage at a specific path against percentage or absolute size limits.
    At least one of max_percent or max_mb must be specified.

    Attributes:
        path: Path to check disk usage for (e.g., "/", "/var/log")
        max_percent: Maximum disk usage as percentage (0-100, optional)
        max_mb: Maximum disk usage in megabytes (optional)
        timeout_seconds: Maximum time to wait (default: 5)

    Example:
        >>> # Check by percentage
        >>> DiskUsageAssert(path="/", max_percent=80)
        >>>
        >>> # Check by absolute size
        >>> DiskUsageAssert(path="/var/log", max_mb=10240)  # 10 GB
        >>>
        >>> # Check both
        >>> DiskUsageAssert(path="/data", max_percent=90, max_mb=50000)
    """

    path: str
    max_percent: Optional[float] = None
    max_mb: Optional[int] = None
    timeout_seconds: int = 5

    def to_pyinfra_operation(self, resource: Any) -> str:
        """Generate PyInfra operation to check disk usage.

        Args:
            resource: Parent resource (could be any resource type)

        Returns:
            PyInfra server.shell operation that checks disk usage
        """
        desc = self.description or f"Disk usage at {self.path} within limits"

        checks = []

        if self.max_percent is not None:
            checks.append(f"[ $PERCENT -le {int(self.max_percent)} ]")

        if self.max_mb is not None:
            checks.append(f"[ $USED_MB -le {self.max_mb} ]")

        check_cmd = " && ".join(checks) if checks else "true"

        return f'''
# Assert: {desc}
server.shell(
    name="Assert: {desc}",
    commands=[
        "DISK_INFO=$(df -m {self.path} | tail -1); "
        "USED_MB=$(echo $DISK_INFO | awk '{{print $3}}'); "
        "PERCENT=$(echo $DISK_INFO | awk '{{print $5}}' | sed 's/%//'); "
        "{check_cmd} || exit 1"
    ],
)
'''
