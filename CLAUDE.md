# Clockwork Development Guide

**Factory for intelligent declarative infrastructure tasks.**

## Setup

This project uses `uv` for Python package management:

```bash
# Run CLI
uv run clockwork --help

# Run tests
uv run pytest tests/

# Run example
cd examples/file-generation
uv run clockwork apply
```

## Architecture

Clockwork is a **factory for intelligent declarative infrastructure tasks** using a simple **Python + PyInfra** architecture:

1. **Declare** (Pydantic models): Users define infrastructure tasks in Python
2. **Generate** (AI via OpenRouter): AI creates dynamic artifacts when needed
3. **Compile** (Templates): Resources generate PyInfra operations
4. **Deploy** (PyInfra): Native PyInfra executes the infrastructure tasks

The "factory" metaphor: You provide the blueprint (Pydantic resources), the factory (Clockwork) intelligently manufactures the artifacts (via AI) and assembles them (via PyInfra).

## Assertions

Clockwork provides a **type-safe assertion system** for validating deployed resources:

### Type-Safe Assertions

**Type-safe assertion classes**:
- Pydantic-based classes with IDE autocomplete
- Instant compilation to PyInfra operations
- No API costs or latency
- Example: `HealthcheckAssert(url="http://localhost:80")`

### Available Assertion Classes

**HTTP/Network:**
- `HealthcheckAssert(url, expected_status=200)` - HTTP endpoint validation
- `PortAccessibleAssert(port, host="localhost")` - Port connectivity checks
- `ResponseTimeAssert(url, max_ms)` - Performance validation

**Container:**
- `ContainerRunningAssert()` - Docker container status
- `ContainerHealthyAssert()` - Health check validation
- `LogContainsAssert(pattern, lines=100)` - Log pattern matching

**File:**
- `FileExistsAssert(path)` - File/directory existence
- `FilePermissionsAssert(path, mode, owner, group)` - Permission validation
- `FileSizeAssert(path, min_bytes, max_bytes)` - Size bounds
- `FileContentMatchesAssert(path, pattern, sha256)` - Content validation

**Resources:**
- `MemoryUsageAssert(max_mb)` - Memory limit validation
- `CpuUsageAssert(max_percent)` - CPU usage limits
- `DiskUsageAssert(path, max_percent, max_mb)` - Disk usage

**Process:**
- `ProcessRunningAssert(name, min_count=1)` - Process validation
- `ProcessNotRunningAssert(name)` - Absence validation

### Usage Example

```python
from clockwork.resources import DockerServiceResource
from clockwork.assertions import (
    HealthcheckAssert,
    PortAccessibleAssert,
    ContainerRunningAssert,
)

nginx = DockerServiceResource(
    name="nginx-web",
    description="Web server",
    ports=["80:80"],
    assertions=[
        # Type-safe assertions
        ContainerRunningAssert(),
        PortAccessibleAssert(port=80),
        HealthcheckAssert(url="http://localhost:80/health"),
        ResponseTimeAssert(url="http://localhost:80", max_ms=200),
    ]
)
```

### Running Assertions

```bash
cd examples/docker-service
clockwork assert

# Output:
# ✓ All assertions passed
#   ✓ nginx-web: ContainerRunningAssert
#   ✓ nginx-web: PortAccessibleAssert (port 80)
#   ✓ nginx-web: HealthcheckAssert (http://localhost:80/health)
#   ✓ nginx-web: ResponseTimeAssert (< 200ms)
```

## Configuration

Clockwork uses **Pydantic Settings** for configuration management via `.env` files.

### Setup .env File

Create a `.env` file in the project root:

```bash
OPENROUTER_API_KEY=your-api-key-here
OPENROUTER_MODEL=openai/gpt-oss-20b:free
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
PYINFRA_OUTPUT_DIR=.clockwork/pyinfra
LOG_LEVEL=INFO
```

### Available Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `OPENROUTER_API_KEY` | None | OpenRouter API key (required) |
| `OPENROUTER_MODEL` | `openai/gpt-oss-20b:free` | Model for AI generation |
| `OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` | OpenRouter API endpoint |
| `PYINFRA_OUTPUT_DIR` | `.clockwork/pyinfra` | PyInfra output directory |
| `LOG_LEVEL` | `INFO` | Logging level |
| `PROJECT_NAME` | None | Project identifier (optional) |

### Override Hierarchy

Settings can be overridden:

1. **CLI flags** (highest priority) - `--api-key`, `--model`
2. **Environment variables** - `export OPENROUTER_API_KEY="..."`
3. **.env file** - loaded from project root
4. **Defaults** (lowest priority) - defined in settings

Example using CLI override:

```bash
uv run clockwork apply --model "openai/gpt-4o-mini"
```

### PyInfra Output

Clockwork generates PyInfra files in the configured output directory (default: `.clockwork/pyinfra/`):

- `inventory.py` - Target hosts (default: `@local`)
- `deploy.py` - Infrastructure operations

## Project Structure

```text
clockwork/
├── clockwork/
│   ├── resources/          # Pydantic resource models
│   │   ├── base.py        # Base Resource class
│   │   ├── file.py        # FileResource
│   │   └── docker.py      # DockerServiceResource
│   ├── artifact_generator.py  # AI-powered content generation
│   ├── pyinfra_compiler.py    # Template-based PyInfra code gen
│   ├── core.py               # Main pipeline orchestrator
│   ├── cli.py                # CLI interface
│   └── settings.py           # Configuration via Pydantic Settings
├── examples/
│   ├── file-generation/    # File generation example
│   └── docker-service/     # Docker service example
├── tests/                  # Test suite
└── pyproject.toml         # Dependencies
```

## Development Workflow

### Adding a New Resource Type

1. Create a new resource class in `clockwork/resources/`:

```python
from .base import Resource, ArtifactSize
from typing import Optional, Dict, Any

class MyResource(Resource):
    name: str
    # ... your fields

    def needs_artifact_generation(self) -> bool:
        # Return True if AI should generate content
        return self.content is None

    def to_pyinfra_operations(self, artifacts: Dict[str, Any]) -> str:
        # Return PyInfra operation code as string
        return f'''
# Your PyInfra operation
server.shell(
    name="My operation",
    commands=["echo 'hello'"]
)
'''

    def to_pyinfra_destroy_operations(self, artifacts: Dict[str, Any]) -> str:
        # Return PyInfra operation code to tear down the resource
        return f'''
# Remove MyResource
server.shell(
    name="Remove my resource",
    commands=["echo 'cleanup'"]
)
'''
```

1. Export it in `clockwork/resources/__init__.py`
2. Add tests in `tests/test_resources.py`
3. Create an example in `examples/`

#### Example: DockerServiceResource

The `DockerServiceResource` demonstrates a complete resource implementation with AI-powered image suggestions:

```python
from clockwork.resources import DockerServiceResource

# AI suggests the Docker image based on description
nginx = DockerServiceResource(
    name="nginx-web",
    description="Web server for serving static content",
    ports=["80:80"],
    volumes=["./html:/usr/share/nginx/html"],
    env_vars={"ENV": "production"}
)

# Explicit image specification
redis = DockerServiceResource(
    name="redis-cache",
    description="Redis cache server",
    image="redis:7-alpine",
    ports=["6379:6379"],
    volumes=["redis_data:/data"]
)
```

### Testing

Run all tests:

```bash
uv run pytest tests/ -v
```

Run specific test file:

```bash
uv run pytest tests/test_resources.py -v
```

### Demo Command

Test the full pipeline:

```bash
# Create .env file with API key
echo "OPENROUTER_API_KEY=your-key-here" > .env

# Run file generation example
cd examples/file-generation
uv run clockwork apply

# Validate deployed resources
uv run clockwork assert

# Destroy deployed resources
uv run clockwork destroy

# Test Docker service example
cd ../docker-service
uv run clockwork apply

# Run assertions
uv run clockwork assert

# Destroy Docker containers
uv run clockwork destroy
```

## Code Guidelines

**Follow Google Python Style Guide**: <https://google.github.io/styleguide/pyguide.html>

Key conventions:

- **Imports**: Group by standard library → third-party → local, alphabetically sorted
- **Naming**: `lowercase_with_underscores` for functions/variables, `CapWords` for classes
- **Type hints**: Use for all public APIs and function signatures
- **Docstrings**: Use triple-double quotes with Args/Returns/Raises sections
- **Settings**: Always use `get_settings()`, never `os.getenv()` or hardcoded defaults
- **Error handling**: Use specific exceptions with meaningful messages
- **API Documentation**: Always use Context7 MCP server first for library documentation via `mcp__context7__resolve-library-id` and `mcp__context7__get-library-docs` tools. Fall back to WebFetch/WebSearch only if Context7 doesn't have the needed docs.

## Important Notes

- **Settings-based configuration**: Always use `.env` file or `get_settings()`, never hardcode
- **AI requires API key**: OpenRouter API key must be configured in `.env` file
- **Keep it simple**: PyInfra handles all the complex execution logic
- **Test the demo**: Always verify the examples work by running `clockwork apply` from their directories

## Cleanup

After testing, clean up generated files:

```bash
# Use destroy command to tear down resources
cd examples/file-generation
uv run clockwork destroy

cd ../docker-service
uv run clockwork destroy

# Or manually clean up
rm -rf .clockwork/
rm -rf examples/scratch/

# Stop Docker containers if needed
docker ps -a | grep -E "nginx-ai|redis-cache|postgres-db" | awk '{print $1}' | xargs docker rm -f
```
