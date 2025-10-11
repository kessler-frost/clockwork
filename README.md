# Clockwork

**Intelligent Infrastructure Orchestration in Python.**

Define infrastructure as pure Python code with AI-powered intelligence and PyInfra deployment.

[![Version](https://img.shields.io/badge/version-0.2.0-blue)](./pyproject.toml)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue)](./pyproject.toml)
[![Deploy](https://img.shields.io/badge/deploy-PyInfra-orange)](https://pyinfra.com)

## Overview

Clockwork orchestrates infrastructure intelligently using **pure Python**. You define what you want using Pydantic models, then Clockwork:

1. **AI completes** missing fields and configurations
2. **Compiles** to PyInfra operations
3. **Deploys** your infrastructure

**The approach**: Declarative Python resources → Intelligent AI processing → Automated PyInfra deployment.

No custom DSL. No YAML files. Just Python with AI assistance.

## Quick Start

In your `main.py`:

```python
from clockwork.resources import FileResource, ArtifactSize

article = FileResource(
    name="article.md",
    description="Write about Conway's Game of Life",
    size=ArtifactSize.MEDIUM,
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
from clockwork.resources import FileResource, ArtifactSize

# AI generates content
article = FileResource(
    name="game_of_life.md",
    description="Write a comprehensive article about Conway's Game of Life",
    size=ArtifactSize.MEDIUM,
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

# Destroy deployed resources (removes .clockwork directory by default)
uv run clockwork destroy

# Destroy but keep .clockwork directory
uv run clockwork destroy --keep-files

# Custom model
uv run clockwork apply --model "openai/gpt-4o-mini"

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
    size=ArtifactSize.SMALL,    # SMALL | MEDIUM | LARGE
    directory="path/to/dir",     # where to create
    content=None,                # if set, skips AI
    mode="644"                   # file permissions
)
```

### AppleContainerResource

Runs Apple Containers with optional AI-suggested images.

```python
AppleContainerResource(
    name="web-server",
    description="A lightweight web server for testing and demos",
    ports=["8080:80"]  # Host port 8080 -> Container port 80
)
```

**AI-Powered**: When `image` is not specified, AI suggests appropriate container images (e.g., nginx:alpine).

## Assertions

Validate deployed resources with **type-safe assertion classes**:

```python
from clockwork.assertions import (
    HealthcheckAssert,
    PortAccessibleAssert,
    ContainerRunningAssert,
    ResponseTimeAssert,
)

nginx = AppleContainerResource(
    name="nginx-web",
    ports=["8080:80"],
    assertions=[
        ContainerRunningAssert(),
        PortAccessibleAssert(port=8080),
        HealthcheckAssert(url="http://localhost:8080"),
        ResponseTimeAssert(url="http://localhost:8080", max_ms=200),
    ]
)
```

### Natural Language Assertions

AI-generated and cached:

```python
nginx = AppleContainerResource(
    name="nginx-web",
    ports=["8080:80"],
    assertions=[
        "Container uses less than 100MB of memory",
        "Response time is under 200ms",
    ]
)
```

Run assertions:

```bash
uv run clockwork assert
```

See [CLAUDE.md](./CLAUDE.md) for available assertion classes.

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
| `CW_PYINFRA_OUTPUT_DIR` | `.clockwork/pyinfra` | PyInfra output directory |
| `CW_LOG_LEVEL` | `INFO` | Logging level |

Override via CLI:

```bash
uv run clockwork apply --model "openai/gpt-4o-mini"
```

## Why Clockwork?

- **Pure Python**: No custom DSL or YAML, just Pydantic models
- **Intelligent**: AI-powered content generation and resource configuration
- **Orchestrated**: Automated pipeline from definition to deployment
- **Type-safe**: Full IDE support with Pydantic validation
- **Verifiable**: Built-in assertion system for deployment validation

## Examples

```bash
# File generation
cd examples/file-generation
uv run clockwork apply
uv run clockwork assert
uv run clockwork destroy

# Apple Container services
cd examples/apple-container-service
uv run clockwork apply
uv run clockwork assert
uv run clockwork destroy
```

See `examples/` directory for more.

## Development

```bash
# Run tests
uv run pytest tests/ -v

# Clean up
rm -rf .clockwork/ scratch/
```

See [CLAUDE.md](./CLAUDE.md) for development guide.

## Roadmap

See [ROADMAP.md](./ROADMAP.md) for upcoming features.
