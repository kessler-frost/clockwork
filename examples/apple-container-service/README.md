# Apple Container Service Example

Intelligent container orchestration with AI-suggested images using Apple Containers.

## What it does

Orchestrates a lightweight web server with Clockwork's AI-powered image selection using Apple's native container runtime.

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

1. **AI intelligence**: Analyzes the description and intelligently suggests an appropriate container image (e.g., nginx:alpine, httpd:alpine)
2. **Orchestration**: Clockwork compiles to PyInfra operations and deploys as an Apple Container on port 8080
3. **Service runs**: Access the web server at <http://localhost:8080>
4. **`.clockwork/`** directory created in current directory
