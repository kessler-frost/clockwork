"""Tests for all Clockwork Connection types.

This module provides comprehensive tests for:
- DependencyConnection
- NetworkConnection
- DatabaseConnection
- FileConnection
- ServiceMeshConnection
"""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from clockwork.assertions import HealthcheckAssert
from clockwork.connections import (
    DatabaseConnection,
    DependencyConnection,
    FileConnection,
    NetworkConnection,
    ServiceMeshConnection,
)
from clockwork.resources import AppleContainerResource, FileResource


@pytest.fixture(autouse=True)
def event_loop():
    """Create an event loop for each test (needed for Pulumi Output)."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop

    # Clean up pending tasks to avoid warnings
    try:
        pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()
        if pending:
            loop.run_until_complete(
                asyncio.gather(*pending, return_exceptions=True)
            )
    except Exception:
        pass
    finally:
        loop.close()


# ========== DependencyConnection Tests ==========


class TestDependencyConnection:
    """Tests for DependencyConnection - simplest connection type."""

    def test_basic_instantiation(self):
        """Test DependencyConnection can be instantiated."""
        db = AppleContainerResource(
            description="postgres database",
            name="postgres",
            image="postgres:15",
            ports=["5432:5432"],
        )

        api = AppleContainerResource(
            description="api server",
            name="api",
            image="node:20",
            ports=["3000:3000"],
        )

        conn = DependencyConnection(from_resource=api, to_resource=db)

        assert conn.from_resource == api
        assert conn.to_resource == db
        assert conn.description is None

    def test_needs_completion_always_false(self):
        """Test DependencyConnection never needs AI completion."""
        db = AppleContainerResource(
            description="database", name="db", image="postgres:15"
        )
        api = AppleContainerResource(
            description="api", name="api", image="node:20"
        )

        # Without description
        conn1 = DependencyConnection(from_resource=api, to_resource=db)
        assert conn1.needs_completion() is False

        # With description
        conn2 = DependencyConnection(
            from_resource=api,
            to_resource=db,
            description="API depends on database",
        )
        assert conn2.needs_completion() is False

    def test_get_connection_context(self):
        """Test get_connection_context returns correct info."""
        db = AppleContainerResource(
            description="database", name="postgres", image="postgres:15"
        )
        api = AppleContainerResource(
            description="api", name="api", image="node:20"
        )

        conn = DependencyConnection(
            from_resource=api,
            to_resource=db,
            description="API depends on database",
        )

        context = conn.get_connection_context()

        assert context["type"] == "DependencyConnection"
        assert context["from_resource"] == "api"
        assert context["to_resource"] == "postgres"
        assert context["description"] == "API depends on database"

    def test_to_pulumi_returns_none(self):
        """Test to_pulumi returns None (no setup resources)."""
        db = AppleContainerResource(
            description="database", name="db", image="postgres:15"
        )
        api = AppleContainerResource(
            description="api", name="api", image="node:20"
        )

        conn = DependencyConnection(from_resource=api, to_resource=db)

        result = conn.to_pulumi()

        assert result is None

    def test_automatic_creation_via_connect(self):
        """Test DependencyConnection is auto-created by connect()."""
        db = AppleContainerResource(
            description="database", name="postgres", image="postgres:15"
        )
        api = AppleContainerResource(
            description="api", name="api", image="node:20"
        )

        # connect() should create a DependencyConnection internally
        api.connect(db)

        # Verify connection was stored
        assert len(api._connections) == 1
        assert isinstance(api._connections[0], DependencyConnection)


# ========== NetworkConnection Tests ==========


class TestNetworkConnection:
    """Tests for NetworkConnection - creates container networks."""

    def test_instantiation_with_all_fields(self):
        """Test NetworkConnection with network name specified."""
        db = AppleContainerResource(
            description="test", name="postgres", image="postgres:15"
        )

        conn = NetworkConnection(
            to_resource=db,
            network_name="backend-network",
        )

        assert conn.network_name == "backend-network"

    def test_needs_completion_logic(self):
        """Test needs_completion returns True when network_name is missing."""
        db = AppleContainerResource(
            description="test", name="postgres", image="postgres:15"
        )

        # With description but no network_name - needs completion
        conn1 = NetworkConnection(
            to_resource=db,
            description="backend network for API and database",
        )
        assert conn1.needs_completion() is True

        # With network_name - doesn't need completion
        conn2 = NetworkConnection(
            to_resource=db,
            network_name="backend-network",
        )
        assert conn2.needs_completion() is False

        # Without description - doesn't need completion
        conn3 = NetworkConnection(to_resource=db)
        assert conn3.needs_completion() is False

    def test_get_connection_context(self):
        """Test get_connection_context returns network details."""
        db = AppleContainerResource(
            description="test", name="postgres", image="postgres:15"
        )
        api = AppleContainerResource(
            description="test", name="api", image="node:20"
        )

        conn = NetworkConnection(
            from_resource=api,
            to_resource=db,
            network_name="backend-network",
        )

        context = conn.get_connection_context()

        assert context["type"] == "NetworkConnection"
        assert context["network_name"] == "backend-network"
        assert context["from_resource"] == "api"
        assert context["to_resource"] == "postgres"

    @patch("pulumi_command.local.Command")
    def test_network_creation(self, mock_command):
        """Test NetworkConnection creates container network."""
        db = AppleContainerResource(
            description="test", name="postgres", image="postgres:15"
        )
        api = AppleContainerResource(
            description="test", name="api", image="node:20"
        )

        conn = NetworkConnection(
            from_resource=api,
            to_resource=db,
            network_name="backend-network",
        )

        # Mock the network creation
        mock_command_instance = MagicMock()
        mock_command.return_value = mock_command_instance

        resources = conn.to_pulumi()

        # Verify network was created via command
        mock_command.assert_called_once()
        call_args = mock_command.call_args

        # Check the command resource name
        assert call_args[0][0] == "network-backend-network"
        # Check create command
        assert (
            "container network create backend-network" in call_args[1]["create"]
        )
        # Check delete command
        assert "container network rm backend-network" in call_args[1]["delete"]

        # Verify resources returned
        assert resources is not None
        assert len(resources) == 1

    def test_resource_modification_adding_to_networks(self):
        """Test that connection adds network to both resources."""
        db = AppleContainerResource(
            description="test", name="postgres", image="postgres:15"
        )
        api = AppleContainerResource(
            description="test", name="api", image="node:20"
        )

        conn = NetworkConnection(
            from_resource=api,
            to_resource=db,
            network_name="backend-network",
        )

        # Mock Pulumi Command to avoid actual resource creation
        with patch("pulumi_command.local.Command"):
            conn.to_pulumi()

        # Verify network was added to both resources
        assert "backend-network" in api.networks
        assert "backend-network" in db.networks

    def test_hostname_injection(self):
        """Test that connection injects hostname env vars."""
        db = AppleContainerResource(
            description="test", name="postgres-db", image="postgres:15"
        )
        api = AppleContainerResource(
            description="test", name="api-server", image="node:20"
        )

        conn = NetworkConnection(
            from_resource=api,
            to_resource=db,
            network_name="backend-network",
        )

        # Mock Pulumi Command
        with patch("pulumi_command.local.Command"):
            conn.to_pulumi()

        # Verify hostname env vars were injected
        assert "POSTGRES_DB_HOST" in api.env_vars
        assert api.env_vars["POSTGRES_DB_HOST"] == "postgres-db"

        assert "API_SERVER_HOST" in db.env_vars
        assert db.env_vars["API_SERVER_HOST"] == "api-server"

    def test_network_missing_network_name_raises_error(self):
        """Test that to_pulumi raises error if network_name not set."""
        db = AppleContainerResource(
            description="test", name="postgres", image="postgres:15"
        )

        conn = NetworkConnection(to_resource=db)

        with pytest.raises(ValueError, match="network_name must be set"):
            conn.to_pulumi()


# ========== DatabaseConnection Tests ==========


class TestDatabaseConnection:
    """Tests for DatabaseConnection - database setup with migrations."""

    def test_instantiation(self):
        """Test DatabaseConnection can be instantiated."""
        db = AppleContainerResource(
            description="postgres database",
            name="postgres",
            image="postgres:15",
            ports=["5432:5432"],
        )

        conn = DatabaseConnection(
            to_resource=db,
            connection_string_template="postgresql://{user}:{password}@{host}:{port}/{database}",
            username="postgres",
            password="secret",  # pragma: allowlist secret
            database_name="myapp",
        )

        assert conn.username == "postgres"
        assert conn.password == "secret"  # pragma: allowlist secret
        assert conn.database_name == "myapp"
        assert conn.env_var_name == "DATABASE_URL"

    def test_connection_string_generation(self):
        """Test connection string is generated correctly."""
        db = AppleContainerResource(
            description="postgres database",
            name="postgres",
            image="postgres:15",
            ports=["5432:5432"],
        )

        conn = DatabaseConnection(
            to_resource=db,
            connection_string_template="postgresql://{user}:{password}@{host}:{port}/{database}",
            username="testuser",
            password="testpass",  # pragma: allowlist secret
            database_name="testdb",
        )

        connection_string = conn._build_connection_string()

        assert (
            connection_string
            == "postgresql://testuser:testpass@postgres:5432/testdb"  # pragma: allowlist secret
        )

    def test_needs_completion_logic(self):
        """Test needs_completion returns True when fields are missing."""
        db = AppleContainerResource(
            description="test", name="postgres", image="postgres:15"
        )

        # With description but no connection_string_template - needs completion
        conn1 = DatabaseConnection(
            to_resource=db,
            description="database connection",
        )
        assert conn1.needs_completion() is True

        # With connection_string_template - doesn't need completion
        conn2 = DatabaseConnection(
            to_resource=db,
            connection_string_template="postgresql://{user}:{password}@{host}:{port}/{database}",
        )
        assert conn2.needs_completion() is False

    def test_env_var_injection(self):
        """Test DATABASE_URL is injected into from_resource."""
        db = AppleContainerResource(
            description="postgres database",
            name="postgres",
            image="postgres:15",
            ports=["5432:5432"],
        )
        api = AppleContainerResource(
            description="test", name="api", image="node:20"
        )

        conn = DatabaseConnection(
            from_resource=api,
            to_resource=db,
            connection_string_template="postgresql://{user}:{password}@{host}:{port}/{database}",
            username="postgres",
            password="secret",  # pragma: allowlist secret
            database_name="myapp",
            wait_for_ready=False,  # Skip wait command for testing
        )

        # Mock pulumi commands
        with patch("pulumi_command.local.Command"):
            conn.to_pulumi()

        # Verify env var was injected
        assert "DATABASE_URL" in api.env_vars
        assert (
            api.env_vars["DATABASE_URL"]
            == "postgresql://postgres:secret@postgres:5432/myapp"  # pragma: allowlist secret
        )

    def test_custom_env_var_name(self):
        """Test custom environment variable name."""
        db = AppleContainerResource(
            description="test",
            name="postgres",
            image="postgres:15",
            ports=["5432:5432"],
        )
        api = AppleContainerResource(
            description="test", name="api", image="node:20"
        )

        conn = DatabaseConnection(
            from_resource=api,
            to_resource=db,
            connection_string_template="postgresql://{user}:{password}@{host}:{port}/{database}",
            env_var_name="DB_CONNECTION_STRING",
            username="postgres",
            password="secret",  # pragma: allowlist secret
            database_name="myapp",
            wait_for_ready=False,
        )

        with patch("pulumi_command.local.Command"):
            conn.to_pulumi()

        assert "DB_CONNECTION_STRING" in api.env_vars

    def test_port_extraction(self):
        """Test port is correctly extracted from ports list."""
        db = AppleContainerResource(
            description="postgres database",
            name="postgres",
            image="postgres:15",
            ports=["5433:5432"],
        )

        conn = DatabaseConnection(
            to_resource=db,
            connection_string_template="postgresql://{user}:{password}@{host}:{port}/{database}",
        )

        # Extract port
        port = conn._extract_port(["5433:5432"])
        assert port == "5432"

        # Simple format
        port2 = conn._extract_port(["5432"])
        assert port2 == "5432"

    def test_wait_for_ready_command(self):
        """Test wait-for-ready command is created."""
        db = AppleContainerResource(
            description="test",
            name="postgres",
            image="postgres:15",
            ports=["5432:5432"],
        )
        api = AppleContainerResource(
            description="test", name="api", image="node:20"
        )

        conn = DatabaseConnection(
            from_resource=api,
            to_resource=db,
            connection_string_template="postgresql://{user}:{password}@{host}:{port}/{database}",
            wait_for_ready=True,
            timeout=60,
        )

        with patch("pulumi_command.local.Command") as mock_cmd:
            conn.to_pulumi()

            # Verify wait command was created
            calls = mock_cmd.call_args_list
            assert len(calls) > 0

            # Check first call is wait-for-db
            first_call = calls[0]
            assert "wait-for-db" in first_call[0][0]

    def test_schema_file_execution(self, tmp_path):
        """Test schema file is executed if provided."""
        schema_file = tmp_path / "schema.sql"
        schema_file.write_text("CREATE TABLE users (id SERIAL PRIMARY KEY);")

        db = AppleContainerResource(
            description="test",
            name="postgres",
            image="postgres:15",
            ports=["5432:5432"],
        )
        api = AppleContainerResource(
            description="test", name="api", image="node:20"
        )

        conn = DatabaseConnection(
            from_resource=api,
            to_resource=db,
            connection_string_template="postgresql://{user}:{password}@{host}:{port}/{database}",
            schema_file=str(schema_file),
            wait_for_ready=False,
        )

        with patch("pulumi_command.local.Command") as mock_cmd:
            conn.to_pulumi()

            # Verify schema command was created
            calls = mock_cmd.call_args_list
            assert any("schema" in str(call) for call in calls)

    def test_migrations_execution(self, tmp_path):
        """Test migrations are executed if directory provided."""
        migrations_dir = tmp_path / "migrations"
        migrations_dir.mkdir()
        (migrations_dir / "001_initial.sql").write_text(
            "CREATE TABLE users (id SERIAL);"
        )
        (migrations_dir / "002_add_email.sql").write_text(
            "ALTER TABLE users ADD COLUMN email TEXT;"
        )

        db = AppleContainerResource(
            description="test",
            name="postgres",
            image="postgres:15",
            ports=["5432:5432"],
        )
        api = AppleContainerResource(
            description="test", name="api", image="node:20"
        )

        conn = DatabaseConnection(
            from_resource=api,
            to_resource=db,
            connection_string_template="postgresql://{user}:{password}@{host}:{port}/{database}",
            migrations_dir=str(migrations_dir),
            wait_for_ready=False,
        )

        with patch("pulumi_command.local.Command") as mock_cmd:
            conn.to_pulumi()

            # Verify migration commands were created
            calls = mock_cmd.call_args_list
            assert any("migration" in str(call) for call in calls)

    def test_get_connection_context(self):
        """Test get_connection_context returns database info."""
        db = AppleContainerResource(
            description="test", name="postgres", image="postgres:15"
        )

        conn = DatabaseConnection(
            to_resource=db,
            connection_string_template="postgresql://{user}:{password}@{host}:{port}/{database}",
            database_name="testdb",
            username="testuser",
            schema_file="schema.sql",
        )

        context = conn.get_connection_context()

        assert context["connection_type"] == "database"
        assert context["database_name"] == "testdb"
        assert context["username"] == "testuser"
        assert context["env_var_name"] == "DATABASE_URL"
        assert context["schema_file"] == "schema.sql"


# ========== FileConnection Tests ==========


class TestFileConnection:
    """Tests for FileConnection - file and volume sharing."""

    def test_volume_creation(self):
        """Test FileConnection creates container volume."""
        container_res = AppleContainerResource(
            description="test container",
            name="test",
            image="nginx:alpine",
            ports=["80:80"],
        )

        conn = FileConnection(
            from_resource=container_res,
            to_resource=None,
            mount_path="/data",
            volume_name="test-volume",
            create_volume=True,
        )

        with patch("pulumi_command.local.Command") as mock_command:
            conn.to_pulumi()

            # Verify volume was created via command
            mock_command.assert_called_once()
            call_args = mock_command.call_args
            assert call_args[0][0] == "volume-test-volume"

    def test_mount_configuration(self):
        """Test mount is added to container."""
        container_res = AppleContainerResource(
            description="test container",
            name="test",
            image="nginx:alpine",
            ports=["80:80"],
        )

        conn = FileConnection(
            from_resource=container_res,
            to_resource=None,
            mount_path="/data",
            volume_name="test-volume",
            create_volume=False,
        )

        conn.to_pulumi()

        # Verify mount was added
        assert len(container_res.volumes) == 1
        assert container_res.volumes[0] == "test-volume:/data"

    def test_needs_completion_logic(self):
        """Test needs_completion logic for FileConnection."""
        # No description - doesn't need completion
        conn1 = FileConnection(
            to_resource=None,
            mount_path="/data",
            volume_name="test-volume",
        )
        assert conn1.needs_completion() is False

        # Description but missing mount_path - needs completion
        conn2 = FileConnection(
            to_resource=None,
            description="shared data volume",
            volume_name="test-volume",
        )
        assert conn2.needs_completion() is True

        # Description but missing volume_name - needs completion
        conn3 = FileConnection(
            to_resource=None,
            description="shared data volume",
            mount_path="/data",
            create_volume=True,
        )
        assert conn3.needs_completion() is True

    def test_read_only_mounts(self):
        """Test read-only mount configuration."""
        container_res = AppleContainerResource(
            description="test container",
            name="test",
            image="nginx:alpine",
            ports=["80:80"],
        )

        conn = FileConnection(
            from_resource=container_res,
            to_resource=None,
            mount_path="/data",
            source_path="/host/data",
            read_only=True,
            create_volume=False,
        )

        conn.to_pulumi()

        # Verify read-only flag is set
        assert container_res.volumes[0] == "/host/data:/data:ro"

    def test_file_resource_mount(self):
        """Test FileConnection with FileResource."""
        file_res = FileResource(
            description="config file",
            name="config.yaml",
            directory="/tmp",
            content="test: value",
        )

        container_res = AppleContainerResource(
            description="test container",
            name="test",
            image="nginx:alpine",
            ports=["80:80"],
        )

        conn = FileConnection(
            from_resource=container_res,
            to_resource=file_res,
            mount_path="/etc/config.yaml",
            read_only=True,
        )

        conn.to_pulumi()

        # Verify bind mount was created
        assert len(container_res.volumes) == 1
        assert (
            container_res.volumes[0] == "/tmp/config.yaml:/etc/config.yaml:ro"
        )

    def test_bind_mount_with_source_path(self):
        """Test bind mount with explicit source_path."""
        container_res = AppleContainerResource(
            description="test container",
            name="test",
            image="nginx:alpine",
            ports=["80:80"],
        )

        conn = FileConnection(
            from_resource=container_res,
            to_resource=None,
            mount_path="/data",
            source_path="/host/data",
            create_volume=False,
        )

        conn.to_pulumi()

        assert container_res.volumes[0] == "/host/data:/data"

    def test_get_connection_context(self):
        """Test get_connection_context returns file connection info."""
        conn = FileConnection(
            to_resource=None,
            mount_path="/data",
            volume_name="test-volume",
            read_only=True,
            description="test connection",
        )

        context = conn.get_connection_context()

        assert context["connection_type"] == "file"
        assert context["mount_path"] == "/data"
        assert context["volume_name"] == "test-volume"
        assert context["read_only"] is True


# ========== ServiceMeshConnection Tests ==========


class TestServiceMeshConnection:
    """Tests for ServiceMeshConnection - service discovery and mesh."""

    def test_port_discovery(self):
        """Test port is discovered from to_resource."""
        api = AppleContainerResource(
            description="API backend",
            name="api-server",
            image="node:20",
            ports=["8000:8000"],
        )

        mesh = ServiceMeshConnection(
            to_resource=api,
            protocol="http",
        )

        mesh._discover_port()
        assert mesh.port == 8000

    def test_port_discovery_simple_format(self):
        """Test port discovery with simple port format."""
        api = AppleContainerResource(
            description="API backend",
            name="api-server",
            image="node:20",
            ports=["8000"],
        )

        mesh = ServiceMeshConnection(
            to_resource=api,
            protocol="http",
        )

        mesh._discover_port()
        assert mesh.port == 8000

    def test_service_url_injection(self):
        """Test service URL is injected into from_resource."""
        api = AppleContainerResource(
            description="API backend",
            name="api-server",
            image="node:20",
            ports=["8000:8000"],
        )

        web = AppleContainerResource(
            description="Web frontend",
            name="web-frontend",
            image="nginx:alpine",
        )

        mesh = ServiceMeshConnection(
            from_resource=web,
            to_resource=api,
            protocol="http",
        )

        mesh._discover_port()
        mesh._set_service_name()
        mesh._inject_service_url()

        assert "API_SERVER_URL" in web.env_vars
        assert web.env_vars["API_SERVER_URL"] == "http://api-server:8000"

    def test_health_check_assertion_creation(self):
        """Test health check assertion is created."""
        api = AppleContainerResource(
            description="API backend",
            name="api-server",
            image="node:20",
            ports=["8000:8000"],
        )

        web = AppleContainerResource(
            description="Web frontend",
            name="web-frontend",
            image="nginx:alpine",
        )

        mesh = ServiceMeshConnection(
            from_resource=web,
            to_resource=api,
            protocol="http",
            health_check_path="/healthz",
        )

        mesh._discover_port()
        mesh._set_service_name()
        mesh._add_health_check_assertion()

        assert mesh.assertions is not None
        assert len(mesh.assertions) == 1
        assert isinstance(mesh.assertions[0], HealthcheckAssert)
        assert mesh.assertions[0].url == "http://api-server:8000/healthz"

    def test_needs_completion_logic(self):
        """Test needs_completion returns True when fields are missing."""
        api = AppleContainerResource(
            name="api-server",
            description="API backend",
            ports=["8000:8000"],
        )

        # Without description - doesn't need completion
        mesh1 = ServiceMeshConnection(
            to_resource=api,
            protocol="http",
            port=8000,
            service_name="api-server",
        )
        assert not mesh1.needs_completion()

        # With description but missing port - needs completion
        mesh2 = ServiceMeshConnection(
            to_resource=api,
            description="API service connection",
            protocol="http",
        )
        assert mesh2.needs_completion()

    def test_tls_certificate_creation(self):
        """Test TLS certificates are created when TLS is enabled."""
        api = AppleContainerResource(
            description="API backend",
            name="api-server",
            image="node:20",
            ports=["8443:8443"],
        )

        mesh = ServiceMeshConnection(
            to_resource=api,
            protocol="https",
            tls_enabled=True,
        )

        mesh._set_service_name()
        mesh._create_tls_certificates()

        # Verify certificates were added to setup_resources
        assert len(mesh.setup_resources) == 2
        assert mesh.cert_path is not None
        assert mesh.key_path is not None

    def test_get_connection_context(self):
        """Test get_connection_context returns service mesh info."""
        api = AppleContainerResource(
            description="API backend", name="api-server", image="node:20"
        )
        web = AppleContainerResource(
            description="Web frontend",
            name="web-frontend",
            image="nginx:alpine",
        )

        mesh = ServiceMeshConnection(
            from_resource=web,
            to_resource=api,
            protocol="https",
            port=8443,
            service_name="api-service",
            tls_enabled=True,
            health_check_path="/healthz",
            load_balancing="least_conn",
        )

        context = mesh.get_connection_context()

        assert context["protocol"] == "https"
        assert context["port"] == 8443
        assert context["service_name"] == "api-service"
        assert context["tls_enabled"] is True
        assert context["health_check_path"] == "/healthz"
        assert context["load_balancing"] == "least_conn"

    def test_extract_port_helper(self):
        """Test _extract_port helper method."""
        api = AppleContainerResource(
            description="test",
            name="api-server",
            image="node:20",
            ports=["8000:8000"],
        )

        mesh = ServiceMeshConnection(to_resource=api)

        # Test host:container format
        assert mesh._extract_port("8080:80") == 80
        assert mesh._extract_port("5432:5432") == 5432

        # Test simple port format
        assert mesh._extract_port("8000") == 8000
        assert mesh._extract_port("3000") == 3000

    def test_full_to_pulumi_workflow(self):
        """Test complete to_pulumi workflow."""
        api = AppleContainerResource(
            description="API backend",
            name="api-server",
            image="node:20",
            ports=["8000:8000"],
        )

        web = AppleContainerResource(
            description="Web frontend",
            name="web-frontend",
            image="nginx:alpine",
        )

        mesh = ServiceMeshConnection(
            from_resource=web,
            to_resource=api,
            protocol="http",
            health_check_path="/health",
        )

        # to_pulumi should discover port, set service name, inject URL, and add health check
        mesh.to_pulumi()

        # Verify port was discovered
        assert mesh.port == 8000

        # Verify service name was set
        assert mesh.service_name == "api-server"

        # Verify URL was injected
        assert "API_SERVER_URL" in web.env_vars
        assert web.env_vars["API_SERVER_URL"] == "http://api-server:8000"

        # Verify health check was added
        assert mesh.assertions is not None
        assert len(mesh.assertions) == 1


# ========== Integration Tests ==========


class TestConnectionIntegration:
    """Integration tests across multiple connection types."""

    def test_multiple_connection_types_on_resource(self):
        """Test resource with multiple different connection types."""
        db = AppleContainerResource(
            description="test",
            name="postgres",
            image="postgres:15",
            ports=["5432:5432"],
        )
        cache = AppleContainerResource(
            description="test",
            name="redis",
            image="redis:7",
            ports=["6379:6379"],
        )
        api = AppleContainerResource(
            description="test", name="api", image="node:20", ports=["3000:3000"]
        )

        # Create different connection types
        db_conn = DatabaseConnection(
            from_resource=api,
            to_resource=db,
            connection_string_template="postgresql://{user}:{password}@{host}:{port}/{database}",
            wait_for_ready=False,
        )

        cache_conn = ServiceMeshConnection(
            from_resource=api,
            to_resource=cache,
            protocol="tcp",
        )

        with patch("pulumi_command.local.Command"):
            db_conn.to_pulumi()

        cache_conn.to_pulumi()

        # Verify both connections worked
        assert "DATABASE_URL" in api.env_vars
        assert "REDIS_URL" in api.env_vars

    def test_connection_context_inheritance(self):
        """Test that all connection types properly inherit from base Connection."""
        db = AppleContainerResource(
            description="test", name="postgres", image="postgres:15"
        )

        connections = [
            DependencyConnection(to_resource=db),
            NetworkConnection(to_resource=db, network_name="test-net"),
            DatabaseConnection(
                to_resource=db,
                connection_string_template="postgresql://{user}:{password}@{host}:{port}/{database}",
            ),
            FileConnection(
                to_resource=db, mount_path="/data", volume_name="test"
            ),
            ServiceMeshConnection(to_resource=db, port=5432),
        ]

        for conn in connections:
            context = conn.get_connection_context()
            assert "type" in context
            assert "to_resource" in context
            assert context["to_resource"] == "postgres"
