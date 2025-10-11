"""
Docker Service Example - AI completes everything from a description.

This example demonstrates the power of Clockwork's minimal API:
- Just describe what you want, AI handles the rest
- One minimal example (just description)
- One advanced example (description + overrides + assertions)
"""

from clockwork.resources import DockerResource
from clockwork.assertions import (
    HealthcheckAssert,
    PortAccessibleAssert,
    ContainerRunningAssert,
)

# Example with all fields specified (no AI completion needed)
nginx_web = DockerResource(
    description="lightweight nginx web server for testing",
    name="nginx-web",
    image="nginx:alpine",
    ports=["8091:80"],
    volumes=[],
    env_vars={},
    networks=[],
    assertions=[
        ContainerRunningAssert(timeout_seconds=10),
        PortAccessibleAssert(port=8091, host="localhost", protocol="tcp"),
        HealthcheckAssert(url="http://localhost:8091", expected_status=200, timeout_seconds=5),
    ]
)
