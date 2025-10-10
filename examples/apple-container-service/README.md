# Apple Container Service Example

Simple web service deployed with AI-suggested container image using Apple Containers.

## What it does

Deploys a lightweight web server using Clockwork's AI-powered image suggestions with Apple's native container runtime.

## Prerequisites

- Apple Containers CLI installed and running
- macOS system with container support

## Run the example

```bash
# Navigate to example directory
cd examples/apple-container-service

# Deploy the service
clockwork apply

# Test it
curl localhost:8080

# Clean up
clockwork destroy
```

## How it works

1. **AI suggests image**: Clockwork's AI analyzes the description and suggests an appropriate container image (e.g., nginx:alpine, httpd:alpine)
2. **PyInfra deploys**: The suggested image is deployed as an Apple Container on port 8080 using the `container` CLI
3. **Service runs**: Access the web server at <http://localhost:8080>
4. **`.clockwork/`** directory created in current directory
