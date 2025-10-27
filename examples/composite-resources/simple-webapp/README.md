# Simple Web App Composite Example

## Overview

This example demonstrates the fundamental composite resource pattern by creating a simple three-tier web application stack. It shows how to group related infrastructure components together using `BlankResource`.

## What This Demonstrates

- **Basic Composite Pattern**: Using `BlankResource` as a container
- **Adding Children**: Using `.add()` to include resources in the composite
- **Creating Dependencies**: Using `.connect()` to establish resource relationships
- **Assertions**: Verifying that resources are running and accessible
- **Environment Configuration**: Passing connection strings between services

## Architecture

```
simple-webapp (BlankResource)
├── postgres-db (DockerResource)
│   └── Port: 5432
├── redis-cache (DockerResource)
│   └── Port: 6379
└── api-server (DockerResource)
    ├── Port: 3000
    ├── Depends on: postgres-db
    └── Depends on: redis-cache
```

## Components

### 1. PostgreSQL Database (`postgres-db`)
- **Image**: `postgres:15-alpine`
- **Port**: 5432
- **Purpose**: Stores application data
- **Assertions**: Container running, port accessible

### 2. Redis Cache (`redis-cache`)
- **Image**: `redis:7-alpine`
- **Port**: 6379
- **Purpose**: Session storage and caching
- **Assertions**: Container running, port accessible

### 3. Node.js API Server (`api-server`)
- **Port**: 3000
- **Purpose**: REST API server
- **Dependencies**: PostgreSQL and Redis
- **Assertions**: Container running, port accessible, health check

## Deployment Order

Thanks to `.connect()`, resources deploy in the correct order:

1. `postgres-db` starts first (no dependencies)
2. `redis-cache` starts second (no dependencies)
3. `api-server` starts last (depends on both)

## Running This Example

### Deploy the Stack

```bash
cd examples/composite-resources/simple-webapp
uv run clockwork apply
```

### Verify Assertions

```bash
uv run clockwork assert
```

Expected output:
- All containers running
- All ports accessible
- API health check passes

### Test the API

```bash
# Check if API is responding
curl http://localhost:3000/health

# Check database connection (if endpoint exists)
curl http://localhost:3000/db/status
```

### Clean Up

```bash
uv run clockwork destroy
```

## Expected Output

When you run `clockwork apply`, you should see:

1. Composite creation: `simple-webapp`
2. Resource deployment in order:
   - `postgres-db` container starting
   - `redis-cache` container starting
   - `api-server` container starting (after dependencies)
3. Assertions passing for all resources

## Key Concepts

### Composite Pattern Benefits

1. **Logical Grouping**: All related resources are managed together
2. **Clear Structure**: Easy to understand what's part of the application
3. **Dependency Management**: `.connect()` ensures proper startup order
4. **Reusability**: Can copy this pattern for staging/production environments

### The `.add()` Method

```python
resource = composite.add(Resource(...))
```

- Adds a resource as a child of the composite
- Returns the added resource for further use (connecting, assertions, etc.)
- Allows chaining and references

### The `.connect()` Method

```python
api.connect(database)
```

- Establishes a dependency relationship
- Ensures `database` deploys before `api`
- Provides AI context about connected resources
- Prevents circular dependencies

## Customization Ideas

Try modifying this example to:

1. **Add nginx**: Include a reverse proxy in front of the API
2. **Add monitoring**: Include a Prometheus container
3. **Use AI completion**: Remove `image` field from API and let AI choose
4. **Add volumes**: Persist database data across restarts
5. **Create network**: Put all containers on a custom Docker network

## When to Use This Pattern

✅ **Use this pattern when**:
- You have multiple related services
- Services have dependencies on each other
- You want to manage them as a unit
- You need clear deployment ordering

❌ **Don't use when**:
- You have only one service
- Services are completely independent
- You need to deploy services at different times

## Next Steps

After understanding this example, check out:

- `nested-composites/`: Learn about hierarchical composite structures
- `mixed-pattern/`: See how to mix composites with standalone resources
- `post-creation-overrides/`: Advanced configuration patterns

## Related Examples

- `examples/connected-services/`: Real-world service connections
- `examples/showcase/`: Complete feature showcase
