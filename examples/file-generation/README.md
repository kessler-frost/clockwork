# File Generation Example

This example demonstrates Clockwork's intelligent file orchestration with AI-powered content generation.

## What it does

Creates three files in `scratch/`:

1. **game_of_life.md** - AI-generated article about Conway's Game of Life
2. **clockwork_poem.txt** - AI-generated poem about infrastructure automation
3. **README.md** - User-provided content (no AI generation)

## Run the example

```bash
# Navigate to example directory
cd examples/file-generation

# Deploy
clockwork apply

# Check the results
ls -la scratch/
cat scratch/game_of_life.md

# Clean up
clockwork destroy
```

## How it works

1. **Load**: Clockwork loads resources from `main.py` in current directory
2. **Generate**: AI generates content for resources with `content=None`
3. **Compile**: Resources compile to Pulumi resources (custom dynamic providers)
4. **Deploy**: Pulumi executes the deployment via Automation API
5. **`.clockwork/`** directory created in current directory

## Customization

- Modify descriptions to generate different content
- Add more FileResource instances
- Change `directory` to deploy files elsewhere
- Add custom assertions for file validation
