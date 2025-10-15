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
