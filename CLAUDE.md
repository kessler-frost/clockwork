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

### Platform Requirements

**macOS Compatible**: All examples in this repository are designed to run on macOS using the `@local` connector. Examples use Mac-compatible tools like:
- Docker (requires Docker Desktop for Mac)
- Homebrew for package management
- Standard Unix utilities (git, cron, etc.)

For Linux/remote deployments, modify the inventory in your `main.py` or use SSH connectors as documented in the PyInfra documentation.

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
- `ContainerRunningAssert()` - Apple Container status
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
from clockwork.resources import AppleContainerResource
from clockwork.assertions import (
    HealthcheckAssert,
    PortAccessibleAssert,
    ContainerRunningAssert,
)

nginx = AppleContainerResource(
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
cd examples/apple-container-service
clockwork assert

# Output:
# ✓ All assertions passed
#   ✓ nginx-web: ContainerRunningAssert
#   ✓ nginx-web: PortAccessibleAssert (port 80)
#   ✓ nginx-web: HealthcheckAssert (http://localhost:80/health)
#   ✓ nginx-web: ResponseTimeAssert (< 200ms)
```

## Tool Usage

Clockwork supports **PydanticAI tools** and **MCP (Model Context Protocol) servers** to extend AI capabilities during artifact generation. Tools enable the AI to access real-time information, interact with external systems, and perform complex operations beyond its base knowledge.

### Available Tool Types

1. **PydanticAI Common Tools** - Universal tools that work with any model/provider
   - `duckduckgo_search_tool()` - Web search for real-time information (works with OpenRouter ✅)
   - `tavily_search_tool()` - Alternative search (requires Tavily API key)
   - Custom tools - Implement your own PydanticAI-compatible tools

2. **MCP Servers** - External services via Model Context Protocol
   - Filesystem access, database queries, API integrations
   - Any MCP-compatible server (stdio, HTTP, or Docker-based)

> **Note on Built-in Tools:** PydanticAI has provider-specific built-in tools like `WebSearchTool` and `CodeExecutionTool` that only work with Anthropic (`claude-sonnet-4-0`) and OpenAI (`gpt-4.1`) native APIs. Since Clockwork uses **OpenRouter with free models**, we use **common tools** instead, which work universally with any provider.

### Using PydanticAI Tools

**DuckDuckGo search tool** enables web search for current information:

```python
from pydantic_ai.common_tools.duckduckgo import duckduckgo_search_tool
from clockwork.resources import FileResource, ArtifactSize

# AI can search the web for real-time information
tech_news = FileResource(
    name="tech_news_today.md",
    description="Write about the latest AI developments and breakthroughs from this week",
    size=ArtifactSize.MEDIUM,
    directory="scratch",
    # Enable web search capability
    tools=[duckduckgo_search_tool()],
)
```

**Installation requirement**:
```bash
# DuckDuckGo tool is already included in Clockwork's dependencies
# pydantic-ai-slim[duckduckgo] is installed automatically via pyproject.toml
```

### Using MCP Servers

**MCP servers** allow AI to interact with external systems through a standardized protocol:

```python
from clockwork.resources import FileResource, ArtifactSize
from pydantic_ai.mcp import MCPServerStdio

# Initialize MCP filesystem server
filesystem_mcp = MCPServerStdio(
    'npx',
    args=['-y', '@modelcontextprotocol/server-filesystem', '/path/to/project']
)

# AI can read and analyze local files
project_analysis = FileResource(
    name="project_analysis.md",
    description="Analyze the project structure and provide insights about the architecture",
    size=ArtifactSize.LARGE,
    directory="scratch",
    toolsets=[filesystem_mcp],  # Note: toolsets not tools for MCP
)
```

### Common MCP Servers

**Official MCP servers** (via npm):

```python
from pydantic_ai.mcp import MCPServerStdio

# Filesystem access
filesystem_mcp = MCPServerStdio(
    'npx',
    args=['-y', '@modelcontextprotocol/server-filesystem', '/path']
)

# PostgreSQL database
postgres_mcp = MCPServerStdio(
    'npx',
    args=['-y', '@modelcontextprotocol/server-postgres', 'postgresql://user:pass@host/db']
)

# SQLite database
sqlite_mcp = MCPServerStdio(
    'npx',
    args=['-y', '@modelcontextprotocol/server-sqlite', '/path/to/database.db']
)

# GitHub integration
github_mcp = MCPServerStdio(
    'npx',
    args=['-y', '@modelcontextprotocol/server-github']
)

# Google Drive
gdrive_mcp = MCPServerStdio(
    'npx',
    args=['-y', '@modelcontextprotocol/server-gdrive']
)
```

**Custom MCP servers**:

```python
from pydantic_ai.mcp import MCPServerStdio

# Python-based MCP server
python_mcp = MCPServerStdio('python', args=['/path/to/custom_server.py'])

# Docker-based MCP server
docker_mcp = MCPServerStdio('docker', args=['run', '-i', 'my-mcp-server'])
```

### Combining Tools and MCP

You can use both PydanticAI tools and MCP servers together:

```python
from pydantic_ai.common_tools.duckduckgo import duckduckgo_search_tool
from pydantic_ai.mcp import MCPServerStdio
from clockwork.resources import FileResource, ArtifactSize

# Initialize MCP server
filesystem_mcp = MCPServerStdio(
    'npx',
    args=['-y', '@modelcontextprotocol/server-filesystem', '/Users/user/project']
)

# AI can both search the web AND read local files
comprehensive_report = FileResource(
    name="comprehensive_analysis.md",
    description="Analyze our codebase and compare with industry best practices from the web",
    size=ArtifactSize.LARGE,
    directory="scratch",
    tools=[duckduckgo_search_tool()],  # Web search
    toolsets=[filesystem_mcp],         # Filesystem access (note: separate parameter)
)
```


### Practical Examples

**Example 1: Real-time Market Data**
```python
from pydantic_ai.common_tools.duckduckgo import duckduckgo_search_tool

market_report = FileResource(
    name="market_report.md",
    description="Current tech stock trends and analyst insights for Apple, Google, Microsoft",
    tools=[duckduckgo_search_tool()],  # Fetches real-time data
)
```

**Example 2: Code Analysis with Filesystem**
```python
from pydantic_ai.mcp import MCPServerStdio

filesystem_mcp = MCPServerStdio(
    'npx',
    args=['-y', '@modelcontextprotocol/server-filesystem', '/path/to/code']
)

code_review = FileResource(
    name="code_review.md",
    description="Review the codebase for security issues and best practices",
    toolsets=[filesystem_mcp],
)
```

**Example 3: Database-Driven Reports**
```python
from pydantic_ai.mcp import MCPServerStdio

postgres_mcp = MCPServerStdio(
    'npx',
    args=['-y', '@modelcontextprotocol/server-postgres', 'postgresql://user:pass@host/db']
)

db_report = FileResource(
    name="analytics.md",
    description="Generate analytics report from our production database",
    toolsets=[postgres_mcp],
)
```

**Example 4: Multi-Source Analysis**
```python
from pydantic_ai.common_tools.duckduckgo import duckduckgo_search_tool
from pydantic_ai.mcp import MCPServerStdio

postgres_mcp = MCPServerStdio(
    'npx',
    args=['-y', '@modelcontextprotocol/server-postgres', 'postgresql://localhost/myapp']
)
filesystem_mcp = MCPServerStdio(
    'npx',
    args=['-y', '@modelcontextprotocol/server-filesystem', '/path/to/app']
)

hybrid_analysis = FileResource(
    name="competitive_analysis.md",
    description="Compare our app with competitors using our database and web research",
    tools=[duckduckgo_search_tool()],
    toolsets=[postgres_mcp, filesystem_mcp],
)
```

### Tool Examples Directory

See the complete example:
- `examples/mcp-integration/` - MCP server usage patterns

```bash
# Try the MCP example
cd examples/mcp-integration
npm install -g @modelcontextprotocol/server-filesystem
uv run clockwork apply
```

### Important Notes

- **Tools are optional** - Resources work fine without tools using AI's base knowledge
- **MCP requires installation** - Ensure MCP servers are installed before use
- **Authentication** - Some MCP servers require API keys or credentials
- **Permissions** - Filesystem MCP requires explicit directory permissions
- **Performance** - Tools add latency but provide real-time/external data access

## Configuration

Clockwork uses **Pydantic Settings** for configuration management via `.env` files.

### Setup .env File

Create a `.env` file in the project root:

```bash
CW_OPENROUTER_API_KEY=your-api-key-here
CW_OPENROUTER_MODEL=meta-llama/llama-4-scout:free
CW_OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
CW_PYINFRA_OUTPUT_DIR=.clockwork/pyinfra
CW_LOG_LEVEL=INFO
```

### Available Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `CW_OPENROUTER_API_KEY` | None | OpenRouter API key (required) |
| `CW_OPENROUTER_MODEL` | `meta-llama/llama-4-scout:free` | Model for AI generation |
| `CW_OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` | OpenRouter API endpoint |
| `CW_PYINFRA_OUTPUT_DIR` | `.clockwork/pyinfra` | PyInfra output directory |
| `CW_LOG_LEVEL` | `INFO` | Logging level |

### Override Hierarchy

Settings can be overridden:

1. **CLI flags** (highest priority) - `--api-key`, `--model`
2. **Environment variables** - `export CW_OPENROUTER_API_KEY="..."`
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
- `destroy.py` - Cleanup operations (generated during apply)
- `assert.py` - Assertion validations (generated during assert)

## Project Structure

```text
clockwork/
├── clockwork/
│   ├── resources/              # Pydantic resource models
│   │   ├── base.py            # Base Resource class
│   │   ├── file.py            # FileResource
│   │   └── apple_container.py # AppleContainerResource
│   ├── pyinfra_operations/    # Custom PyInfra operations
│   │   └── apple_containers.py # Apple Containers CLI operations
│   ├── pyinfra_facts/         # Custom PyInfra facts
│   │   └── apple_containers.py # Apple Containers CLI facts
│   ├── artifact_generator.py  # AI-powered content generation
│   ├── pyinfra_compiler.py    # Template-based PyInfra code gen
│   ├── core.py                # Main pipeline orchestrator
│   ├── cli.py                 # CLI interface
│   └── settings.py            # Configuration via Pydantic Settings
├── examples/
│   ├── file-generation/           # File generation example
│   ├── apple-container-service/   # Apple Container service example
│   └── mcp-integration/           # MCP server integration example
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

#### Example: AppleContainerResource

The `AppleContainerResource` demonstrates a complete resource implementation with AI-powered image suggestions:

```python
from clockwork.resources import AppleContainerResource

# AI suggests the container image based on description
nginx = AppleContainerResource(
    name="nginx-web",
    description="Web server for serving static content",
    ports=["80:80"],
    volumes=["./html:/usr/share/nginx/html"],
    env_vars={"ENV": "production"}
)

# Explicit image specification
redis = AppleContainerResource(
    name="redis-cache",
    description="Redis cache server",
    image="redis:7-alpine",
    ports=["6379:6379"],
    volumes=["redis_data:/data"]
)
```

**Note on structured outputs**: DockerServiceResource uses PydanticAI's structured output capabilities to ensure the AI returns a properly formatted Docker image specification. This leverages Pydantic models for type-safe validation of AI-generated content.

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
echo "CW_OPENROUTER_API_KEY=your-key-here" > .env

# Run file generation example
cd examples/file-generation
uv run clockwork apply

# Validate deployed resources
uv run clockwork assert

# Destroy deployed resources
uv run clockwork destroy

# Test Apple Container service example
cd ../apple-container-service
uv run clockwork apply

# Run assertions
uv run clockwork assert

# Destroy containers
uv run clockwork destroy

# Test MCP integration (filesystem access)
cd ../mcp-integration
npm install -g @modelcontextprotocol/server-filesystem
uv run clockwork apply
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

cd ../apple-container-service
uv run clockwork destroy

# Or manually clean up
rm -rf .clockwork/
rm -rf examples/scratch/

# Stop containers if needed
container ls -a --format json | jq -r '.[] | select(.name | test("nginx-ai|redis-cache|postgres-db")) | .name' | xargs -I {} container rm -f {}
```
