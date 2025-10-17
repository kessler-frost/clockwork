"""
Connected Services Example - Full-stack application with primitive connections.

This example demonstrates Clockwork's primitive connection system, which enables:
1. Dependency-aware deployment order
2. AI-powered configuration with context from connected primitives
3. Automatic environment variable generation for service communication
4. Network-aware container deployment

Architecture:
- PostgreSQL database (independent)
- Redis cache (independent)
- FastAPI backend (connected to postgres + redis)
- Background worker (connected to redis)

The connection system ensures:
- Deployment order: postgres/redis → api/worker
- AI generates appropriate DATABASE_URL, REDIS_URL env vars
- All services deployed on the same Docker network
"""

from clockwork.resources import DockerResource
from clockwork.assertions import (
    ContainerRunningAssert,
    PortAccessibleAssert,
    HealthcheckAssert,
)

# Layer 1: Data services (no dependencies)
# These deploy first since they have no connections

postgres = DockerResource(
    description="PostgreSQL database server for application data",
    name="postgres-db",
    image="postgres:15-alpine",
    ports=["5432:5432"],
    env_vars={
        "POSTGRES_DB": "appdb",
        "POSTGRES_USER": "admin",
        "POSTGRES_PASSWORD": "secret123"
    },
    assertions=[
        ContainerRunningAssert(timeout_seconds=10),
        PortAccessibleAssert(port=5432, host="localhost", protocol="tcp"),
    ]
)

redis = DockerResource(
    description="Redis cache server for session storage and job queues",
    name="redis-cache",
    image="redis:7-alpine",
    ports=["6379:6379"],
    assertions=[
        ContainerRunningAssert(timeout_seconds=10),
        PortAccessibleAssert(port=6379, host="localhost", protocol="tcp"),
    ]
)

# Layer 2: Application services (depend on data services)
# These deploy after postgres and redis are ready

api = DockerResource(
    description="Nginx web server acting as API gateway and static content server. Connects to backend database and cache services.",
    name="api-server",
    image="nginx:alpine",  # Nginx has default running process
    ports=["8000:80"],  # Map host 8000 to container 80
    connections=[postgres, redis],  # AI will use this context to generate DATABASE_URL and REDIS_URL
    assertions=[
        ContainerRunningAssert(timeout_seconds=10),
        PortAccessibleAssert(port=8000, host="localhost", protocol="tcp"),
        HealthcheckAssert(url="http://localhost:8000"),
    ]
)

worker = DockerResource(
    description="Nginx web server acting as background worker proxy for processing async jobs. Monitors Redis for new tasks.",
    name="worker-service",
    image="nginx:alpine",  # Nginx has default running process
    connections=[redis],  # AI will use this context to generate REDIS_URL
    assertions=[
        ContainerRunningAssert(timeout_seconds=10),
    ]
)

# Note: Deployment order will be automatically determined:
# 1. postgres-db (no dependencies)
# 2. redis-cache (no dependencies)
# 3. api-server (depends on postgres + redis)
# 4. worker-service (depends on redis)
#
# AI completion behavior:
# - api-server: Should generate DATABASE_URL pointing to postgres-db and REDIS_URL pointing to redis-cache
# - worker-service: Should generate REDIS_URL pointing to redis-cache
# - All services: Should be placed on the same Docker network for inter-container communication
