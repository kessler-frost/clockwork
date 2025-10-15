# Docker Service Example

Cross-platform container orchestration with AI-powered Docker management.

## What it does

DockerResource provides intelligent Docker container management using Pulumi's Docker provider. Works on Mac, Linux, Windows, and remote servers via SSH.

## Prerequisites

- Docker installed and running
- Docker daemon accessible from command line
- Network access to pull container images

## Run the example

```bash
# Navigate to example directory
cd examples/docker-service

# Deploy containers
clockwork apply

# Verify deployment with assertions
clockwork assert

# Test the services
curl localhost:80      # Minimal example
curl localhost:8091    # Advanced example with custom port

# Clean up
clockwork destroy
```

## How it works

1. **AI completion**: Analyzes descriptions and suggests appropriate container images, ports, volumes, and configuration
2. **Cross-platform**: Uses Pulumi Docker provider for universal Docker support
3. **Orchestration**: Deploys containers with specified configuration
4. **Assertions**: Validates deployment with health checks and port accessibility tests
5. **`.clockwork/`** directory created in current directory with Pulumi state

## Platform support

- **macOS**: Docker Desktop
- **Linux**: Docker Engine
- **Windows**: Docker Desktop (WSL2)
- **Remote servers**: SSH connector with Docker installed

## Examples included

### Minimal example
```python
minimal = DockerResource(
    description="lightweight nginx web server for testing"
)
```

AI completes all fields: name, image, ports, volumes, env_vars, networks

### Advanced example
```python
api = DockerResource(
    description="lightweight web server for testing and demos",
    ports=["8091:80"],  # Override port mapping
    assertions=[
        ContainerRunningAssert(timeout_seconds=10),
        PortAccessibleAssert(port=8091, host="localhost", protocol="tcp"),
        HealthcheckAssert(url="http://localhost:8091", expected_status=200, timeout_seconds=5),
    ]
)
```

AI completes missing fields while preserving user overrides.

## Verification

The `clockwork assert` command validates:
- Container existence
- Container running state
- Port accessibility (8091)
- HTTP health check endpoint
- Response time

## Commands

```bash
# Deploy resources
clockwork apply

# Run assertions
clockwork assert

# Destroy resources (removes .clockwork directory by default)
clockwork destroy

# Destroy resources but keep .clockwork directory
clockwork destroy --keep-files
```
