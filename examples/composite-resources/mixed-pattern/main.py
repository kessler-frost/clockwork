"""Mixed Pattern Example

This example demonstrates how to combine composite resources with standalone
resources in the same project. It shows:

1. A composite web app (database + API)
2. A standalone shared monitoring service (Prometheus)
3. The web app depends on the monitoring service

This pattern is useful when you have:
- Some resources that are logically grouped (composites)
- Other resources that are shared/independent (standalone)
"""

from clockwork.assertions import (
    ContainerRunningAssert,
    HealthcheckAssert,
    PortAccessibleAssert,
)
from clockwork.resources import AppleContainerResource, BlankResource

# ==================================================================
# STANDALONE RESOURCE: Shared Monitoring Service
# ==================================================================
# This is NOT part of any composite - it's a standalone resource
# that can be shared across multiple applications.
# Resources defined at module level for Clockwork to discover
#
# Use standalone resources when:
# - Resource is shared across multiple applications
# - Resource has independent lifecycle
# - Resource doesn't logically belong to a specific group

monitoring = AppleContainerResource(
    name="prometheus",
    description="Shared Prometheus monitoring service for metrics collection",
    image="prom/prometheus:v2.45.0",
    ports=["9090:9090"],
    volumes=[
        # Mount config file (you would create this separately)
        "./prometheus.yml:/etc/prometheus/prometheus.yml",
    ],
    assertions=[
        ContainerRunningAssert(),
        PortAccessibleAssert(port=9090),
        HealthcheckAssert(url="http://localhost:9090/-/healthy"),
    ],
)

# ==================================================================
# COMPOSITE RESOURCE: Web Application
# ==================================================================
# This IS a composite - it groups related app-specific resources.
#
# Use composites when:
# - Resources are tightly coupled
# - Resources deploy/destroy together
# - Resources share a common purpose

webapp = BlankResource(
    name="webapp",
    description="Web application with database and API service",
)

# --- Database (part of webapp composite) ---
webapp.add(
    AppleContainerResource(
        name="postgres-db",
        description="PostgreSQL database for the web application",
        image="postgres:15-alpine",
        ports=["5432:5432"],
        env_vars={
            "POSTGRES_USER": "webapp",
            "POSTGRES_PASSWORD": "webapp_password",
            "POSTGRES_DB": "webapp_db",
        },
        assertions=[
            ContainerRunningAssert(),
            PortAccessibleAssert(port=5432),
        ],
    )
)

# --- API Service (part of webapp composite) ---
webapp.add(
    AppleContainerResource(
        name="api-service",
        description="FastAPI service with metrics endpoint for Prometheus scraping",
        ports=["8000:8000"],
        env_vars={
            # Database connection
            "DATABASE_URL": "postgresql://webapp:webapp_password@postgres-db:5432/webapp_db",
            # Monitoring configuration
            "PROMETHEUS_URL": "http://prometheus:9090",
            "METRICS_ENABLED": "true",
            "METRICS_PORT": "8000",
        },
        assertions=[
            ContainerRunningAssert(),
            PortAccessibleAssert(port=8000),
            HealthcheckAssert(url="http://localhost:8000/health"),
            # Verify metrics endpoint is available
            HealthcheckAssert(url="http://localhost:8000/metrics"),
        ],
    )
)

# ==================================================================
# DEPENDENCIES
# ==================================================================

# --- Internal composite dependencies ---
# API depends on database (both within same composite)
webapp.children["api-service"].connect(webapp.children["postgres-db"])

# --- External dependency (composite → standalone) ---
# API depends on monitoring service (crosses composite boundary)
# This shows that composites can depend on external resources!
webapp.children["api-service"].connect(monitoring)

# Why this matters:
# 1. Monitoring starts first (standalone, no deps)
# 2. Database starts second (part of webapp)
# 3. API starts last (needs both database and monitoring)

# ==================================================================
# Architecture Summary
# ==================================================================
# This creates the following structure:
#
# prometheus (standalone)
# └── Port: 9090
#
# webapp (composite)
# ├── postgres-db
# │   └── Port: 5432
# └── api-service
#     ├── Port: 8000
#     ├── Depends on: postgres-db (internal)
#     └── Depends on: prometheus (external)
#
# Key insights:
# 1. prometheus is standalone (shared, independent lifecycle)
# 2. webapp is a composite (grouped, coupled lifecycle)
# 3. Dependencies work across this boundary
# 4. You can mix patterns in the same project

# ==================================================================
# Accessing Children in Mixed Pattern
# ==================================================================
# The .children property works seamlessly with composite resources
#
# Example usage (commented out to avoid creating module-level variables):
#
# # Access children from the composite using dict-style syntax:
# db = webapp.children["postgres-db"]
# webapp.children["api-service"]
#
# # Verify child configuration:
# if "postgres-db" in webapp.children:
#     print(f"Database configured on port: {db.ports}")
#
# # Iterate over composite children while standalone resource exists separately:
# print("\nWebapp composite children:")
# for name, child in webapp.children.items():
#     print(f"  - {name}: {child.description}")
#
# # The standalone resource (monitoring) has no children:
# print(f"\nMonitoring has children: {len(monitoring.children) > 0}")  # False
#
# # This demonstrates how composites and standalones coexist cleanly
# # - Composites group resources: access via .children["name"]
# # - Standalones are independent: accessed directly by variable


def alternative_pattern():
    """Alternative: Everything as standalone resources.

    This function shows what the same architecture would look like
    without composites - just for comparison.
    """
    # Without composites, you have flat structure
    monitoring = AppleContainerResource(
        name="prometheus", description="Monitoring"
    )
    database = AppleContainerResource(name="postgres", description="Database")
    api = AppleContainerResource(name="api", description="API")

    api.connect(database)
    api.connect(monitoring)

    # This works, but:
    # - Less organized (no logical grouping)
    # - Harder to see what's related
    # - Can't manage webapp as a unit

    return monitoring, database, api


# ==================================================================
# Guidelines for choosing between composite and standalone
# ==================================================================
#
# COMPOSITE (BlankResource):
# ✓ Resources are tightly coupled
# ✓ Resources share a lifecycle
# ✓ Resources form a logical unit
# ✓ You want to manage them together
# Examples: Web app stack, microservice cluster, dev environment
#
# STANDALONE:
# ✓ Resource is shared across apps
# ✓ Resource has independent lifecycle
# ✓ Resource doesn't belong to a group
# Examples: Monitoring, logging, shared databases, message queues
#
# MIXED (This Example):
# ✓ Some resources grouped, others shared
# ✓ Clear separation of concerns
# ✓ Flexible dependency management
# Examples: Multiple apps sharing monitoring, shared services + app-specific stacks


# To deploy this example:
# cd examples/composite-resources/mixed-pattern
# uv run clockwork apply

# To verify assertions:
# uv run clockwork assert

# To destroy:
# uv run clockwork destroy

# Note: You can also destroy selectively:
# - Destroy just the webapp: Remove webapp but keep monitoring
# - Destroy just monitoring: Remove monitoring but keep webapp (will fail if webapp depends on it)
