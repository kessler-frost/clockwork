## Development Preferences

- **Use uv for all commands**: `uv run python script.py`, `uv run clockwork --help`
- **Minimize if/else and try/except blocks**: Keep code simple and direct
- **No backward compatibility concerns**: Don't add fallback mechanisms
- **Commands auto-detect main.cw**: All commands default to `main.cw` in current directory
- **Plan should work like Terraform**: Show actual vs desired state, not just generated code
- **Always test commands after changes**: Ensure basic functionality works
- **Clean up artifacts after testing**: Remove temporary files and state

## PyInfra-Based Architecture

Clockwork now uses **PyInfra** for infrastructure management with the following characteristics:

### Key Features
- **PyInfra Integration**: Direct conversion of .cw files to PyInfra operations
- **Two-Phase Pipeline**: Parse → Execute workflow
- **Multi-Target Support**: @local, @docker:container, @ssh:host
- **Terraform-like Planning**: Shows current vs desired state with drift detection
- **Auto Config Detection**: Commands default to main.cw in current directory

### Configuration

Key environment variables:
- `CLOCKWORK_LOG_LEVEL`: Log level (default: INFO)
- `CLOCKWORK_TARGET`: Default deployment target (default: @local)

Target deployment:
```bash
# Deploy to Docker container
uv run clockwork apply --target @docker:mycontainer

# Deploy to SSH host
uv run clockwork apply --target @ssh:production-server
```

### How It Works

1. **Parse** `.cw` files → Generate PyInfra Python code
2. **Plan** - Compare current vs desired state (like `terraform plan`)
3. **Apply** - Execute PyInfra operations on target infrastructure
4. **State** - Track deployed resources in `.clockwork/state.json`

### Usage Examples

All commands auto-detect `main.cw` in current directory:

```bash
# Plan (show what would change)
uv run clockwork plan

# Apply changes
uv run clockwork apply

# Deploy to specific targets
uv run clockwork apply --target @docker:mycontainer
uv run clockwork apply --target @ssh:production-server

# Watch for file changes
uv run clockwork watch

# Check system facts
uv run clockwork facts @local

# Manage state
uv run clockwork state show
uv run clockwork destroy
```

Testing the example:
```bash
cd examples/basic-web-service
uv run clockwork plan
uv run clockwork apply --dry-run
```