"""Tests for AppleContainerResource."""

import pytest
from clockwork.resources import AppleContainerResource


def test_apple_container_resource_basic():
    """Test basic AppleContainerResource instantiation."""
    container = AppleContainerResource(
        name="test-container",
        description="Test container"
    )

    assert container.name == "test-container"
    assert container.description == "Test container"
    assert container.image is None
    assert container.ports is None
    assert container.volumes is None
    assert container.env_vars is None
    assert container.networks is None
    assert container.present is True
    assert container.start is True


def test_apple_container_resource_with_image():
    """Test AppleContainerResource with explicit image."""
    container = AppleContainerResource(
        name="redis",
        description="Redis cache",
        image="redis:7-alpine",
        ports=["6379:6379"]
    )

    assert container.name == "redis"
    assert container.image == "redis:7-alpine"
    assert container.ports == ["6379:6379"]


def test_apple_container_resource_full_config():
    """Test AppleContainerResource with all parameters."""
    container = AppleContainerResource(
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

    assert container.name == "postgres"
    assert container.image == "postgres:16-alpine"
    assert container.ports == ["5432:5432"]
    assert container.volumes == ["pg_data:/var/lib/postgresql/data"]
    assert container.env_vars == {"POSTGRES_PASSWORD": "secret", "POSTGRES_USER": "admin"}
    assert container.networks == ["backend"]
    assert container.present is True
    assert container.start is True


def test_needs_artifact_generation_no_image():
    """Test needs_artifact_generation() returns True when no image specified."""
    container = AppleContainerResource(
        name="nginx",
        description="Web server"
    )

    assert container.needs_artifact_generation() is True


def test_needs_artifact_generation_with_image():
    """Test needs_artifact_generation() returns False when image is specified."""
    container = AppleContainerResource(
        name="nginx",
        description="Web server",
        image="nginx:latest"
    )

    assert container.needs_artifact_generation() is False


def test_to_pyinfra_operations_with_image():
    """Test PyInfra code generation with explicit image."""
    container = AppleContainerResource(
        name="redis",
        description="Redis cache",
        image="redis:7-alpine",
        ports=["6379:6379"],
        volumes=["redis_data:/data"],
        env_vars={"REDIS_PASSWORD": "secret"},
        networks=["cache"]
    )

    operations = container.to_pyinfra_operations({})

    # Check apple_containers operation calls
    assert 'apple_containers.container_remove(' in operations
    assert 'apple_containers.container_run(' in operations

    # Check container name
    assert 'name="redis"' in operations

    # Check image
    assert 'redis:7-alpine' in operations

    # Check ports, volumes, env_vars, networks
    assert '"6379:6379"' in operations
    assert '"redis_data:/data"' in operations
    assert '"REDIS_PASSWORD": "secret"' in operations
    assert '"cache"' in operations

    # Check container removal operation
    assert 'container_id="redis"' in operations
    assert 'force=True' in operations


def test_to_pyinfra_operations_with_ai_image():
    """Test PyInfra code generation with AI-suggested image from artifacts."""
    container = AppleContainerResource(
        name="nginx-ai",
        description="Web server for static content"
    )

    # Simulate AI-generated artifact
    artifacts = {
        "nginx-ai": {"image": "nginx:latest"}
    }

    operations = container.to_pyinfra_operations(artifacts)

    # Check that AI-suggested image is used
    assert 'nginx:latest' in operations
    assert 'name="nginx-ai"' in operations
    assert 'apple_containers.container_run(' in operations


def test_to_pyinfra_operations_multiple_ports():
    """Test PyInfra code generation with multiple port mappings."""
    container = AppleContainerResource(
        name="web",
        description="Web server",
        image="nginx:latest",
        ports=["80:80", "443:443", "8080:8080"]
    )

    operations = container.to_pyinfra_operations({})

    assert '"80:80"' in operations
    assert '"443:443"' in operations
    assert '"8080:8080"' in operations
    assert 'apple_containers.container_run(' in operations


def test_to_pyinfra_operations_multiple_volumes():
    """Test PyInfra code generation with multiple volume mounts."""
    container = AppleContainerResource(
        name="data",
        description="Data container",
        image="alpine:latest",
        volumes=[
            "/host/data:/container/data",
            "named_volume:/app",
            "/etc/config:/config:ro"
        ]
    )

    operations = container.to_pyinfra_operations({})

    assert '"/host/data:/container/data"' in operations
    assert '"named_volume:/app"' in operations
    assert '"/etc/config:/config:ro"' in operations
    assert 'apple_containers.container_run(' in operations


def test_to_pyinfra_operations_multiple_networks():
    """Test PyInfra code generation with multiple networks."""
    container = AppleContainerResource(
        name="networked",
        description="Multi-network container",
        image="alpine:latest",
        networks=["frontend", "backend", "monitoring"]
    )

    operations = container.to_pyinfra_operations({})

    assert '"frontend"' in operations
    assert '"backend"' in operations
    assert '"monitoring"' in operations
    assert 'apple_containers.container_run(' in operations


def test_to_pyinfra_operations_complex_env_vars():
    """Test PyInfra code generation with complex environment variables."""
    container = AppleContainerResource(
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

    operations = container.to_pyinfra_operations({})

    assert '"DATABASE_URL": "postgresql://user:pass@db:5432/mydb"' in operations
    assert '"REDIS_URL": "redis://cache:6379"' in operations
    assert '"DEBUG": "false"' in operations
    assert '"PORT": "3000"' in operations
    assert 'apple_containers.container_run(' in operations


def test_to_pyinfra_operations_artifact_string_format():
    """Test PyInfra code generation when artifact is a string (not dict)."""
    container = AppleContainerResource(
        name="test",
        description="Test container"
    )

    # Artifact as simple string instead of dict
    artifacts = {
        "test": "simple:latest"
    }

    operations = container.to_pyinfra_operations(artifacts)

    # Should handle string artifact format
    assert 'simple:latest' in operations
    assert 'apple_containers.container_run(' in operations


def test_to_pyinfra_operations_missing_artifact():
    """Test PyInfra code generation when artifact is missing uses empty string."""
    container = AppleContainerResource(
        name="missing",
        description="Container with missing artifact"
    )

    operations = container.to_pyinfra_operations({})

    # Should fall back to empty string when artifact is missing
    assert 'apple_containers.container_run(' in operations


def test_to_pyinfra_destroy_operations():
    """Test PyInfra destroy code generation."""
    container = AppleContainerResource(
        name="remove-me",
        description="Container to remove",
        image="alpine:latest"
    )

    operations = container.to_pyinfra_destroy_operations({})

    # Check destroy operation uses apple_containers.container_remove
    assert 'name="Remove remove-me"' in operations
    assert 'container_id="remove-me"' in operations
    assert 'apple_containers.container_remove(' in operations
    assert 'force=True' in operations


def test_to_pyinfra_destroy_operations_ignores_artifacts():
    """Test destroy operations don't use artifacts."""
    container = AppleContainerResource(
        name="test-destroy",
        description="Test"
    )

    # Provide artifacts, but they should be ignored
    artifacts = {"test-destroy": {"image": "nginx:latest"}}
    operations = container.to_pyinfra_destroy_operations(artifacts)

    # Should only have container_remove operation
    assert 'apple_containers.container_remove(' in operations
    assert 'container_id="test-destroy"' in operations
    assert 'nginx:latest' not in operations


def test_apple_container_resource_present_false():
    """Test AppleContainerResource with present=False."""
    container = AppleContainerResource(
        name="stopped",
        description="Stopped container",
        image="alpine:latest",
        present=False
    )

    operations = container.to_pyinfra_operations({})

    # When present=False, should remove the container
    assert 'apple_containers.container_remove(' in operations
    assert 'container_id="stopped"' in operations


def test_apple_container_resource_start_false():
    """Test AppleContainerResource with start=False."""
    container = AppleContainerResource(
        name="not-running",
        description="Container that exists but doesn't run",
        image="alpine:latest",
        start=False
    )

    operations = container.to_pyinfra_operations({})

    # When start=False, should use 'container_create' instead of 'container_run'
    assert 'apple_containers.container_create(' in operations
    assert 'name="not-running"' in operations


def test_container_run_command_format():
    """Test that container run operation is properly formatted."""
    container = AppleContainerResource(
        name="test",
        description="Test container",
        image="nginx:latest",
        ports=["80:80"],
        volumes=["/data:/data"],
        env_vars={"KEY": "value"}
    )

    operations = container.to_pyinfra_operations({})

    # Verify operation structure
    assert 'apple_containers.container_run(' in operations
    assert 'name="test"' in operations
    assert '"80:80"' in operations
    assert '"/data:/data"' in operations
    assert '"KEY": "value"' in operations
    assert 'nginx:latest' in operations


def test_to_pyinfra_assert_operations_default():
    """Test default assertion generation."""
    container = AppleContainerResource(
        name="nginx",
        description="Web server",
        image="nginx:latest"
    )

    operations = container.to_pyinfra_assert_operations({})

    # Check for default assertions using custom facts
    assert 'ContainerExists' in operations
    assert 'ContainerRunning' in operations
    assert 'container_id="nginx"' in operations
    assert 'Container nginx does not exist' in operations
    assert 'Container nginx is not running' in operations


def test_to_pyinfra_assert_operations_present_only():
    """Test assertion when container should exist but not run."""
    container = AppleContainerResource(
        name="stopped",
        description="Stopped container",
        image="alpine:latest",
        start=False
    )

    operations = container.to_pyinfra_assert_operations({})

    # Should check existence but not running status
    assert 'ContainerExists' in operations
    assert 'container_id="stopped"' in operations
    # Should not check for running status since start=False
    assert 'ContainerRunning' not in operations
    assert 'is not running' not in operations


def test_pydantic_validation():
    """Test Pydantic validation enforces required fields."""
    with pytest.raises(Exception):
        # Missing required 'name' field
        AppleContainerResource(description="Test")

    with pytest.raises(Exception):
        # Missing required 'description' field
        AppleContainerResource(name="test")


def test_container_commands_not_docker():
    """Test that generated operations use 'apple_containers', not 'docker'."""
    container = AppleContainerResource(
        name="test",
        description="Test container",
        image="nginx:latest"
    )

    operations = container.to_pyinfra_operations({})
    destroy_ops = container.to_pyinfra_destroy_operations({})
    assert_ops = container.to_pyinfra_assert_operations({})

    # Verify no docker commands are used
    assert "docker" not in operations.lower()
    assert "docker" not in destroy_ops.lower()
    assert "docker" not in assert_ops.lower()

    # Verify apple_containers operations are used
    assert "apple_containers.container_run(" in operations or "apple_containers.container_create(" in operations
    assert "apple_containers.container_remove(" in destroy_ops
    assert "ContainerExists" in assert_ops or "ContainerRunning" in assert_ops
