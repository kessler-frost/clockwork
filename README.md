# Clockwork

**Intelligent, Composable Primitives for Infrastructure.**

Build infrastructure using composable primitives in Python - AI handles the parts you find tedious, you control what matters.

[![Version](https://img.shields.io/badge/version-0.3.0-blue)](./pyproject.toml)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue)](./pyproject.toml)
[![Deploy](https://img.shields.io/badge/deploy-Pulumi-blueviolet)](https://pulumi.com)
[![License](https://img.shields.io/badge/license-Apache%202.0-green)](./LICENSE)

## Build Infrastructure Your Way

Clockwork provides intelligent primitives that adapt to how you want to work.

**The insight:** What's tedious is personal.

- Some people love writing Docker configs, others just want containers running
- Some enjoy crafting nginx rules, others prefer describing requirements
- Some care about specific image versions, others just need something that works

**Your choice:**

- **Specify everything** → Full control, zero AI
- **Specify key details** → AI fills gaps
- **Describe what you need** → AI handles implementation

Clockwork gives you flexibility to work how you prefer, on what you prefer.

## How It Works

Same primitive, different levels of control - you choose per resource:

**Full control** (No AI):

```python
nginx = DockerResource(
    description="Nginx web server",
    name="my-nginx",
    image="nginx:1.25-alpine",
    ports=["8080:80"],
    volumes=["/configs:/etc/nginx"]
)
# You specified everything - AI does nothing
```

**Hybrid** (AI assists):

```python
nginx = DockerResource(
    description="web server with caching enabled",
    ports=["8080:80"]  # You care about the port
    # AI picks image, generates config with caching
)
```

**Fast** (AI handles implementation):

```python
nginx = DockerResource(
    description="web server for static files",
    assertions=[HealthcheckAssert(url="http://localhost:8080")]
)
# AI handles everything, assertions verify behavior
```

No custom DSL. No YAML files. Just Python with adjustable AI assistance.

## Why Clockwork?

- **Pure Python**: No custom DSL or YAML, just Pydantic models
- **Composable**: Mix and match primitives like building blocks
- **Flexible**: You choose how much AI handles vs how much you specify
- **Intelligent**: AI-powered completion adapts to your needs
- **Functionally Deterministic**: Assertions validate behavior, ensuring reliable outcomes
- **Type-safe**: Full IDE support with Pydantic validation
- **Composite Resources**: Build higher-level abstractions by composing basic resources into reusable groups

## Prerequisites

Before getting started, ensure you have:

- **Python 3.12 or higher** - Required for modern Python features
- **uv package manager** - Fast Python package installer and resolver
- **Git** - For cloning the repository
- **Docker** (Linux/Windows) or **Apple Containers** (macOS) - For container resources

## Installation

### Install uv

First, install the uv package manager if you don't have it:

```bash
# Install uv package manager
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Install Clockwork

Since Clockwork is not yet published to PyPI, clone and install directly from GitHub:

```bash
# Clone the repository
git clone https://github.com/kessler-frost/clockwork.git
cd clockwork

# Install dependencies
uv sync

# Create your main.py and start building (see Quick Start below)
```

## Quick Start

In your `main.py`:

```python
from clockwork.resources import FileResource

article = FileResource(
    name="article.md",
    description="Write about the Fibonacci sequence and its mathematical properties",
    directory="output"
)
```

Create a `.env` file:

```bash
# Get a free API key from OpenRouter: https://openrouter.ai/keys
# Or use LM Studio locally (set CW_BASE_URL=http://localhost:1234/v1, no key needed)
CW_API_KEY=your-api-key-here
CW_MODEL=meta-llama/llama-4-scout:free  # Free tier model

# See Configuration section below for all options
```

Deploy:

```bash
uv run clockwork apply
```

## Example

```python
from clockwork.resources import FileResource, DockerResource
from clockwork.assertions import HealthcheckAssert

# AI-generated content
article = FileResource(
    name="game_of_life.md",
    description="Write about Conway's Game of Life",
    directory="scratch"
)

# User-provided content
readme = FileResource(
    name="README.md",
    content="# My Project\n\nGenerated with Clockwork!",
    directory="scratch"
)

# Container with health check
nginx = DockerResource(
    description="web server for static files",
    ports=["8080:80"],
    assertions=[HealthcheckAssert(url="http://localhost:8080")]
)
```

```bash
uv run clockwork apply
```

### Next Steps

After your first deployment:

1. **Explore other resources**: Try `DockerResource`, `AppleContainerResource`, `GitRepoResource`
2. **Add assertions**: Validate your deployments with `HealthcheckAssert`, `PortAccessibleAssert`
3. **Connect resources**: Use `.connect()` to link services with automatic configuration
4. **Build composites**: Group related resources with `BlankResource` for reusable patterns
5. **Check examples**: Browse `examples/` directory for real-world patterns

Run `uv run clockwork --help` to see all available commands.

## Resources

Currently available:

### FileResource

Creates files with optional AI-generated content.

```python
FileResource(
    name="article.md",
    description="About...",      # what AI should write
    directory="path/to/dir",     # where to create
    content=None,                # if set, skips AI
    mode="644"                   # file permissions
)
```

### Container Resources

Clockwork provides two container resource types:

| Resource | Platform | Runtime |
|----------|----------|---------|
| `DockerResource` | Cross-platform (macOS, Linux, Windows) | Docker Engine via Pulumi provider |
| `AppleContainerResource` | macOS only | Apple Containers CLI (native runtime) |

Both support AI-powered image suggestion when `image` is not specified (e.g., nginx:alpine, redis:alpine).

**Example Usage** (identical syntax for both):

```python
# Use DockerResource or AppleContainerResource - syntax is identical
resource = DockerResource(
    name="web-server",
    description="A lightweight web server for testing and demos",
    ports=["8080:80"]  # Host port 8080 -> Container port 80
)
```

**When to use which:**
- Use `DockerResource` for cross-platform compatibility or when deploying to Linux/Windows
- Use `AppleContainerResource` for macOS-optimized local development with Apple's native container runtime

### GitRepoResource

Clones and manages Git repositories with optional AI-suggested repository URLs. Automatically clones repositories and keeps them updated.

```python
GitRepoResource(
    name="fastapi-repo",
    description="FastAPI Python web framework repository",
    dest="./repos/fastapi"  # Where to clone
)
```

**AI-Powered**: When `repo_url` is not specified, AI suggests appropriate repository URLs (e.g., official GitHub repositories).
**Smart Defaults**: AI picks sensible values for branch (main/master) and destination directory if not specified.

**Key Properties**:
- `repo_url`: Git repository URL (e.g., `https://github.com/tiangolo/fastapi.git`)
- `dest`: Destination directory for cloning (e.g., `./repos/fastapi`)
- `branch`: Git branch to checkout (e.g., `main`, `master`, `develop`)
- `pull`: Update repository if it already exists (default: `True`)

**Use Cases**:
- Clone dependencies or third-party libraries
- Set up project scaffolding from template repositories
- Download configuration or data repositories
- Maintain local mirrors of remote repositories

## Assertions

Validate deployed resources with **type-safe assertion classes**:

```python
from clockwork.assertions import (
    HealthcheckAssert,
    PortAccessibleAssert,
    ContainerRunningAssert,
)

nginx = AppleContainerResource(
    name="nginx-web",
    ports=["8080:80"],
    assertions=[
        ContainerRunningAssert(),
        PortAccessibleAssert(port=8080),
        HealthcheckAssert(url="http://localhost:8080"),
    ]
)
```

Run assertions:

```bash
uv run clockwork assert
```

**Available Assertion Classes**:

- **HTTP/Network**: `HealthcheckAssert`, `PortAccessibleAssert`
- **Container**: `ContainerRunningAssert`
- **File**: `FileExistsAssert`, `FileContentMatchesAssert`

All assertions are type-safe, Pydantic-based validators with no AI costs.

## CLI

All commands must be run from the clockwork directory where your `main.py` is located.

**Discovering Commands**: Use `--help` to explore available commands and options:

```bash
# Show all available commands
uv run clockwork --help

# Show options for a specific command
uv run clockwork apply --help
uv run clockwork destroy --help
uv run clockwork assert --help
```

**Available Commands**:

```bash
# Full deployment
uv run clockwork apply

# Plan resources without deploying
uv run clockwork plan

# Validate deployed resources
uv run clockwork assert

# Destroy deployed resources (removes working directories by default)
uv run clockwork destroy

# Destroy but keep working directories created by resources
uv run clockwork destroy --keep-files

# Custom model
uv run clockwork apply --model "anthropic/claude-haiku-4.5"

# Show version
uv run clockwork version
```

## Resource Connections

Declare dependencies between resources for proper deployment ordering and AI-powered auto-configuration.

**How it works:**

```python
from clockwork.resources import DockerResource

# Create independent resources
postgres = DockerResource(
    name="postgres-db",
    description="PostgreSQL database",
    image="postgres:15-alpine",
    ports=["5432:5432"]
)

redis = DockerResource(
    name="redis-cache",
    description="Redis cache",
    image="redis:7-alpine",
    ports=["6379:6379"]
)

# Connect API to dependencies
api = DockerResource(
    name="api-server",
    description="FastAPI backend with database and cache",
    ports=["8000:8000"]
).connect(postgres, redis)

# Result: postgres → redis → api (deployment order)
# AI auto-generates DATABASE_URL and REDIS_URL environment variables
```

**Benefits:**

1. **Automatic Deployment Ordering**: Resources deploy in dependency order (topological sort)
2. **AI Context Awareness**: Connected resources share context (name, image, ports, env vars)
3. **Auto-Configuration**: AI generates connection strings, URLs, and configuration
4. **Cycle Detection**: Prevents circular dependencies before deployment
5. **Independent Lifecycles**: Each resource can be updated/destroyed separately

See `examples/connected-services/` for complete examples.

## Composite Resources

**Build reusable groups** of related resources with `BlankResource` - organize infrastructure into logical units with atomic lifecycle management.

### Basic Usage

```python
from clockwork.resources import BlankResource, DockerResource

# Create a composite web application
webapp = BlankResource(
    name="webapp",
    description="Web application with database and cache"
).add(
    DockerResource(name="db", image="postgres:15-alpine", ports=["5432:5432"]),
    DockerResource(name="cache", image="redis:7-alpine", ports=["6379:6379"]),
    DockerResource(name="api", description="API server", ports=["8000:8000"])
)

# Access and modify children
webapp.children["db"].ports = ["5433:5432"]
webapp.children["api"].connect(webapp.children["db"], webapp.children["cache"])
```

### Key Concepts

**`.add()` - Composition** (atomic lifecycle):
- Resources deploy/destroy together as one unit
- Organized under single parent in Pulumi hierarchy
- Use for: resources that belong together (app + config + db)

**`.connect()` - Dependencies** (independent lifecycle):
- Resources deploy in dependency order
- AI receives context for auto-configuration
- See **Resource Connections** section above for details

**Accessing Children**:

```python
# Dict-style access
db = webapp.children["db"]

# Safe access
maybe_cache = webapp.children.get("cache")

# Iterate
for name, resource in webapp.children.items():
    print(f"{name}: {resource.image}")
```

### Examples

See `examples/composite-resources/` for detailed examples:
- **simple-webapp/** - Basic composition patterns
- **nested-composites/** - Hierarchical structures
- **mixed-pattern/** - Combining `.add()` and `.connect()`
- **post-creation-overrides/** - Modifying after composition

## Configuration

Clockwork uses `.env` files for configuration via Pydantic Settings.

For a minimal setup, see the Quick Start section above. For all available options, see the table below.

### Available Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `CW_API_KEY` | None | API key (required for cloud models) |
| `CW_MODEL` | `meta-llama/llama-4-scout:free` | Model for AI completion (default, free). Recommended upgrade: `anthropic/claude-haiku-4.5` for better quality |
| `CW_BASE_URL` | `https://openrouter.ai/api/v1` | API endpoint (OpenRouter, LM Studio, etc.) |
| `CW_COMPLETION_MAX_RETRIES` | `3` | Maximum retry attempts for AI resource completion |
| `CW_PULUMI_CONFIG_PASSPHRASE` | `clockwork` | Pulumi passphrase for state encryption (also accepts `PULUMI_CONFIG_PASSPHRASE`) |
| `CW_LOG_LEVEL` | `INFO` | Logging level |

Override via CLI:

```bash
uv run clockwork apply --model "anthropic/claude-haiku-4.5"
```

### Important Notes

**State Management**: Pulumi stores state in `~/.pulumi/` directory (user's home directory) when using the Automation API. This state tracks all deployed resources and their configurations.

**Model Requirements**: AI models must support tool calling (function calling). Most modern models from OpenRouter, OpenAI, Anthropic, and local models served via LM Studio support this feature.

**Platform-Specific Resources**:
- **AppleContainerResource**: macOS only - requires Apple Containers CLI
- **DockerResource**: Cross-platform - works on macOS, Linux, and Windows

## Getting Help

- **Questions & Discussions**: [GitHub Discussions](https://github.com/kessler-frost/clockwork/discussions) - Ask questions, share ideas, and discuss best practices
- **Bug Reports & Feature Requests**: [GitHub Issues](https://github.com/kessler-frost/clockwork/issues) - Report bugs or request new features
- **Technical Deep Dive**: [ARCHITECTURE.md](./ARCHITECTURE.md) - Implementation details and design decisions
- **Contributing**: See Development section below for setup instructions

## Examples

Make sure you're in the clockwork directory, then explore these examples:

```bash
# Comprehensive showcase - Demonstrates all Clockwork features
# Includes: FileResource, DockerResource, AppleContainerResource, GitRepoResource, assertions, connections
cd examples/showcase
uv run clockwork apply
uv run clockwork assert
uv run clockwork destroy

# Connected services - Multi-service architecture with dependencies
# Shows: Resource connections, AI auto-configuration, deployment ordering
cd examples/connected-services
uv run clockwork apply
uv run clockwork assert
uv run clockwork destroy

# Composite resources - Grouping and hierarchical structures
# Demonstrates: BlankResource, .add() composition, nested composites
cd examples/composite-resources/simple-webapp
uv run clockwork apply
uv run clockwork assert
uv run clockwork destroy
```

See `examples/` directory for more details.

## Architecture

For a comprehensive technical deep dive into Clockwork's implementation, design decisions, and internal architecture, see [ARCHITECTURE.md](./ARCHITECTURE.md).

This document covers the complete flow: Declare (Pydantic) → Resolve (dependencies) → Complete (AI) → Compile (Pulumi) → Deploy (Automation API).

## Development

```bash
# Install dependencies including dev tools
uv sync --all-groups

# Install pre-commit hooks
uv run pre-commit install

# Run pre-commit on all files (optional)
uv run pre-commit run --all-files

# Run tests
uv run pytest tests/ -v

# Lint and format code
uv run ruff check --fix .
uv run ruff format .

# Clean up example outputs
rm -rf scratch/
```

### Pre-commit Hooks

This project uses [pre-commit](https://pre-commit.com/) with [Ruff](https://docs.astral.sh/ruff/) for code quality:

- **Ruff linter**: Checks code for errors, style issues, and import sorting
- **Ruff formatter**: Formats code according to Google Python Style Guide
- **Standard hooks**: Trailing whitespace, EOF fixing, YAML/TOML validation

After installation, hooks run automatically on `git commit`. To run manually:

```bash
uv run pre-commit run --all-files
```

## Roadmap

See [POTENTIAL_ROADMAP.md](./POTENTIAL_ROADMAP.md) for upcoming features.
