# Clockwork

**Factory for intelligent declarative infrastructure tasks.**

Python-first infrastructure automation with AI-powered artifact generation and PyInfra deployment.

[![Version](https://img.shields.io/badge/version-0.2.0-blue)](./pyproject.toml)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue)](./pyproject.toml)
[![AI](https://img.shields.io/badge/AI-OpenRouter-green)](https://openrouter.ai)
[![Deploy](https://img.shields.io/badge/deploy-PyInfra-orange)](https://pyinfra.com)

## Overview

Clockwork is a **factory for intelligent declarative infrastructure tasks**. You define what you want in **pure Python** using Pydantic models, then Clockwork:

1. **AI generates** dynamic content/artifacts (via OpenRouter)
2. **Templates compile** to PyInfra operations
3. **PyInfra deploys** your infrastructure

**The factory metaphor**: You provide the blueprint (Pydantic resources) → Factory manufactures artifacts (AI generation) → Assembly line puts it together (PyInfra deployment).

No custom DSL. No complex configuration. Just Python.

## Quick Start

```bash
# Install
uv add clockwork

# Create .env file with API key
echo "OPENROUTER_API_KEY=your-key-here" > .env

# Run example
uv run clockwork apply examples/file-generation/main.py
```

## Example

```python
from clockwork.resources import FileResource, ArtifactSize

# AI generates content
article = FileResource(
    name="game_of_life.md",
    description="Write a comprehensive article about Conway's Game of Life",
    size=ArtifactSize.MEDIUM,
    directory="examples/scratch"
)

# User provides content
readme = FileResource(
    name="README.md",
    content="# My Project\n\nGenerated with Clockwork!",
    directory="examples/scratch"
)
```

```bash
uv run clockwork apply main.py
```

See [ARCHITECTURE.md](./ARCHITECTURE.md) for how it works.

## CLI

```bash
# Full deployment
clockwork apply main.py

# Dry run (plan mode)
clockwork plan main.py

# Destroy deployed resources
clockwork destroy main.py

# Run interactive demo
clockwork demo --text-only

# Custom model
clockwork apply main.py --model "openai/gpt-4o-mini"

# Show version
clockwork version
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
    name="nginx",
    description="Web server for serving static content",  # AI suggests image
    ports=["80:80"],
    volumes=["data:/usr/share/nginx/html"],
    env_vars={"ENV": "production"},
    networks=["web"]
)
```

**AI-Powered**: When `image` is not specified, AI suggests appropriate Docker images.

## Configuration

Clockwork uses `.env` files for configuration via Pydantic Settings.

### Create .env File

```bash
OPENROUTER_API_KEY=your-api-key-here
OPENROUTER_MODEL=openai/gpt-oss-20b:free
LOG_LEVEL=INFO
```

### Available Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `OPENROUTER_API_KEY` | None | OpenRouter API key (required) |
| `OPENROUTER_MODEL` | `openai/gpt-oss-20b:free` | Model for AI generation |
| `PYINFRA_OUTPUT_DIR` | `.clockwork/pyinfra` | PyInfra output directory |
| `LOG_LEVEL` | `INFO` | Logging level |

Override via CLI:
```bash
clockwork apply main.py --model "openai/gpt-4o-mini"
```

## Why Clockwork?

- **Pure Python**: No custom DSL, just Pydantic models
- **AI-powered**: Dynamic content generation via OpenRouter
- **Simple pipeline**: Load → Generate → Compile → Deploy
- **Pythonic**: Type-safe with full IDE support

## Examples

```bash
# File generation
uv run clockwork apply examples/file-generation/main.py
uv run clockwork destroy examples/file-generation/main.py

# Docker services
uv run clockwork apply examples/docker-service/main.py
uv run clockwork destroy examples/docker-service/main.py
```

See `examples/` directory for more.

## Development

```bash
# Run tests
uv run pytest tests/ -v

# Clean up
rm -rf .clockwork/ examples/scratch/
```

See [CLAUDE.md](./CLAUDE.md) for development guide.

## Roadmap

See [ROADMAP.md](./ROADMAP.md) for upcoming features.
