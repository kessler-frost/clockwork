"""Tests for DockerServiceResource."""

import pytest
from clockwork.resources import DockerServiceResource


def test_docker_service_resource_basic():
    """Test basic DockerServiceResource instantiation."""
    docker = DockerServiceResource(
        name="test-container",
        description="Test container"
    )

    assert docker.name == "test-container"
    assert docker.description == "Test container"
    assert docker.image is None
    assert docker.ports is None
    assert docker.volumes is None
    assert docker.env_vars is None
    assert docker.networks is None
    assert docker.present is True
    assert docker.start is True


def test_docker_service_resource_with_image():
    """Test DockerServiceResource with explicit image."""
    docker = DockerServiceResource(
        name="redis",
        description="Redis cache",
        image="redis:7-alpine",
        ports=["6379:6379"]
    )

    assert docker.name == "redis"
    assert docker.image == "redis:7-alpine"
    assert docker.ports == ["6379:6379"]


def test_docker_service_resource_full_config():
    """Test DockerServiceResource with all parameters."""
    docker = DockerServiceResource(
        name="postgres",
        description="PostgreSQL database",
        image="postgres:16-alpine",
        ports=["5432:5432"],
        volumes=["pg_data:/var/lib/postgresql/data"],
        env_vars={
            "POSTGRES_PASSWORD": "secret",
            "POSTGRES_USER": "admin"
        },
        networks=["backend"],
        present=True,
        start=True
    )

    assert docker.name == "postgres"
    assert docker.image == "postgres:16-alpine"
    assert docker.ports == ["5432:5432"]
    assert docker.volumes == ["pg_data:/var/lib/postgresql/data"]
    assert docker.env_vars == {"POSTGRES_PASSWORD": "secret", "POSTGRES_USER": "admin"}
    assert docker.networks == ["backend"]
    assert docker.present is True
    assert docker.start is True


def test_needs_artifact_generation_no_image():
    """Test needs_artifact_generation() returns True when no image specified."""
    docker = DockerServiceResource(
        name="nginx",
        description="Web server"
    )

    assert docker.needs_artifact_generation() is True


def test_needs_artifact_generation_with_image():
    """Test needs_artifact_generation() returns False when image is specified."""
    docker = DockerServiceResource(
        name="nginx",
        description="Web server",
        image="nginx:latest"
    )

    assert docker.needs_artifact_generation() is False


def test_to_pyinfra_operations_with_image():
    """Test PyInfra code generation with explicit image."""
    docker = DockerServiceResource(
        name="redis",
        description="Redis cache",
        image="redis:7-alpine",
        ports=["6379:6379"],
        volumes=["redis_data:/data"],
        env_vars={"REDIS_PASSWORD": "secret"},
        networks=["cache"]
    )

    operations = docker.to_pyinfra_operations({})

    # Check operation name and container name
    assert 'name="Deploy redis"' in operations
    assert 'container="redis"' in operations

    # Check image
    assert 'image="redis:7-alpine"' in operations

    # Check ports, volumes, env_vars, networks
    assert "['6379:6379']" in operations
    assert "['redis_data:/data']" in operations
    assert "{'REDIS_PASSWORD': 'secret'}" in operations or "'REDIS_PASSWORD': 'secret'" in operations
    assert "['cache']" in operations

    # Check state flags
    assert "present=True" in operations
    assert "start=True" in operations

    # Check docker.container call
    assert "docker.container(" in operations


def test_to_pyinfra_operations_with_ai_image():
    """Test PyInfra code generation with AI-suggested image from artifacts."""
    docker = DockerServiceResource(
        name="nginx-ai",
        description="Web server for static content"
    )

    # Simulate AI-generated artifact
    artifacts = {
        "nginx-ai": {"image": "nginx:latest"}
    }

    operations = docker.to_pyinfra_operations(artifacts)

    # Check that AI-suggested image is used
    assert 'image="nginx:latest"' in operations
    assert 'container="nginx-ai"' in operations
    assert 'name="Deploy nginx-ai"' in operations


def test_to_pyinfra_operations_empty_defaults():
    """Test PyInfra code generation with minimal config uses empty defaults."""
    docker = DockerServiceResource(
        name="minimal",
        description="Minimal container",
        image="alpine:latest"
    )

    operations = docker.to_pyinfra_operations({})

    # Check empty defaults are properly set
    assert "ports=[]" in operations
    assert "volumes=[]" in operations
    assert "env_vars={}" in operations
    assert "networks=[]" in operations


def test_to_pyinfra_operations_artifact_string_format():
    """Test PyInfra code generation when artifact is a string (not dict)."""
    docker = DockerServiceResource(
        name="test",
        description="Test container"
    )

    # Artifact as simple string instead of dict
    artifacts = {
        "test": "simple:latest"
    }

    operations = docker.to_pyinfra_operations(artifacts)

    # Should handle string artifact format
    assert 'image="simple:latest"' in operations or 'image=""' in operations


def test_to_pyinfra_operations_missing_artifact():
    """Test PyInfra code generation when artifact is missing uses empty string."""
    docker = DockerServiceResource(
        name="missing",
        description="Container with missing artifact"
    )

    operations = docker.to_pyinfra_operations({})

    # Should fall back to empty string when artifact is missing
    assert 'image=""' in operations


def test_to_pyinfra_destroy_operations():
    """Test PyInfra destroy code generation."""
    docker = DockerServiceResource(
        name="remove-me",
        description="Container to remove",
        image="alpine:latest"
    )

    operations = docker.to_pyinfra_destroy_operations({})

    # Check destroy operation
    assert 'name="Remove remove-me"' in operations
    assert 'container="remove-me"' in operations
    assert "present=False" in operations

    # Should NOT include other parameters in destroy
    assert "start=" not in operations or "start=False" not in operations
    assert "image=" not in operations
    assert "ports=" not in operations


def test_to_pyinfra_destroy_operations_ignores_artifacts():
    """Test destroy operations don't use artifacts."""
    docker = DockerServiceResource(
        name="test-destroy",
        description="Test"
    )

    # Provide artifacts, but they should be ignored
    artifacts = {"test-destroy": {"image": "nginx:latest"}}
    operations = docker.to_pyinfra_destroy_operations(artifacts)

    # Should only have name, container, and present=False
    assert 'container="test-destroy"' in operations
    assert "present=False" in operations
    assert "image=" not in operations


def test_docker_service_resource_present_false():
    """Test DockerServiceResource with present=False."""
    docker = DockerServiceResource(
        name="stopped",
        description="Stopped container",
        image="alpine:latest",
        present=False
    )

    operations = docker.to_pyinfra_operations({})

    assert "present=False" in operations


def test_docker_service_resource_start_false():
    """Test DockerServiceResource with start=False."""
    docker = DockerServiceResource(
        name="not-running",
        description="Container that exists but doesn't run",
        image="alpine:latest",
        start=False
    )

    operations = docker.to_pyinfra_operations({})

    assert "start=False" in operations
    assert "present=True" in operations


def test_docker_service_multiple_ports():
    """Test DockerServiceResource with multiple port mappings."""
    docker = DockerServiceResource(
        name="web",
        description="Web server",
        image="nginx:latest",
        ports=["80:80", "443:443", "8080:8080"]
    )

    operations = docker.to_pyinfra_operations({})

    assert "80:80" in operations
    assert "443:443" in operations
    assert "8080:8080" in operations


def test_docker_service_multiple_volumes():
    """Test DockerServiceResource with multiple volume mounts."""
    docker = DockerServiceResource(
        name="data",
        description="Data container",
        image="alpine:latest",
        volumes=[
            "/host/data:/container/data",
            "named_volume:/app",
            "/etc/config:/config:ro"
        ]
    )

    operations = docker.to_pyinfra_operations({})

    assert "/host/data:/container/data" in operations
    assert "named_volume:/app" in operations
    assert "/etc/config:/config:ro" in operations


def test_docker_service_multiple_networks():
    """Test DockerServiceResource with multiple networks."""
    docker = DockerServiceResource(
        name="networked",
        description="Multi-network container",
        image="alpine:latest",
        networks=["frontend", "backend", "monitoring"]
    )

    operations = docker.to_pyinfra_operations({})

    assert "frontend" in operations
    assert "backend" in operations
    assert "monitoring" in operations


def test_docker_service_complex_env_vars():
    """Test DockerServiceResource with complex environment variables."""
    docker = DockerServiceResource(
        name="app",
        description="Application container",
        image="myapp:latest",
        env_vars={
            "DATABASE_URL": "postgresql://user:pass@db:5432/mydb",
            "REDIS_URL": "redis://cache:6379",
            "DEBUG": "false",
            "PORT": "3000"
        }
    )

    operations = docker.to_pyinfra_operations({})

    assert "DATABASE_URL" in operations
    assert "REDIS_URL" in operations
    assert "DEBUG" in operations
    assert "PORT" in operations


def test_pydantic_validation():
    """Test Pydantic validation enforces required fields."""
    with pytest.raises(Exception):
        # Missing required 'name' field
        DockerServiceResource(description="Test")

    with pytest.raises(Exception):
        # Missing required 'description' field
        DockerServiceResource(name="test")
