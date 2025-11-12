"""Tests for ServiceMeshConnection."""

from clockwork.connections import ServiceMeshConnection
from clockwork.resources import AppleContainerResource


def test_service_mesh_connection_instantiation():
    """Test that ServiceMeshConnection can be instantiated."""
    api = AppleContainerResource(
        name="api-server",
        description="API backend",
        ports=["8000:8000"],
    )

    AppleContainerResource(
        name="web-frontend",
        description="Web frontend",
    )

    mesh = ServiceMeshConnection(
        to_resource=api,
        protocol="http",
        health_check_path="/health",
    )

    assert mesh.protocol == "http"
    assert mesh.health_check_path == "/health"
    assert mesh.to_resource == api


def test_service_mesh_port_discovery():
    """Test that port is discovered from to_resource."""
    api = AppleContainerResource(
        name="api-server",
        description="API backend",
        ports=["8000:8000"],
    )

    mesh = ServiceMeshConnection(
        to_resource=api,
        protocol="http",
    )

    # Port should be discovered
    mesh._discover_port()
    assert mesh.port == 8000


def test_service_mesh_port_discovery_simple_format():
    """Test port discovery with simple port format."""
    api = AppleContainerResource(
        name="api-server",
        description="API backend",
        ports=["8000"],
    )

    mesh = ServiceMeshConnection(
        to_resource=api,
        protocol="http",
    )

    mesh._discover_port()
    assert mesh.port == 8000


def test_service_mesh_service_name_setting():
    """Test that service_name is set to to_resource.name."""
    api = AppleContainerResource(
        name="api-server",
        description="API backend",
        ports=["8000:8000"],
    )

    mesh = ServiceMeshConnection(
        to_resource=api,
        protocol="http",
    )

    mesh._set_service_name()
    assert mesh.service_name == "api-server"


def test_service_mesh_url_injection():
    """Test that service URL is injected into from_resource."""
    api = AppleContainerResource(
        name="api-server",
        description="API backend",
        ports=["8000:8000"],
    )

    web = AppleContainerResource(
        name="web-frontend",
        description="Web frontend",
    )

    mesh = ServiceMeshConnection(
        from_resource=web,
        to_resource=api,
        protocol="http",
    )

    # Setup connection
    mesh._discover_port()
    mesh._set_service_name()
    mesh._inject_service_url()

    # Check environment variable was injected
    assert "API_SERVER_URL" in web.env_vars
    assert web.env_vars["API_SERVER_URL"] == "http://api-server:8000"


def test_service_mesh_needs_completion():
    """Test needs_completion logic."""
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

    # With description but has port and service_name - doesn't need completion
    mesh3 = ServiceMeshConnection(
        to_resource=api,
        description="API service connection",
        protocol="http",
        port=8000,
        service_name="api-server",
    )
    assert not mesh3.needs_completion()


def test_service_mesh_get_connection_context():
    """Test get_connection_context returns correct info."""
    api = AppleContainerResource(
        name="api-server",
        description="API backend",
        ports=["8000:8000"],
    )

    web = AppleContainerResource(
        name="web-frontend",
        description="Web frontend",
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

    assert context["type"] == "ServiceMeshConnection"
    assert context["protocol"] == "https"
    assert context["port"] == 8443
    assert context["service_name"] == "api-service"
    assert context["tls_enabled"] is True
    assert context["health_check_path"] == "/healthz"
    assert context["load_balancing"] == "least_conn"
    assert context["from_resource"] == "web-frontend"
    assert context["to_resource"] == "api-server"


def test_service_mesh_extract_port():
    """Test _extract_port helper method."""
    api = AppleContainerResource(
        name="api-server",
        description="API backend",
        ports=["8000:8000"],
    )

    mesh = ServiceMeshConnection(to_resource=api)

    # Test host:container format
    assert mesh._extract_port("8080:80") == 80
    assert mesh._extract_port("5432:5432") == 5432

    # Test simple port format
    assert mesh._extract_port("8000") == 8000
    assert mesh._extract_port("3000") == 3000
