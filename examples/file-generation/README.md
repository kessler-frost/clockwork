# File Generation Example

This example demonstrates Clockwork's AI-powered file generation capabilities.

## What it does

Creates three files in `examples/scratch/`:
1. **game_of_life.md** - AI-generated article about Conway's Game of Life (MEDIUM size)
2. **clockwork_poem.txt** - AI-generated poem about infrastructure automation (SMALL size)
3. **README.md** - User-provided content (no AI generation)

## Run the example

```bash
# Apply (full deployment)
uv run clockwork apply examples/file-generation/main.py

# Check the results
ls -la examples/scratch/
cat examples/scratch/game_of_life.md

# Clean up
uv run clockwork destroy examples/file-generation/main.py
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
- Change `directory` to deploy files elsewhere
