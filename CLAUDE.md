# Clockwork Development Guide

**Intelligent, Composable Primitives for Infrastructure.**

## Quick Start

```bash
uv run clockwork --help
uv run pytest tests/
cd examples/showcase && uv run clockwork apply
```

**Platform**: macOS, Linux, Windows | **Runtime**: Docker/Apple Containers

## Architecture

**Flow**: Declare (Pydantic) → Resolve (deps) → Complete (AI) → Compile (Pulumi) → Deploy (Automation API)

## AI Control Levels

Choose per resource how much AI handles:

```python
# Full control - no AI
DockerResource(name="nginx", image="nginx:1.25", ports=["8080:80"])

# Hybrid - AI fills gaps
DockerResource(description="web server", ports=["8080:80"])

# Fast - AI handles everything
DockerResource(description="web server", assertions=[HealthcheckAssert(...)])
```

## Resources

**Containers**: DockerResource, AppleContainerResource | **Files**: FileResource | **Other**: GitRepoResource, BlankResource (composition)

All support AI completion via `description`.

## Connections

First-class components for resource relationships. Handle complex setup beyond simple dependency ordering.

**Types**: DependencyConnection, DatabaseConnection, NetworkConnection, FileConnection, ServiceMeshConnection

All support AI completion via `description`.

```python
# Simple dependency (auto-creates DependencyConnection)
api.connect(db)

# Explicit connection type
api.connect(DatabaseConnection(
    to_resource=db,
    schema_file="./schema.sql",
    connection_string_template="postgresql://{user}:{password}@{host}:{port}/{database}",
    username="postgres",
    password="secret",  # pragma: allowlist secret
    database_name="appdb"
))

# Chaining
api.connect(db_conn).connect(cache_conn).connect(network_conn)
```

**Features**: Auto-configuration (connection strings, env vars), setup resources (networks, volumes), validation, AI completion, type-safe Pydantic

See `examples/connections-showcase/` and `examples/connected-services/`

## Composites: `.add()` vs `.connect()`

**`.add()`**: Parent-child composition (atomic lifecycle, 1 Pulumi ComponentResource)
**`.connect()`**: Dependencies (independent lifecycle, N resources)

```python
# Composition - one composite resource
app = BlankResource(name="app", description="Web app").add(
    DockerResource(description="nginx"),
    FileResource(description="config")
)

# Connection - separate resources with dependencies
db = DockerResource(name="db", description="postgres")
api = DockerResource(name="api", description="API").connect(db)
```

**Two-Phase AI**: Composites complete in 2 phases: (1) parent planning with full context, (2) child completion with parent/sibling awareness

**Child Access**: Use `resource.children["name"]` for post-creation modifications (dict-style API)

See `examples/composite-resources/` for complete examples.

## Assertions

Verify behavior for functional determinism:

**Types**: HealthcheckAssert, PortAccessibleAssert, ContainerRunningAssert, FileExistsAssert, FileContentMatchesAssert

```python
DockerResource(
    description="web server",
    assertions=[ContainerRunningAssert(), HealthcheckAssert(url="...")]
)
```

Run: `clockwork assert`

## Tools

**PydanticAI**: `duckduckgo_search_tool()`, custom functions | **MCP Servers**: Filesystem (pre-integrated), manual setup via `MCPServerStdio`

```python
FileResource(description="...", tools=[duckduckgo_search_tool()])
```

## Configuration

`.env` file:

```bash
# LM Studio (local, auto-loads model)
CW_API_KEY=lm-studio
CW_MODEL=qwen/qwen3-coder-30b
CW_BASE_URL=http://localhost:1234/v1

# OpenRouter (cloud)
CW_API_KEY=your-key
CW_MODEL=meta-llama/llama-4-scout:free
CW_BASE_URL=https://openrouter.ai/api/v1

# Optional
CW_COMPLETION_MAX_RETRIES=3
CW_PULUMI_CONFIG_PASSPHRASE=clockwork
CW_LOG_LEVEL=INFO
```

**LM Studio Auto-Loading**: When using `localhost:1234`, Clockwork auto-loads the specified model

**Models**: Must support tool calling. Default: `meta-llama/llama-4-scout:free`. Recommended: `anthropic/claude-haiku-4.5`

**State**: `~/.pulumi/`

## Project Structure

```text
clockwork/
├── clockwork/       # Core
├── examples/        # Examples
├── tests/           # Tests
└── pyproject.toml
```

## Development

**Adding Resources**:
1. Create class in `clockwork/resources/` with `needs_completion()` and `to_pulumi()`
2. Export in `__init__.py`
3. Add tests, create example

**Testing**: `uv run pytest tests/ -v`

## Code Guidelines

- **Style**: Google Python Style Guide | **Imports**: stdlib → third-party → local
- **Settings**: Use `get_settings()`, never `os.getenv()`
- **API Docs**: Context7 MCP first, then WebFetch/WebSearch
- **Python Packages**: Context7 MCP (`resolve-library-id` + `get-library-docs`)
- **Pulumi**: Use native providers (pulumi-docker, pulumi-command)
- **Pre-commit**: Always run and fix before finalizing

## Cleanup

```bash
clockwork destroy  # Remove all deployed resources
```
