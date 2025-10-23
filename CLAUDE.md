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
    description="Nginx web server",
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
**Files**: FileResource
**Other**: GitRepoResource

All support AI completion with `description` field.

## Composite Resources

Composite resources enable building complex infrastructure from simpler components. **Philosophy**: All resources are composites - some are just atomic (0 children).

**Benefits**:
- **Organization**: Group related resources into logical units
- **Reusability**: Define once, instantiate many times
- **Abstraction**: Hide implementation details, expose clean interfaces

### `.add()` vs `.connect()` - Critical Distinction

Understanding the difference between composition and connection is fundamental to Clockwork:

| Aspect | `.add()` | `.connect()` |
|--------|----------|--------------|
| **Relationship** | Parent-child composition | Dependency/reference |
| **Resource Count** | 1 composite resource | N independent resources |
| **Lifecycle** | Atomic (all children deploy/destroy together) | Independent (each resource has own lifecycle) |
| **Pulumi Type** | ComponentResource with children | Separate resources with dependencies |
| **Naming** | Children namespaced under parent | Each resource has own name |
| **Use Case** | "Contains" - part of the whole | "Depends on" - needs to reference |

**When to use `.add()`**:
- Resources that belong together conceptually (e.g., app + config + volume)
- You want atomic lifecycle management
- Building reusable templates

**When to use `.connect()`**:
- Resources that reference each other (e.g., API depends on database)
- Independent lifecycles (database may outlive API)
- Need AI to understand dependencies for auto-configuration

```python
# Composition (.add) - One "web-app" resource with 3 children
web_app = BlankResource(name="web-app", description="Complete web application")
web_app.add(
    DockerResource(description="nginx reverse proxy", ports=["80:80"]),
    FileResource(description="nginx configuration"),
    DockerResource(description="app container", ports=["8080:8080"])
)

# Connection (.connect) - 3 separate resources with dependencies
db = DockerResource(name="postgres", description="database", ports=["5432:5432"])
cache = DockerResource(name="redis", description="cache", ports=["6379:6379"])
api = DockerResource(
    name="api",
    description="API server",
    ports=["8000:8000"]
).connect(db, cache)  # API depends on db + cache
```

### Creating Composite Resources

Use `BlankResource` for pure composition (no implementation, just organization):

```python
from clockwork import BlankResource, DockerResource, FileResource

# Simple composite
monitoring = BlankResource(
    name="monitoring-stack",
    description="Complete monitoring solution"
).add(
    DockerResource(description="Prometheus metrics collector", ports=["9090:9090"]),
    DockerResource(description="Grafana dashboard", ports=["3000:3000"]),
    FileResource(description="Prometheus configuration")
)

# Chainable API - mix .add() and .connect()
app = BlankResource(name="app", description="Full application stack")
app.add(
    DockerResource(description="application server", ports=["8080:8080"]),
    FileResource(description="app config")
).connect(monitoring)  # App depends on monitoring

# Nested composites - composites can contain composites
full_system = BlankResource(name="system", description="Complete system")
full_system.add(monitoring, app)
```

### Two-Phase AI Completion

Composites leverage a sophisticated two-phase completion process:

**Phase 1: Composite-Level Planning**
- AI sees the composite as a whole with all child descriptions
- Plans how children should work together
- Determines overall architecture and relationships

**Phase 2: Child Completion**
- Each child receives completion with parent context
- AI knows about siblings and parent requirements
- Can make coordinated decisions

```python
# The AI sees this holistically
web_service = BlankResource(
    name="web-service",
    description="Production web service with caching and database"
).add(
    DockerResource(description="web server"),
    DockerResource(description="cache layer"),
    DockerResource(description="database")
)

# Phase 1: AI plans overall architecture
# - Decides web server should be nginx
# - Cache should be redis
# - Database should be postgres
# - Plans how they interconnect

# Phase 2: AI completes each child
# - Web server gets nginx config that connects to cache/db
# - Cache gets appropriate memory settings
# - Database gets appropriate volume mounts
# - All receive coordinated network configuration
```

**Benefits**:
- **Coherent systems**: Children are configured to work together
- **Smart defaults**: AI picks compatible versions and configurations
- **Context awareness**: Each child knows its role in the larger system

### Post-Creation Field Access

After composition, you can access and modify child properties using the `.children` property, which provides dict-style access:

```python
stack = BlankResource(name="app-stack", description="Application with database").add(
    DockerResource(description="PostgreSQL database", name="db"),
    DockerResource(description="FastAPI application", name="api")
)

# Dict-style access to children by name
stack.children["db"].ports = ["5433:5432"]  # Change postgres port
stack.children["api"].env_vars = {"DEBUG": "true"}  # Add env var

# Safe access with default
api = stack.children.get("api")  # Returns None if not found
api = stack.children.get("api", fallback_resource)  # With default

# Check if child exists
if "db" in stack.children:
    stack.children["db"].restart_policy = "always"

# Iterate over children
for name in stack.children.keys():
    print(f"Child: {name}")

for resource in stack.children.values():
    print(f"Resource: {resource.name}")

for name, resource in stack.children.items():
    print(f"{name}: {resource.name}")
```

**The `.children` property returns a ChildrenCollection** (implements `Mapping` protocol):
- **Dict-style access**: `children["name"]` - raises `KeyError` if not found
- **Safe access**: `children.get("name", default)` - returns default if not found
- **Membership test**: `"name" in children` - check if child exists
- **Iteration**: `children.keys()`, `children.values()`, `children.items()`
- **Read-only**: You can access and modify children's properties, but not add/remove children

**Useful for**:
- Overriding AI decisions
- Dynamic configuration based on environment
- Testing variations
- Progressive enhancement

**Best practices**:
- Access children after initial composition
- Use for environment-specific overrides
- Document why you're overriding AI decisions
- Consider if the description should be more specific instead

### Pulumi Integration

Composites compile to Pulumi ComponentResource with proper parent-child hierarchy:

```python
web_app = BlankResource(name="my-app", description="Web application").add(
    DockerResource(description="nginx", name="web"),
    DockerResource(description="postgres", name="db")
)

# Compiles to:
# - ComponentResource: my-app
#   - Container: my-app-web (namespaced under parent)
#   - Container: my-app-db (namespaced under parent)
```

**Pulumi benefits**:
- **Hierarchical state**: Resources organized in logical groups
- **Resource naming**: Children automatically namespaced
- **Dependency tracking**: Pulumi knows parent-child relationships
- **Atomic operations**: Destroy parent removes all children
- **State visualization**: `pulumi stack graph` shows hierarchy

### Examples

See `examples/composite-resources/` for complete examples:

- **`basic_composite.py`**: Simple composite with BlankResource
- **`nested_composites.py`**: Composites containing composites
- **`web_app_composite.py`**: Real-world web application (nginx + app + db)
- **`monitoring_stack.py`**: Prometheus + Grafana + Alertmanager
- **`field_access.py`**: Modifying children post-composition

## Assertions: Functional Determinism

Clockwork achieves **functional determinism** through validation - assertions verify behavior, not implementation.

**Philosophy**: Same requirements → validated equivalent results
- AI can choose optimal implementations
- Outcomes are verified, not assumed
- Flexibility without unpredictability

**Type-safe validation** (Pydantic-based, no AI costs):

**HTTP/Network**: HealthcheckAssert, PortAccessibleAssert
**Container**: ContainerRunningAssert
**File**: FileExistsAssert, FileContentMatchesAssert

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
postgres = DockerResource(description="PostgreSQL database", name="postgres-db", image="postgres:15-alpine", ports=["5432:5432"])
redis = DockerResource(description="Redis cache", name="redis-cache", image="redis:7-alpine", ports=["6379:6379"])

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
**Recommended**: `meta-llama/llama-4-scout:free`, `anthropic/claude-haiku-4.5`

**State Management**: Pulumi stores state in `.pulumi/` directory (current working directory)

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
- always run pre-commit hooks after you've made final changes and fix things accordingly
