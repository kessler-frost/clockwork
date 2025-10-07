"""
Docker Service Example - Deploy a web service with type-safe assertions.

This example demonstrates:
- DockerServiceResource with AI-suggested image
- Type-safe assertion classes for container validation
- Common assertion patterns for Docker containers
"""

from clockwork.resources import DockerServiceResource
from clockwork.assertions import (
    HealthcheckAssert,
    PortAccessibleAssert,
    ContainerRunningAssert,
    LogContainsAssert,
    ResponseTimeAssert,
)

# Web API service with comprehensive type-safe assertions
api = DockerServiceResource(
    name="clockwork-demo",
    description="A lightweight web server for testing and demos",
    ports=["8080:80"],
    assertions=[
        # Type-safe built-in assertions (instant compilation)
        ContainerRunningAssert(
            timeout_seconds=10
        ),
        PortAccessibleAssert(
            port=8080,
            host="localhost",
            protocol="tcp"
        ),
        HealthcheckAssert(
            url="http://localhost:8080",
            expected_status=200,
            timeout_seconds=5
        ),
        ResponseTimeAssert(
            url="http://localhost:8080",
            max_ms=200,
            timeout_seconds=5
        ),
        LogContainsAssert(
            pattern="start",  # Generic pattern that matches common startup messages
            lines=50
        ),
    ]
)
