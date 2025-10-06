# Docker Service Example

This example demonstrates Clockwork's AI-powered Docker service deployment with intelligent image suggestions.

## What it does

Deploys three Docker containers with different configuration approaches:

1. **nginx-ai** - AI-suggested image based on description (web server for static content)
2. **redis-cache** - Explicit image with minimal config (Redis 7 Alpine)
3. **postgres-db** - Fully specified configuration (PostgreSQL 16 with env vars and volumes)

## Prerequisites

1. OpenRouter API key:
   ```bash
   export OPENROUTER_API_KEY="your-key-here"
   ```

2. Install Clockwork:
   ```bash
   uv add clockwork
   ```

3. Docker installed and running

## Run the example

```bash
# Plan mode (dry run - shows what would be deployed)
uv run clockwork plan examples/docker-service/main.py

# Apply (full deployment)
uv run clockwork apply examples/docker-service/main.py
```

## Expected output

```
Clockwork Apply
File: examples/docker-service/main.py
Model: openai/gpt-oss-20b:free

Loaded 3 resources
Generating artifact for: nginx-ai
Generated 1 artifacts
Compiled to PyInfra: .clockwork/pyinfra

✓ Deployment successful!
```

## Check the results

```bash
# List running containers
docker ps

# Check specific containers
docker ps | grep nginx-ai
docker ps | grep redis-cache
docker ps | grep postgres-db

# Inspect container
docker inspect nginx-ai
```

## How it works

1. **Load**: Clockwork loads DockerServiceResource instances from `main.py`
2. **Generate**: AI suggests Docker image for resources without explicit image
3. **Compile**: Resources compile to PyInfra `docker.container` operations
4. **Deploy**: PyInfra executes the deployment

## Three approaches demonstrated

### 1. AI-suggested image (nginx-ai)
```python
DockerServiceResource(
    name="nginx-ai",
    description="A production-ready web server for serving static content and reverse proxying",
    ports=["80:80", "443:443"],
    networks=["web"]
)
```
- No image specified
- AI analyzes description and suggests appropriate image
- Useful when you're not sure which image to use

### 2. Explicit image (redis-cache)
```python
DockerServiceResource(
    name="redis-cache",
    description="Redis cache server for session storage with persistence",
    image="redis:7-alpine",
    ports=["6379:6379"],
    volumes=["redis_data:/data"]
)
```
- Explicit image version control
- No AI needed for image selection
- Best for production reproducibility

### 3. Fully specified (postgres-db)
```python
DockerServiceResource(
    name="postgres-db",
    description="PostgreSQL database server for application data",
    image="postgres:16-alpine",
    ports=["5432:5432"],
    env_vars={
        "POSTGRES_PASSWORD": "example",
        "POSTGRES_USER": "clockwork",
        "POSTGRES_DB": "app"
    },
    volumes=["pg_data:/var/lib/postgresql/data"],
    networks=["backend"]
)
```
- Complete configuration
- No AI suggestions needed
- Maximum control

## Cleanup

```bash
# Destroy all deployed containers
uv run clockwork destroy examples/docker-service/main.py

# Or manually remove
docker rm -f nginx-ai redis-cache postgres-db
```

## Customization

- Change `description` to get different AI-suggested images
- Add more containers by creating new DockerServiceResource instances
- Customize ports, volumes, env_vars, and networks
- Use `present=False` to ensure container is removed
- Use `start=False` to create but not start containers
