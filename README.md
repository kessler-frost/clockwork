# Clockwork

**Factory for intelligent declarative infrastructure tasks.**

Python-first infrastructure automation with AI-powered artifact generation and PyInfra deployment.

[![Version](https://img.shields.io/badge/version-0.2.0-blue)](./pyproject.toml)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue)](./pyproject.toml)
[![Deploy](https://img.shields.io/badge/deploy-PyInfra-orange)](https://pyinfra.com)

## Overview

Clockwork is a **factory for intelligent declarative infrastructure tasks**. You define what you want in **pure Python** using Pydantic models, then Clockwork:

1. **AI generates** dynamic content/artifacts
2. **Templates compile** to PyInfra operations
3. **PyInfra deploys** your infrastructure

**The factory metaphor**: You provide the blueprint (Pydantic resources) → Factory manufactures artifacts (AI generation) → Assembly line puts it together (PyInfra deployment).

No custom DSL. No complex configuration. Just Python.

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
CW_OPENROUTER_API_KEY=your-key-here
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

# Generate artifacts without deploying
uv run clockwork generate

# Validate deployed resources
uv run clockwork assert

# Destroy deployed resources
uv run clockwork destroy

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
    ports=["80:80"],
    assertions=[
        ContainerRunningAssert(),
        PortAccessibleAssert(port=80),
        HealthcheckAssert(url="http://localhost:80"),
        ResponseTimeAssert(url="http://localhost:80", max_ms=200),
    ]
)
```

### Natural Language Assertions

AI-generated and cached:

```python
nginx = AppleContainerResource(
    name="nginx-web",
    ports=["80:80"],
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
# AI Provider (currently OpenRouter - LM Studio and others coming soon)
CW_OPENROUTER_API_KEY=your-api-key-here
CW_OPENROUTER_MODEL=meta-llama/llama-4-scout:free

# Logging
CW_LOG_LEVEL=INFO
```

### Available Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `CW_OPENROUTER_API_KEY` | None | API key (required for now) |
| `CW_OPENROUTER_MODEL` | `meta-llama/llama-4-scout:free` | Model for AI generation |
| `CW_OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` | OpenRouter API endpoint |
| `CW_PYINFRA_OUTPUT_DIR` | `.clockwork/pyinfra` | PyInfra output directory |
| `CW_LOG_LEVEL` | `INFO` | Logging level |

Override via CLI:

```bash
uv run clockwork apply --model "openai/gpt-4o-mini"
```

## Why Clockwork?

- **Pure Python**: No custom DSL, just Pydantic models
- **AI-powered**: Dynamic content generation and intelligent resource suggestions
- **Simple pipeline**: Load → Generate → Compile → Deploy → Validate
- **Pythonic**: Type-safe with full IDE support
- **Type-safe assertions**: Validate deployments with assertion classes

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
