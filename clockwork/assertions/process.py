"""Process management assertions for validating running processes."""

from typing import Any
from .base import BaseAssertion


class ProcessRunningAssert(BaseAssertion):
    """Assert that a process is running with minimum instance count.

    Checks if a process with the specified name is running and optionally
    validates that at least a minimum number of instances are running.

    Attributes:
        name: Process name to search for (matches against command/process name)
        min_count: Minimum number of process instances required (default: 1)
        timeout_seconds: Maximum time to wait (default: 5)

    Example:
        >>> # Check single process
        >>> ProcessRunningAssert(name="nginx")
        >>>
        >>> # Check multiple instances
        >>> ProcessRunningAssert(name="worker", min_count=4)
    """

    name: str
    min_count: int = 1
    timeout_seconds: int = 5


class ProcessNotRunningAssert(BaseAssertion):
    """Assert that a process is NOT running.

    Validates that no instances of the specified process are currently running.
    Useful for ensuring cleanup or verifying service shutdown.

    Attributes:
        name: Process name to search for (should not be found)
        timeout_seconds: Maximum time to wait (default: 5)

    Example:
        >>> ProcessNotRunningAssert(name="old-service")
        >>> ProcessNotRunningAssert(name="zombie-worker")
    """

    name: str
    timeout_seconds: int = 5
