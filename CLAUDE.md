**Product priority:** Treat Clockwork as a persistent executable representation of user intent: preserve specified intent, reason only over authorized ambiguity, and keep resolution and observed reality traceable to that intent.

# Clockwork Development Guide

**Intelligent, Composable Primitives for Infrastructure in Python.**

## Quick Start

```bash
clockwork --help
uv run pytest tests/
cd examples/composite-resources/simple-webapp && clockwork apply
```

**Platform**: macOS | **Runtime**: Apple Containers

## Prerequisites

**Apple Container CLI**: Clockwork requires the `container` command for Apple Container management.

```bash
# Check if installed
which container

# List available commands
container --help

# Common commands
container list              # List containers
container run <image>       # Run a container
container network create    # Create a network
container rm <id>          # Remove a container
```

**Installation**: The `container` command is available on macOS 26 "Tahoe" (beta) and later. See [Apple's documentation](https://developer.apple.com/documentation/Container) for installation details.

## Architecture

**Flow**: Declare (Pydantic) → Resolve (deps) → Complete (Intelligence) → Compile (Pulumi) → Deploy (Automation API)

## Workbench Frontend Architecture

Before implementing or reviewing Workbench interface code, read:

1. `PRODUCT.md`
2. `docs/design/DESIGN.md`
3. `docs/design/CANVAS.md`
4. `docs/design/INTERACTIONS.md`
5. `docs/design/MOTION.md`
6. `docs/design/ACCESSIBILITY.md`
7. `docs/solutions/design-patterns/clockwork-workbench-prototype-direction.md`

**Central rule:** shadcn owns the component ecosystem, React Flow owns spatial interaction, and Clockwork owns everything semantic.

- React Flow nodes and edges are projections; primitives, relationships, hierarchy, lifecycle, provenance, proposals, desired state, and observed state remain in Clockwork.
- Route meaningful human and agent actions through the same typed Clockwork operations. Canvas callbacks must not become business logic.
- Keep editor history separate from Clockwork evolution.
- Look for an existing `@clockwork` primitive before composing generic shadcn components. Promote recurring semantic interactions into the first-party design system; do not abstract one-off markup.
- Use the shadcn MCP as the external registry-search interface when no existing Clockwork primitive fits. Base UI supplies accessible low-level behavior; Clockwork tokens and components define the finished product.
- Preserve the approved Hybrid Workbench direction: Precision owns the operating shell and spatial grammar; Motion contributes lifecycle/evidence depth and semantic physical feedback.

## Architecture Deep Dive

### Pipeline Stages

1. **Load**: Execute `main.py`, collect `Resource` instances
2. **Resolve Dependencies**: Flatten composites, detect cycles, topological sort
3. **Complete**: Fill missing fields via PydanticAI structured outputs
4. **Compile**: Convert resources to Pulumi program function
5. **Deploy**: Execute via Pulumi Automation API (`stack.up()`)

### Key File Locations

| Component | Location |
|-----------|----------|
| Core Orchestrator | `clockwork/core.py` |
| Resource Completer | `clockwork/resource_completer.py` |
| Pulumi Compiler | `clockwork/pulumi_compiler.py` |
| Resource Base Class | `clockwork/resources/base.py` |
| Connection Types | `clockwork/connections/` |
| Assertions | `clockwork/assertions/` |
| Settings | `clockwork/settings.py` |
| CLI | `clockwork/cli.py` |

### Two-Phase Composite Completion

Composite resources use two-phase completion for system-level reasoning:

**Phase 1: Parent with Children Context**
- Intelligence sees composite description + all child descriptions
- Plans overall architecture and relationships
- Determines compatibility requirements

**Phase 2: Children with Parent Context**
- Each child receives completion with parent context
- Intelligence knows about siblings through parent's context
- Makes coordinated decisions (compatible versions, shared networks)

### Connection Patterns

**Dual-Storage Pattern** (in `Resource` base class):
- `connections: list[dict]` - Serializable context for intelligence
- `_connection_resources: list[Resource]` - Object references for graph traversal

**Connection Context Flow**:
1. Resource A connects to Resource B
2. B's `get_connection_context()` extracts serializable data
3. Context stored in A's `connections` list
4. B stored in A's `_connection_resources` for dependency resolution

### Dependency Resolution Flow

1. **Composite Flattening**: Recursively extract children
2. **Implicit Dependencies**: Parent→child dependencies added
3. **Cycle Detection**: DFS-based detection with clear error messages
4. **Topological Sort**: Order resources so dependencies deploy first

## Intelligence Control Levels

Choose per resource how much intelligence handles:

```python
# Full control - no intelligence
AppleContainerResource(name="nginx", image="nginx:1.25", ports=["8080:80"])

# Hybrid - intelligence fills gaps
AppleContainerResource(description="web server", ports=["8080:80"])

# Fast - intelligence handles everything
AppleContainerResource(description="web server", assertions=[HealthcheckAssert(...)])
```

## Resources

**Containers**: AppleContainerResource (macOS), DockerResource (cross-platform) | **Files**: FileResource | **Other**: GitRepoResource, BlankResource (composition)

All support intelligent completion via `description`.

## Connections

First-class components for resource relationships. Handle complex setup beyond simple dependency ordering.

**Types**: DependencyConnection, DatabaseConnection, NetworkConnection, FileConnection, ServiceMeshConnection

All support intelligent completion via `description`.

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

**Features**: Auto-configuration (connection strings, env vars), setup resources (networks, volumes), validation, intelligent completion, type-safe Pydantic

See `examples/composite-resources/` for connection patterns within composites.

## Composites: `.add()` vs `.connect()`

**`.add()`**: Parent-child composition (atomic lifecycle, 1 Pulumi ComponentResource)
**`.connect()`**: Dependencies (independent lifecycle, N resources)

```python
# Composition - one composite resource
app = BlankResource(name="app", description="Web app").add(
    AppleContainerResource(description="nginx"),
    FileResource(description="config")
)

# Connection - separate resources with dependencies
db = AppleContainerResource(name="db", description="postgres")
api = AppleContainerResource(name="api", description="API").connect(db)
```

**Two-Phase Completion**: Composites complete in 2 phases: (1) parent planning with full context, (2) child completion with parent/sibling awareness

**Child Access**: Use `resource.children["name"]` for post-creation modifications (dict-style API)

See `examples/composite-resources/` for complete examples.

## Assertions

Verify behavior for functional determinism:

**Types**: HealthcheckAssert, PortAccessibleAssert, ContainerRunningAssert, FileExistsAssert, FileContentMatchesAssert

```python
AppleContainerResource(
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
# LM Studio (local) - RECOMMENDED for development
CW_API_KEY=lm-studio
CW_MODEL=qwen/qwen3-30b-a3b
CW_BASE_URL=http://localhost:1234/v1

# OpenRouter (cloud)
CW_API_KEY=your-key
CW_MODEL=meta-llama/llama-4-scout:free
CW_BASE_URL=https://openrouter.ai/api/v1

# Optional
CW_COMPLETION_MAX_RETRIES=3
CW_COMPLETION_TIMEOUT=30
CW_CACHE_ENABLED=true
CW_CACHE_TTL_DAYS=7
CW_PULUMI_CONFIG_PASSPHRASE=clockwork
CW_LOG_LEVEL=INFO
```

### LM Studio Setup (Recommended)

```bash
# 1. Start daemon
lms daemon up

# 2. Load model with tool support (required for Clockwork)
lms load zai-org/glm-4.7-flash --ttl 3600

# 3. Verify model is loaded
lms ps

# 4. Run Clockwork
clockwork show
```

**Auto-Loading**: Clockwork auto-loads models when using `localhost:1234` if not already loaded.

**Model Requirements**: Must support tool calling. Recommended:
- `zai-org/glm-4.7-flash` - Best tool calling (τ²-Bench: 79.5), 40 tok/s on Apple Silicon

**State**: `~/.pulumi/`

## Project Structure

```text
clockwork/
├── clockwork/       # Core
├── examples/        # Examples
├── tests/           # Tests
└── pyproject.toml
```

## Private Local Material

- `.local/` contains private, gitignored working notes; consult it only when relevant to the task.
- Never copy `.local/` content into tracked files, commits, PRs, issues, logs, or external tools without explicit permission.

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
- **Pulumi**: Use native providers (pulumi-command, pulumi providers for Apple ecosystem)
- **Pre-commit**: Always run and fix before finalizing

## Implementation Strategy

**Parallel Agent Execution**: For complex multi-file tasks, leverage multiple agents in parallel for maximum efficiency:

- Launch agents simultaneously in a single message with multiple Task tool calls
- Assign logical domains: core code, examples, tests, documentation
- Example: Removing a feature across the codebase = 4 parallel agents (core, examples, tests, docs)
- Always mention parallel agent strategy in execution plans

**Benefits**: 75%+ faster completion, better separation of concerns, independent progress tracking

## Cleanup

```bash
clockwork destroy  # Remove all deployed resources
```
