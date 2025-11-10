"""Connections Showcase

Demonstrates all Clockwork connection types in a realistic microservices architecture:

Connection Types:
1. DependencyConnection - Simple deployment ordering
2. DatabaseConnection - Database with connection strings and schema
3. NetworkConnection - Docker networks for service discovery
4. FileConnection - Volume sharing and config files
5. ServiceMeshConnection - Service discovery with health checks

Architecture:
- PostgreSQL database with schema
- Redis cache
- API server (connects to database and redis via network)
- Frontend (connects to API via service mesh)
- Shared configuration via file connections

Each connection type demonstrates:
- When to use it
- How AI completion works with descriptions
- The benefits over manual configuration
"""

from pathlib import Path

from clockwork.assertions import ContainerRunningAssert, HealthcheckAssert
from clockwork.connections import (
    DatabaseConnection,
    FileConnection,
    NetworkConnection,
    ServiceMeshConnection,
)
from clockwork.resources import DockerResource, FileResource

# =============================================================================
# 1. DATABASE WITH DatabaseConnection
# =============================================================================
# DatabaseConnection automatically:
# - Generates connection strings
# - Waits for database readiness
# - Executes schema files
# - Injects DATABASE_URL into connected services

postgres = DockerResource(
    name="postgres",
    image="postgres:15-alpine",
    ports=["5432:5432"],
    env_vars={
        "POSTGRES_DB": "appdb",
        "POSTGRES_USER": "postgres",
        "POSTGRES_PASSWORD": "secret123",  # pragma: allowlist secret
    },
    assertions=[ContainerRunningAssert(timeout_seconds=15)],
)

# =============================================================================
# 2. REDIS WITH SIMPLE DependencyConnection
# =============================================================================
# DependencyConnection is the simplest - just establishes deployment order
# No setup resources needed, just ensures redis deploys before dependent services

redis = DockerResource(
    name="redis",
    image="redis:7-alpine",
    ports=["6379:6379"],
    assertions=[ContainerRunningAssert(timeout_seconds=10)],
)

# =============================================================================
# 3. API SERVER WITH DatabaseConnection AND NetworkConnection
# =============================================================================
# This demonstrates combining multiple connection types on one resource

api = DockerResource(
    name="api",
    image="nginx:alpine",  # Using nginx for demo (replace with actual API image)
    ports=["8000:80"],
    assertions=[
        ContainerRunningAssert(timeout_seconds=15),
        HealthcheckAssert(url="http://localhost:8000"),
    ],
)

# DatabaseConnection: Automatically injects DATABASE_URL into api's env_vars
# The connection string is built from the template with postgres connection info
api.connect(
    DatabaseConnection(
        to_resource=postgres,
        connection_string_template="postgresql://{user}:{password}@{host}:{port}/{database}",
        username="postgres",
        password="secret123",  # pragma: allowlist secret
        database_name="appdb",
        schema_file=str(
            Path(__file__).parent / "schema.sql"
        ),  # Execute schema on startup
        wait_for_ready=True,
        timeout=30,
    )
)

# NetworkConnection: Creates a Docker network and connects both containers
# This enables service discovery - api can reach redis at "redis:6379"
# Also injects REDIS_HOST=redis into api's environment
api.connect(
    NetworkConnection(
        to_resource=redis,
        network_name="backend-network",
        driver="bridge",
        internal=False,  # Allow external access
    )
)

# =============================================================================
# 4. CONFIG FILE WITH FileConnection
# =============================================================================
# FileConnection demonstrates:
# - Mounting FileResource outputs to containers
# - Read-only mounts for immutable config
# - Sharing configuration between resources

config_file = FileResource(
    name="api-config",
    path=str(Path(__file__).parent / "config.json"),
    content='{"log_level": "info", "max_connections": 100, "timeout": 30}',
)

# Mount the config file into the API container at /app/config.json
# read_only=True ensures the container can't modify the config
api.connect(
    FileConnection(
        to_resource=config_file,
        mount_path="/etc/app/config.json",
        read_only=True,
    )
)

# =============================================================================
# 5. SHARED DATA VOLUME WITH FileConnection
# =============================================================================
# FileConnection can also create and share Docker volumes between containers
# This is useful for persistent data, shared uploads, etc.

# Create a storage container that will use the shared volume
storage = DockerResource(
    name="storage",
    image="nginx:alpine",
    assertions=[ContainerRunningAssert(timeout_seconds=10)],
)

# Create a shared volume - both api and storage can access it
# AI could complete volume_name if we provided only description
shared_volume_connection = FileConnection(
    to_resource=storage,
    mount_path="/data/shared",
    volume_name="app-shared-data",
    create_volume=True,
    read_only=False,
)

api.connect(shared_volume_connection)

# =============================================================================
# 6. FRONTEND WITH ServiceMeshConnection
# =============================================================================
# ServiceMeshConnection provides:
# - Automatic service URL injection
# - Port discovery from target service
# - Health check assertions
# - Service discovery naming

frontend = DockerResource(
    name="frontend",
    image="nginx:alpine",
    ports=["80:80"],
    assertions=[
        ContainerRunningAssert(timeout_seconds=10),
        HealthcheckAssert(url="http://localhost:80"),
    ],
)

# ServiceMeshConnection automatically:
# 1. Discovers port 8000 from api.ports
# 2. Sets service_name to "api"
# 3. Injects API_URL=http://api:8000 into frontend's env_vars
# 4. Adds health check assertion for http://api:8000/health
frontend.connect(
    ServiceMeshConnection(
        to_resource=api,
        protocol="http",
        health_check_path="/health",
        load_balancing="round_robin",
    )
)

# =============================================================================
# 7. SIMPLE DEPENDENCY (AUTO-CREATES DependencyConnection)
# =============================================================================
# When you call .connect() with a plain resource (not a Connection object),
# Clockwork automatically creates a DependencyConnection
# This ensures frontend deploys after redis is ready

frontend.connect(
    redis
)  # Shorthand for: DependencyConnection(to_resource=redis)

# =============================================================================
# SUMMARY
# =============================================================================
# Deployment order (determined automatically from connections):
# 1. postgres (no dependencies)
# 2. redis (no dependencies)
# 3. config_file (no dependencies)
# 4. storage (no dependencies)
# 5. api (depends on: postgres, redis, config_file, storage)
# 6. frontend (depends on: api, redis)
#
# Environment variables injected automatically:
# - api.env_vars["DATABASE_URL"] = "postgresql://postgres:secret123@postgres:5432/appdb"  # pragma: allowlist secret
# - api.env_vars["REDIS_HOST"] = "redis"
# - frontend.env_vars["API_URL"] = "http://api:8000"
#
# Networks created automatically:
# - backend-network (contains: api, redis)
#
# Volumes created automatically:
# - app-shared-data (mounted in: api at /data/shared, storage at /data/shared)
#
# Files mounted automatically:
# - config.json -> api:/etc/app/config.json (read-only)
#
# Run with:
#   cd examples/connections-showcase
#   clockwork apply
#   clockwork assert  # Verify all connections are working
#   clockwork destroy  # Clean up
