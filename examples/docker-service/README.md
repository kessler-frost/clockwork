# Docker Service Example

Simple web service deployed with AI-suggested Docker image.

## What it does

Deploys a lightweight web server using Clockwork's AI-powered image suggestions.

## Prerequisites

1. OpenRouter API key:
   ```bash
   export OPENROUTER_API_KEY="your-key-here"
   ```

2. Docker installed and running

## Run the example

```bash
# Deploy the service
uv run clockwork apply examples/docker-service/main.py

# Test it
curl localhost:8080

# Clean up
uv run clockwork destroy examples/docker-service/main.py
```

## How it works

1. **AI suggests image**: Clockwork's AI analyzes the description and suggests an appropriate Docker image (e.g., nginx, httpd)
2. **PyInfra deploys**: The suggested image is deployed as a Docker container on port 8080
3. **Service runs**: Access the web server at http://localhost:8080
