# Post-Creation Overrides Example

## Overview

This example demonstrates and compares different approaches to configuring child resources in composite patterns. It shows the trade-offs between constructor-based configuration and post-creation overrides, helping you choose the right approach for your use case.

## What This Demonstrates

- **Pattern 1**: Constructor-based configuration (all config upfront)
- **Pattern 2**: Post-creation override configuration (modify after creation)
- **Pattern 3**: Hybrid approach (combine both patterns)
- **Pattern 4**: Shared configuration pattern (DRY for multiple resources)
- **Trade-offs**: When to use each pattern
- **Best Practices**: Recommendations for real projects

## The Four Patterns

### Pattern 1: Constructor-Based Configuration

**When to use**: Most of the time (recommended default)

```python
# All configuration in constructor
database = webapp.add(
    DockerResource(
        name="postgres-db",
        description="PostgreSQL database",
        image="postgres:15-alpine",
        ports=["5432:5432"],
        env_vars={"POSTGRES_USER": "webapp"},
        restart_policy="always",
    )
)
```

**Pros**:
- Clear and explicit
- All config in one place
- Easy to read and understand
- Immutable after creation

**Cons**:
- Verbose if many fields
- Can't easily share common config
- Less flexible for dynamic scenarios

### Pattern 2: Post-Creation Overrides

**When to use**: Dynamic/programmatic resource generation

```python
# Minimal constructor
database = webapp.add(
    DockerResource(
        name="postgres-db",
        description="PostgreSQL database",
    )
)

# Configure after creation
database.image = "postgres:15-alpine"
database.ports = ["5432:5432"]
database.env_vars = {"POSTGRES_USER": "webapp"}
database.restart_policy = "always"
```

**Pros**:
- Flexible and dynamic
- Can apply common patterns
- Good for programmatic generation
- Can adjust based on context

**Cons**:
- Config spread across multiple locations
- Harder to see complete config at a glance
- More mutable (can lead to confusion)

### Pattern 3: Hybrid Approach

**When to use**: Complex projects with conditionals (recommended for production)

```python
# Core config in constructor
api = webapp.add(
    DockerResource(
        name="api-service",
        image="node:18-alpine",
        ports=["8000:8000"],
        env_vars={"NODE_ENV": "production"},
    )
)

# Conditional overrides
import os
if os.getenv("DEBUG_MODE") == "true":
    api.env_vars["DEBUG"] = "true"
    api.env_vars["LOG_LEVEL"] = "debug"

environment = os.getenv("ENVIRONMENT", "development")
if environment == "production":
    api.restart_policy = "always"
    api.volumes = ["./data:/data"]
```

**Pros**:
- Combines clarity + flexibility
- Good for environment-specific config
- Core config is clear
- Overrides are explicit

**Cons**:
- Config in two places (but intentionally)
- Requires discipline to keep organized

### Pattern 4: Shared Configuration

**When to use**: Multiple similar resources (microservices, clusters)

```python
# Create multiple services
services = []
for name in ["api", "worker", "scheduler"]:
    service = webapp.add(DockerResource(name=name, description=f"{name} service"))
    services.append(service)

# Apply common config
common_env = {"NODE_ENV": "production", "LOG_LEVEL": "info"}
for service in services:
    service.image = "node:18-alpine"
    service.restart_policy = "always"
    service.env_vars = common_env.copy()

# Customize each service
services[0].ports = ["8000:8000"]  # API
services[1].env_vars["ROLE"] = "worker"
services[2].env_vars["ROLE"] = "scheduler"
```

**Pros**:
- DRY (Don't Repeat Yourself)
- Consistent configuration
- Easy to apply patterns
- Reduces duplication

**Cons**:
- Less obvious what each resource has
- Requires careful dict copying (avoid reference sharing)

## Running This Example

### Deploy with Default Pattern (Hybrid)

```bash
cd examples/composite-resources/post-creation-overrides
uv run clockwork apply
```

### Deploy with Debug Mode

```bash
DEBUG_MODE=true uv run clockwork apply
```

This will:
- Add DEBUG environment variables
- Enable debug logging

### Deploy for Production

```bash
ENVIRONMENT=production uv run clockwork apply
```

This will:
- Enable auto-restart policies
- Add volume persistence
- Use production optimizations

### Verify Assertions

```bash
uv run clockwork assert
```

### Clean Up

```bash
uv run clockwork destroy
```

## Comparison Table

| Aspect | Pattern 1 (Constructor) | Pattern 2 (Post-Creation) | Pattern 3 (Hybrid) | Pattern 4 (Shared) |
|--------|------------------------|---------------------------|--------------------|--------------------|
| **Clarity** | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| **Flexibility** | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **Maintainability** | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| **DRY Principle** | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **Best For** | Simple config | Dynamic generation | Production projects | Microservices |

## Decision Guide

### Choose Pattern 1 (Constructor) When:

✅ Configuration is known at creation time
✅ You value clarity and explicitness
✅ Resources have simple, static config
✅ You're learning Clockwork

**Example Use Cases**:
- Simple web applications
- Development environments
- Proof of concepts
- Tutorial examples

### Choose Pattern 2 (Post-Creation) When:

✅ Building resources programmatically
✅ Configuration depends on runtime conditions
✅ Generating many similar resources
✅ You need maximum flexibility

**Example Use Cases**:
- Infrastructure generation tools
- Dynamic scaling systems
- Config-driven deployments
- Testing frameworks

### Choose Pattern 3 (Hybrid) When:

✅ You have core config + conditional overrides
✅ Supporting multiple environments (dev/staging/prod)
✅ Config depends on environment variables
✅ Building production systems

**Example Use Cases**:
- Production applications
- Multi-environment deployments
- Feature flags
- A/B testing infrastructure

### Choose Pattern 4 (Shared Config) When:

✅ Multiple resources share common configuration
✅ Building microservices architectures
✅ Deploying clusters of similar services
✅ Enforcing consistent patterns

**Example Use Cases**:
- Microservices platforms
- Container clusters
- Distributed systems
- Multi-tenant applications

## Best Practices

### 1. Start Simple (Pattern 1)

Begin with constructor-based configuration. Only move to other patterns when you have a specific need.

### 2. Be Consistent

Pick one pattern per project and stick with it. Don't mix patterns arbitrarily.

### 3. Document Overrides

If using post-creation overrides, comment why:

```python
# Override for production environment
if environment == "production":
    api.restart_policy = "always"  # Auto-restart in production
```

### 4. Avoid Dict Reference Sharing

When applying common config, copy dicts:

```python
# Bad: Shares reference
for service in services:
    service.env_vars = common_env  # All services share same dict!

# Good: Copies dict
for service in services:
    service.env_vars = common_env.copy()  # Each service gets own dict
```

### 5. Use Hybrid for Production

For production systems, hybrid approach (Pattern 3) provides the best balance:
- Core config in constructor (clarity)
- Environment-specific overrides (flexibility)

## Common Patterns

### Environment-Based Configuration

```python
# Core config
api = webapp.add(DockerResource(name="api", image="node:18"))

# Environment-specific
import os
env = os.getenv("ENVIRONMENT", "development")

if env == "production":
    api.restart_policy = "always"
    api.volumes = ["./data:/data"]
elif env == "development":
    api.restart_policy = "no"
    api.env_vars["DEBUG"] = "true"
```

### Feature Flags

```python
# Core config
api = webapp.add(DockerResource(name="api", image="node:18"))

# Feature flags
import os
if os.getenv("FEATURE_METRICS") == "enabled":
    api.env_vars["METRICS_ENABLED"] = "true"
    api.ports.append("9090:9090")  # Metrics port
```

### Resource Limits Based on Environment

```python
# Core config
api = webapp.add(DockerResource(name="api", image="node:18"))

# Adjust resources
import os
if os.getenv("ENVIRONMENT") == "production":
    # Production: more resources
    api.env_vars["WORKER_COUNT"] = "8"
    api.env_vars["MEMORY_LIMIT"] = "2GB"
else:
    # Development: fewer resources
    api.env_vars["WORKER_COUNT"] = "2"
    api.env_vars["MEMORY_LIMIT"] = "512MB"
```

## Troubleshooting

### Config Not Applied

If post-creation overrides aren't working:

1. Check you're modifying before deployment
2. Verify you're returning the correct composite
3. Ensure you're not reassigning the variable

### Shared Dictionary Issues

If all services have the same env_vars unexpectedly:

```python
# Problem: Shared reference
common_env = {"NODE_ENV": "production"}
service1.env_vars = common_env
service2.env_vars = common_env  # Both point to same dict!

# Solution: Copy
service1.env_vars = common_env.copy()
service2.env_vars = common_env.copy()
```

## Next Steps

After understanding these patterns:

1. Review your current projects - which pattern fits best?
2. Try modifying this example with your own use cases
3. Experiment with environment variables
4. Build a multi-environment configuration

## Related Examples

- `examples/composite-resources/simple-webapp/`: Basic composites (uses Pattern 1)
- `examples/composite-resources/nested-composites/`: Complex hierarchies (uses Pattern 1)
- `examples/composite-resources/mixed-pattern/`: Hybrid architectures (uses Pattern 1)

## Summary

**Quick Recommendations**:

- **Learning**: Use Pattern 1 (Constructor)
- **Simple Projects**: Use Pattern 1 (Constructor)
- **Production**: Use Pattern 3 (Hybrid)
- **Microservices**: Use Pattern 4 (Shared Config)
- **Dynamic Generation**: Use Pattern 2 (Post-Creation)

When in doubt, start with Pattern 1 and migrate to Pattern 3 when you need environment-specific configuration.
