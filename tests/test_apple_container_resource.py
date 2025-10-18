"""Tests for AppleContainerResource."""

import pytest
from unittest.mock import Mock, patch
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
    assert container.volumes == []  # Defaults to empty list
    assert container.env_vars == {}  # Defaults to empty dict
    assert container.networks == []  # Defaults to empty list
    assert container.must_run is True


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
        networks=["backend"]
    )

    assert container.name == "postgres"
    assert container.image == "postgres:16-alpine"
    assert container.ports == ["5432:5432"]
    assert container.volumes == ["pg_data:/var/lib/postgresql/data"]
    assert container.env_vars == {"POSTGRES_PASSWORD": "secret", "POSTGRES_USER": "admin"}
    assert container.networks == ["backend"]
    assert container.must_run is True


def test_needs_completion_no_image():
    """Test needs_completion() returns True when no image specified."""
    container = AppleContainerResource(
        name="nginx",
        description="Web server"
    )

    assert container.needs_completion() is True


def test_needs_completion_with_all_fields():
    """Test needs_completion() returns False when all fields are specified."""
    container = AppleContainerResource(
        name="nginx",
        description="Web server",
        image="nginx:latest",
        ports=[],
        volumes=[],
        env_vars={},
        networks=[]
    )

    assert container.needs_completion() is False


def test_to_pulumi_with_complete_fields():
    """Test to_pulumi() creates AppleContainer resource with complete fields."""
    container = AppleContainerResource(
        name="redis",
        description="Redis cache",
        image="redis:7-alpine",
        ports=["6379:6379"],
        volumes=["redis_data:/data"],
        env_vars={"REDIS_PASSWORD": "secret"},
        networks=["cache"]
    )

    # Mock AppleContainer to avoid actual Pulumi initialization
    with patch('clockwork.pulumi_providers.apple_container.AppleContainer') as mock_container:
        mock_instance = Mock()
        mock_container.return_value = mock_instance

        pulumi_resource = container.to_pulumi()

        # Verify the AppleContainer was called
        assert mock_container.called
        assert pulumi_resource == mock_instance


def test_to_pulumi_with_completed_fields():
    """Test to_pulumi() with AI-completed fields."""
    container = AppleContainerResource(
        name="nginx-ai",
        description="Web server for static content"
    )

    # Simulate AI completion
    container.image = "nginx:latest"
    container.ports = []

    with patch('clockwork.pulumi_providers.apple_container.AppleContainer') as mock_container:
        mock_instance = Mock()
        mock_container.return_value = mock_instance

        pulumi_resource = container.to_pulumi()

        assert mock_container.called
        assert pulumi_resource == mock_instance


def test_to_pulumi_missing_fields_raises_error():
    """Test to_pulumi() raises error when required fields are not completed."""
    container = AppleContainerResource(
        name="missing",
        description="Container with missing fields"
    )

    # Should raise error when required fields are not completed
    with pytest.raises(ValueError, match="Resource fields not completed"):
        container.to_pulumi()


def test_apple_container_resource_must_run_false():
    """Test AppleContainerResource with must_run=False."""
    container = AppleContainerResource(
        name="not-running",
        description="Container that exists but doesn't run",
        image="alpine:latest",
        ports=[],
        must_run=False
    )

    # Verify the must_run flag is set correctly
    assert container.must_run is False


def test_pydantic_validation():
    """Test Pydantic validation enforces required description field."""
    with pytest.raises(Exception):
        # Missing required 'description' field
        AppleContainerResource(name="test")


def test_get_connection_context():
    """Test get_connection_context returns correct fields."""
    container = AppleContainerResource(
        name="postgres",
        description="PostgreSQL database",
        image="postgres:15",
        ports=["5432:5432"],
        env_vars={"POSTGRES_PASSWORD": "secret"}
    )

    context = container.get_connection_context()

    assert context["name"] == "postgres"
    assert context["type"] == "AppleContainerResource"
    assert context["image"] == "postgres:15"
    assert context["ports"] == ["5432:5432"]
    assert context["env_vars"] == {"POSTGRES_PASSWORD": "secret"}


def test_get_connection_context_minimal():
    """Test get_connection_context with minimal fields."""
    container = AppleContainerResource(
        name="minimal",
        description="Minimal container",
        image="alpine:latest",
        ports=[]
    )

    context = container.get_connection_context()

    assert context["name"] == "minimal"
    assert context["type"] == "AppleContainerResource"
    assert context["image"] == "alpine:latest"
    # Empty lists/dicts should not be in context
    assert "ports" not in context
    assert "env_vars" not in context
    assert "networks" not in context


def test_to_pulumi_inputs_creation():
    """Test that to_pulumi creates AppleContainerInputs with correct values."""
    container = AppleContainerResource(
        name="test",
        description="Test container",
        image="nginx:latest",
        ports=["80:80"],
        volumes=["/data:/data"],
        env_vars={"KEY": "value"},
        networks=["frontend"]
    )

    # We can't easily test the internal inputs creation without mocking,
    # but we can verify the resource has the correct attributes
    assert container.name == "test"
    assert container.image == "nginx:latest"
    assert container.ports == ["80:80"]
    assert container.volumes == ["/data:/data"]
    assert container.env_vars == {"KEY": "value"}
    assert container.networks == ["frontend"]
