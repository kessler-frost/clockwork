# Clockwork

**Intelligent, Composable Primitives for Infrastructure.**

Build infrastructure using composable primitives in Python - AI handles the parts you find tedious, you control what matters.

[![Version](https://img.shields.io/badge/version-0.3.0-blue)](./pyproject.toml)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue)](./pyproject.toml)
[![Deploy](https://img.shields.io/badge/deploy-Pulumi-blueviolet)](https://pulumi.com)

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

## Quick Start

In your `main.py`:

```python
from clockwork.resources import FileResource

article = FileResource(
    name="article.md",
    description="Write about Conway's Game of Life",
    directory="output"
)
```

Create a `.env` file:

```bash
CW_API_KEY=your-key-here
```

Deploy:

```bash
cd your-project
uv run clockwork apply
```

## Example

```python
from clockwork.resources import FileResource

# AI generates content
article = FileResource(
    name="game_of_life.md",
    description="Write a comprehensive article about Conway's Game of Life",
    directory="scratch"
)

# User provides content
readme = FileResource(
    name="README.md",
    content="# My Project\n\nGenerated with Clockwork!",
    directory="scratch"
)
```

```bash
uv run clockwork apply
```

See [ARCHITECTURE.md](./ARCHITECTURE.md) for how it works.

## CLI

All commands must be run from a directory containing `main.py`:

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

### DockerResource

Runs Docker containers with optional AI-suggested images. Cross-platform support (Mac, Linux, Windows).

```python
DockerResource(
    name="web-server",
    description="A lightweight web server for testing and demos",
    ports=["8080:80"]  # Host port 8080 -> Container port 80
)
```

**AI-Powered**: When `image` is not specified, AI suggests appropriate container images (e.g., nginx:alpine).
**Cross-Platform**: Uses Pulumi Docker provider for universal Docker support.

### AppleContainerResource

Runs Apple Containers with optional AI-suggested images. macOS-specific using Apple Containers CLI.

```python
AppleContainerResource(
    name="web-server",
    description="A lightweight web server for testing and demos",
    ports=["8080:80"]  # Host port 8080 -> Container port 80
)
```

**AI-Powered**: When `image` is not specified, AI suggests appropriate container images (e.g., nginx:alpine).
**macOS Optimized**: Uses Apple's native container runtime for local development.

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

See [CLAUDE.md](./CLAUDE.md) for available assertion classes.

## Composite Resources

**Build reusable groups** of related resources with `BlankResource` - a lightweight container for organizing infrastructure into logical units.

### Why Composite Resources?

Composite resources let you:
- **Group related resources** for organized deployment (e.g., database + cache + API)
- **Create reusable patterns** that can be instantiated multiple times
- **Manage complex stacks** with atomic lifecycle (deploy/destroy together)
- **Build hierarchical structures** by nesting composites

### Quick Example

```python
from clockwork.resources import BlankResource, DockerResource

# Create a composite web application
webapp = BlankResource(
    name="simple-webapp",
    description="Web application with database, cache, and API"
)

# Add resources to the composition
webapp.add(
    DockerResource(
        name="postgres-db",
        image="postgres:15-alpine",
        ports=["5432:5432"]
    ),
    DockerResource(
        name="redis-cache",
        image="redis:7-alpine",
        ports=["6379:6379"]
    ),
    DockerResource(
        name="api-server",
        description="Node.js API server",
        ports=["3000:3000"]
    )
)

# Access children using dict-style syntax
postgres = webapp.children["postgres-db"]
redis = webapp.children["redis-cache"]
api = webapp.children["api-server"]

# Establish dependencies for proper startup order
api.connect(postgres)  # API depends on database
api.connect(redis)     # API depends on cache
```

### Key Concepts

**`.add()` creates compositions** - Resources added to a composite share an atomic lifecycle:
- Deploy together as a logical unit
- Destroy together when the composite is destroyed
- Organized under a single parent in Pulumi's resource hierarchy

**`.connect()` creates dependencies** - Resources have independent lifecycles but explicit ordering:
- Each resource can be deployed/destroyed independently
- Dependencies control deployment order (postgres → redis → api)
- No parent-child relationship in Pulumi's hierarchy

**When to use each**:
- Use `.add()` when resources logically belong together (e.g., all parts of a web app)
- Use `.connect()` when resources are independent but have ordering requirements

### Accessing Children

After adding resources to a composite, access them using the `.children` property with dict-style syntax:

```python
webapp = BlankResource(name="webapp", description="Web app").add(
    DockerResource(name="db", image="postgres:15"),
    DockerResource(name="cache", image="redis:7")
)

# Dict-style access
db = webapp.children["db"]
cache = webapp.children["cache"]

# Safe access (returns None if not found)
maybe_db = webapp.children.get("db")

# Check existence
if "db" in webapp.children:
    webapp.children["db"].ports = ["5432:5432"]

# Iterate over children
for name, resource in webapp.children.items():
    print(f"{name}: {resource.image}")
```

The `.children` property provides a read-only, dict-like interface for accessing child resources by name.

### Examples

See `examples/composite-resources/` directory for complete examples:
- **simple-webapp/** - Basic composition with database, cache, and API
- **nested-composites/** - Hierarchical compositions (frontend + backend)
- **mixed-pattern/** - Combining `.add()` and `.connect()` patterns
- **post-creation-overrides/** - Modifying resources after composition

For detailed documentation on composite resources, see [CLAUDE.md](./CLAUDE.md).

## Configuration

Clockwork uses `.env` files for configuration via Pydantic Settings.

### Create .env File

```bash
# AI Provider (OpenAI-compatible: OpenRouter, LM Studio, Ollama, etc.)
CW_API_KEY=your-api-key-here
CW_MODEL=meta-llama/llama-4-scout:free
CW_BASE_URL=https://openrouter.ai/api/v1

# Logging
CW_LOG_LEVEL=INFO
```

### Available Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `CW_API_KEY` | None | API key (required for cloud models) |
| `CW_MODEL` | `meta-llama/llama-4-scout:free` | Model for AI completion |
| `CW_BASE_URL` | `https://openrouter.ai/api/v1` | API endpoint (OpenRouter, LM Studio, etc.) |
| `CW_LOG_LEVEL` | `INFO` | Logging level |

Override via CLI:

```bash
uv run clockwork apply --model "anthropic/claude-haiku-4.5"
```

## Why Clockwork?

- **Pure Python**: No custom DSL or YAML, just Pydantic models
- **Composable**: Mix and match primitives like building blocks
- **Flexible**: You choose how much AI handles vs how much you specify
- **Intelligent**: AI-powered completion adapts to your needs
- **Functionally Deterministic**: Assertions validate behavior, ensuring reliable outcomes
- **Type-safe**: Full IDE support with Pydantic validation
- **Composite Resources**: Build higher-level abstractions by composing basic resources into reusable groups

## Examples

```bash
# Comprehensive showcase (all features)
cd examples/showcase
uv run clockwork apply
uv run clockwork assert
uv run clockwork destroy

# Connected services (multi-service with dependencies)
cd examples/connected-services
uv run clockwork apply
uv run clockwork assert
uv run clockwork destroy

# Composite resources (grouping and hierarchies)
cd examples/composite-resources/simple-webapp
uv run clockwork apply
uv run clockwork assert
uv run clockwork destroy
```

See `examples/` directory for more details.

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

See [CLAUDE.md](./CLAUDE.md) for development guide.

## Roadmap

See [POTENTIAL_ROADMAP.md](./POTENTIAL_ROADMAP.md) for upcoming features.
