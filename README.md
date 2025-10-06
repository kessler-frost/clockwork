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

# Set OpenRouter API key
export OPENROUTER_API_KEY="your-key-here"

# Run example
uv run clockwork apply examples/file-generation/main.py
```

## Example

**main.py** - Define resources in Python:
```python
from clockwork.resources import FileResource, ArtifactSize

# AI generates content
article = FileResource(
    name="game_of_life.md",
    description="Write a comprehensive article about Conway's Game of Life",
    size=ArtifactSize.MEDIUM,
    path="/tmp/game_of_life.md"
)

# User provides content
readme = FileResource(
    name="README.md",
    content="# My Project\n\nGenerated with Clockwork!",
    path="/tmp/README.md"
)
```

**Deploy it:**
```bash
uv run clockwork apply main.py
```

**What happens:**
1. Clockwork loads your resources from `main.py`
2. AI generates content for `article` (because `content` is not set)
3. Resources compile to PyInfra operations
4. PyInfra creates the files on your system

## Architecture

```
Python Resources → AI Generation → PyInfra Compilation → Deployment
```

**Simple pipeline:**
- **Load**: Execute `main.py`, collect Resource instances
- **Generate**: AI creates content via OpenRouter (only when needed)
- **Compile**: Resources generate PyInfra operation code (templates)
- **Deploy**: PyInfra executes the deployment

See [ARCHITECTURE.md](./ARCHITECTURE.md) for details.

## CLI

```bash
# Full deployment
clockwork apply main.py

# Dry run (plan mode)
clockwork plan main.py

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
    name="article.md",           # filename
    description="About...",      # what AI should write
    size=ArtifactSize.SMALL,    # SMALL | MEDIUM | LARGE
    path="/tmp/article.md",      # where to create
    content=None,                # if set, skips AI
    mode="644"                   # file permissions
)
```

More resource types coming soon (services, databases, etc.).

## Configuration

### OpenRouter API

Required for AI generation:

```bash
export OPENROUTER_API_KEY="your-key"
```

Default model: `openai/gpt-oss-20b:free`

### PyInfra

Clockwork generates PyInfra files in `.clockwork/pyinfra/`:
- `inventory.py` - Target hosts (default: localhost)
- `deploy.py` - Operations to execute

## Development

```bash
# Run tests
uv run pytest tests/ -v

# Run specific test
uv run pytest tests/test_resources.py -v

# Clean up
rm -rf .clockwork/
```

See [CLAUDE.md](./CLAUDE.md) for development guide.

## Project Structure

```
clockwork/
├── clockwork/
│   ├── resources/              # Pydantic resource models
│   │   ├── base.py            # Base Resource class
│   │   └── file.py            # FileResource
│   ├── artifact_generator.py  # AI-powered content generation
│   ├── pyinfra_compiler.py    # PyInfra code generation
│   ├── core.py                # Pipeline orchestrator
│   ├── cli.py                 # CLI interface
│   └── errors.py              # Error classes
├── examples/
│   └── file-generation/       # Example
├── tests/                     # Test suite
└── pyproject.toml            # Dependencies
```

## Why Clockwork?

**Before (v0.1.0):**
- Custom HCL-like DSL
- Complex 3-phase pipeline
- Custom executors and state management
- ~17,000 lines of code
- 13 dependencies

**After (v0.2.0):**
- Pure Python (Pydantic)
- Simple linear pipeline
- PyInfra handles deployment
- ~2,000 lines of code
- 7 dependencies

**85% code reduction. 100% more Pythonic.**

## How It Works

### 1. Define Resources (Python)
```python
from clockwork.resources import FileResource, ArtifactSize

config = FileResource(
    name="config.json",
    description="Generate a JSON config for a web server",
    size=ArtifactSize.SMALL
)
```

### 2. AI Generates Content
Clockwork calls OpenRouter to generate the content:
```json
{
  "server": {
    "port": 8080,
    "host": "0.0.0.0"
  }
}
```

### 3. Compile to PyInfra
Resource generates PyInfra operation:
```python
files.put(
    name="Create config.json",
    src=StringIO("""{"server": {...}}"""),
    dest="/tmp/config.json",
    mode="644"
)
```

### 4. PyInfra Deploys
PyInfra executes the operation and creates the file.

## Examples

See `examples/` directory:

- **file-generation/**: AI-generated and user-provided files

More examples coming soon!

## Requirements

- Python 3.12+
- OpenRouter API key (for AI generation)

## Dependencies

```toml
dependencies = [
    "pydantic>=2.0.0",
    "pydantic-settings>=2.0.0",
    "typer>=0.16.0",
    "rich>=13.0.0",
    "agno>=2.0.4",
    "openai>=1.99.9",
    "pyinfra>=3.0",
]
```

## License

See [LICENSE](./LICENSE) file.

## Contributing

This is v0.2.0 - a complete rewrite. We're starting fresh!

1. Fork the repo
2. Create a feature branch
3. Add tests for your changes
4. Submit a pull request

See [CLAUDE.md](./CLAUDE.md) for development setup.

## Roadmap

- [ ] ServiceResource (systemd services)
- [ ] DatabaseResource (PostgreSQL, MySQL)
- [ ] Remote deployments (SSH, Kubernetes)
- [ ] Resource dependencies
- [ ] Artifact caching
- [ ] Streaming AI output

## Support

- Issues: [GitHub Issues](https://github.com/yourusername/clockwork/issues)
- Docs: [ARCHITECTURE.md](./ARCHITECTURE.md)
- Dev Guide: [CLAUDE.md](./CLAUDE.md)
