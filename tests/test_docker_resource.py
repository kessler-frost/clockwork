"""Tests for DockerResource."""

from unittest.mock import Mock, patch

import pytest

from clockwork.resources import DockerResource


class TestDockerResourceBasic:
    """Test basic DockerResource instantiation."""

    def test_docker_resource_basic(self):
        """Test basic DockerResource instantiation."""
        container = DockerResource(
            name="test-container", description="Test container"
        )

        assert container.name == "test-container"
        assert container.description == "Test container"
        assert container.image is None
        assert container.ports is None
        assert container.volumes == []  # Defaults to empty list
        assert container.env_vars == {}  # Defaults to empty dict
        assert container.command is None
        assert container.networks == []  # Defaults to empty list
        assert container.must_run is True

    def test_docker_resource_with_image(self):
        """Test DockerResource with explicit image."""
        container = DockerResource(
            name="redis",
            description="Redis cache",
            image="redis:7-alpine",
            ports=["6379:6379"],
        )

        assert container.name == "redis"
        assert container.image == "redis:7-alpine"
        assert container.ports == ["6379:6379"]

    def test_docker_resource_full_config(self):
        """Test DockerResource with all parameters."""
        container = DockerResource(
            name="postgres",
            description="PostgreSQL database",
            image="postgres:16-alpine",
            ports=["5432:5432"],
            volumes=["pg_data:/var/lib/postgresql/data"],
            env_vars={
                "POSTGRES_PASSWORD": "secret",  # pragma: allowlist secret
                "POSTGRES_USER": "admin",
            },
            command="postgres -c shared_buffers=256MB",
            networks=["backend"],
        )

        assert container.name == "postgres"
        assert container.image == "postgres:16-alpine"
        assert container.ports == ["5432:5432"]
        assert container.volumes == ["pg_data:/var/lib/postgresql/data"]
        assert container.env_vars == {
            "POSTGRES_PASSWORD": "secret",  # pragma: allowlist secret
            "POSTGRES_USER": "admin",
        }
        assert container.command == "postgres -c shared_buffers=256MB"
        assert container.networks == ["backend"]
        assert container.must_run is True


class TestDockerResourceNeedsCompletion:
    """Test needs_completion() method."""

    def test_needs_completion_no_image(self):
        """Test needs_completion() returns True when no image specified."""
        container = DockerResource(name="nginx", description="Web server")

        assert container.needs_completion() is True

    def test_needs_completion_no_name(self):
        """Test needs_completion() returns True when no name specified."""
        container = DockerResource(
            description="Web server",
            image="nginx:alpine",
            ports=["80:80"],
        )

        assert container.needs_completion() is True

    def test_needs_completion_no_ports(self):
        """Test needs_completion() returns True when no ports specified."""
        container = DockerResource(
            name="nginx",
            description="Web server",
            image="nginx:alpine",
        )

        assert container.needs_completion() is True

    def test_needs_completion_with_all_fields(self):
        """Test needs_completion() returns False when all fields specified."""
        container = DockerResource(
            name="nginx",
            description="Web server",
            image="nginx:latest",
            ports=[],
            volumes=[],
            env_vars={},
            networks=[],
        )

        assert container.needs_completion() is False

    def test_needs_completion_empty_ports_is_complete(self):
        """Test needs_completion() returns False with empty ports list."""
        container = DockerResource(
            name="nginx",
            description="Web server",
            image="nginx:alpine",
            ports=[],
        )

        assert container.needs_completion() is False


class TestDockerResourceToPulumi:
    """Test to_pulumi() method."""

    def test_to_pulumi_with_complete_fields(self):
        """Test to_pulumi() creates DockerContainer resource."""
        container = DockerResource(
            name="redis",
            description="Redis cache",
            image="redis:7-alpine",
            ports=["6379:6379"],
            volumes=["redis_data:/data"],
            env_vars={"REDIS_PASSWORD": "secret"},  # pragma: allowlist secret
            networks=["cache"],
        )

        # Mock DockerContainer to avoid actual Pulumi initialization
        with patch(
            "clockwork.resources.docker_resource.DockerContainer"
        ) as mock_container:
            mock_instance = Mock()
            mock_container.return_value = mock_instance

            pulumi_resource = container.to_pulumi()

            # Verify the DockerContainer was called
            assert mock_container.called
            assert pulumi_resource == mock_instance

    def test_to_pulumi_with_completed_fields(self):
        """Test to_pulumi() with intelligently completed fields."""
        container = DockerResource(
            name="nginx-ai", description="Web server for static content"
        )

        # Simulate intelligent completion
        container.image = "nginx:latest"
        container.ports = []

        with patch(
            "clockwork.resources.docker_resource.DockerContainer"
        ) as mock_container:
            mock_instance = Mock()
            mock_container.return_value = mock_instance

            pulumi_resource = container.to_pulumi()

            assert mock_container.called
            assert pulumi_resource == mock_instance

    def test_to_pulumi_missing_fields_raises_error(self):
        """Test to_pulumi() raises error when required fields not completed."""
        container = DockerResource(
            name="missing", description="Container with missing fields"
        )

        # Should raise error when required fields are not completed
        with pytest.raises(ValueError, match="Resource fields not completed"):
            container.to_pulumi()

    def test_to_pulumi_missing_name_raises_error(self):
        """Test to_pulumi() raises error when name is missing."""
        container = DockerResource(
            description="Container without name",
            image="nginx:alpine",
        )

        with pytest.raises(ValueError, match="Resource fields not completed"):
            container.to_pulumi()

    def test_to_pulumi_with_command(self):
        """Test to_pulumi() with command field."""
        container = DockerResource(
            name="custom",
            description="Container with custom command",
            image="alpine:latest",
            ports=[],
            command="echo hello",
        )

        with patch(
            "clockwork.resources.docker_resource.DockerContainer"
        ) as mock_container:
            mock_instance = Mock()
            mock_container.return_value = mock_instance

            container.to_pulumi()

            assert mock_container.called
            # Verify the inputs included the command
            call_args = mock_container.call_args
            inputs = call_args.kwargs.get("inputs") or call_args[1].get(
                "inputs"
            )
            assert inputs.command == "echo hello"


class TestDockerResourceMustRun:
    """Test must_run flag behavior."""

    def test_docker_resource_must_run_default(self):
        """Test DockerResource defaults to must_run=True."""
        container = DockerResource(
            name="running",
            description="Container that should run",
            image="alpine:latest",
            ports=[],
        )

        assert container.must_run is True

    def test_docker_resource_must_run_false(self):
        """Test DockerResource with must_run=False."""
        container = DockerResource(
            name="not-running",
            description="Container that exists but doesn't run",
            image="alpine:latest",
            ports=[],
            must_run=False,
        )

        assert container.must_run is False


class TestDockerResourceConnectionContext:
    """Test get_connection_context() method."""

    def test_get_connection_context(self):
        """Test get_connection_context returns correct fields."""
        container = DockerResource(
            name="postgres",
            description="PostgreSQL database",
            image="postgres:15",
            ports=["5432:5432"],
            env_vars={
                "POSTGRES_PASSWORD": "testpass"  # pragma: allowlist secret
            },
        )

        context = container.get_connection_context()

        assert context["name"] == "postgres"
        assert context["type"] == "DockerResource"
        assert context["image"] == "postgres:15"
        assert context["ports"] == ["5432:5432"]
        assert context["env_vars"] == {
            "POSTGRES_PASSWORD": "testpass"
        }  # pragma: allowlist secret

    def test_get_connection_context_minimal(self):
        """Test get_connection_context with minimal fields."""
        container = DockerResource(
            name="minimal",
            description="Minimal container",
            image="alpine:latest",
            ports=[],
        )

        context = container.get_connection_context()

        assert context["name"] == "minimal"
        assert context["type"] == "DockerResource"
        assert context["image"] == "alpine:latest"
        # Empty lists/dicts should not be in context
        assert "ports" not in context
        assert "env_vars" not in context
        assert "networks" not in context
        assert "command" not in context

    def test_get_connection_context_with_command(self):
        """Test get_connection_context includes command when set."""
        container = DockerResource(
            name="custom",
            description="Container with command",
            image="alpine:latest",
            ports=["8080:80"],
            command="python app.py",
        )

        context = container.get_connection_context()

        assert context["name"] == "custom"
        assert context["type"] == "DockerResource"
        assert context["image"] == "alpine:latest"
        assert context["ports"] == ["8080:80"]
        assert context["command"] == "python app.py"

    def test_get_connection_context_with_networks(self):
        """Test get_connection_context includes networks when set."""
        container = DockerResource(
            name="networked",
            description="Container with networks",
            image="nginx:alpine",
            ports=["80:80"],
            networks=["frontend", "backend"],
        )

        context = container.get_connection_context()

        assert context["name"] == "networked"
        assert context["networks"] == ["frontend", "backend"]


class TestDockerResourceInputs:
    """Test DockerContainerInputs creation."""

    def test_to_pulumi_inputs_creation(self):
        """Test that to_pulumi creates inputs with correct values."""
        container = DockerResource(
            name="test",
            description="Test container",
            image="nginx:latest",
            ports=["80:80"],
            volumes=["/data:/data"],
            env_vars={"KEY": "value"},
            command="nginx -g 'daemon off;'",
            networks=["frontend"],
        )

        # Verify the resource has correct attributes
        assert container.name == "test"
        assert container.image == "nginx:latest"
        assert container.ports == ["80:80"]
        assert container.volumes == ["/data:/data"]
        assert container.env_vars == {"KEY": "value"}
        assert container.command == "nginx -g 'daemon off;'"
        assert container.networks == ["frontend"]


class TestPlatformDetection:
    """Test platform detection utilities."""

    def test_is_docker_available_with_docker(self):
        """Test is_docker_available when Docker is present."""
        from clockwork.platform import is_docker_available

        with (
            patch("shutil.which", return_value="/usr/bin/docker"),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = Mock(returncode=0)
            assert is_docker_available() is True

    def test_is_docker_available_without_docker(self):
        """Test is_docker_available when Docker is not present."""
        from clockwork.platform import is_docker_available

        with patch("shutil.which", return_value=None):
            assert is_docker_available() is False

    def test_is_docker_available_daemon_not_running(self):
        """Test is_docker_available when daemon is not running."""
        from clockwork.platform import is_docker_available

        with (
            patch("shutil.which", return_value="/usr/bin/docker"),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = Mock(returncode=1)
            assert is_docker_available() is False

    def test_get_container_runtime_docker(self):
        """Test get_container_runtime returns DOCKER when available."""
        from clockwork.platform import ContainerRuntime, get_container_runtime

        with (
            patch("clockwork.platform.is_docker_available", return_value=True),
            patch(
                "clockwork.platform.is_apple_containers_available",
                return_value=False,
            ),
        ):
            assert get_container_runtime() == ContainerRuntime.DOCKER

    def test_get_container_runtime_apple(self):
        """Test get_container_runtime returns APPLE_CONTAINERS."""
        from clockwork.platform import ContainerRuntime, get_container_runtime

        with (
            patch("clockwork.platform.is_docker_available", return_value=False),
            patch(
                "clockwork.platform.is_apple_containers_available",
                return_value=True,
            ),
        ):
            assert get_container_runtime() == ContainerRuntime.APPLE_CONTAINERS

    def test_get_container_runtime_none(self):
        """Test get_container_runtime returns NONE when nothing available."""
        from clockwork.platform import ContainerRuntime, get_container_runtime

        with (
            patch("clockwork.platform.is_docker_available", return_value=False),
            patch(
                "clockwork.platform.is_apple_containers_available",
                return_value=False,
            ),
        ):
            assert get_container_runtime() == ContainerRuntime.NONE

    def test_require_docker_available(self):
        """Test require_docker when Docker is available."""
        from clockwork.platform import require_docker

        with patch("clockwork.platform.is_docker_available", return_value=True):
            # Should not raise
            require_docker()

    def test_require_docker_unavailable(self):
        """Test require_docker raises when Docker is unavailable."""
        from clockwork.platform import require_docker

        with (
            patch("clockwork.platform.is_docker_available", return_value=False),
            pytest.raises(RuntimeError, match="Docker is required"),
        ):
            require_docker()


class TestDockerContainerProvider:
    """Test DockerContainerProvider methods."""

    def test_build_common_options(self):
        """Test _build_common_options builds correct options."""
        from clockwork.pulumi_providers.docker_container import (
            DockerContainerProvider,
        )

        provider = DockerContainerProvider()
        props = {
            "container_name": "test",
            "ports": ["8080:80"],
            "volumes": ["/data:/data"],
            "env_vars": {"KEY": "value"},
            "networks": ["frontend"],
            "labels": {"app": "test"},
        }

        options = provider._build_common_options(props)

        assert "--name" in options
        assert "test" in options
        assert "-p" in options
        assert "8080:80" in options
        assert "-v" in options
        assert "/data:/data" in options
        assert "-e" in options
        assert "KEY=value" in options
        assert "--network" in options
        assert "frontend" in options
        assert "--label" in options
        assert "app=test" in options

    def test_build_run_command(self):
        """Test _build_run_command builds correct command."""
        from clockwork.pulumi_providers.docker_container import (
            DockerContainerProvider,
        )

        provider = DockerContainerProvider()
        props = {
            "container_name": "nginx",
            "image": "nginx:alpine",
            "ports": ["80:80"],
            "volumes": [],
            "env_vars": {},
            "networks": [],
            "labels": {},
        }

        cmd = provider._build_run_command(props)

        assert cmd[0] == "docker"
        assert cmd[1] == "run"
        assert "-d" in cmd
        assert "--name" in cmd
        assert "nginx" in cmd
        assert "nginx:alpine" in cmd

    def test_build_run_command_with_command(self):
        """Test _build_run_command includes container command."""
        from clockwork.pulumi_providers.docker_container import (
            DockerContainerProvider,
        )

        provider = DockerContainerProvider()
        props = {
            "container_name": "custom",
            "image": "alpine:latest",
            "ports": [],
            "volumes": [],
            "env_vars": {},
            "networks": [],
            "labels": {},
            "command": "echo hello",
        }

        cmd = provider._build_run_command(props)

        assert "alpine:latest" in cmd
        # Command should be split and appended
        assert "echo" in cmd
        assert "hello" in cmd


def _docker_available() -> bool:
    """Return True if a working Docker daemon is reachable."""
    from clockwork.platform import is_docker_available

    return is_docker_available()


# Integration tests run against a real Docker daemon when one is reachable and
# are skipped cleanly otherwise (e.g. local dev / CI without Docker). They
# exercise the DockerContainerProvider lifecycle end-to-end.
@pytest.mark.skipif(
    not _docker_available(),
    reason="Docker daemon not available (live integration test)",
)
class TestDockerResourceIntegration:
    """Integration tests for DockerResource against a live Docker daemon."""

    @pytest.fixture
    def provider(self):
        """Provide a DockerContainerProvider instance."""
        from clockwork.pulumi_providers.docker_container import (
            DockerContainerProvider,
        )

        return DockerContainerProvider()

    def test_docker_container_lifecycle(self, provider):
        """Create, read, then delete a real container via the provider.

        Uses a long-lived, lightweight image (busybox sleep) so the container
        stays running between create and read.
        """
        from clockwork.pulumi_providers.docker_container import (
            DockerContainerInputs,
        )

        name = "clockwork-it-busybox"
        inputs = DockerContainerInputs(
            image="busybox:latest",
            container_name=name,
            command="sleep 3600",
        )
        props = inputs.model_dump()

        create_result = provider.create(props)
        try:
            assert create_result.id_  # docker returned a container id
            # read should report the container as running
            read_props = provider.read(create_result.id_, props)
            assert read_props.get("status") == "running"
        finally:
            # Always clean up the container, even if assertions fail
            provider.delete(create_result.id_, props)

        # After delete, read returns props unchanged (container gone)
        post = provider.read(create_result.id_, props)
        assert post.get("status") != "running"
