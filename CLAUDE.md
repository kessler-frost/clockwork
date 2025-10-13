# Clockwork Development Guide

**Intelligent Infrastructure Orchestration in Python.**

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

**Cross-Platform Support**: Clockwork works on macOS, Linux, and Windows with support for both local and remote deployments:
- **Docker**: Works on any platform with Docker installed (Docker Desktop for Mac/Windows, native Docker for Linux)
- **macOS tools**: Homebrew, Apple Containers CLI
- **Standard Unix utilities**: git, cron, etc.

**Deployment options:**
- `@local` connector: Run operations on your local machine (Mac/Linux/Windows)
- SSH connectors: Deploy to remote Linux servers (see PyInfra documentation)

## Architecture

Clockwork provides **intelligent infrastructure orchestration** using a simple **Python + PyInfra** architecture:

1. **Declare** (Pydantic models): Define infrastructure in pure Python with optional resource connections
2. **Resolve** (Dependency ordering): Detect cycles and sort resources topologically
3. **Complete** (AI): Intelligent resource completion with connection context
4. **Compile** (Templates): Convert resources to PyInfra operations
5. **Deploy** (PyInfra): Execute infrastructure deployment in correct order

The orchestration flow: Python definitions → Dependency resolution → AI intelligence → PyInfra automation → Deployed infrastructure.

## Resource Types

Clockwork provides multiple resource types for different infrastructure needs:

### Container Resources

**DockerResource** - Cross-platform Docker container management:
- Uses PyInfra's native `docker.container` operation
- Works on Mac, Linux, Windows, and remote servers via SSH
- Standard Docker commands and workflows
- Best for: Production deployments, Linux servers, cross-platform compatibility

**AppleContainerResource** - macOS-optimized container management:
- Uses Apple Containers CLI (`container` command)
- macOS-specific optimizations
- Best for: Local macOS development and testing

Both resources provide the same API (description, name, image, ports, volumes, env_vars, networks) and support AI completion of missing fields.

### Other Resources

- **FileResource** - File generation and management
- **DirectoryResource** - Directory creation with permissions
- **GitRepoResource** - Git repository cloning
- **BrewPackageResource** - Homebrew package installation (macOS)
- **UserResource** - User account management

## Assertions

Clockwork provides a **type-safe assertion system** for validating deployed resources:

### Type-Safe Assertions

**Type-safe assertion classes**:
- Pydantic-based classes with IDE autocomplete
- Instant compilation to PyInfra operations
- No API costs or latency
- Example: `HealthcheckAssert(url="http://localhost:8080")`

### Available Assertion Classes

**HTTP/Network:**
- `HealthcheckAssert(url, expected_status=200)` - HTTP endpoint validation
- `PortAccessibleAssert(port, host="localhost")` - Port connectivity checks
- `ResponseTimeAssert(url, max_ms)` - Performance validation

**Container:**
- `ContainerRunningAssert()` - Container running status (Docker or Apple Containers)
- `ContainerHealthyAssert()` - Health check validation (Docker or Apple Containers)
- `LogContainsAssert(pattern, lines=100)` - Log pattern matching (Docker or Apple Containers)

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
    ports=["8080:80"],
    assertions=[
        # Type-safe assertions
        ContainerRunningAssert(),
        PortAccessibleAssert(port=8080),
        HealthcheckAssert(url="http://localhost:8080/health"),
        ResponseTimeAssert(url="http://localhost:8080", max_ms=200),
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
#   ✓ nginx-web: PortAccessibleAssert (port 8080)
#   ✓ nginx-web: HealthcheckAssert (http://localhost:8080/health)
#   ✓ nginx-web: ResponseTimeAssert (< 200ms)
```

## Tool Usage

Clockwork supports **PydanticAI tools** and **MCP (Model Context Protocol) servers** to extend AI capabilities during resource completion. Tools enable the AI to access real-time information, interact with external systems, and perform complex operations beyond its base knowledge.

### Available Tool Types

1. **PydanticAI Common Tools** - Universal tools that work with any model/provider
   - `duckduckgo_search_tool()` - Web search for real-time information (works with OpenRouter ✅)
   - `tavily_search_tool()` - Alternative search (requires Tavily API key)
   - Custom tools - Implement your own PydanticAI-compatible tools

2. **MCP Servers** - External services via Model Context Protocol
   - Filesystem access, database queries, API integrations
   - Any MCP-compatible server (stdio, HTTP, or Docker-based)

> **Note on Built-in Tools:** PydanticAI has provider-specific built-in tools like `WebSearchTool` and `CodeExecutionTool` that only work with Anthropic (`claude-sonnet-4-0`) and OpenAI (`gpt-4.1`) native APIs. Since Clockwork uses **OpenAI-compatible APIs** (which includes OpenRouter, LM Studio, Ollama, etc.), we use **common tools** instead, which work universally with any provider.

### Using PydanticAI Tools

**DuckDuckGo search tool** enables web search for current information:

```python
from pydantic_ai.common_tools.duckduckgo import duckduckgo_search_tool
from clockwork.resources import FileResource

# AI can search the web for real-time information
tech_news = FileResource(
    name="tech_news_today.md",
    description="Write about the latest AI developments and breakthroughs from this week",
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
from clockwork.resources import FileResource
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
from clockwork.resources import FileResource

# Initialize MCP server
filesystem_mcp = MCPServerStdio(
    'npx',
    args=['-y', '@modelcontextprotocol/server-filesystem', '/Users/user/project']
)

# AI can both search the web AND read local files
comprehensive_report = FileResource(
    name="comprehensive_analysis.md",
    description="Analyze our codebase and compare with industry best practices from the web",
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
- `examples/tool-integration/` - PydanticAI tool usage (web search) with optional MCP examples

```bash
# Try the tool integration example (no setup required)
cd examples/tool-integration
uv run clockwork apply
```

### Important Notes

- **Tools are optional** - Resources work fine without tools using AI's base knowledge
- **MCP requires installation** - Ensure MCP servers are installed before use
- **Authentication** - Some MCP servers require API keys or credentials
- **Permissions** - Filesystem MCP requires explicit directory permissions
- **Performance** - Tools add latency but provide real-time/external data access

## Resource Connections

Clockwork provides a **powerful connection system** that allows resources to declare dependencies on other resources. This enables:

1. **AI-powered completion with context** - AI sees connected resources and makes intelligent configuration decisions
2. **Automatic dependency ordering** - Resources are deployed in the correct order (dependencies first)
3. **Cross-resource configuration sharing** - Resources can access connection details from their dependencies
4. **Cycle detection** - Prevents circular dependencies before deployment

### Basic Usage

Declare connections by passing a list of Resource objects to the `connections` field:

```python
from clockwork.resources import DockerResource

# Define dependencies
postgres = DockerResource(
    name="postgres-db",
    image="postgres:15-alpine",
    ports=["5432:5432"],
    env_vars={"POSTGRES_PASSWORD": "secret", "POSTGRES_DB": "myapp"}
)

redis = DockerResource(
    name="redis-cache",
    image="redis:7-alpine",
    ports=["6379:6379"]
)

# Connect API to postgres + redis
api = DockerResource(
    description="FastAPI backend with database and cache",
    ports=["8000:8000"],
    connections=[postgres, redis]  # AI sees these during completion
)

# Deployment order: postgres → redis → api
# AI generates: DATABASE_URL, REDIS_URL env vars automatically
```

### Connection Context

When resources are connected, the AI receives **connection context** during completion. Each resource type exposes relevant fields through the `get_connection_context()` method:

**Container Resources (Docker, AppleContainer):**
- `name` - Container name
- `image` - Container image
- `ports` - Port mappings
- `env_vars` - Environment variables
- `networks` - Container networks

**File Resources (File, TemplateFile):**
- `name` - File name
- `path` - File path
- `directory` - Directory location
- `variables` - Template variables (TemplateFile only)

**Other Resources:**
- `GitRepoResource` - name, repo_url, branch, dest
- `BrewPackageResource` - name, packages, cask
- `DirectoryResource` - name, path, mode
- `UserResource` - name, system, home, shell, group

### AI-Powered Completion with Connections

The AI uses connection context to make intelligent decisions about configuration:

```python
# Without connections - AI guesses
api = DockerResource(
    description="FastAPI backend",
    ports=["8000:8000"]
)
# AI might generate: Generic image, no connection env vars

# With connections - AI knows exactly what to configure
api = DockerResource(
    description="FastAPI backend with database and cache",
    ports=["8000:8000"],
    connections=[postgres, redis]
)
# AI generates:
# - image: "tiangolo/uvicorn-gunicorn-fastapi:python3.11-slim"
# - env_vars:
#     DATABASE_URL: "postgresql://postgres:secret@postgres-db:5432/myapp"
#     REDIS_URL: "redis://redis-cache:6379"
# - networks: ["app-network"]  # Shared network for inter-container communication
```

### Automatic Dependency Ordering

Clockwork automatically orders resource deployment based on connections using **topological sorting**:

```python
# Definition order doesn't matter
a = DockerResource(name="a", connections=[b])
c = DockerResource(name="c", connections=[a])
b = DockerResource(name="b", connections=[])

# Deployment order: b → a → c
# (Dependencies are always deployed before dependents)
```

**Complex dependency graphs** are handled correctly:

```python
# Diamond dependency pattern
#     A
#    / \
#   B   C
#    \ /
#     D

d = DockerResource(name="d")
b = DockerResource(name="b", connections=[d])
c = DockerResource(name="c", connections=[d])
a = DockerResource(name="a", connections=[b, c])

# Deployment order: d → b → c → a
# OR: d → c → b → a (both valid topological sorts)
```

### Cycle Detection

Clockwork detects circular dependencies **before deployment** and provides clear error messages:

```python
# Circular dependency
a = DockerResource(name="a", connections=[b])
b = DockerResource(name="b", connections=[c])
c = DockerResource(name="c", connections=[a])  # Creates cycle: a → b → c → a

# Error: Dependency cycle detected: a → b → c → a
```

The cycle detection algorithm uses **Depth-First Search (DFS)** and runs in O(V+E) time, where V is the number of resources and E is the number of connections.

### Real-World Example: Full-Stack Application

```python
from clockwork.resources import DockerResource

# Layer 1: Data stores (no dependencies)
postgres = DockerResource(
    name="postgres-db",
    image="postgres:15-alpine",
    ports=["5432:5432"],
    env_vars={
        "POSTGRES_DB": "appdb",
        "POSTGRES_USER": "admin",
        "POSTGRES_PASSWORD": "secret123"
    },
    volumes=["postgres_data:/var/lib/postgresql/data"]
)

redis = DockerResource(
    name="redis-cache",
    image="redis:7-alpine",
    ports=["6379:6379"],
    volumes=["redis_data:/data"]
)

# Layer 2: Backend services (depend on data stores)
api = DockerResource(
    description="FastAPI backend server with database and cache support",
    ports=["8000:8000"],
    connections=[postgres, redis]
)

worker = DockerResource(
    description="Background worker processing jobs from Redis queue",
    connections=[redis]
)

# Deployment order: postgres, redis → api, worker
```

See the full example in `examples/connected-services/`.

### Connection Patterns

**1. Database Connection Pattern**
```python
db = DockerResource(name="db", image="postgres:15")
app = DockerResource(
    description="App that needs database",
    connections=[db]
)
# AI generates: DATABASE_URL env var with correct connection string
```

**2. Cache Pattern**
```python
cache = DockerResource(name="cache", image="redis:7-alpine")
app = DockerResource(
    description="App that needs caching",
    connections=[cache]
)
# AI generates: REDIS_URL or CACHE_URL env var
```

**3. Queue/Worker Pattern**
```python
queue = DockerResource(name="queue", image="redis:7-alpine")
worker1 = DockerResource(description="Worker 1", connections=[queue])
worker2 = DockerResource(description="Worker 2", connections=[queue])
api = DockerResource(description="API that enqueues jobs", connections=[queue])
# All get QUEUE_URL/REDIS_URL env vars, shared network
```

**4. Microservices Pattern**
```python
service_a = DockerResource(name="service-a", image="my-service-a")
service_b = DockerResource(
    description="Service B that calls Service A",
    connections=[service_a]
)
# AI configures service_b to connect to service_a on shared network
```

### Best Practices

1. **Declare connections explicitly** - Even if the AI could infer relationships, explicit connections ensure correct ordering and context

2. **Use descriptive resource descriptions** - Mention what the resource needs to connect to:
   ```python
   # Good
   api = DockerResource(
       description="FastAPI app that needs PostgreSQL database and Redis cache",
       connections=[postgres, redis]
   )

   # Less effective
   api = DockerResource(
       description="Web API",
       connections=[postgres, redis]
   )
   ```

3. **Keep dependency graphs shallow** - Deeply nested dependencies (>5 levels) can be harder to understand and debug

4. **Avoid circular dependencies** - Design your architecture to have clear dependency layers

5. **Use connection context** - Override `get_connection_context()` in custom resource types to expose relevant fields:
   ```python
   class MyDatabaseResource(Resource):
       host: str
       port: int

       def get_connection_context(self) -> Dict[str, Any]:
           context = super().get_connection_context()
           context.update({
               "host": self.host,
               "port": self.port,
               "connection_string": f"{self.host}:{self.port}"
           })
           return context
   ```

### Connection Examples

See complete working examples in the `examples/` directory:
- `examples/connected-services/` - Full-stack application with PostgreSQL, Redis, API, and Worker

```bash
cd examples/connected-services
uv run clockwork apply    # Deploy in correct order
uv run clockwork assert   # Verify connections
uv run clockwork destroy  # Clean up
```

## Configuration

Clockwork uses **Pydantic Settings** for configuration management via `.env` files.

### Setup .env File

Create a `.env` file in the project root:

**For LM Studio (local development):**
```bash
CW_API_KEY=lm-studio
CW_MODEL=local-model
CW_BASE_URL=http://localhost:1234/v1
CW_PYINFRA_OUTPUT_DIR=.clockwork/pyinfra
CW_LOG_LEVEL=INFO
```

**For OpenRouter (cloud):**
```bash
CW_API_KEY=your-api-key-here
CW_MODEL=meta-llama/llama-4-scout:free
CW_BASE_URL=https://openrouter.ai/api/v1
CW_PYINFRA_OUTPUT_DIR=.clockwork/pyinfra
CW_LOG_LEVEL=INFO
```

### Available Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `CW_API_KEY` | None | API key (required for cloud models) |
| `CW_MODEL` | `meta-llama/llama-4-scout:free` | Model for AI completion |
| `CW_BASE_URL` | `https://openrouter.ai/api/v1` | API endpoint (use `http://localhost:1234/v1` for LM Studio) |
| `CW_PYINFRA_OUTPUT_DIR` | `.clockwork/pyinfra` | PyInfra output directory |
| `CW_LOG_LEVEL` | `INFO` | Logging level |

### Override Hierarchy

Settings can be overridden:

1. **CLI flags** (highest priority) - `--api-key`, `--model`
2. **Environment variables** - `export CW_API_KEY="..."`
3. **.env file** - loaded from project root
4. **Defaults** (lowest priority) - defined in settings

Example using CLI override:

```bash
uv run clockwork apply --model "meta-llama/llama-4-maverick:free"
```

### PyInfra Output

Clockwork generates PyInfra files in the configured output directory (default: `.clockwork/pyinfra/`):

- `inventory.py` - Target hosts (default: `@local`)
- `deploy.py` - Infrastructure operations
- `destroy.py` - Cleanup operations (generated during apply)
- `assert.py` - Assertion validations (generated during assert)

### Recommended AI Models

Clockwork supports both **local models** (LM Studio, Ollama) and **cloud models** (OpenRouter) for AI-powered resource completion.

#### Local Models (LM Studio, Ollama)

**LM Studio** ✅ **RECOMMENDED FOR LOCAL** - Best local development experience:
```bash
# .env configuration for LM Studio
CW_API_KEY=lm-studio
CW_MODEL=local-model
CW_BASE_URL=http://localhost:1234/v1
```

**Ollama** - Alternative local option:
```bash
# .env configuration for Ollama
CW_API_KEY=ollama
CW_MODEL=llama3.2
CW_BASE_URL=http://localhost:11434/v1
```

#### Cloud Models (OpenRouter)

**Recommended FREE models**:
- `meta-llama/llama-4-scout:free` ✅ Fast and capable
- `qwen/qwen-2.5-72b-instruct:free` ✅ Alternative free option
- `google/gemini-2.0-flash-exp:free` ⚠️ Can be rate-limited

**Paid models**:
- `openai/gpt-4o-mini` - Inexpensive and very capable
- `anthropic/claude-3-haiku` - Fast and reliable

OpenRouter configuration:
```bash
CW_API_KEY=your-api-key-here
CW_MODEL=meta-llama/llama-4-scout:free
CW_BASE_URL=https://openrouter.ai/api/v1
```

#### Model Requirements

**All models must support tool calls** (function calling). Clockwork uses PydanticAI's **Tool Output mode** for structured data generation, which is the most reliable approach for getting properly formatted resource completions from AI models.

**Why Tool Output mode?**
- Most reliable method for structured data generation
- Built-in validation and retry logic
- Better error handling than prompt-based approaches
- Works with any OpenAI-compatible API

**If a model doesn't support tool calls**, choose a different model from the recommendations above. All recommended models (both free and paid) support tool calling.

## Project Structure

```text
clockwork/
├── clockwork/
│   ├── resources/              # Pydantic resource models
│   │   ├── base.py            # Base Resource class
│   │   ├── file.py            # FileResource
│   │   ├── docker.py          # DockerResource (cross-platform)
│   │   └── apple_container.py # AppleContainerResource (macOS)
│   ├── pyinfra_operations/    # Custom PyInfra operations
│   │   └── apple_containers.py # Apple Containers CLI operations
│   ├── pyinfra_facts/         # Custom PyInfra facts
│   │   └── apple_containers.py # Apple Containers CLI facts
│   ├── resource_completer.py  # AI-powered resource completion
│   ├── pyinfra_compiler.py    # Template-based PyInfra code gen
│   ├── core.py                # Main pipeline orchestrator
│   ├── cli.py                 # CLI interface
│   └── settings.py            # Configuration via Pydantic Settings
├── examples/
│   ├── file-generation/           # File generation example
│   ├── docker-service/            # Docker service example (cross-platform)
│   ├── apple-container-service/   # Apple Container service example (macOS)
│   ├── tool-integration/          # Tool integration example (web search)
│   └── connected-services/        # Resource connections example (full-stack app)
├── tests/                  # Test suite
└── pyproject.toml         # Dependencies
```

## Development Workflow

### Adding a New Resource Type

1. Create a new resource class in `clockwork/resources/`:

```python
from .base import Resource
from typing import Optional, Dict, Any

class MyResource(Resource):
    name: str
    # ... your fields

    def needs_completion(self) -> bool:
        # Return True if AI should complete missing fields
        return self.content is None

    def to_pyinfra_operations(self) -> str:
        # Return PyInfra operation code as string
        return f'''
# Your PyInfra operation
server.shell(
    name="My operation",
    commands=["echo 'hello'"]
)
'''

    def to_pyinfra_destroy_operations(self) -> str:
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

**Note on structured outputs**: Clockwork uses PydanticAI's **Tool Output mode** for structured data generation. This is the most reliable approach, using function calling to ensure the AI returns properly formatted resource completions. The system automatically validates output against Pydantic models and retries if validation fails, providing type-safe, production-ready infrastructure definitions.

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
echo "CW_API_KEY=your-key-here" > .env

# Run file generation example
cd examples/file-generation
uv run clockwork apply

# Validate deployed resources
uv run clockwork assert

# Destroy deployed resources
uv run clockwork destroy

# Test Docker service example (cross-platform)
cd ../docker-service
uv run clockwork apply

# Run assertions
uv run clockwork assert

# Destroy containers
uv run clockwork destroy

# Test Apple Container service example (macOS)
cd ../apple-container-service
uv run clockwork apply

# Run assertions
uv run clockwork assert

# Destroy containers
uv run clockwork destroy

# Test tool integration (web search - no setup required)
cd ../tool-integration
uv run clockwork apply

# Test connected services (resource connections with full-stack app)
cd ../connected-services
uv run clockwork apply
uv run clockwork assert
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
- **PyInfra First**: Always use PyInfra's native operations and methods. Avoid `server.shell()` unless absolutely necessary. Prefer:
  - `docker.container()` over `server.shell(commands=["docker run"])`
  - `files.file()` over `server.shell(commands=["echo > file"])`
  - `git.repo()` over `server.shell(commands=["git clone"])`
  - PyInfra facts over shell commands for assertions

## Important Notes

- **Settings-based configuration**: Always use `.env` file or `get_settings()`, never hardcode
- **AI requires API key**: API key must be configured in `.env` file (for cloud models)
- **Keep it simple**: PyInfra handles all the complex execution logic
- **Test the demo**: Always verify the examples work by running `clockwork apply` from their directories

## Cleanup

After testing, clean up generated files:

```bash
# Use destroy command to tear down resources
# By default, this removes the .clockwork directory
cd examples/file-generation
uv run clockwork destroy

cd ../apple-container-service
uv run clockwork destroy

# Keep .clockwork directory after destroy (optional)
uv run clockwork destroy --keep-files

# Or manually clean up
rm -rf .clockwork/
rm -rf examples/scratch/

# Stop containers if needed
container ls -a --format json | jq -r '.[] | select(.name | test("nginx-ai|redis-cache|postgres-db")) | .name' | xargs -I {} container rm -f {}
```

**Note**: The `destroy` command automatically removes the `.clockwork` directory after successfully destroying resources. Use `--keep-files` to preserve the directory if needed for debugging or inspection.
