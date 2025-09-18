# Hello World Example

**Status**: ✅ **Minimal Working Example**

The simplest possible Clockwork service deployment - perfect for getting started.

## What This Example Does

- Deploys nginx:alpine container (smallest nginx image)
- Runs on port 8080
- Sets a custom welcome message via environment variable

## Files

- `main.cw` - Minimal service configuration
- `variables.cwvars` - Simple message customization

## Usage

```bash
# Deploy
uv run clockwork apply --auto-approve

# Test
curl http://localhost:8080

# Clean up
docker stop hello-world && docker rm hello-world
```

## Customization

Change the message:
```bash
# Edit variables.cwvars
message = "Your custom message here!"
```

## Expected Output

```
✓ Deploy service: hello-world (nginx:alpine): apply

Apply complete! Resources: 1 applied, 0 failed.
```