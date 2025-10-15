# Apple Container Service Example

Intelligent container orchestration with AI-suggested images using Apple Containers CLI (macOS).

## What it does

AppleContainerResource provides intelligent container management using Apple's native container runtime on macOS. Works with the Apple Containers CLI (`container` command).

## Prerequisites

- Apple Containers CLI installed and running
- macOS system with container support
- Network access to pull container images

## Run the example

```bash
# Navigate to example directory
cd examples/apple-container-service

# Deploy containers
clockwork apply

# Verify deployment with assertions
clockwork assert

# Test the services
curl localhost:80      # Minimal example
curl localhost:8090    # Advanced example with custom port

# Clean up
clockwork destroy
```

## How it works

1. **AI completion**: Analyzes descriptions and suggests appropriate container images, ports, volumes, and configuration
2. **macOS Optimized**: Uses Apple Containers CLI via Pulumi custom dynamic provider
3. **Orchestration**: Deploys containers with specified configuration
4. **Assertions**: Validates deployment with health checks and port accessibility tests
5. **`.clockwork/`** directory created in current directory with Pulumi state

## Platform support

- **macOS**: Apple Containers CLI (native container runtime)
- **Best for**: Local macOS development and testing

For cross-platform Docker support, see the `docker-service` example.

## Examples included

### Minimal example
```python
minimal = AppleContainerResource(
    description="lightweight nginx web server for testing"
)
```

AI completes all fields: name, image, ports, volumes, env_vars, networks

### Advanced example
```python
api = AppleContainerResource(
    description="lightweight web server for testing and demos",
    ports=["8090:80"],  # Override port mapping
    assertions=[
        ContainerRunningAssert(timeout_seconds=10),
        PortAccessibleAssert(port=8090, host="localhost", protocol="tcp"),
        HealthcheckAssert(url="http://localhost:8090", expected_status=200, timeout_seconds=5),
    ]
)
```

AI completes missing fields while preserving user overrides.

## Verification

The `clockwork assert` command validates:
- Container existence
- Container running state
- Port accessibility (8090)
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
