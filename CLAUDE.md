# Clockwork Development Guide

**Factory for intelligent declarative infrastructure tasks.**

## Setup

This project uses `uv` for Python package management:

```bash
# Run CLI
uv run clockwork --help

# Run tests
uv run pytest tests/

# Run example
uv run clockwork apply examples/file-generation/main.py
```

## Architecture

Clockwork is a **factory for intelligent declarative infrastructure tasks** using a simple **Python + PyInfra** architecture:

1. **Declare** (Pydantic models): Users define infrastructure tasks in Python
2. **Generate** (AI via OpenRouter): AI creates dynamic artifacts when needed
3. **Compile** (Templates): Resources generate PyInfra operations
4. **Deploy** (PyInfra): Native PyInfra executes the infrastructure tasks

The "factory" metaphor: You provide the blueprint (Pydantic resources), the factory (Clockwork) intelligently manufactures the artifacts (via AI) and assembles them (via PyInfra).

## Key Configuration

### OpenRouter API (for AI generation)

Set your OpenRouter API key:

```bash
export OPENROUTER_API_KEY="your-key-here"
```

Default model: `openai/gpt-oss-20b:free`

Change model:
```bash
uv run clockwork apply main.py --model "openai/gpt-4o-mini"
```

### PyInfra (for deployment)

PyInfra is installed as a dependency. Clockwork generates PyInfra files in `.clockwork/pyinfra/`:
- `inventory.py` - Target hosts (default: localhost)
- `deploy.py` - Operations to execute

## Project Structure

```
clockwork/
├── clockwork/
│   ├── resources/          # Pydantic resource models
│   │   ├── base.py        # Base Resource class
│   │   └── file.py        # FileResource
│   ├── artifact_generator.py  # AI-powered content generation
│   ├── pyinfra_compiler.py    # Template-based PyInfra code gen
│   ├── core.py               # Main pipeline orchestrator
│   ├── cli.py                # CLI interface
│   └── errors.py             # Error classes
├── examples/
│   └── file-generation/    # Example Python infrastructure
├── tests/                  # Test suite
└── pyproject.toml         # Dependencies
```

## Development Workflow

### Adding a New Resource Type

1. Create a new resource class in `clockwork/resources/`:

```python
from .base import Resource, ArtifactSize
from typing import Optional, Dict, Any

class MyResource(Resource):
    name: str
    # ... your fields

    def needs_artifact_generation(self) -> bool:
        # Return True if AI should generate content
        return self.content is None

    def to_pyinfra_operations(self, artifacts: Dict[str, Any]) -> str:
        # Return PyInfra operation code as string
        return f'''
# Your PyInfra operation
server.shell(
    name="My operation",
    commands=["echo 'hello'"]
)
'''
```

2. Export it in `clockwork/resources/__init__.py`
3. Add tests in `tests/test_resources.py`
4. Create an example in `examples/`

### Testing

Run all tests:
```bash
uv run pytest tests/ -v
```

Run specific test file:
```bash
uv run pytest tests/test_resources.py -v
```

### Demo Command

Test the full pipeline:
```bash
# Set API key
export OPENROUTER_API_KEY="your-key"

# Run example
uv run clockwork apply examples/file-generation/main.py
```

## Code Guidelines

**Follow Google Python Style Guide**: https://google.github.io/styleguide/pyguide.html

Key conventions:
- **Imports**: Group by standard library → third-party → local, alphabetically sorted
- **Naming**: `lowercase_with_underscores` for functions/variables, `CapWords` for classes
- **Type hints**: Use for all public APIs and function signatures
- **Docstrings**: Use triple-double quotes with Args/Returns/Raises sections
- **Settings**: Always use `get_settings()`, never `os.getenv()` or hardcoded defaults
- **Error handling**: Use specific exceptions with meaningful messages

## Important Notes

- **No backwards compatibility**: This is v0.2.0, completely rewritten
- **No fallback mechanisms**: AI generation requires OpenRouter API key
- **Keep it simple**: PyInfra handles all the complex execution logic
- **Test the demo**: Always verify `clockwork apply examples/file-generation/main.py` works

## Cleanup

After testing, clean up generated files:
```bash
rm -rf .clockwork/
rm -f /tmp/*.md /tmp/*.txt
```
