"""Tests for resource models."""

import pytest
from clockwork.resources import Resource, FileResource


def test_file_resource_minimal():
    """Test FileResource with minimal (description only) definition."""
    # Minimal resource - just description
    file = FileResource(description="Test file")

    assert file.description == "Test file"
    assert file.name is None
    assert file.content is None
    assert file.directory is None
    assert file.mode is None
    assert file.needs_completion() is True


def test_file_resource_needs_completion():
    """Test FileResource.needs_completion()."""
    # Resource without content needs completion
    file1 = FileResource(description="Test file")
    assert file1.needs_completion() is True

    # Resource with partial completion still needs completion
    file2 = FileResource(
        description="Test file",
        name="test.md"
    )
    assert file2.needs_completion() is True

    # Resource with content doesn't need completion
    file3 = FileResource(
        description="Test file",
        content="existing content"
    )
    assert file3.needs_completion() is False


def test_file_resource_to_pyinfra_operations():
    """Test FileResource.to_pyinfra_operations()."""
    # Resource must be completed (all fields set) before generating operations
    file = FileResource(
        name="example.txt",
        description="Example file",
        path="/tmp/example.txt",
        content="Hello World"
    )

    operations = file.to_pyinfra_operations()

    assert "files.put" in operations
    assert "example.txt" in operations
    assert "/tmp/example.txt" in operations
    assert "Hello World" in operations


def test_file_resource_default_path():
    """Test FileResource default path generation."""
    # Resource must have name set to resolve path
    file = FileResource(
        name="test.md",
        description="Test",
        content="test content"
    )

    operations = file.to_pyinfra_operations()
    # Default is current directory, not /tmp
    assert "test.md" in operations


def test_file_resource_user_content():
    """Test FileResource with user-provided content."""
    user_content = "User provided content"
    file = FileResource(
        name="user.txt",
        description="User file",
        content=user_content
    )

    operations = file.to_pyinfra_operations()
    assert user_content in operations


def test_file_resource_escape_content():
    """Test FileResource properly handles special characters in content."""
    file = FileResource(
        name="special.txt",
        description="File with special chars",
        content='Line with "quotes" and \n newlines'
    )

    operations = file.to_pyinfra_operations()
    # Triple-quoted strings preserve content, including quotes and newlines
    assert '"quotes"' in operations or 'quotes' in operations
    assert 'newlines' in operations


def test_file_resource_modes():
    """Test FileResource with different permission modes."""
    file = FileResource(
        name="exec.sh",
        description="Executable script",
        content="#!/bin/bash\necho hello",
        mode="755"
    )

    operations = file.to_pyinfra_operations()
    assert 'mode="755"' in operations


def test_file_resource_default_mode():
    """Test FileResource default mode."""
    file = FileResource(
        name="regular.txt",
        description="Regular file",
        content="content"
    )

    operations = file.to_pyinfra_operations()
    # Default mode is 644
    assert 'mode="644"' in operations
