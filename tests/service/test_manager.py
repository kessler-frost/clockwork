"""Tests for ProjectManager."""

import asyncio
from pathlib import Path
import pytest

from clockwork.service.manager import ProjectManager
from clockwork.resources import FileResource


@pytest.fixture
def test_resources():
    """Create test resources."""
    return [
        FileResource(
            name="test_file_1.txt",
            description="Test file 1",
            content="Hello world 1"
        ),
        FileResource(
            name="test_file_2.txt",
            description="Test file 2",
            content="Hello world 2"
        )
    ]


@pytest.mark.asyncio
async def test_register_project(test_resources):
    """Test project registration."""
    manager = ProjectManager()

    project_id = await manager.register_project(
        Path("test/main.py"),
        test_resources
    )

    assert project_id is not None
    assert isinstance(project_id, str)

    # Cleanup
    await manager.unregister_project(project_id)


@pytest.mark.asyncio
async def test_get_project(test_resources):
    """Test getting project by ID."""
    manager = ProjectManager()

    project_id = await manager.register_project(
        Path("test/main.py"),
        test_resources
    )

    project = await manager.get_project(project_id)

    assert project is not None
    assert project.project_id == project_id
    assert len(project.resources) == 2

    # Cleanup
    await manager.unregister_project(project_id)


@pytest.mark.asyncio
async def test_list_projects(test_resources):
    """Test listing all projects."""
    manager = ProjectManager()

    # Register multiple projects
    project_id_1 = await manager.register_project(
        Path("test1/main.py"),
        test_resources
    )
    project_id_2 = await manager.register_project(
        Path("test2/main.py"),
        test_resources
    )

    projects = await manager.list_projects()

    assert len(projects) >= 2
    project_ids = [p.project_id for p in projects]
    assert project_id_1 in project_ids
    assert project_id_2 in project_ids

    # Cleanup
    await manager.unregister_project(project_id_1)
    await manager.unregister_project(project_id_2)


@pytest.mark.asyncio
async def test_unregister_project(test_resources):
    """Test unregistering a project."""
    manager = ProjectManager()

    project_id = await manager.register_project(
        Path("test/main.py"),
        test_resources
    )

    success = await manager.unregister_project(project_id)
    assert success is True

    # Verify project is gone
    project = await manager.get_project(project_id)
    assert project is None

    # Try to unregister again
    success = await manager.unregister_project(project_id)
    assert success is False


@pytest.mark.asyncio
async def test_update_health_status(test_resources):
    """Test updating resource health status."""
    manager = ProjectManager()

    project_id = await manager.register_project(
        Path("test/main.py"),
        test_resources
    )

    # Update health status
    success = await manager.update_health_status(
        project_id,
        "test_file_1.txt",
        False
    )
    assert success is True

    # Verify status updated
    project = await manager.get_project(project_id)
    assert project.health_status["test_file_1.txt"] is False
    assert "test_file_1.txt" in project.last_check

    # Cleanup
    await manager.unregister_project(project_id)


@pytest.mark.asyncio
async def test_increment_remediation_attempt(test_resources):
    """Test incrementing remediation attempt counter."""
    manager = ProjectManager()

    project_id = await manager.register_project(
        Path("test/main.py"),
        test_resources
    )

    # Increment counter
    await manager.increment_remediation_attempt(project_id, "test_file_1.txt")
    await manager.increment_remediation_attempt(project_id, "test_file_1.txt")

    project = await manager.get_project(project_id)
    assert project.remediation_attempts["test_file_1.txt"] == 2

    # Cleanup
    await manager.unregister_project(project_id)


@pytest.mark.asyncio
async def test_reset_remediation_attempts(test_resources):
    """Test resetting remediation attempt counter."""
    manager = ProjectManager()

    project_id = await manager.register_project(
        Path("test/main.py"),
        test_resources
    )

    # Increment and reset
    await manager.increment_remediation_attempt(project_id, "test_file_1.txt")
    await manager.increment_remediation_attempt(project_id, "test_file_1.txt")

    success = await manager.reset_remediation_attempts(project_id, "test_file_1.txt")
    assert success is True

    project = await manager.get_project(project_id)
    assert project.remediation_attempts["test_file_1.txt"] == 0

    # Cleanup
    await manager.unregister_project(project_id)


@pytest.mark.asyncio
async def test_get_health_summary(test_resources):
    """Test getting health summary."""
    manager = ProjectManager()

    project_id = await manager.register_project(
        Path("test/main.py"),
        test_resources
    )

    # Mark one resource as unhealthy
    await manager.update_health_status(project_id, "test_file_1.txt", False)

    summary = await manager.get_health_summary(project_id)

    assert summary["total"] == 2
    assert summary["healthy"] == 1
    assert summary["unhealthy"] == 1

    # Cleanup
    await manager.unregister_project(project_id)
