"""
Connected Services Example - Full-stack application with DatabaseConnection.

This example demonstrates Clockwork's DatabaseConnection feature, which enables:
1. Dependency-aware deployment order
2. Automatic DATABASE_URL generation and injection
3. Optional schema file execution
4. Optional migrations directory support
5. Database readiness checking before deployment

Architecture:
- PostgreSQL database (independent)
- Redis cache (independent)
- FastAPI backend (connected to postgres via DatabaseConnection + redis)
- Background worker (connected to redis)

DatabaseConnection provides:
- Automatic connection string generation: postgresql://{user}:{password}@{host}:{port}/{database}
- Automatic DATABASE_URL environment variable injection
- Database readiness checking (wait_for_ready=True)
- Schema file execution (optional)
- Migrations directory support (optional)
"""

from clockwork.assertions import (
    ContainerRunningAssert,
    HealthcheckAssert,
    PortAccessibleAssert,
)
from clockwork.connections import DatabaseConnection
from clockwork.resources import DockerResource

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
        "POSTGRES_PASSWORD": "secret123",
    },
    assertions=[
        ContainerRunningAssert(timeout_seconds=10),
        PortAccessibleAssert(port=5432, host="localhost", protocol="tcp"),
    ],
)

redis = DockerResource(
    description="Redis cache server for session storage and job queues",
    name="redis-cache",
    image="redis:7-alpine",
    ports=["6379:6379"],
    assertions=[
        ContainerRunningAssert(timeout_seconds=10),
        PortAccessibleAssert(port=6379, host="localhost", protocol="tcp"),
    ],
)

# Layer 2: Application services (depend on data services)
# These deploy after postgres and redis are ready

# API server with DatabaseConnection for automatic configuration
api = DockerResource(
    description="Nginx web server acting as API gateway and static content server. Connects to backend database and cache services.",
    name="api-server",
    image="nginx:alpine",  # Nginx has default running process
    ports=["8000:80"],  # Map host 8000 to container 80
    assertions=[
        ContainerRunningAssert(timeout_seconds=10),
        PortAccessibleAssert(port=8000, host="localhost", protocol="tcp"),
        HealthcheckAssert(url="http://localhost:8000"),
    ],
)

# Connect API to database using DatabaseConnection
# This automatically:
# - Generates DATABASE_URL: postgresql://admin:secret123@postgres-db:5432/appdb  # pragma: allowlist secret
# - Injects it into api's environment variables
# - Waits for database to be ready before deploying api
# - Optionally executes schema file and migrations (see commented examples below)
api.connect(
    DatabaseConnection(
        to_resource=postgres,
        connection_string_template="postgresql://{user}:{password}@{host}:{port}/{database}",
        username="admin",
        password="secret123",
        database_name="appdb",
        env_var_name="DATABASE_URL",
        wait_for_ready=True,
        timeout=30,
        # Optional: Execute schema file on deployment
        # schema_file="schema.sql",
        # Optional: Run migrations from directory
        # migrations_dir="migrations/",
    )
)

# Connect API to Redis (simple connection for cache)
api.connect(redis)

worker = DockerResource(
    description="Nginx web server acting as background worker proxy for processing async jobs. Monitors Redis for new tasks.",
    name="worker-service",
    image="nginx:alpine",  # Nginx has default running process
    connections=[redis],  # AI will use this context to generate REDIS_URL
    assertions=[
        ContainerRunningAssert(timeout_seconds=10),
    ],
)

# Note: Deployment order will be automatically determined:
# 1. postgres-db (no dependencies)
# 2. redis-cache (no dependencies)
# 3. api-server (depends on postgres via DatabaseConnection + redis)
# 4. worker-service (depends on redis)
#
# DatabaseConnection behavior:
# - api-server: DatabaseConnection automatically generates and injects:
#   DATABASE_URL=postgresql://admin:secret123@postgres-db:5432/appdb  # pragma: allowlist secret
# - api-server: Also connects to redis for cache (AI may generate REDIS_URL)
# - worker-service: Simple connection to redis (AI may generate REDIS_URL)
# - All services: Should be placed on the same Docker network for inter-container communication
#
# Key benefits of DatabaseConnection:
# - No manual connection string construction
# - Automatic environment variable injection
# - Database readiness checking (waits for pg_isready)
# - Optional schema file execution on deployment
# - Optional migrations directory support
# - Type-safe configuration with Pydantic validation
