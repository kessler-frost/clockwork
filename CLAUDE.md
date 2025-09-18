- "I'm using uv in this repo so run the scripts and cli by keeping that in mind"
- "Use uv to run python scripts and python based cli (e.g., 'uv run python script.py', 'uv run clockwork --help')"
- "when generating a plan, keep in mind to allocate spawning separate agents for tasks in the plan that can be parallelized"
- "don't worry about backward's compatibility and fallback mechanisms"
- "Always test whether the demo command is broken or not"
- "Always do cleanup after final testing and demoing is finished"

## PyInfra-Based Architecture

Clockwork now uses **PyInfra** for infrastructure management with the following characteristics:

### Key Features
- **PyInfra Integration**: Direct conversion of .cw files to PyInfra operations
- **Two-Phase Pipeline**: Simple Parse → Execute workflow
- **Multi-Target Support**: Local, SSH, Docker, and Kubernetes deployment targets
- **State Management**: Built-in state tracking and drift detection
- **Dry-Run Safety**: All operations can be previewed before execution

### Configuration

Use environment variables for configuration:

- `CLOCKWORK_PROJECT_NAME`: Project identifier (default: current directory name)
- `CLOCKWORK_LOG_LEVEL`: Log level (default: INFO)
- `CLOCKWORK_TARGET`: Default deployment target (default: localhost)
- `CLOCKWORK_PARALLEL_LIMIT`: Parallel execution limit (default: 4)
- `CLOCKWORK_DEFAULT_TIMEOUT`: Default operation timeout in seconds (default: 300)
- `CLOCKWORK_STATE_FILE`: State file location (default: .clockwork/state.json)

To configure deployment:
```bash
CLOCKWORK_TARGET="@docker:mycontainer" uv run clockwork apply examples/basic-web-service/main.cw
```

Or use a .env file:
```bash
echo "CLOCKWORK_TARGET=@ssh:production-server" >> .env
uv run clockwork apply examples/basic-web-service/main.cw
```

### Integration Details
- **PyInfra Operations**: Uses standard PyInfra operations for all infrastructure management
- **Target Support**: @local, @docker:container, @ssh:host for flexible deployment
- **State Tracking**: Automatic state management with drift detection
- **Health Checks**: Built-in HTTP, TCP, and file system health verification

### Architecture Changes
- **Simplified pipeline**: Direct Parse → Execute (no more Intake → Assembly → Forge)
- **No AI dependency**: Pure PyInfra-based execution, no LLM requirements
- **Direct execution**: Operations run immediately without artifact generation
- **State persistence**: Automatic state tracking in .clockwork/state.json

### Usage Examples

```bash
# Plan deployment (dry-run)
uv run clockwork plan examples/basic-web-service/main.cw

# Apply to local infrastructure
uv run clockwork apply examples/basic-web-service/main.cw

# Deploy to remote server via SSH
uv run clockwork apply --target @ssh:production-server examples/basic-web-service/main.cw

# Deploy to Docker container
uv run clockwork apply --target @docker:mycontainer examples/basic-web-service/main.cw

# Watch for changes and auto-apply
uv run clockwork watch examples/basic-web-service/main.cw

# Check system facts
uv run clockwork facts @local

# Manage deployment state
uv run clockwork state show
uv run clockwork state drift --config examples/basic-web-service/main.cw
```

When testing, always ensure the basic examples work:
```bash
# Test hello-world example
uv run clockwork plan examples/hello-world/main.cw
uv run clockwork apply examples/hello-world/main.cw

# Test basic-web-service example
uv run clockwork plan examples/basic-web-service/main.cw
uv run clockwork apply examples/basic-web-service/main.cw
```