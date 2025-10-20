"""Post-Creation Overrides Example

This example demonstrates two approaches to configuring child resources:
1. Constructor-based configuration (specify everything upfront)
2. Post-creation overrides (modify after adding to composite)

It shows the trade-offs between each approach and when to use which pattern.
"""

from clockwork.resources import BlankResource, DockerResource
from clockwork.resources.assertions import (
    ContainerRunningAssert,
    HealthcheckAssert,
    PortAccessibleAssert,
)


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
        DockerResource(
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
        DockerResource(
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
        DockerResource(
            name="postgres-db",
            description="PostgreSQL database",
        )
    )

    webapp.add(
        DockerResource(
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


def pattern_3_hybrid_approach():
    """Pattern 3: Hybrid - Specify core config in constructor, override special cases.

    This combines the best of both approaches.

    Use this when:
    - Most config is known upfront
    - Some config needs to be dynamic or conditional
    - You want clarity + flexibility
    """
    print("\n=== Pattern 3: Hybrid Approach ===\n")

    webapp = BlankResource(
        name="webapp-pattern3",
        description="Web app using hybrid configuration approach",
    )

    # Specify core config in constructor
    database = webapp.add(
        DockerResource(
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

    api = webapp.add(
        DockerResource(
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
    import os
    if os.getenv("DEBUG_MODE") == "true":
        api.env_vars["DEBUG"] = "true"
        api.env_vars["LOG_LEVEL"] = "debug"

    # Example: Adjust resources based on environment
    environment = os.getenv("ENVIRONMENT", "development")
    if environment == "production":
        # Production needs persistence and auto-restart
        database.volumes = ["./postgres-data:/var/lib/postgresql/data"]
        database.restart_policy = "always"
        api.restart_policy = "always"
    else:
        # Development doesn't need persistence
        database.restart_policy = "no"
        api.restart_policy = "no"

    # Add assertions after conditional config
    database.assertions = [
        ContainerRunningAssert(),
        PortAccessibleAssert(port=5432),
    ]

    api.assertions = [
        ContainerRunningAssert(),
        PortAccessibleAssert(port=8000),
        HealthcheckAssert(url="http://localhost:8000/health"),
    ]

    api.connect(database)

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
            DockerResource(
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
        service.env_vars = common_env.copy()  # Copy to avoid sharing dict reference

        # Add common assertions
        service.assertions = [ContainerRunningAssert()]

    # Now customize each service specifically using dict-style access
    # NEW API: Use webapp.children["name"] instead of services[index]
    # Old: services[0].ports = ["8000:8000"]
    # New: webapp.children["api-service"].ports = ["8000:8000"]

    webapp.children["api-service"].ports = ["8000:8000"]  # API
    webapp.children["api-service"].env_vars["SERVICE_TYPE"] = "api"
    webapp.children["api-service"].assertions.append(PortAccessibleAssert(port=8000))
    webapp.children["api-service"].assertions.append(HealthcheckAssert(url="http://localhost:8000/health"))

    webapp.children["worker-service"].env_vars["SERVICE_TYPE"] = "worker"  # Worker

    webapp.children["scheduler-service"].env_vars["SERVICE_TYPE"] = "scheduler"  # Scheduler

    # You can also iterate using .items() for name + resource:
    print("\nConfigured services:")
    for name, service in webapp.children.items():
        service_type = service.env_vars.get("SERVICE_TYPE", "unknown")
        print(f"  - {name}: {service_type}")

    return webapp


def comparison_summary():
    """Summary of when to use each pattern.

    PATTERN 1 - Constructor Config:
    ✓ Use when config is known upfront
    ✓ Use for simple, static configurations
    ✓ Use when you value clarity and immutability
    ✓ RECOMMENDED for most cases

    PATTERN 2 - Post-Creation Overrides:
    ✓ Use when building resources dynamically
    ✓ Use when config depends on runtime conditions
    ✓ Use when generating many similar resources
    ✓ Use with caution (can be hard to follow)

    PATTERN 3 - Hybrid:
    ✓ Use when you need both clarity and flexibility
    ✓ Use for environment-specific overrides
    ✓ Use for conditional configuration
    ✓ RECOMMENDED for complex projects

    PATTERN 4 - Shared Config:
    ✓ Use when multiple resources share config
    ✓ Use to apply common patterns
    ✓ Use to reduce duplication (DRY principle)
    ✓ RECOMMENDED for microservices architectures
    """
    pass


def main():
    """Demonstrate all four patterns."""

    # Pattern 1: Constructor-based (most common)
    webapp1 = pattern_1_constructor_config()

    # Pattern 2: Post-creation overrides (flexible)
    webapp2 = pattern_2_post_creation_overrides()

    # Pattern 3: Hybrid approach (balanced)
    webapp3 = pattern_3_hybrid_approach()

    # Pattern 4: Shared config (DRY)
    webapp4 = pattern_4_shared_config()

    # For this demo, let's use Pattern 3 (hybrid) as it's most practical
    return webapp3


if __name__ == "__main__":
    # Create and deploy using the hybrid pattern
    app = main()

    # To deploy this example:
    # cd /Users/sankalp/dev/clockwork/examples/composite-resources/post-creation-overrides
    # uv run clockwork apply

    # To deploy with debug mode:
    # DEBUG_MODE=true uv run clockwork apply

    # To deploy for production:
    # ENVIRONMENT=production uv run clockwork apply

    # To verify assertions:
    # uv run clockwork assert

    # To destroy:
    # uv run clockwork destroy

    print("\n" + "="*70)
    print("Configuration Pattern Summary")
    print("="*70)
    print("""
    Pattern 1 (Constructor): Best for simple, static configurations
    Pattern 2 (Post-Creation): Best for dynamic, programmatic generation
    Pattern 3 (Hybrid): Best for complex projects with conditionals
    Pattern 4 (Shared Config): Best for multiple similar resources

    Recommendation: Start with Pattern 1, use Pattern 3 when you need
    environment-specific or conditional configuration.
    """)
