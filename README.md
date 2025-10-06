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

- **Pure Python**: No custom DSL, just Pydantic models
- **AI-powered**: Dynamic content generation via OpenRouter
- **Simple pipeline**: Load → Generate → Compile → Deploy
- **Minimal code**: ~700 lines of core logic
- **7 dependencies**: Focused and lightweight
- **Pythonic**: Type-safe with full IDE support

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
