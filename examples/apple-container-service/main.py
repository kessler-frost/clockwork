"""
Apple Container Service Example - Demonstrates Apple Containers on macOS.

This example shows how to deploy containers using Apple's native container runtime.
Includes AI-generated template file example.
"""

from clockwork.resources import AppleContainerResource, TemplateFileResource
from clockwork.assertions import (
    HealthcheckAssert,
    PortAccessibleAssert,
    ContainerRunningAssert,
    FileExistsAssert,
)

# Example 1: AI-generated template file (minimal - AI completes template_content and variables)
redis_config = TemplateFileResource(
    description="Redis configuration file for a simple cache server with 256MB max memory and LRU eviction policy",
    name="redis.conf",
    directory="scratch",
    # AI will generate template_content and variables based on description!
)

# Example 2: Apple Container (simplified - no need for empty values!)
nginx_web = AppleContainerResource(
    description="lightweight nginx web server for testing",
    name="nginx-test",
    image="nginx:alpine",
    ports=["8090:80"],
    # volumes, env_vars, networks default to empty - no need to specify!
    assertions=[
        ContainerRunningAssert(timeout_seconds=10),
        PortAccessibleAssert(port=8090, host="localhost", protocol="tcp"),
        HealthcheckAssert(url="http://localhost:8090", expected_status=200, timeout_seconds=5),
    ]
)
