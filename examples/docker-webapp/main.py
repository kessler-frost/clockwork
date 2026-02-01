"""Docker Web Application Example

This example demonstrates using DockerResource for cross-platform container
management. It creates a simple web application stack with:
- PostgreSQL database
- Redis cache
- Nginx web server

Works on any platform with Docker installed (Linux, macOS, Windows).
"""

from clockwork.assertions import (
    ContainerRunningAssert,
    HealthcheckAssert,
    PortAccessibleAssert,
)
from clockwork.resources import BlankResource, DockerResource

# Step 1: Create the composite resource at module level for Clockwork to discover
# BlankResource acts as a container for related resources
webapp = BlankResource(
    name="docker-webapp",
    description="A simple web application using Docker containers",
)

# Step 2: Add database to the composite
webapp.add(
    DockerResource(
        name="postgres-db",
        description="PostgreSQL database for the web application",
        image="postgres:15-alpine",
        ports=["5432:5432"],
        volumes=["pg_data:/var/lib/postgresql/data"],
        env_vars={
            "POSTGRES_USER": "webapp",
            "POSTGRES_PASSWORD": "webapp_password",  # pragma: allowlist secret
            "POSTGRES_DB": "webapp_db",
        },
        # Assertions verify the database is running and accessible
        assertions=[
            ContainerRunningAssert(),
            PortAccessibleAssert(port=5432),
        ],
    )
)

# Step 3: Add cache to the composite
webapp.add(
    DockerResource(
        name="redis-cache",
        description="Redis cache for session storage and caching",
        image="redis:7-alpine",
        ports=["6379:6379"],
        # Assertions verify the cache is running and accessible
        assertions=[
            ContainerRunningAssert(),
            PortAccessibleAssert(port=6379),
        ],
    )
)

# Step 4: Add web server to the composite
webapp.add(
    DockerResource(
        name="nginx-web",
        description="Nginx web server for serving static content",
        image="nginx:alpine",
        ports=["8080:80"],
        # Assertions verify the web server is running and responding
        assertions=[
            ContainerRunningAssert(),
            PortAccessibleAssert(port=8080),
            HealthcheckAssert(url="http://localhost:8080/"),
        ],
    )
)

# Step 5: Establish dependencies between resources
# Using .connect() ensures proper startup order:
# 1. postgres starts first
# 2. redis starts second
# 3. nginx starts last (after both dependencies are ready)
webapp.children["nginx-web"].connect(
    webapp.children["postgres-db"]
)  # Web server waits for database
webapp.children["nginx-web"].connect(
    webapp.children["redis-cache"]
)  # Web server waits for cache

# The composite pattern provides several benefits:
# 1. Logical grouping: All related resources are together
# 2. Clear dependencies: .connect() shows relationships
# 3. Ordered deployment: Resources deploy in dependency order
# 4. Easy management: Deploy/destroy the entire stack together

# To deploy this example:
# cd examples/docker-webapp
# uv run clockwork apply

# To verify assertions:
# uv run clockwork assert

# To destroy:
# uv run clockwork destroy
