# Clockwork Development Guide

**Intelligent, Composable Primitives for Infrastructure.**

## Setup

```bash
uv run clockwork --help          # CLI help
uv run pytest tests/             # Run tests
cd examples/showcase && uv run clockwork apply  # Run example
```

**Platform**: macOS, Linux, Windows (local or SSH remote)
**Tools**: Docker, Homebrew, Apple Containers CLI, standard Unix utilities

## Architecture

**Flow**: Declare (Pydantic) → Resolve (dependencies) → Complete (AI) → Compile (Pulumi) → Deploy (Automation API)

## Controlling AI Involvement

Clockwork primitives offer **adjustable intelligence** - you choose how much AI handles per resource:

**Full Control (No AI)**:
```python
DockerResource(
    name="my-nginx",
    image="nginx:1.25-alpine",
    ports=["8080:80"],
    volumes=["/configs:/etc/nginx"]
)
# All fields specified → AI skipped
```

**Hybrid (AI Assists)**:
```python
DockerResource(
    description="web server with caching",
    ports=["8080:80"]  # You specify port
    # AI picks image and config
)
```

**Fast Mode (AI Handles Implementation)**:
```python
DockerResource(
    description="web server for static files",
    assertions=[HealthcheckAssert(url="http://localhost:8080")]
)
# AI handles everything, assertions verify behavior
```

Choose per primitive, per project. What you find tedious is personal.

## Resource Types

**Containers**: DockerResource (cross-platform), AppleContainerResource (macOS)
**Files**: FileResource, TemplateFileResource (Jinja2)
**Other**: GitRepoResource

All support AI completion with `description` field.

### TemplateFileResource Example

```python
TemplateFileResource(
    description="Nginx config on port 8080",
    template_content="server { listen {{ port }}; }",
    variables={"port": 8080}  # Optional, AI can infer
)
```

## Assertions: Functional Determinism

Clockwork achieves **functional determinism** through validation - assertions verify behavior, not implementation.

**Philosophy**: Same requirements → validated equivalent results
- AI can choose optimal implementations
- Outcomes are verified, not assumed
- Flexibility without unpredictability

**Type-safe validation** (Pydantic-based, no AI costs):

**HTTP/Network**: HealthcheckAssert, PortAccessibleAssert, ResponseTimeAssert
**Container**: ContainerRunningAssert, ContainerHealthyAssert, LogContainsAssert
**File**: FileExistsAssert, FilePermissionsAssert, FileSizeAssert, FileContentMatchesAssert
**Resources**: MemoryUsageAssert, CpuUsageAssert, DiskUsageAssert
**Process**: ProcessRunningAssert, ProcessNotRunningAssert

```python
nginx = AppleContainerResource(
    name="nginx", description="Web server", ports=["8080:80"],
    assertions=[ContainerRunningAssert(), HealthcheckAssert(url="http://localhost:8080")]
)
# AI might pick nginx OR caddy, but both must pass assertions
```

Run: `clockwork assert`

## Tool Usage

**PydanticAI Tools**: Web search (`duckduckgo_search_tool()`), custom tools
**MCP Servers**: Filesystem, databases (Postgres/SQLite), GitHub, Google Drive

```python
# Web search
FileResource(
    description="Latest AI news", tools=[duckduckgo_search_tool()]
)

# MCP filesystem
filesystem_mcp = MCPServerStdio('npx', args=['-y', '@modelcontextprotocol/server-filesystem', '/path'])
FileResource(description="Code analysis", toolsets=[filesystem_mcp])
```

See `examples/showcase/` for tool integration examples

## Resource Connections

Declare dependencies for AI context, automatic ordering, and cycle detection:

```python
postgres = DockerResource(name="postgres-db", image="postgres:15-alpine", ports=["5432:5432"])
redis = DockerResource(name="redis-cache", image="redis:7-alpine", ports=["6379:6379"])

# AI auto-generates DATABASE_URL, REDIS_URL env vars
api = DockerResource(
    description="FastAPI backend with database and cache",
    ports=["8000:8000"],
    connections=[postgres, redis]  # Deployed after postgres & redis
)
```

**Connection context**: AI sees connected resource details (name, image, ports, env_vars, networks)
**Topological sort**: Automatic dependency ordering (O(V+E))
**Cycle detection**: Prevents circular dependencies before deployment

See `examples/connected-services/`

## Configuration

`.env` file (Pydantic Settings):

```bash
# Local (LM Studio)
CW_API_KEY=lm-studio
CW_MODEL=local-model
CW_BASE_URL=http://localhost:1234/v1

# Cloud (OpenRouter)
CW_API_KEY=your-key
CW_MODEL=meta-llama/llama-4-scout:free
CW_BASE_URL=https://openrouter.ai/api/v1
```

**Override**: CLI flags > env vars > .env > defaults

**Models**: LM Studio (local), OpenRouter free/paid (cloud). Must support tool calls.
**Recommended**: `meta-llama/llama-4-scout:free`, `openai/gpt-4o-mini`

**Output**: `.clockwork/state/` (Pulumi state files)

## Project Structure

```text
clockwork/
├── clockwork/          # Core (resources, completer, compiler, cli, settings)
├── examples/          # showcase (all features), connected-services (real-world)
├── tests/
└── pyproject.toml
```

## Development

### Adding Resources

1. Create class in `clockwork/resources/` with `needs_completion()` and `to_pulumi()`
2. Export in `__init__.py`
3. Add tests in `tests/`
4. Create example in `examples/`

**Note**: Uses PydanticAI Tool Output mode for structured data generation. Resources return Pulumi Resource objects from `to_pulumi()` method.

### Testing

```bash
uv run pytest tests/ -v
uv run pytest tests/test_resources.py -v  # Specific file
```

## Code Guidelines

**Style**: Google Python Style Guide
**Key**: Imports (stdlib→third-party→local), naming (`snake_case`, `CapWords`), type hints, docstrings (Args/Returns/Raises)
**Settings**: Use `get_settings()`, never `os.getenv()` or hardcoded values
**API Docs**: Context7 MCP server first, then WebFetch/WebSearch
**Python Packages**: ALWAYS use Context7 MCP server to check API reference before making code changes involving Python packages (e.g., PydanticAI, Pulumi, Pydantic). Use `resolve-library-id` then `get-library-docs` to get current API documentation.
**Pulumi Patterns**: Use native providers (pulumi-docker, pulumi-command) and custom dynamic providers for special cases

## Cleanup

```bash
clockwork destroy  # Removes all deployed resources
```
