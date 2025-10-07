"""HTTP-based assertions for web services and APIs."""

from typing import Any, Literal
from .base import BaseAssertion


class HealthcheckAssert(BaseAssertion):
    """Assert that an HTTP endpoint returns expected status code.

    Performs an HTTP GET request to the specified URL and validates the
    response status code. Useful for health checks and API validation.

    Attributes:
        url: Full URL to check (e.g., "http://localhost:8080/health")
        expected_status: HTTP status code to expect (default: 200)
        timeout_seconds: Maximum time to wait for response (default: 5)

    Example:
        >>> HealthcheckAssert(
        ...     url="http://localhost:8080/health",
        ...     expected_status=200,
        ...     timeout_seconds=5
        ... )
    """

    url: str
    expected_status: int = 200
    timeout_seconds: int = 5

    def to_pyinfra_operation(self, resource: Any) -> str:
        """Generate PyInfra operation for HTTP health check.

        Args:
            resource: Parent resource (typically a DockerServiceResource)

        Returns:
            PyInfra server.shell operation that uses curl to check HTTP status
        """
        desc = self.description or f"HTTP {self.expected_status} at {self.url}"

        return f'''
# Assert: {desc}
server.shell(
    name="Assert: {desc}",
    commands=[
        "curl -f -s -o /dev/null -w '%{{http_code}}' --max-time {self.timeout_seconds} {self.url} | grep -q '^{self.expected_status}$' || exit 1"
    ],
)
'''


class PortAccessibleAssert(BaseAssertion):
    """Assert that a network port is accessible and listening.

    Checks if a TCP or UDP port is open and accepting connections on the
    specified host. Uses netcat (nc) to test connectivity.

    Attributes:
        port: Port number to check (1-65535)
        host: Hostname or IP address (default: "localhost")
        protocol: Protocol to test - "tcp" or "udp" (default: "tcp")
        timeout_seconds: Maximum time to wait for connection (default: 5)

    Example:
        >>> PortAccessibleAssert(
        ...     port=8080,
        ...     host="localhost",
        ...     protocol="tcp"
        ... )
    """

    port: int
    host: str = "localhost"
    protocol: Literal["tcp", "udp"] = "tcp"
    timeout_seconds: int = 5

    def to_pyinfra_operation(self, resource: Any) -> str:
        """Generate PyInfra operation for port accessibility check.

        Args:
            resource: Parent resource (typically a DockerServiceResource)

        Returns:
            PyInfra server.shell operation that uses nc to check port
        """
        desc = self.description or f"Port {self.port} accessible on {self.host}"

        # Build nc command based on protocol
        nc_flag = "-u" if self.protocol == "udp" else ""

        return f'''
# Assert: {desc}
server.shell(
    name="Assert: {desc}",
    commands=[
        "nc {nc_flag} -z -w {self.timeout_seconds} {self.host} {self.port} || exit 1"
    ],
)
'''


class ResponseTimeAssert(BaseAssertion):
    """Assert that an HTTP endpoint responds within a time limit.

    Measures the total time for an HTTP request and validates it completes
    within the specified maximum time in milliseconds.

    Attributes:
        url: Full URL to check (e.g., "http://localhost:8080/api")
        max_ms: Maximum response time in milliseconds
        timeout_seconds: Maximum time to wait before giving up (default: 30)

    Example:
        >>> ResponseTimeAssert(
        ...     url="http://localhost:8080/api/users",
        ...     max_ms=500
        ... )
    """

    url: str
    max_ms: int
    timeout_seconds: int = 30

    def to_pyinfra_operation(self, resource: Any) -> str:
        """Generate PyInfra operation for response time check.

        Args:
            resource: Parent resource (typically a DockerServiceResource)

        Returns:
            PyInfra server.shell operation that uses curl to measure response time
        """
        desc = self.description or f"Response time < {self.max_ms}ms for {self.url}"
        max_seconds = self.max_ms / 1000.0

        return f'''
# Assert: {desc}
server.shell(
    name="Assert: {desc}",
    commands=[
        "TIME=$(curl -w '%{{time_total}}' -o /dev/null -s --max-time {self.timeout_seconds} {self.url}); [ \\"$(echo \\"$TIME < {max_seconds}\\" | bc)\\" -eq 1 ] || exit 1"
    ],
)
'''
