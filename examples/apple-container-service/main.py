"""
Apple Container Service Example - Demonstrates Apple Containers on macOS.

This example shows how to deploy containers using Apple's native container runtime.
All fields are specified to avoid AI completion issues.
"""

from clockwork.resources import AppleContainerResource
from clockwork.assertions import (
    HealthcheckAssert,
    PortAccessibleAssert,
    ContainerRunningAssert,
)

# Example with all fields specified (no AI completion needed)
nginx_web = AppleContainerResource(
    description="lightweight nginx web server for testing",
    name="nginx-test",
    image="nginx:alpine",
    ports=["8090:80"],
    volumes=[],
    env_vars={},
    networks=[],
    assertions=[
        ContainerRunningAssert(timeout_seconds=10),
        PortAccessibleAssert(port=8090, host="localhost", protocol="tcp"),
        HealthcheckAssert(url="http://localhost:8090", expected_status=200, timeout_seconds=5),
    ]
)
