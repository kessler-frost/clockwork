"""Tests for FileConnection class."""

from clockwork.connections.file import FileConnection
from clockwork.resources.apple_container import AppleContainerResource
from clockwork.resources.file import FileResource


def test_file_connection_instantiation():
    """Test basic FileConnection instantiation."""
    connection = FileConnection(
        to_resource=None,
        mount_path="/data",
        volume_name="test-volume",
    )

    assert connection.mount_path == "/data"
    assert connection.volume_name == "test-volume"
    assert connection.read_only is False
    assert connection.create_volume is True
    assert connection.volume_size == "1G"


def test_file_connection_needs_completion_no_description():
    """Test needs_completion returns False when no description."""
    connection = FileConnection(
        to_resource=None,
        mount_path="/data",
        volume_name="test-volume",
    )

    assert connection.needs_completion() is False


def test_file_connection_needs_completion_missing_mount_path():
    """Test needs_completion returns True when mount_path is missing."""
    connection = FileConnection(
        to_resource=None,
        description="shared data volume",
        volume_name="test-volume",
    )

    assert connection.needs_completion() is True


def test_file_connection_needs_completion_missing_volume_name():
    """Test needs_completion returns True when volume_name is missing."""
    connection = FileConnection(
        to_resource=None,
        description="shared data volume",
        mount_path="/data",
        create_volume=True,
    )

    assert connection.needs_completion() is True


def test_file_connection_needs_completion_with_source_path():
    """Test needs_completion returns False when source_path is provided."""
    connection = FileConnection(
        to_resource=None,
        description="bind mount",
        mount_path="/data",
        source_path="/host/data",
        create_volume=False,
    )

    assert connection.needs_completion() is False


def test_file_connection_context():
    """Test get_connection_context returns correct info."""
    connection = FileConnection(
        to_resource=None,
        mount_path="/data",
        volume_name="test-volume",
        read_only=True,
        description="test connection",
    )

    context = connection.get_connection_context()

    assert context["connection_type"] == "file"
    assert context["mount_path"] == "/data"
    assert context["volume_name"] == "test-volume"
    assert context["read_only"] is True
    assert context["create_volume"] is True


def test_file_connection_with_apple_container_resource():
    """Test FileConnection modifies AppleContainerResource volumes."""
    container_res = AppleContainerResource(
        description="test container",
        name="test",
        image="nginx:alpine",
        ports=["80:80"],
    )

    connection = FileConnection(
        from_resource=container_res,
        to_resource=None,
        mount_path="/data",
        volume_name="test-volume",
        create_volume=False,  # Don't create to avoid Pulumi during test
    )

    # Call to_pulumi to trigger mount addition
    connection.to_pulumi()

    # Verify volume was added to AppleContainerResource
    assert len(container_res.volumes) == 1
    assert container_res.volumes[0] == "test-volume:/data"


def test_file_connection_with_file_resource():
    """Test FileConnection with FileResource as source."""
    file_res = FileResource(
        description="config file",
        name="config.yaml",
        directory="/tmp",
        content="test: value",
        mode="644",
    )

    container_res = AppleContainerResource(
        description="test container",
        name="test",
        image="nginx:alpine",
        ports=["80:80"],
    )

    connection = FileConnection(
        from_resource=container_res,
        to_resource=file_res,
        mount_path="/etc/config.yaml",
        read_only=True,
    )

    # Call to_pulumi to trigger mount addition
    connection.to_pulumi()

    # Verify volume was added to AppleContainerResource
    assert len(container_res.volumes) == 1
    assert container_res.volumes[0] == "/tmp/config.yaml:/etc/config.yaml:ro"


def test_file_connection_bind_mount():
    """Test FileConnection with bind mount."""
    container_res = AppleContainerResource(
        description="test container",
        name="test",
        image="nginx:alpine",
        ports=["80:80"],
    )

    connection = FileConnection(
        from_resource=container_res,
        to_resource=None,
        mount_path="/data",
        source_path="/host/data",
        create_volume=False,
    )

    # Call to_pulumi to trigger mount addition
    connection.to_pulumi()

    # Verify bind mount was added to AppleContainerResource
    assert len(container_res.volumes) == 1
    assert container_res.volumes[0] == "/host/data:/data"


def test_file_connection_read_only():
    """Test FileConnection with read_only flag."""
    container_res = AppleContainerResource(
        description="test container",
        name="test",
        image="nginx:alpine",
        ports=["80:80"],
    )

    connection = FileConnection(
        from_resource=container_res,
        to_resource=None,
        mount_path="/data",
        source_path="/host/data",
        read_only=True,
        create_volume=False,
    )

    # Call to_pulumi to trigger mount addition
    connection.to_pulumi()

    # Verify read-only mount was added
    assert len(container_res.volumes) == 1
    assert container_res.volumes[0] == "/host/data:/data:ro"
