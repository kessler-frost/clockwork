"""Tests for DockerResource."""

import pytest
from unittest.mock import Mock, patch
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
    """Test needs_completion() returns False when all required fields are specified."""
    container = DockerResource(
        name="nginx",
        description="Web server",
        image="nginx:latest",
        ports=[]
    )

    assert container.needs_completion() is False


@patch('clockwork.resources.docker.docker.Container')
def test_to_pulumi_basic(mock_container):
    """Test Pulumi resource creation with basic fields."""
    mock_pulumi_container = Mock()
    mock_container.return_value = mock_pulumi_container

    container = DockerResource(
        name="redis",
        description="Redis cache",
        image="redis:7-alpine",
        ports=["6379:6379"]
    )

    result = container.to_pulumi()

    # Verify Container was called with correct arguments
    mock_container.assert_called_once()
    call_args = mock_container.call_args

    assert call_args[0][0] == "redis"  # Resource name
    assert call_args[1]["image"] == "redis:7-alpine"
    assert call_args[1]["name"] == "redis"
    assert len(call_args[1]["ports"]) == 1
    assert call_args[1]["ports"][0].internal == 6379
    assert call_args[1]["ports"][0].external == 6379

    # Verify result and storage
    assert result == mock_pulumi_container
    assert container._pulumi_resource == mock_pulumi_container


@patch('clockwork.resources.docker.docker.Container')
def test_to_pulumi_with_volumes_and_env(mock_container):
    """Test Pulumi resource creation with volumes and environment variables."""
    mock_pulumi_container = Mock()
    mock_container.return_value = mock_pulumi_container

    container = DockerResource(
        name="postgres",
        description="Database",
        image="postgres:15",
        ports=["5432:5432"],
        volumes=["pg_data:/var/lib/postgresql/data"],
        env_vars={"POSTGRES_PASSWORD": "secret", "POSTGRES_USER": "admin"},
        networks=["backend"]
    )

    result = container.to_pulumi()

    call_args = mock_container.call_args

    # Check volumes
    assert len(call_args[1]["volumes"]) == 1
    assert call_args[1]["volumes"][0].host_path == "pg_data"
    assert call_args[1]["volumes"][0].container_path == "/var/lib/postgresql/data"
    assert call_args[1]["volumes"][0].read_only is False

    # Check environment variables
    assert "POSTGRES_PASSWORD=secret" in call_args[1]["envs"]
    assert "POSTGRES_USER=admin" in call_args[1]["envs"]

    # Check networks
    assert len(call_args[1]["networks_advanced"]) == 1
    assert call_args[1]["networks_advanced"][0].name == "backend"


@patch('clockwork.resources.docker.docker.Container')
def test_to_pulumi_multiple_ports(mock_container):
    """Test Pulumi resource creation with multiple port mappings."""
    mock_pulumi_container = Mock()
    mock_container.return_value = mock_pulumi_container

    container = DockerResource(
        name="web",
        description="Web server",
        image="nginx:latest",
        ports=["80:80", "443:443", "8080:8080"]
    )

    container.to_pulumi()

    call_args = mock_container.call_args
    ports = call_args[1]["ports"]

    assert len(ports) == 3
    assert ports[0].internal == 80 and ports[0].external == 80
    assert ports[1].internal == 443 and ports[1].external == 443
    assert ports[2].internal == 8080 and ports[2].external == 8080


@patch('clockwork.resources.docker.docker.Container')
def test_to_pulumi_multiple_volumes(mock_container):
    """Test Pulumi resource creation with multiple volume mounts."""
    mock_pulumi_container = Mock()
    mock_container.return_value = mock_pulumi_container

    container = DockerResource(
        name="data",
        description="Data container",
        image="alpine:latest",
        ports=[],
        volumes=[
            "/host/data:/container/data",
            "named_volume:/app",
            "/etc/config:/config:ro"
        ]
    )

    container.to_pulumi()

    call_args = mock_container.call_args
    volumes = call_args[1]["volumes"]

    assert len(volumes) == 3
    assert volumes[0].host_path == "/host/data"
    assert volumes[0].container_path == "/container/data"
    assert volumes[0].read_only is False

    assert volumes[1].host_path == "named_volume"
    assert volumes[1].container_path == "/app"
    assert volumes[1].read_only is False

    assert volumes[2].host_path == "/etc/config"
    assert volumes[2].container_path == "/config"
    assert volumes[2].read_only is True


@patch('clockwork.resources.docker.docker.Container')
def test_to_pulumi_multiple_networks(mock_container):
    """Test Pulumi resource creation with multiple networks."""
    mock_pulumi_container = Mock()
    mock_container.return_value = mock_pulumi_container

    container = DockerResource(
        name="networked",
        description="Multi-network container",
        image="alpine:latest",
        ports=[],
        networks=["frontend", "backend", "monitoring"]
    )

    container.to_pulumi()

    call_args = mock_container.call_args
    networks = call_args[1]["networks_advanced"]

    assert len(networks) == 3
    assert networks[0].name == "frontend"
    assert networks[1].name == "backend"
    assert networks[2].name == "monitoring"


@patch('clockwork.resources.docker.docker.Container')
def test_to_pulumi_complex_env_vars(mock_container):
    """Test Pulumi resource creation with complex environment variables."""
    mock_pulumi_container = Mock()
    mock_container.return_value = mock_pulumi_container

    container = DockerResource(
        name="app",
        description="Application container",
        image="myapp:latest",
        ports=[],
        env_vars={
            "DATABASE_URL": "postgresql://user:pass@db:5432/mydb",
            "REDIS_URL": "redis://cache:6379",
            "DEBUG": "false",
            "PORT": "3000"
        }
    )

    container.to_pulumi()

    call_args = mock_container.call_args
    envs = call_args[1]["envs"]

    assert "DATABASE_URL=postgresql://user:pass@db:5432/mydb" in envs
    assert "REDIS_URL=redis://cache:6379" in envs
    assert "DEBUG=false" in envs
    assert "PORT=3000" in envs


def test_to_pulumi_missing_fields_raises_error():
    """Test to_pulumi() raises error when fields are not completed."""
    container = DockerResource(
        name="missing",
        description="Container with missing fields"
    )

    # Should raise error when required fields are not completed
    with pytest.raises(ValueError, match="Resource not completed"):
        container.to_pulumi()


@patch('clockwork.resources.docker.docker.Container')
def test_to_pulumi_with_connections(mock_container):
    """Test Pulumi resource creation with connection dependencies."""
    import pulumi

    mock_pulumi_container = Mock()
    mock_container.return_value = mock_pulumi_container

    # Create a real connected resource without Pulumi resource set
    # This tests that the code handles connections correctly
    db_container = DockerResource(
        name="postgres",
        description="Database",
        image="postgres:15",
        ports=["5432:5432"]
    )
    # Don't set _pulumi_resource - test that code handles missing resources

    # Create app container with connection to database
    app_container = DockerResource(
        name="app",
        description="Application",
        image="myapp:latest",
        ports=["8000:8000"],
        connections=[db_container]
    )

    app_container.to_pulumi()

    call_args = mock_container.call_args

    # When connected resource doesn't have _pulumi_resource set,
    # opts should be None
    opts = call_args[1]["opts"]
    assert opts is None

    # Verify connections are stored in _connection_resources
    assert len(app_container._connection_resources) == 1
    assert app_container._connection_resources[0] == db_container


@patch('clockwork.resources.docker.docker.Container')
def test_to_pulumi_start_false(mock_container):
    """Test Pulumi resource creation with start=False."""
    mock_pulumi_container = Mock()
    mock_container.return_value = mock_pulumi_container

    container = DockerResource(
        name="not-running",
        description="Container that exists but doesn't run",
        image="alpine:latest",
        ports=[],
        start=False
    )

    container.to_pulumi()

    call_args = mock_container.call_args

    # When start=False, should have restart="no" and must_run=False
    assert call_args[1]["restart"] == "no"
    assert call_args[1]["must_run"] is False


@patch('clockwork.resources.docker.docker.Container')
def test_to_pulumi_port_internal_only(mock_container):
    """Test Pulumi resource creation with internal-only port."""
    mock_pulumi_container = Mock()
    mock_container.return_value = mock_pulumi_container

    container = DockerResource(
        name="internal",
        description="Internal service",
        image="alpine:latest",
        ports=["3000"]  # Internal only, Docker assigns external
    )

    container.to_pulumi()

    call_args = mock_container.call_args
    ports = call_args[1]["ports"]

    assert len(ports) == 1
    assert ports[0].internal == 3000
    assert not hasattr(ports[0], 'external') or ports[0].external is None


def test_pydantic_validation():
    """Test Pydantic validation enforces required description field."""
    with pytest.raises(Exception):
        # Missing required 'description' field
        DockerResource(name="test")


def test_get_connection_context():
    """Test that connection context is properly generated."""
    container = DockerResource(
        name="postgres",
        description="Database",
        image="postgres:15",
        ports=["5432:5432"],
        env_vars={"POSTGRES_PASSWORD": "secret"},
        networks=["backend"]
    )

    context = container.get_connection_context()

    assert context["name"] == "postgres"
    assert context["type"] == "DockerResource"
    assert context["image"] == "postgres:15"
    assert context["ports"] == ["5432:5432"]
    assert context["env_vars"] == {"POSTGRES_PASSWORD": "secret"}
    assert context["networks"] == ["backend"]
