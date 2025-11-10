"""Example: Service Mesh Connection with automatic service discovery.

This example demonstrates how to use ServiceMeshConnection to:
1. Automatically discover service ports
2. Inject service URLs into environment variables
3. Enable health checks for service-to-service communication
4. Configure TLS for secure communication

Run with:
    uv run clockwork apply examples/service-mesh-example.py
"""

from clockwork.connections import ServiceMeshConnection
from clockwork.resources import DockerResource

# Create backend API service
api = DockerResource(
    name="api-server",
    description="Backend API service",
    image="nginx:alpine",
    ports=["8000:80"],
)

# Create frontend web service that connects to API
web = DockerResource(
    name="web-frontend",
    description="Frontend web service",
    image="nginx:alpine",
    ports=["8080:80"],
)

# Create service mesh connection
# - Port will be auto-discovered from api.ports
# - Service name will default to "api-server"
# - URL will be injected as API_SERVER_URL=http://api-server:8000
# - Health check will verify the API is accessible
mesh = ServiceMeshConnection(
    to_resource=api,
    protocol="http",
    health_check_path="/",  # nginx default health endpoint
)

# Connect web to api through service mesh
web.connect(mesh)

# After connection, web.env_vars will contain:
# {
#     "API_SERVER_URL": "http://api-server:8000"
# }

# Example with explicit configuration
db = DockerResource(
    name="postgres-db",
    description="PostgreSQL database",
    image="postgres:15-alpine",
    ports=["5432:5432"],
    env_vars={
        "POSTGRES_PASSWORD": "secret",  # pragma: allowlist secret
        "POSTGRES_DB": "myapp",
    },
)

# API connects to database with explicit settings
db_mesh = ServiceMeshConnection(
    to_resource=db,
    protocol="tcp",
    port=5432,
    service_name="postgres-db",
    health_check_path=None,  # No HTTP health check for PostgreSQL
)

api.connect(db_mesh)

# After connection, api.env_vars will contain:
# {
#     "POSTGRES_DB_URL": "tcp://postgres-db:5432"
# }

# Example with TLS enabled (for production)
secure_api = DockerResource(
    name="secure-api",
    description="Secure API with TLS",
    image="nginx:alpine",
    ports=["8443:443"],
)

secure_web = DockerResource(
    name="secure-web",
    description="Secure web frontend",
    image="nginx:alpine",
    ports=["443:443"],
)

# Service mesh with TLS
secure_mesh = ServiceMeshConnection(
    to_resource=secure_api,
    protocol="https",
    tls_enabled=True,
    # cert_path and key_path will be auto-generated if not provided
    health_check_path="/health",
)

secure_web.connect(secure_mesh)

# After connection, secure_web.env_vars will contain:
# {
#     "SECURE_API_URL": "https://secure-api:8443"
# }
