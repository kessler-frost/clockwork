"""Tests for DockerResource."""

import pytest
from clockwork.resources import DockerResource


def test_docker_resource_basic():
    """Test basic DockerResource instantiation."""
    container = DockerResource(
        name="test-container",
        description="Test container"
    )

    assert container.name == "test-container"
    assert container.description == "Test container"
    assert container.image is None
    assert container.ports is None
    assert container.volumes == []  # Defaults to empty list
    assert container.env_vars == {}  # Defaults to empty dict
    assert container.networks == []  # Defaults to empty list
    assert container.present is True
    assert container.start is True


def test_docker_resource_with_image():
    """Test DockerResource with explicit image."""
    container = DockerResource(
        name="redis",
        description="Redis cache",
        image="redis:7-alpine",
        ports=["6379:6379"]
    )

    assert container.name == "redis"
    assert container.image == "redis:7-alpine"
    assert container.ports == ["6379:6379"]


def test_docker_resource_full_config():
    """Test DockerResource with all parameters."""
    container = DockerResource(
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


def test_needs_completion_no_image():
    """Test needs_completion() returns True when no image specified."""
    container = DockerResource(
        name="nginx",
        description="Web server"
    )

    assert container.needs_completion() is True


def test_needs_completion_with_all_fields():
    """Test needs_completion() returns False when all fields are specified."""
    container = DockerResource(
        name="nginx",
        description="Web server",
        image="nginx:latest",
        ports=[],
        volumes=[],
        env_vars={},
        networks=[]
    )

    assert container.needs_completion() is False


def test_to_pyinfra_operations_with_image():
    """Test PyInfra code generation with explicit image."""
    container = DockerResource(
        name="redis",
        description="Redis cache",
        image="redis:7-alpine",
        ports=["6379:6379"],
        volumes=["redis_data:/data"],
        env_vars={"REDIS_PASSWORD": "secret"},
        networks=["cache"]
    )

    operations = container.to_pyinfra_operations()

    # Check docker.container operation calls
    assert 'docker.container(' in operations

    # Check container name
    assert 'container="redis"' in operations

    # Check image
    assert 'redis:7-alpine' in operations

    # Check ports, volumes, env_vars, networks
    assert '"6379:6379"' in operations
    assert '"redis_data:/data"' in operations
    # PyInfra uses env_vars as list of KEY=VALUE strings
    assert '"REDIS_PASSWORD=secret"' in operations
    assert '"cache"' in operations

    # Check state flags
    assert 'present=True' in operations
    assert 'start=True' in operations


def test_to_pyinfra_operations_with_ai_image():
    """Test PyInfra code generation with AI-completed fields."""
    container = DockerResource(
        name="nginx-ai",
        description="Web server for static content"
    )

    # Simulate AI completion
    container.image = "nginx:latest"
    container.ports = []
    container.volumes = []
    container.env_vars = {}
    container.networks = []

    operations = container.to_pyinfra_operations()

    # Check that AI-completed image is used
    assert 'nginx:latest' in operations
    assert 'container="nginx-ai"' in operations
    assert 'docker.container(' in operations


def test_to_pyinfra_operations_multiple_ports():
    """Test PyInfra code generation with multiple port mappings."""
    container = DockerResource(
        name="web",
        description="Web server",
        image="nginx:latest",
        ports=["80:80", "443:443", "8080:8080"]
    )

    operations = container.to_pyinfra_operations()

    assert '"80:80"' in operations
    assert '"443:443"' in operations
    assert '"8080:8080"' in operations
    assert 'docker.container(' in operations


def test_to_pyinfra_operations_multiple_volumes():
    """Test PyInfra code generation with multiple volume mounts."""
    container = DockerResource(
        name="data",
        description="Data container",
        image="alpine:latest",
        volumes=[
            "/host/data:/container/data",
            "named_volume:/app",
            "/etc/config:/config:ro"
        ]
    )

    operations = container.to_pyinfra_operations()

    assert '"/host/data:/container/data"' in operations
    assert '"named_volume:/app"' in operations
    assert '"/etc/config:/config:ro"' in operations
    assert 'docker.container(' in operations


def test_to_pyinfra_operations_multiple_networks():
    """Test PyInfra code generation with multiple networks."""
    container = DockerResource(
        name="networked",
        description="Multi-network container",
        image="alpine:latest",
        networks=["frontend", "backend", "monitoring"]
    )

    operations = container.to_pyinfra_operations()

    assert '"frontend"' in operations
    assert '"backend"' in operations
    assert '"monitoring"' in operations
    assert 'docker.container(' in operations


def test_to_pyinfra_operations_complex_env_vars():
    """Test PyInfra code generation with complex environment variables."""
    container = DockerResource(
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

    operations = container.to_pyinfra_operations()

    # PyInfra uses env_vars as list of KEY=VALUE strings
    assert '"DATABASE_URL=postgresql://user:pass@db:5432/mydb"' in operations
    assert '"REDIS_URL=redis://cache:6379"' in operations
    assert '"DEBUG=false"' in operations
    assert '"PORT=3000"' in operations
    assert 'docker.container(' in operations


def test_to_pyinfra_operations_completed_fields():
    """Test PyInfra code generation with completed fields."""
    container = DockerResource(
        name="test",
        description="Test container",
        image="simple:latest",
        ports=[],
        volumes=[],
        env_vars={},
        networks=[]
    )

    operations = container.to_pyinfra_operations()

    # Should use completed image field
    assert 'simple:latest' in operations
    assert 'docker.container(' in operations


def test_to_pyinfra_operations_missing_fields_raises_error():
    """Test PyInfra code generation when fields are not completed raises error."""
    container = DockerResource(
        name="missing",
        description="Container with missing fields"
    )

    # Should raise error when required fields are not completed
    with pytest.raises(ValueError, match="Resource fields not completed"):
        container.to_pyinfra_operations()


def test_to_pyinfra_destroy_operations():
    """Test PyInfra destroy code generation."""
    container = DockerResource(
        name="remove-me",
        description="Container to remove",
        image="alpine:latest"
    )

    operations = container.to_pyinfra_destroy_operations()

    # Check destroy operation uses docker.container with present=False
    assert 'name="Remove remove-me"' in operations
    assert 'container="remove-me"' in operations
    assert 'docker.container(' in operations
    assert 'present=False' in operations


def test_to_pyinfra_destroy_operations_only_needs_name():
    """Test destroy operations only need name field."""
    container = DockerResource(
        name="test-destroy",
        description="Test"
    )

    # Destroy only needs name field
    operations = container.to_pyinfra_destroy_operations()

    # Should only have docker.container operation with present=False
    assert 'docker.container(' in operations
    assert 'container="test-destroy"' in operations
    assert 'present=False' in operations


def test_docker_resource_present_false():
    """Test DockerResource with present=False."""
    container = DockerResource(
        name="stopped",
        description="Stopped container",
        image="alpine:latest",
        present=False
    )

    operations = container.to_pyinfra_operations()

    # When present=False, should remove the container
    assert 'docker.container(' in operations
    assert 'container="stopped"' in operations
    assert 'present=False' in operations


def test_docker_resource_start_false():
    """Test DockerResource with start=False."""
    container = DockerResource(
        name="not-running",
        description="Container that exists but doesn't run",
        image="alpine:latest",
        start=False
    )

    operations = container.to_pyinfra_operations()

    # When start=False, should have start=False
    assert 'docker.container(' in operations
    assert 'container="not-running"' in operations
    assert 'start=False' in operations
    assert 'present=True' in operations


def test_container_operation_format():
    """Test that container operation is properly formatted."""
    container = DockerResource(
        name="test",
        description="Test container",
        image="nginx:latest",
        ports=["80:80"],
        volumes=["/data:/data"],
        env_vars={"KEY": "value"}
    )

    operations = container.to_pyinfra_operations()

    # Verify operation structure
    assert 'docker.container(' in operations
    assert 'container="test"' in operations
    assert '"80:80"' in operations
    assert '"/data:/data"' in operations
    # PyInfra uses env_vars as list of KEY=VALUE strings
    assert '"KEY=value"' in operations
    assert 'nginx:latest' in operations


def test_to_pyinfra_assert_operations_default():
    """Test default assertion generation."""
    container = DockerResource(
        name="nginx",
        description="Web server",
        image="nginx:latest"
    )

    operations = container.to_pyinfra_assert_operations()

    # No default assertions generated - users must explicitly add assertion objects
    assert operations == ""


def test_to_pyinfra_assert_operations_present_only():
    """Test assertion when container should exist but not run."""
    container = DockerResource(
        name="stopped",
        description="Stopped container",
        image="alpine:latest",
        start=False
    )

    operations = container.to_pyinfra_assert_operations()

    # No default assertions generated - users must explicitly add assertion objects
    assert operations == ""


def test_pydantic_validation():
    """Test Pydantic validation enforces required description field."""
    with pytest.raises(Exception):
        # Missing required 'description' field
        DockerResource(name="test")


def test_docker_operations_use_docker_not_apple():
    """Test that generated operations use 'docker.container', not 'apple_containers'."""
    container = DockerResource(
        name="test",
        description="Test container",
        image="nginx:latest"
    )

    operations = container.to_pyinfra_operations()
    destroy_ops = container.to_pyinfra_destroy_operations()
    assert_ops = container.to_pyinfra_assert_operations()

    # Verify docker.container is used
    assert "docker.container(" in operations
    assert "docker.container(" in destroy_ops

    # Verify no apple_containers operations are used
    assert "apple_containers" not in operations.lower()
    assert "apple_containers" not in destroy_ops.lower()
    assert "apple_containers" not in assert_ops.lower()

    # No default assertions generated
    assert assert_ops == ""
