- "I'm using uv in this repo so run the scripts and cli by keeping that in mind"
- "Use uv to run python scripts and python based cli (e.g., 'uv run python script.py', 'uv run clockwork --help')"
- "when generating a plan, keep in mind to allocate spawning separate agents for tasks in the plan that can be parallelized"
- "don't worry about backward's compatibility and fallback mechanisms"
- "Always test whether the demo command is broken or not"

- "Always do cleanup after final testing and demoing is finished"

## LM Studio Configuration

Use environment variables for all configuration:

- `CLOCKWORK_LM_STUDIO_MODEL`: Model ID (default: `openai/gpt-oss-20b`)
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

When I ask you to change the model, update the `CLOCKWORK_LM_STUDIO_MODEL` environment variable.