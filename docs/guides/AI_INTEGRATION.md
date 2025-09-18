# AI Integration (DEPRECATED)

⚠️ **This guide is deprecated.** Clockwork has moved to a simplified PyInfra-based architecture
that no longer requires AI integration.

## New Architecture

Clockwork now uses a direct **Parse → Execute** pipeline with PyInfra for infrastructure management:

- No AI or LLM dependencies required
- Direct conversion of `.cw` files to PyInfra operations
- Immediate execution on target infrastructure
- Built-in state management and drift detection

## Migration Guide

If you were using AI-powered compilation:

1. **Remove AI dependencies**: No longer need `agno`, `openai`, or LM Studio
2. **Update configurations**: Remove AI-related environment variables
3. **Use new CLI**: Switch to `uv run clockwork plan|apply` commands
4. **Update .cw files**: Ensure compatibility with PyInfra operations

## New Documentation

See the main documentation for current architecture:

- [README.md](../../README.md) - Getting started with new architecture
- [ARCHITECTURE.md](../../ARCHITECTURE.md) - Technical details
- [CLAUDE.md](../../CLAUDE.md) - Development instructions

## Legacy Support

This AI integration approach is no longer supported. The new PyInfra-based approach provides:

- **Better reliability**: No dependency on external AI services
- **Faster execution**: Direct operation execution without compilation step
- **Easier debugging**: Clear separation between parsing and execution
- **Production ready**: Battle-tested PyInfra execution engine