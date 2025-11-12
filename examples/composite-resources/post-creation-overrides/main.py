"""Post-Creation Overrides Example

This example demonstrates two approaches to configuring child resources:
1. Constructor-based configuration (specify everything upfront)
2. Post-creation overrides (modify after adding to composite)

It shows the trade-offs between each approach and when to use which pattern.

NOTE: This example demonstrates Pattern 3 (Hybrid Approach) at module level.
Other patterns are shown in helper functions for educational purposes.
"""

import os

from clockwork.assertions import (
    ContainerRunningAssert,
    HealthcheckAssert,
    PortAccessibleAssert,
)
from clockwork.resources import AppleContainerResource, BlankResource

# ==================================================================
# PATTERN 3: Hybrid Approach (Deployed Example)
# ==================================================================
# This combines the best of both approaches - used at module level for deployment
#
# Use this when:
# - Most config is known upfront
# - Some config needs to be dynamic or conditional
# - You want clarity + flexibility

webapp = BlankResource(
    name="webapp-pattern3",
    description="Web app using hybrid configuration approach",
)

# Specify core config in constructor
webapp.add(
    AppleContainerResource(
        name="postgres-db",
        description="PostgreSQL database",
        image="postgres:15-alpine",
        ports=["5432:5432"],
        env_vars={
            "POSTGRES_USER": "webapp",
            "POSTGRES_PASSWORD": "webapp_password",
            "POSTGRES_DB": "webapp_db",
        },
    )
)

webapp.add(
    AppleContainerResource(
        name="api-service",
        description="API service",
        image="node:18-alpine",
        ports=["8000:8000"],
        env_vars={
            "DATABASE_URL": "postgresql://webapp:webapp_password@postgres-db:5432/webapp_db",
            "NODE_ENV": "production",
        },
    )
)

# Conditionally override specific fields post-creation
# Example: Add debug mode based on environment variable
if os.getenv("DEBUG_MODE") == "true":
    webapp.children["api-service"].env_vars["DEBUG"] = "true"
    webapp.children["api-service"].env_vars["LOG_LEVEL"] = "debug"

# Example: Adjust resources based on environment
environment = os.getenv("ENVIRONMENT", "development")
if environment == "production":
    # Production needs persistence and auto-restart
    webapp.children["postgres-db"].volumes = [
        "./postgres-data:/var/lib/postgresql/data"
    ]
    webapp.children["postgres-db"].restart_policy = "always"
    webapp.children["api-service"].restart_policy = "always"
else:
    # Development doesn't need persistence
    webapp.children["postgres-db"].restart_policy = "no"
    webapp.children["api-service"].restart_policy = "no"

# Add assertions after conditional config
webapp.children["postgres-db"].assertions = [
    ContainerRunningAssert(),
    PortAccessibleAssert(port=5432),
]

webapp.children["api-service"].assertions = [
    ContainerRunningAssert(),
    PortAccessibleAssert(port=8000),
    HealthcheckAssert(url="http://localhost:8000/health"),
]

webapp.children["api-service"].connect(webapp.children["postgres-db"])


# ==================================================================
# Educational Pattern Examples (Not Deployed)
# ==================================================================
# The functions below demonstrate alternative patterns for reference only


def pattern_1_constructor_config():
    """Pattern 1: Configure resources fully in constructor.

    This is the recommended approach for most cases.

    Pros:
    - Clear and explicit
    - All config in one place
    - Easy to read and understand
    - Immutable after creation

    Cons:
    - Verbose if many fields
    - Can't easily share common config
    """
    print("\n=== Pattern 1: Constructor-Based Configuration ===\n")

    webapp = BlankResource(
        name="webapp-pattern1",
        description="Web app using constructor-based configuration",
    )

    # All configuration specified in constructor
    database = webapp.add(
        AppleContainerResource(
            name="postgres-db",
            description="PostgreSQL database",
            image="postgres:15-alpine",
            ports=["5432:5432"],
            env_vars={
                "POSTGRES_USER": "webapp",
                "POSTGRES_PASSWORD": "webapp_password",
                "POSTGRES_DB": "webapp_db",
            },
            volumes=[
                "./postgres-data:/var/lib/postgresql/data",
            ],
            restart_policy="always",
            assertions=[
                ContainerRunningAssert(),
                PortAccessibleAssert(port=5432),
            ],
        )
    )

    api = webapp.add(
        AppleContainerResource(
            name="api-service",
            description="API service with full configuration",
            image="node:18-alpine",
            ports=["8000:8000"],
            env_vars={
                "DATABASE_URL": "postgresql://webapp:webapp_password@postgres-db:5432/webapp_db",
                "NODE_ENV": "production",
                "PORT": "8000",
            },
            command=["node", "server.js"],
            restart_policy="always",
            assertions=[
                ContainerRunningAssert(),
                PortAccessibleAssert(port=8000),
                HealthcheckAssert(url="http://localhost:8000/health"),
            ],
        )
    )

    api.connect(database)

    return webapp


def pattern_2_post_creation_overrides():
    """Pattern 2: Add resources first, then configure.

    This approach is useful when:
    - You want to apply common config to multiple resources
    - You're building resources dynamically
    - You need to modify based on other resources

    Pros:
    - Flexible and dynamic
    - Can apply common patterns
    - Good for programmatic generation
    - Can adjust based on context

    Cons:
    - Config spread across multiple locations
    - Harder to see complete config at a glance
    - More mutable (can be good or bad)
    """
    print("\n=== Pattern 2: Post-Creation Override Configuration ===\n")

    webapp = BlankResource(
        name="webapp-pattern2",
        description="Web app using post-creation override configuration",
    )

    # Step 1: Add resources with minimal config
    webapp.add(
        AppleContainerResource(
            name="postgres-db",
            description="PostgreSQL database",
        )
    )

    webapp.add(
        AppleContainerResource(
            name="api-service",
            description="API service",
        )
    )

    # Step 2: Configure database after creation using .children property
    # NEW API: Use dict-style access instead of get_children()[index]
    # Old: webapp.get_children()[0].image = "postgres:15-alpine"
    # New: webapp.children["postgres-db"].image = "postgres:15-alpine"

    database = webapp.children["postgres-db"]  # Clean dict-style access
    database.image = "postgres:15-alpine"
    database.ports = ["5432:5432"]
    database.env_vars = {
        "POSTGRES_USER": "webapp",
        "POSTGRES_PASSWORD": "webapp_password",
        "POSTGRES_DB": "webapp_db",
    }
    database.volumes = [
        "./postgres-data:/var/lib/postgresql/data",
    ]
    database.restart_policy = "always"
    database.assertions = [
        ContainerRunningAssert(),
        PortAccessibleAssert(port=5432),
    ]

    # Step 3: Configure API after creation using .children property
    # You can also modify directly without creating a variable:
    webapp.children["api-service"].image = "node:18-alpine"
    webapp.children["api-service"].ports = ["8000:8000"]
    webapp.children["api-service"].env_vars = {
        "DATABASE_URL": "postgresql://webapp:webapp_password@postgres-db:5432/webapp_db",
        "NODE_ENV": "production",
        "PORT": "8000",
    }
    webapp.children["api-service"].command = ["node", "server.js"]
    webapp.children["api-service"].restart_policy = "always"
    webapp.children["api-service"].assertions = [
        ContainerRunningAssert(),
        PortAccessibleAssert(port=8000),
        HealthcheckAssert(url="http://localhost:8000/health"),
    ]

    # Step 4: Establish dependencies using the .children property
    webapp.children["api-service"].connect(webapp.children["postgres-db"])

    return webapp


def pattern_4_shared_config():
    """Pattern 4: Apply common configuration to multiple resources.

    This pattern shows how post-creation overrides enable DRY principles
    by applying common config to multiple resources.
    """
    print("\n=== Pattern 4: Shared Configuration Pattern ===\n")

    webapp = BlankResource(
        name="webapp-pattern4",
        description="Web app with shared configuration applied to multiple resources",
    )

    # Create multiple services with minimal config
    service_names = ["api-service", "worker-service", "scheduler-service"]
    for name in service_names:
        webapp.add(
            AppleContainerResource(
                name=name,
                description=f"{name} for the web application",
            )
        )

    # Apply common configuration to all services using .children.values()
    # NEW API: Iterate over children using .values() instead of a separate list
    # Old: for service in services:
    # New: for service in webapp.children.values():

    common_env = {
        "NODE_ENV": "production",
        "LOG_LEVEL": "info",
        "METRICS_ENABLED": "true",
    }

    common_restart_policy = "always"

    for service in webapp.children.values():
        # Apply common config
        service.image = "node:18-alpine"
        service.restart_policy = common_restart_policy
        service.env_vars = (
            common_env.copy()
        )  # Copy to avoid sharing dict reference

        # Add common assertions
        service.assertions = [ContainerRunningAssert()]

    # Now customize each service specifically using dict-style access
    # NEW API: Use webapp.children["name"] instead of services[index]
    # Old: services[0].ports = ["8000:8000"]
    # New: webapp.children["api-service"].ports = ["8000:8000"]

    webapp.children["api-service"].ports = ["8000:8000"]  # API
    webapp.children["api-service"].env_vars["SERVICE_TYPE"] = "api"
    webapp.children["api-service"].assertions.append(
        PortAccessibleAssert(port=8000)
    )
    webapp.children["api-service"].assertions.append(
        HealthcheckAssert(url="http://localhost:8000/health")
    )

    webapp.children["worker-service"].env_vars["SERVICE_TYPE"] = (
        "worker"  # Worker
    )

    webapp.children["scheduler-service"].env_vars["SERVICE_TYPE"] = (
        "scheduler"  # Scheduler
    )

    # You can also iterate using .items() for name + resource:
    print("\nConfigured services:")
    for name, service in webapp.children.items():
        service_type = service.env_vars.get("SERVICE_TYPE", "unknown")
        print(f"  - {name}: {service_type}")

    return webapp


# ==================================================================
# Pattern Summary
# ==================================================================
#
# PATTERN 1 - Constructor Config:
# ✓ Use when config is known upfront
# ✓ Use for simple, static configurations
# ✓ Use when you value clarity and immutability
# ✓ RECOMMENDED for most cases
#
# PATTERN 2 - Post-Creation Overrides:
# ✓ Use when building resources dynamically
# ✓ Use when config depends on runtime conditions
# ✓ Use when generating many similar resources
# ✓ Use with caution (can be hard to follow)
#
# PATTERN 3 - Hybrid (DEPLOYED IN THIS EXAMPLE):
# ✓ Use when you need both clarity and flexibility
# ✓ Use for environment-specific overrides
# ✓ Use for conditional configuration
# ✓ RECOMMENDED for complex projects
#
# PATTERN 4 - Shared Config:
# ✓ Use when multiple resources share config
# ✓ Use to apply common patterns
# ✓ Use to reduce duplication (DRY principle)
# ✓ RECOMMENDED for microservices architectures


# To deploy this example:
# cd examples/composite-resources/post-creation-overrides
# uv run clockwork apply

# To deploy with debug mode:
# DEBUG_MODE=true uv run clockwork apply

# To deploy for production:
# ENVIRONMENT=production uv run clockwork apply

# To verify assertions:
# uv run clockwork assert

# To destroy:
# uv run clockwork destroy

# Configuration Pattern Summary:
#
# Pattern 1 (Constructor): Best for simple, static configurations
# Pattern 2 (Post-Creation): Best for dynamic, programmatic generation
# Pattern 3 (Hybrid): Best for complex projects with conditionals (DEPLOYED)
# Pattern 4 (Shared Config): Best for multiple similar resources
#
# Recommendation: Start with Pattern 1, use Pattern 3 when you need
# environment-specific or conditional configuration.
