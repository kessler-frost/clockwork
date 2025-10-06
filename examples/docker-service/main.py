"""
Docker Service Example - Clockwork with AI-powered Docker image suggestions.

This example demonstrates three different ways to use DockerServiceResource:

1. **AI-suggested image**: No image specified, AI suggests the best image
   - Clockwork analyzes the description and purpose
   - Suggests an appropriate Docker image (e.g., nginx:latest)
   - Useful when you're not sure which image to use

2. **Explicit image with optional AI config**: Image specified, but AI could help with env vars
   - You control the exact image version
   - AI could suggest environment variables (future feature)
   - Best for production where you need version control

3. **Fully specified**: Complete configuration, no AI needed
   - Everything is explicitly defined
   - No AI suggestions needed
   - Maximum control and predictability

Run this example with:
    uv run clockwork demo --text-only --example docker-service
"""

from clockwork.resources import DockerServiceResource

# Example 1: AI-suggested image
# The AI will analyze the description and suggest an appropriate image
nginx = DockerServiceResource(
    name="nginx-ai",
    description="A production-ready web server for serving static content and reverse proxying",
    ports=["80:80", "443:443"],
    networks=["web"]
)

# Example 2: Explicit image with AI config potential
# Image is specified, but AI could potentially suggest env vars in future
redis = DockerServiceResource(
    name="redis-cache",
    description="Redis cache server for session storage with persistence",
    image="redis:7-alpine",
    ports=["6379:6379"],
    volumes=["redis_data:/data"]
)

# Example 3: Fully specified (no AI needed)
# Everything is explicitly defined - maximum control
postgres = DockerServiceResource(
    name="postgres-db",
    description="PostgreSQL database server for application data",
    image="postgres:16-alpine",
    ports=["5432:5432"],
    env_vars={
        "POSTGRES_PASSWORD": "example",
        "POSTGRES_USER": "clockwork",
        "POSTGRES_DB": "app"
    },
    volumes=["pg_data:/var/lib/postgresql/data"],
    networks=["backend"]
)
