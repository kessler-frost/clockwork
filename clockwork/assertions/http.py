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


class PortAccessibleAssert(BaseAssertion):
    """Assert that a network port is accessible and listening.

    Checks if a TCP or UDP port is open and accepting connections on the
    specified host.

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
