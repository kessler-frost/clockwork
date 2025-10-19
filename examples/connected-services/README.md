# Connected Services Example

Full-stack application demonstrating Clockwork's primitive connection system for intelligent dependency management and AI-powered configuration.

## What it demonstrates

The connection system enables three powerful capabilities:

1. **Dependency-aware deployment ordering** - Resources with connections deploy after their dependencies
2. **AI-powered configuration** - AI uses connection context to generate appropriate environment variables and network settings
3. **Cross-resource context sharing** - Connected resources share configuration data automatically

## Architecture

This example deploys a realistic full-stack application with four services:

```
Layer 1 (Independent):
├── postgres-db      (PostgreSQL database)
└── redis-cache      (Redis cache/queue)

Layer 2 (Connected):
├── api-server       (FastAPI backend - connected to postgres + redis)
└── worker-service   (Background worker - connected to redis)
```

## How it works

### 1. Dependency Declaration

Resources declare connections to other resources:

```python
# Independent resources (deploy first)
postgres = DockerResource(
    description="PostgreSQL database",
    name="postgres-db",
    image="postgres:15-alpine",
    ports=["5432:5432"],
    env_vars={...}
)

redis = DockerResource(
    description="Redis cache",
    name="redis-cache",
    image="redis:7-alpine",
    ports=["6379:6379"]
)

# Connected resource (deploys after dependencies)
api = DockerResource(
    description="FastAPI backend server that needs database and cache",
    ports=["8000:8000"],
    connections=[postgres, redis]  # Declares dependencies
)
```

### 2. AI-Powered Configuration

When completing the `api` resource, the AI receives connection context:

```python
# AI sees this context from postgres:
{
    "name": "postgres-db",
    "type": "DockerResource",
    "image": "postgres:15-alpine",
    "ports": ["5432:5432"],
    "env_vars": {"POSTGRES_DB": "appdb", "POSTGRES_USER": "admin", ...}
}

# AI sees this context from redis:
{
    "name": "redis-cache",
    "type": "DockerResource",
    "image": "redis:7-alpine",
    "ports": ["6379:6379"]
}
```

Based on this context, the AI should intelligently generate:

```python
# Expected AI completion for api-server:
{
    "name": "api-server",
    "image": "appropriate-fastapi-image",
    "env_vars": {
        "DATABASE_URL": "postgresql://admin:secret123@postgres-db:5432/appdb",
        "REDIS_URL": "redis://redis-cache:6379"
    },
    "networks": ["app_network"]  # Shared network for inter-container communication
}
```

### 3. Deployment Order

Clockwork automatically determines deployment order based on connections:

```
1. postgres-db      (no dependencies - deploys first)
2. redis-cache      (no dependencies - deploys first)
3. api-server       (depends on postgres + redis - deploys after)
4. worker-service   (depends on redis - deploys after)
```

## Prerequisites

- Docker installed and running
- Docker daemon accessible from command line
- Network access to pull container images

## Run the example

```bash
# Navigate to example directory
cd examples/connected-services

# Deploy all services (respects connection order)
clockwork apply

# Verify deployment with assertions
clockwork assert

# Test the services
curl http://localhost:8000/health  # API health check
docker logs api-server             # Check API logs for database connection
docker logs worker-service         # Check worker logs for Redis connection

# Inspect generated environment variables
docker inspect api-server | jq '.[0].Config.Env'

# Clean up
clockwork destroy
```

## Expected AI behavior

### For api-server (connected to postgres + redis):

**Input to AI:**
- Description: "FastAPI backend server that provides REST API endpoints. Needs database connection for user data and Redis for caching API responses."
- Connection context from postgres-db (name, image, ports, env_vars)
- Connection context from redis-cache (name, image, ports)

**Expected AI completion:**
- Generate appropriate image (e.g., `python:3.11-slim`, `tiangolo/uvicorn-gunicorn-fastapi`)
- Generate DATABASE_URL environment variable using postgres connection info
- Generate REDIS_URL environment variable using redis connection info
- Place container on shared network for inter-container communication
- Possibly generate additional env vars like `API_PORT=8000`, `ENV=development`

### For worker-service (connected to redis):

**Input to AI:**
- Description: "Background worker service that processes async jobs from Redis queue. Monitors Redis for new tasks and executes them."
- Connection context from redis-cache (name, image, ports)

**Expected AI completion:**
- Generate appropriate image (e.g., `python:3.11-slim`)
- Generate REDIS_URL environment variable using redis connection info
- Place container on same network as redis
- No exposed ports (worker doesn't serve HTTP)

## Verification

After running `clockwork apply`, check:

1. **Deployment order** - postgres and redis start before api and worker
2. **Environment variables** - API and worker have correct connection URLs
3. **Network connectivity** - All containers on the same Docker network
4. **Assertions pass** - All health checks and port accessibility tests succeed

```bash
# Check deployment order from docker logs
docker ps --format "table {{.Names}}\t{{.CreatedAt}}"

# Check environment variables
docker exec api-server env | grep -E "(DATABASE|REDIS)"

# Check network connectivity
docker network inspect app_network

# Run assertions
clockwork assert
```

## Key benefits demonstrated

1. **Declarative dependencies** - Just specify connections, system handles the rest
2. **Intelligent AI completion** - AI understands service relationships and generates appropriate config
3. **Zero boilerplate** - No manual network creation or URL construction needed
4. **Type-safe connections** - Pydantic validation ensures connections are valid Resource objects
5. **Deployment safety** - Dependencies always deploy before dependent services

## Extending the example

Try adding more connected services:

```python
# Add a monitoring service connected to all services
monitor = DockerResource(
    description="Prometheus monitoring for all services",
    ports=["9090:9090"],
    connections=[postgres, redis, api, worker]  # AI can generate comprehensive config
)

# Add a frontend connected to the API
frontend = DockerResource(
    description="React frontend served by Nginx, makes API calls to backend",
    ports=["80:80"],
    connections=[api]  # AI generates API_URL env var
)
```

## Cleanup

```bash
# Remove all services and clean up
clockwork destroy

# This will:
# 1. Remove containers in reverse order (worker, api, redis, postgres)
# 2. Remove volumes (postgres_data, redis_data)
# 3. Remove networks (app_network)
```

## Commands

```bash
# Deploy resources (respects connection order)
clockwork apply

# Run assertions (validates all services)
clockwork assert

# Destroy resources
clockwork destroy
```

## Troubleshooting

**Issue**: Containers can't communicate with each other
- Check if all containers are on the same network: `docker network inspect app_network`
- Verify container names match what's in environment variables

**Issue**: API or worker can't connect to database/redis
- Check environment variables: `docker exec api-server env`
- Verify postgres and redis are running: `docker ps`
- Check connection URLs use container names, not localhost

**Issue**: Deployment order seems wrong
- Run `clockwork apply` with verbose logging to see order
- Check for circular dependencies in connections
- Verify connections are specified correctly in resource definitions
