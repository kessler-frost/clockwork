# Git Repository Cloning Example

Demonstrates AI-powered Git repository cloning using `GitRepoResource`. The AI finds repository URLs and picks appropriate destination paths based on descriptions.

## What This Example Creates

This example clones:
- **FastAPI repository** - Python web framework (AI finds GitHub URL)
- **Flask repository** - Python web framework (AI finds GitHub URL)
- **Awesome Python** - Curated Python resources (explicit destination path)

## Prerequisites

- **Git** installed
- **Internet connection** (for cloning repositories)
- **API key** configured in `.env` file (for cloud AI models)

## Usage

### 1. Set Up API Key

Create a `.env` file in the project root:
```bash
cd /Users/fimbulwinter/dev/clockwork
echo "CW_API_KEY=your-api-key-here" > .env
```

### 2. Deploy

```bash
cd examples/git-repo
uv run clockwork apply
```

This will:
- ✅ Clone FastAPI repository (AI finds: https://github.com/fastapi/fastapi)
- ✅ Clone Flask repository (AI finds: https://github.com/pallets/flask)
- ✅ Clone Awesome Python (AI finds: https://github.com/vinta/awesome-python)

**Note**: Initial clone may take 2-5 minutes depending on repository sizes and network speed.

### 3. Verify Cloned Repositories

```bash
# List cloned repositories
ls -la scratch/

# Check repository contents
ls -la scratch/fastapi/
ls -la scratch/flask/
ls -la scratch/awesome/

# Verify git repositories
cd scratch/fastapi && git remote -v
cd scratch/flask && git remote -v
cd scratch/awesome && git remote -v
```

## Cleanup

```bash
cd examples/git-repo
uv run clockwork destroy
```

This will:
- ✅ Remove all cloned repositories
- ✅ Remove the scratch directory
- ✅ Remove the .clockwork directory

## What This Demonstrates

1. **AI Repository Discovery** - AI finds correct GitHub URLs from descriptions
2. **Smart Path Selection** - AI picks appropriate destination paths
3. **Branch Detection** - AI selects default branch (main/master)
4. **Declarative Cloning** - Describe what you want, Clockwork clones it

## Resources Created

| Resource | Description | AI Completion |
|----------|-------------|---------------|
| fastapi_repo | FastAPI framework | AI finds repo URL, picks dest/branch |
| flask_repo | Flask framework | AI finds repo URL, picks dest/branch |
| awesome_python | Awesome Python list | Explicit dest, AI finds URL/branch |

## Troubleshooting

### Clone Fails

**Issue**: `fatal: unable to access 'https://github.com/...': Could not resolve host`

**Solution**: Check internet connection and retry:
```bash
curl -I https://github.com
uv run clockwork destroy
uv run clockwork apply
```

### Directory Already Exists

**Issue**: `fatal: destination path 'scratch/fastapi' already exists`

**Solution**: Remove existing directories:
```bash
rm -rf scratch/
uv run clockwork apply
```

## Learn More

- [Clockwork Documentation](../../CLAUDE.md)
- [Git Documentation](https://git-scm.com/doc)
- [Other Examples](../)
