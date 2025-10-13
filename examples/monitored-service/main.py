"""
Monitored Service Example - Demonstrates Clockwork service monitoring.

This example shows how the Clockwork service continuously monitors resources
and automatically remediates failures through AI-powered resource completion.

Architecture:
- Redis cache (independent)
- Nginx web server (depends on Redis)
- Background monitoring by Clockwork service
- Auto-remediation on failures

The service will:
1. Monitor resource health continuously
2. Detect failures (container crashes, port issues, etc.)
3. Collect diagnostics (logs, status)
4. Use AI to fix the configuration
5. Re-apply and validate the fix
"""

from clockwork.resources import DockerResource
from clockwork.assertions import (
    ContainerRunningAssert,
    PortAccessibleAssert,
    HealthcheckAssert,
)

# Layer 1: Cache service
redis = DockerResource(
    description="Redis cache server for session storage",
    name="redis-monitored",
    image="redis:7-alpine",
    ports=["6380:6379"],  # Using 6380 on host to avoid conflicts
    volumes=["redis_monitored_data:/data"],
    assertions=[
        ContainerRunningAssert(timeout_seconds=10),
        PortAccessibleAssert(port=6380, host="localhost", protocol="tcp"),
    ]
)

# Layer 2: Web server (depends on cache)
nginx = DockerResource(
    description="Nginx web server for testing monitoring and auto-remediation",
    name="nginx-monitored",
    image="nginx:alpine",
    ports=["8081:80"],  # Using 8081 on host to avoid conflicts
    connections=[redis],  # Will share network with redis
    assertions=[
        ContainerRunningAssert(timeout_seconds=10),
        PortAccessibleAssert(port=8081, host="localhost", protocol="tcp"),
        HealthcheckAssert(url="http://localhost:8081"),
    ]
)

# Note: Deploy these resources with the Clockwork service running:
# 1. clockwork service start
# 2. clockwork apply
#
# The service will monitor these resources and automatically remediate failures.
#
# To test auto-remediation:
# 1. docker stop nginx-monitored
# 2. Watch the service logs to see remediation in action
# 3. The service will detect the failure, collect diagnostics, and restart the container
