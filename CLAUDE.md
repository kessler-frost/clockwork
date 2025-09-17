- "I'm using uv in this repo so run the scripts and cli by keeping that in mind"
- "Use uv to run python scripts and python based cli (e.g., 'uv run python script.py', 'uv run clockwork --help')"
- "when generating a plan, keep in mind to allocate spawning separate agents for tasks in the plan that can be parallelized"
- "don't worry about backward's compatibility and fallback mechanisms"
- "Always test whether the demo command is broken or not"

- "Always do cleanup after final testing and demoing is finished"

## Agno 2.0 AI Integration

Clockwork now uses **Agno 2.0** for AI-powered compilation with the following features:

### Key Features
- **Memory Management**: Agents remember successful patterns and optimizations
- **Reasoning Engine**: Step-by-step reasoning for better template selection
- **Structured Outputs**: Native support for typed outputs
- **Exponential Backoff**: Intelligent retry logic with exponential backoff
- **Performance**: 10,000x faster agent instantiation, 50x less memory usage

### Configuration

Use environment variables for all configuration:

- `CLOCKWORK_LM_STUDIO_MODEL`: Model ID (default: `qwen/qwen3-4b-2507`)
- `CLOCKWORK_LM_STUDIO_URL`: LM Studio URL (default: `http://localhost:1234`)
- `CLOCKWORK_USE_AGNO`: Enable/disable AI compilation (default: `true`)

To change the model:
```bash
CLOCKWORK_LM_STUDIO_MODEL="your-model" uv run clockwork demo --text-only
```

Or use a .env file:
```bash
echo "CLOCKWORK_LM_STUDIO_MODEL=your-model" >> .env
uv run clockwork demo --text-only
```

### Breaking Changes from Agno 1.x
- **No backwards compatibility**: All fallback mechanisms removed
- **Required dependencies**: FastAPI now required for workflow support
- **Model defaults**: Changed from `openai/gpt-oss-20b` to `qwen/qwen3-4b-2507`
- **Memory database**: In-memory database automatically created for agent memory

When I ask you to change the model, update the `CLOCKWORK_LM_STUDIO_MODEL` environment variable.