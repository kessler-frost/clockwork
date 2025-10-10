"""
Apple Container Service Example - Deploy a web service with type-safe assertions.

This example demonstrates:
- AppleContainerResource with AI-suggested image
- Type-safe assertion classes for container validation
- Common assertion patterns for Apple Containers
"""

from clockwork.resources import AppleContainerResource
from clockwork.assertions import (
    HealthcheckAssert,
    PortAccessibleAssert,
    ContainerRunningAssert,
    LogContainsAssert,
    ResponseTimeAssert,
)

# Web API service with comprehensive type-safe assertions
api = AppleContainerResource(
    name="clockwork-demo",
    description="A lightweight web server for testing and demos",
    ports=["8090:80"],
    assertions=[
        # Type-safe built-in assertions (instant compilation)
        ContainerRunningAssert(
            timeout_seconds=10
        ),
        PortAccessibleAssert(
            port=8090,
            host="localhost",
            protocol="tcp"
        ),
        HealthcheckAssert(
            url="http://localhost:8090",
            expected_status=200,
            timeout_seconds=5
        ),
        ResponseTimeAssert(
            url="http://localhost:8090",
            max_ms=200,
            timeout_seconds=5
        ),
        LogContainsAssert(
            pattern="ready for start up",  # Nginx startup message
            lines=50
        ),
    ]
)
