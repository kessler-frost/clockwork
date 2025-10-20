"""Nested Composites Example

This example demonstrates multi-level hierarchical composite structures by
creating a three-level architecture:

Level 1: Full Stack (top-level composite)
Level 2: Database Cluster + Application Tier (mid-level composites)
Level 3: Individual Resources (containers)

This pattern is useful for modeling complex, layered infrastructure with
clear separation of concerns.
"""

from clockwork.resources import BlankResource, DockerResource
from clockwork.resources.assertions import (
    ContainerRunningAssert,
    HealthcheckAssert,
    PortAccessibleAssert,
)


def main():
    """Create a three-level nested composite structure."""

    # ==================================================================
    # LEVEL 1: Top-level composite (Full Stack)
    # ==================================================================
    # This is the root composite that contains everything
    full_stack = BlankResource(
        name="full-stack",
        description="Complete three-tier application with database cluster and app services",
    )

    # ==================================================================
    # LEVEL 2: Mid-level composites (Database Cluster & Application Tier)
    # ==================================================================

    # --- Database Cluster Composite ---
    # Groups all database-related resources together
    db_cluster = full_stack.add(
        BlankResource(
            name="database-cluster",
            description="PostgreSQL cluster with primary and read replica",
        )
    )

    # --- Application Tier Composite ---
    # Groups all application services together
    app_tier = full_stack.add(
        BlankResource(
            name="application-tier",
            description="Application services including API, worker, and web frontend",
        )
    )

    # ==================================================================
    # LEVEL 3: Leaf resources (Individual containers)
    # ==================================================================

    # --- Database Cluster Resources ---
    # Add resources to the database cluster composite

    # Primary database (read-write)
    db_primary = db_cluster.add(
        DockerResource(
            name="postgres-primary",
            description="Primary PostgreSQL database with read-write access",
            image="postgres:15-alpine",
            ports=["5432:5432"],
            env_vars={
                "POSTGRES_USER": "appuser",
                "POSTGRES_PASSWORD": "apppassword",
                "POSTGRES_DB": "appdb",
                # Primary-specific config
                "POSTGRES_REPLICATION_MODE": "master",
            },
            assertions=[
                ContainerRunningAssert(),
                PortAccessibleAssert(port=5432),
            ],
        )
    )

    # Read replica (read-only)
    db_replica = db_cluster.add(
        DockerResource(
            name="postgres-replica",
            description="PostgreSQL read replica for scaling read operations",
            image="postgres:15-alpine",
            ports=["5433:5432"],  # Different host port to avoid conflicts
            env_vars={
                "POSTGRES_USER": "appuser",
                "POSTGRES_PASSWORD": "apppassword",
                "POSTGRES_DB": "appdb",
                # Replica-specific config
                "POSTGRES_REPLICATION_MODE": "slave",
                "POSTGRES_MASTER_HOST": "postgres-primary",
            },
            assertions=[
                ContainerRunningAssert(),
                PortAccessibleAssert(port=5433),
            ],
        )
    )

    # Replica depends on primary
    db_replica.connect(db_primary)

    # --- Application Tier Resources ---
    # Add resources to the application tier composite

    # REST API server
    api_service = app_tier.add(
        DockerResource(
            name="api-service",
            description="REST API service handling HTTP requests, connected to primary database",
            ports=["8000:8000"],
            env_vars={
                # Connect to primary for read-write operations
                "DATABASE_URL": "postgresql://appuser:apppassword@postgres-primary:5432/appdb",
                "API_PORT": "8000",
                "NODE_ENV": "production",
            },
            assertions=[
                ContainerRunningAssert(),
                PortAccessibleAssert(port=8000),
                HealthcheckAssert(url="http://localhost:8000/health"),
            ],
        )
    )

    # Background worker service
    worker_service = app_tier.add(
        DockerResource(
            name="worker-service",
            description="Background worker processing jobs from queue, connected to primary database",
            env_vars={
                # Connect to primary for read-write operations
                "DATABASE_URL": "postgresql://appuser:apppassword@postgres-primary:5432/appdb",
                "WORKER_THREADS": "4",
            },
            assertions=[
                ContainerRunningAssert(),
            ],
        )
    )

    # Web frontend (reads from replica)
    web_frontend = app_tier.add(
        DockerResource(
            name="web-frontend",
            description="Web frontend serving static content, connected to read replica",
            ports=["3000:3000"],
            env_vars={
                # Connect to replica for read-only operations (better performance)
                "DATABASE_URL": "postgresql://appuser:apppassword@postgres-replica:5432/appdb",
                "API_URL": "http://api-service:8000",
                "PORT": "3000",
            },
            assertions=[
                ContainerRunningAssert(),
                PortAccessibleAssert(port=3000),
                HealthcheckAssert(url="http://localhost:3000"),
            ],
        )
    )

    # ==================================================================
    # Dependencies between tiers
    # ==================================================================
    # Application services depend on database resources
    # These connections work across composite boundaries

    # API needs primary database (for writes)
    api_service.connect(db_primary)

    # Worker needs primary database (for writes)
    worker_service.connect(db_primary)

    # Frontend needs replica (for reads) and API
    web_frontend.connect(db_replica)
    web_frontend.connect(api_service)

    # ==================================================================
    # Architecture Summary
    # ==================================================================
    # This creates the following hierarchy:
    #
    # full-stack (Level 1)
    # ├── database-cluster (Level 2)
    # │   ├── postgres-primary (Level 3)
    # │   └── postgres-replica (Level 3) → depends on postgres-primary
    # └── application-tier (Level 2)
    #     ├── api-service (Level 3) → depends on postgres-primary
    #     ├── worker-service (Level 3) → depends on postgres-primary
    #     └── web-frontend (Level 3) → depends on postgres-replica, api-service
    #
    # Benefits of this structure:
    # 1. Clear separation: Database vs Application concerns
    # 2. Reusability: Can swap out entire tiers
    # 3. Scalability: Easy to add more replicas or services
    # 4. Organization: Three-level hierarchy is easy to navigate

    # ==================================================================
    # Accessing Nested Children with .children Property
    # ==================================================================
    # The new .children property provides clean dict-style access at all levels

    # Access level 2 composites from the top-level composite:
    db_tier = full_stack.children["database-cluster"]
    app_layer = full_stack.children["application-tier"]

    # Access level 3 resources from mid-level composites:
    primary = db_tier.children["postgres-primary"]
    replica = db_tier.children["postgres-replica"]

    # Navigate through the hierarchy:
    api_from_root = full_stack.children["application-tier"].children["api-service"]

    # Safe access with default values:
    cache = app_layer.children.get("redis-cache", None)  # Returns None if not found

    # Iterate over mid-level composites:
    print("\nTier-level structure:")
    for tier_name in full_stack.children:
        tier = full_stack.children[tier_name]
        print(f"\n{tier_name}:")
        # Iterate over resources in each tier:
        for resource_name in tier.children:
            resource = tier.children[resource_name]
            print(f"  - {resource_name} ({resource.__class__.__name__})")

    # Count children at different levels:
    print(f"\nTotal tiers: {len(full_stack.children)}")
    print(f"Database cluster size: {len(db_tier.children)}")
    print(f"Application services: {len(app_layer.children)}")

    return full_stack


if __name__ == "__main__":
    # Create and deploy the nested composite structure
    stack = main()

    # To deploy this example:
    # cd /Users/sankalp/dev/clockwork/examples/composite-resources/nested-composites
    # uv run clockwork apply

    # To verify assertions:
    # uv run clockwork assert

    # To destroy:
    # uv run clockwork destroy

    # Note: Deployment order is automatically determined by dependencies:
    # 1. postgres-primary (no deps)
    # 2. postgres-replica (depends on primary)
    # 3. api-service, worker-service (depend on primary)
    # 4. web-frontend (depends on replica and api-service)
