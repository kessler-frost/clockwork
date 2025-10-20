"""Simple Web Application Composite Example

This example demonstrates the basic composite resource pattern by creating
a simple web application stack with:
- PostgreSQL database
- Redis cache
- Node.js API server

All resources are grouped into a single BlankResource composite for
organized deployment and management.
"""

from clockwork.resources import BlankResource, DockerResource
from clockwork.resources.assertions import (
    ContainerRunningAssert,
    HealthcheckAssert,
    PortAccessibleAssert,
)


def main():
    """Create a simple web application stack using composite pattern."""

    # Step 1: Create the composite resource
    # BlankResource acts as a container for related resources
    webapp = BlankResource(
        name="simple-webapp",
        description="A simple web application with database, cache, and API",
    )

    # Step 2: Add database to the composite
    # Using .add() adds the resource as a child and returns it for further use
    postgres = webapp.add(
        DockerResource(
            name="postgres-db",
            description="PostgreSQL database for the web application",
            image="postgres:15-alpine",
            ports=["5432:5432"],
            env_vars={
                "POSTGRES_USER": "webapp",
                "POSTGRES_PASSWORD": "webapp_password",
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
    redis = webapp.add(
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

    # Step 4: Add API server to the composite
    api = webapp.add(
        DockerResource(
            name="api-server",
            description="Node.js API server connected to database and cache",
            # Let AI choose appropriate Node.js API image based on connections
            ports=["3000:3000"],
            env_vars={
                # Database connection string
                "DATABASE_URL": "postgresql://webapp:webapp_password@postgres-db:5432/webapp_db",
                # Redis connection string
                "REDIS_URL": "redis://redis-cache:6379",
                # Application config
                "NODE_ENV": "production",
                "PORT": "3000",
            },
            # Assertions verify the API is running and responding
            assertions=[
                ContainerRunningAssert(),
                PortAccessibleAssert(port=3000),
                HealthcheckAssert(url="http://localhost:3000/health"),
            ],
        )
    )

    # Step 5: Establish dependencies between resources
    # Using .connect() ensures proper startup order:
    # 1. postgres starts first
    # 2. redis starts second
    # 3. api starts last (after both dependencies are ready)
    api.connect(postgres)  # API depends on database
    api.connect(redis)  # API depends on cache

    # The composite pattern provides several benefits:
    # 1. Logical grouping: All related resources are together
    # 2. Clear dependencies: .connect() shows relationships
    # 3. Ordered deployment: Resources deploy in dependency order
    # 4. Easy management: Deploy/destroy the entire stack together

    # Step 6: Access children using the new .children property
    # The .children property provides dict-like access to child resources by name

    # Dict-style access (recommended - clean and intuitive):
    webapp.children["postgres-db"]
    webapp.children["redis-cache"]
    webapp.children["api-server"]

    # Safe access with .get() - returns None if child doesn't exist:
    webapp.children.get("non-existent", None)

    # Check if a child exists:
    if "postgres-db" in webapp.children:
        print("Database is configured!")

    # Iterate over all children by name:
    print("\nConfigured services:")
    for name in webapp.children:
        print(f"  - {name}")

    # Iterate over child resources using .values():
    print("\nAll child resources:")
    for child in webapp.children.values():
        print(f"  - {child.name}: {child.description}")

    # Iterate over (name, resource) pairs using .items():
    print("\nService details:")
    for name, child in webapp.children.items():
        print(f"  {name} -> {child.__class__.__name__}")

    return webapp


if __name__ == "__main__":
    # Create and deploy the web application composite
    app = main()

    # To deploy this example:
    # cd /Users/sankalp/dev/clockwork/examples/composite-resources/simple-webapp
    # uv run clockwork apply

    # To verify assertions:
    # uv run clockwork assert

    # To destroy:
    # uv run clockwork destroy
