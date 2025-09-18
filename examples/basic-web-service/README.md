# Basic Web Service Example

**Status**: ✅ **Fully Working and Tested**

This example demonstrates deploying a simple nginx web service using Clockwork.

## What This Example Does

1. **Deploys nginx container**: Uses nginx:1.25-alpine image
2. **Configures port mapping**: Maps host port 3000 to container port 80
3. **Sets environment variables**: Configures SERVER_NAME and PORT
4. **Health check verification**: Verifies the service responds with HTTP 200

## Files

- `main.cw` - Service configuration using Clockwork syntax
- `main.hcl` - Alternative HCL syntax (same functionality)
- `variables.cwvars` - Variable definitions with defaults

## Usage

### Quick Start
```bash
# Deploy the service
uv run clockwork apply --auto-approve

# Verify it's running
docker ps | grep web
curl http://localhost:3000

# Clean up
docker stop web && docker rm web
```

### Step by Step
```bash
# 1. Preview what will be deployed
uv run clockwork plan

# 2. Deploy the service
uv run clockwork apply

# 3. Test the service
curl http://localhost:3000
# Should return nginx welcome page

# 4. Check container status
docker ps
```

## Configuration

Edit `variables.cwvars` to customize:

```hcl
app_name = "my-custom-app"  # Container name
port = 8080                 # Host port
image = "nginx:latest"      # Docker image
```

## Expected Output

When successful, you should see:
```
✓ Deploy service: web (nginx:1.25-alpine): apply
✓ Verify HTTP endpoint is up: apply

Apply complete! Resources: 2 applied, 0 failed.
```

## Troubleshooting

- **"No .cw files found"**: Run from the `basic-web-service` directory
- **Docker errors**: Ensure Docker is running and the port is available
- **Port conflicts**: Change the `port` variable in `variables.cwvars`
