"""Tests for resource models."""

import asyncio

import pytest

from clockwork.resources import FileResource


@pytest.fixture(autouse=True)
def event_loop():
    """Create an event loop for each test (needed for Pulumi Output)."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop

    # Clean up pending tasks to avoid warnings
    try:
        # Cancel all pending tasks
        pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()
        # Run the loop one more time to process cancellations
        if pending:
            loop.run_until_complete(
                asyncio.gather(*pending, return_exceptions=True)
            )
    except Exception:
        pass
    finally:
        loop.close()


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
    file2 = FileResource(description="Test file", name="test.md")
    assert file2.needs_completion() is True

    # Resource with content doesn't need completion
    file3 = FileResource(description="Test file", content="existing content")
    assert file3.needs_completion() is False


def test_file_resource_to_pulumi():
    """Test FileResource.to_pulumi()."""
    # Resource must be completed (all fields set) before generating Pulumi resource
    file = FileResource(
        name="example.txt",
        description="Example file",
        path="/tmp/example.txt",
        content="Hello World",
    )

    # to_pulumi() should return a Pulumi File resource
    pulumi_resource = file.to_pulumi()
    assert pulumi_resource is not None
    assert hasattr(pulumi_resource, "path")
    assert hasattr(pulumi_resource, "content")
    assert hasattr(pulumi_resource, "mode")


def test_file_resource_default_path():
    """Test FileResource default path generation."""
    from pathlib import Path

    # Resource must have name set to resolve path
    file = FileResource(
        name="test.md", description="Test", content="test content"
    )

    file_path, _ = file._resolve_file_path()
    # Default is current directory
    assert "test.md" in file_path
    assert Path(file_path).name == "test.md"


def test_file_resource_user_content():
    """Test FileResource with user-provided content."""
    user_content = "User provided content"
    file = FileResource(
        name="user.txt", description="User file", content=user_content
    )

    assert file.content == user_content


def test_file_resource_escape_content():
    """Test FileResource properly handles special characters in content."""
    file = FileResource(
        name="special.txt",
        description="File with special chars",
        content='Line with "quotes" and \n newlines',
    )

    assert '"quotes"' in file.content or "quotes" in file.content
    assert "newlines" in file.content


def test_file_resource_modes():
    """Test FileResource with different permission modes."""
    file = FileResource(
        name="exec.sh",
        description="Executable script",
        content="#!/bin/bash\necho hello",
        mode="755",
    )

    assert file.mode == "755"


def test_file_resource_default_mode():
    """Test FileResource default mode."""
    file = FileResource(
        name="regular.txt", description="Regular file", content="content"
    )

    # Default mode should be used when creating Pulumi resource
    pulumi_resource = file.to_pulumi()
    assert pulumi_resource is not None
