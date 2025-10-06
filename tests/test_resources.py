"""Tests for resource models."""

import pytest
from clockwork.resources import Resource, FileResource, ArtifactSize


def test_artifact_size_enum():
    """Test ArtifactSize enum values."""
    assert ArtifactSize.SMALL == "small"
    assert ArtifactSize.MEDIUM == "medium"
    assert ArtifactSize.LARGE == "large"


def test_file_resource_needs_generation():
    """Test FileResource.needs_artifact_generation()."""
    # Resource without content needs generation
    file1 = FileResource(
        name="test.md",
        description="Test file",
        size=ArtifactSize.SMALL
    )
    assert file1.needs_artifact_generation() is True

    # Resource with content doesn't need generation
    file2 = FileResource(
        name="test.md",
        description="Test file",
        size=ArtifactSize.SMALL,
        content="existing content"
    )
    assert file2.needs_artifact_generation() is False


def test_file_resource_to_pyinfra_operations():
    """Test FileResource.to_pyinfra_operations()."""
    file = FileResource(
        name="example.txt",
        description="Example file",
        size=ArtifactSize.SMALL,
        path="/tmp/example.txt"
    )

    artifacts = {"example.txt": "Hello World"}
    operations = file.to_pyinfra_operations(artifacts)

    assert "files.put" in operations
    assert "example.txt" in operations
    assert "/tmp/example.txt" in operations
    assert "Hello World" in operations


def test_file_resource_default_path():
    """Test FileResource default path generation."""
    file = FileResource(
        name="test.md",
        description="Test",
        size=ArtifactSize.SMALL
    )

    operations = file.to_pyinfra_operations({})
    assert "/tmp/test.md" in operations


def test_file_resource_user_content():
    """Test FileResource with user-provided content."""
    user_content = "User provided content"
    file = FileResource(
        name="user.txt",
        description="Not used",
        size=ArtifactSize.SMALL,
        content=user_content
    )

    operations = file.to_pyinfra_operations({})
    assert user_content in operations


def test_file_resource_escape_content():
    """Test FileResource properly escapes special characters."""
    file = FileResource(
        name="special.txt",
        description="File with special chars",
        size=ArtifactSize.SMALL,
        content='Line with "quotes" and \n newlines'
    )

    operations = file.to_pyinfra_operations({})
    # Should escape quotes and newlines for Python string
    assert '\\"' in operations or '"quotes"' in operations
    assert '\\n' in operations


def test_file_resource_modes():
    """Test FileResource with different permission modes."""
    file = FileResource(
        name="exec.sh",
        description="Executable script",
        size=ArtifactSize.SMALL,
        mode="755"
    )

    operations = file.to_pyinfra_operations({})
    assert 'mode="755"' in operations


def test_file_resource_artifact_priority():
    """Test that artifacts override user-provided content."""
    file = FileResource(
        name="override.txt",
        description="Test priority",
        size=ArtifactSize.SMALL,
        content="user content"
    )

    # Artifact should take priority
    artifacts = {"override.txt": "AI generated content"}
    operations = file.to_pyinfra_operations(artifacts)
    assert "AI generated content" in operations
    assert "user content" not in operations
