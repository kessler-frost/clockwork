# Docker Web Application Example

This example demonstrates using `DockerResource` for cross-platform container management with Clockwork.

## Prerequisites

- Docker installed and running
- Python 3.12+
- uv package manager

### Verify Docker is available

```bash
docker --version
docker info
```

## Stack Components

This example creates a simple web application stack with:

1. **PostgreSQL Database** (`postgres-db`)
   - Image: `postgres:15-alpine`
   - Port: 5432
   - Persistent volume for data

2. **Redis Cache** (`redis-cache`)
   - Image: `redis:7-alpine`
   - Port: 6379

3. **Nginx Web Server** (`nginx-web`)
   - Image: `nginx:alpine`
   - Port: 8080
   - Depends on database and cache

## Usage

### Deploy

```bash
cd examples/docker-webapp
uv run clockwork apply
```

### Verify Assertions

```bash
uv run clockwork assert
```

### Check Container Status

```bash
docker ps
```

### Destroy

```bash
uv run clockwork destroy
```

## Cross-Platform Support

`DockerResource` works on any platform where Docker is installed:

- **Linux**: Native Docker
- **macOS**: Docker Desktop or Colima
- **Windows**: Docker Desktop with WSL2

## DockerResource vs AppleContainerResource

| Feature | DockerResource | AppleContainerResource |
|---------|----------------|------------------------|
| Platform | Linux, macOS, Windows | macOS 26+ only |
| Runtime | Docker Engine | Apple Containers |
| CLI | `docker` | `container` |
| Use Case | Cross-platform | macOS-native |

Choose `DockerResource` for cross-platform compatibility, or `AppleContainerResource` for macOS-native container support.

## Platform Detection

Clockwork provides platform detection utilities:

```python
from clockwork.platform import (
    is_docker_available,
    is_apple_containers_available,
    get_container_runtime,
    ContainerRuntime,
)

# Check Docker availability
if is_docker_available():
    print("Docker is available")

# Get best available runtime
runtime = get_container_runtime()
if runtime == ContainerRuntime.DOCKER:
    print("Using Docker")
elif runtime == ContainerRuntime.APPLE_CONTAINERS:
    print("Using Apple Containers")
```
