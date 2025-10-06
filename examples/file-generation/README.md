# File Generation Example

This example demonstrates Clockwork's AI-powered file generation capabilities.

## What it does

Creates three files in `/tmp/`:
1. **game_of_life.md** - AI-generated article about Conway's Game of Life (MEDIUM size)
2. **clockwork_poem.txt** - AI-generated poem about infrastructure automation (SMALL size)
3. **README.md** - User-provided content (no AI generation)

## Prerequisites

1. OpenRouter API key:
   ```bash
   export OPENROUTER_API_KEY="your-key-here"
   ```

2. Install Clockwork:
   ```bash
   uv add clockwork
   ```

## Run the example

```bash
# Plan mode (dry run)
uv run clockwork plan examples/file-generation/main.py

# Apply (full deployment)
uv run clockwork apply examples/file-generation/main.py
```

## Expected output

```
Clockwork Apply
File: examples/file-generation/main.py
Model: openai/gpt-oss-20b:free

Loaded 3 resources
Generating artifact for: game_of_life.md
Generating artifact for: clockwork_poem.txt
Generated 2 artifacts
Compiled to PyInfra: .clockwork/pyinfra

✓ Deployment successful!
```

## Check the results

```bash
ls -la /tmp/*.md /tmp/*.txt
cat /tmp/game_of_life.md
cat /tmp/clockwork_poem.txt
cat /tmp/README.md
```

## How it works

1. **Load**: Clockwork loads resources from `main.py`
2. **Generate**: AI generates content for resources with `content=None`
3. **Compile**: Resources compile to PyInfra operations (`files.put`)
4. **Deploy**: PyInfra executes the deployment locally

## Customization

- Change `size` to `ArtifactSize.SMALL` or `ArtifactSize.LARGE`
- Modify descriptions to generate different content
- Add more FileResource instances
- Change paths to deploy files elsewhere
