"""HTTP-based assertions for web services and APIs."""

import socket
from typing import TYPE_CHECKING, Literal

import httpx

from .base import BaseAssertion

if TYPE_CHECKING:
    from clockwork.resources.base import Resource

# Module-level shared HTTP client for connection pooling
_http_client: httpx.AsyncClient | None = None


def get_http_client() -> httpx.AsyncClient:
    """Get or create the shared HTTP client with connection pooling.

    This client is reused across all HTTP assertions for better performance
    through connection pooling and keep-alive connections.

    Returns:
        Shared httpx.AsyncClient instance configured with:
        - 30s timeout
        - Max 10 concurrent connections
        - Max 5 keep-alive connections
    """
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(
            timeout=30.0,
            limits=httpx.Limits(
                max_connections=10, max_keepalive_connections=5
            ),
        )
    return _http_client


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

    async def check(self, resource: "Resource") -> bool:
        """Check if the HTTP endpoint returns expected status code.

        Args:
            resource: The resource to validate

        Returns:
            True if endpoint returns expected status, False otherwise
        """
        try:
            client = get_http_client()
            response = await client.get(self.url, timeout=self.timeout_seconds)
            return response.status_code == self.expected_status
        except Exception:
            return False


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

    async def check(self, resource: "Resource") -> bool:
        """Check if the port is accessible.

        Args:
            resource: The resource to validate

        Returns:
            True if port is accessible, False otherwise
        """
        try:
            if self.protocol == "tcp":
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(self.timeout_seconds)
                result = sock.connect_ex((self.host, self.port))
                sock.close()
                return result == 0
            else:
                # UDP check
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.settimeout(self.timeout_seconds)
                sock.sendto(b"", (self.host, self.port))
                sock.recvfrom(1024)
                sock.close()
                return True
        except Exception:
            return False
