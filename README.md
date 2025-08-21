# Clockwork

Factory for intelligent declarative tasks with AI-powered compiler.

## Quick Start

```bash
# Install
uv add clockwork

# Run example  
uv run clockwork demo --text-only --output /tmp/test
```

## Core Concepts

Three-phase pipeline:

1. **Intake** - Parse `.cw` configuration files
2. **Assembly** - Plan actions and resolve dependencies  
3. **Forge** - Generate and execute artifacts with AI assistance

## CLI Usage

```bash
# Generate demo
uv run clockwork demo --text-only --output /tmp/test

# Build project
uv run clockwork build /tmp/test

# Apply changes
uv run clockwork apply /tmp/test --auto-approve
```

## Configuration

Set environment variables:

- `CLOCKWORK_LM_STUDIO_URL`: LM Studio URL (default: http://localhost:1234)
- `CLOCKWORK_LM_STUDIO_MODEL`: Model to use  
- `CLOCKWORK_USE_AGNO`: Enable AI integration (default: true)