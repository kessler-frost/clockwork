"""Simple test without assertions."""

from clockwork.resources import DockerResource

# Complete resources (no AI needed)
postgres = DockerResource(
    name="postgres-db",
    image="postgres:15-alpine",
    ports=["5432:5432"],
    env_vars={"POSTGRES_PASSWORD": "secret"}
)

redis = DockerResource(
    name="redis-cache",
    image="redis:7-alpine",
    ports=["6379:6379"]
)

# Resource with connections (connection context for AI)
api = DockerResource(
    description="FastAPI backend",
    name="api-server",
    image="python:3.11-slim",
    ports=["8000:8000"],
    connections=[postgres, redis]
)
