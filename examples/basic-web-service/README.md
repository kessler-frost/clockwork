# Basic Web Service Example

This example demonstrates a simple web service deployment using Clockwork.

## What it does

- Deploys a single NGINX web server
- Configures port mapping
- Sets up health checks
- Provides customizable variables

## Files

- `main.cw` - Main configuration defining the web service
- `variables.cwvars` - Variable overrides for customization

## Usage

```bash
# Plan the deployment
clockwork plan

# Apply with custom variables
clockwork apply --var app_name=my-app --var port=9000

# Check status
clockwork status

# Verify health
clockwork verify
```

## Customization

You can customize the deployment by:

1. Editing `variables.cwvars`
2. Using command-line variables: `--var key=value`
3. Modifying `main.cw` for structural changes

## Expected Output

After running `clockwork apply`, you should have:
- A running NGINX container
- Service accessible at the configured port
- Health checks monitoring the service