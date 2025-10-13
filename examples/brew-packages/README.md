# Homebrew Package Installation Example

Demonstrates AI-powered Homebrew package installation on macOS using `BrewPackageResource`.

## What This Example Creates

This example installs:
- **Development tools** - Essential CLI tools like jq and htop (AI-selected packages)
- **Visual Studio Code** - GUI application (AI detects it's a cask)
- **Network utilities** - curl and nmap (explicitly specified packages)

## Prerequisites

- **macOS** (Homebrew is macOS-specific)
- **Homebrew** installed (`/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"`)
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
cd examples/brew-packages
uv run clockwork apply
```

This will:
- ✅ Install development CLI tools (jq, htop, etc.)
- ✅ Install VS Code as a cask (GUI app)
- ✅ Install network utilities (curl, nmap)

### 3. Verify Installation

```bash
# Check installed packages
brew list jq htop

# Check cask
brew list --cask visual-studio-code

# Check network utilities
curl --version
nmap --version
```

## Cleanup

**Note**: Clockwork does **NOT** uninstall Homebrew packages during `clockwork destroy` (by design). This is intentional to avoid removing system-level dependencies.

To manually uninstall (if desired):
```bash
brew uninstall jq htop curl nmap
brew uninstall --cask visual-studio-code
```

## What This Demonstrates

1. **AI Package Selection** - AI picks appropriate packages based on description
2. **Cask Detection** - AI automatically detects GUI apps and sets `cask=True`
3. **Explicit Override** - You can specify exact packages and let AI handle the rest
4. **Declarative Infrastructure** - Define what you need, Clockwork handles installation

## Resources Created

| Resource | Description | AI Completion |
|----------|-------------|---------------|
| dev_tools | Development CLI tools | AI picks packages (jq, htop, etc.) |
| code_editor | VS Code GUI app | AI sets cask=True |
| network_utils | Network utilities | Explicit packages, AI fills name |

## Learn More

- [Clockwork Documentation](../../CLAUDE.md)
- [Homebrew Documentation](https://docs.brew.sh)
- [Other Examples](../)
