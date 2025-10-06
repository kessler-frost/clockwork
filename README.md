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

**main.py**
```python
from clockwork.resources import FileResource, ArtifactSize

article = FileResource(
    name="article.md",
    description="Write about Conway's Game of Life",
    size=ArtifactSize.MEDIUM,
    directory="output"
)
```

**.env**
```bash
OPENROUTER_API_KEY=your-key-here
```

**Deploy**
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

# Dry run (plan mode)
uv run clockwork plan

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

### DockerServiceResource
Runs Docker containers with optional AI-suggested images.

```python
DockerServiceResource(
    name="web-server",
    description="A lightweight web server for testing and demos",
    ports=["8080:80"]  # Host port 8080 -> Container port 80
)
```

**AI-Powered**: When `image` is not specified, AI suggests appropriate Docker images (e.g., nginx:alpine).

## Configuration

Clockwork uses `.env` files for configuration via Pydantic Settings.

### Create .env File

```bash
# AI Provider (currently OpenRouter - LM Studio and others coming soon)
OPENROUTER_API_KEY=your-api-key-here
OPENROUTER_MODEL=openai/gpt-oss-20b:free

# Logging
LOG_LEVEL=INFO
```

### Available Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `OPENROUTER_API_KEY` | None | API key (required for now) |
| `OPENROUTER_MODEL` | `openai/gpt-oss-20b:free` | Model for AI generation |
| `PYINFRA_OUTPUT_DIR` | `.clockwork/pyinfra` | PyInfra output directory |
| `LOG_LEVEL` | `INFO` | Logging level |

Override via CLI:
```bash
uv run clockwork apply --model "openai/gpt-4o-mini"
```

## Why Clockwork?

- **Pure Python**: No custom DSL, just Pydantic models
- **AI-powered**: Dynamic content generation
- **Simple pipeline**: Load → Generate → Compile → Deploy
- **Pythonic**: Type-safe with full IDE support

## Examples

```bash
# File generation
cd examples/file-generation
uv run clockwork apply
uv run clockwork destroy

# Docker services
cd examples/docker-service
uv run clockwork apply
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
