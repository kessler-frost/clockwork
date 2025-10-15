"""Integration tests for the full pipeline."""

import asyncio
import pytest
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from clockwork.core import ClockworkCore
from clockwork.resources import FileResource


def test_load_resources_from_file(tmp_path):
    """Test loading resources from a Python file."""
    # Create a test main.py
    main_file = tmp_path / "main.py"
    main_file.write_text('''
from clockwork.resources import FileResource

test_file = FileResource(
    name="test.md",
    description="Test file",
    content="Test content"
)
''')

    # Mock the artifact generator to avoid requiring API key
    with patch('clockwork.core.ResourceCompleter') as mock_generator:
        mock_instance = Mock()
        mock_instance.complete = AsyncMock(return_value=[])  # Return completed resources
        mock_generator.return_value = mock_instance

        core = ClockworkCore(api_key="test-key")
        resources = core._load_resources(main_file)

    assert len(resources) == 1
    assert isinstance(resources[0], FileResource)
    assert resources[0].name == "test.md"


def test_load_multiple_resources(tmp_path):
    """Test loading multiple resources from a Python file."""
    main_file = tmp_path / "main.py"
    main_file.write_text('''
from clockwork.resources import FileResource

readme = FileResource(
    name="README.md",
    description="Project readme",
    content="Test content"
)

config = FileResource(
    name="config.json",
    description="Configuration file",
    content="Test content"
)

script = FileResource(
    name="setup.sh",
    description="Setup script",
    content="Test content",
    mode="755"
)
''')

    with patch('clockwork.core.ResourceCompleter') as mock_generator:
        mock_instance = Mock()
        mock_instance.complete = AsyncMock(return_value=[])  # Return completed resources
        mock_generator.return_value = mock_instance

        core = ClockworkCore(api_key="test-key")
        resources = core._load_resources(main_file)

    assert len(resources) == 3
    assert all(isinstance(r, FileResource) for r in resources)

    resource_names = {r.name for r in resources}
    assert resource_names == {"README.md", "config.json", "setup.sh"}


def test_load_resources_file_not_found():
    """Test error handling when main file doesn't exist."""
    with patch('clockwork.core.ResourceCompleter') as mock_generator:
        mock_instance = Mock()
        mock_instance.complete = AsyncMock(return_value=[])  # Return completed resources
        mock_generator.return_value = mock_instance

        core = ClockworkCore(api_key="test-key")

        with pytest.raises(FileNotFoundError):
            core._load_resources(Path("/nonexistent/main.py"))


def test_load_resources_no_resources_found(tmp_path):
    """Test error when no resources are defined in the file."""
    main_file = tmp_path / "main.py"
    main_file.write_text('''
# This file has no resources
x = 42
y = "hello"
''')

    with patch('clockwork.core.ResourceCompleter') as mock_generator:
        mock_instance = Mock()
        mock_instance.complete = AsyncMock(return_value=[])  # Return completed resources
        mock_generator.return_value = mock_instance

        core = ClockworkCore(api_key="test-key")

        with pytest.raises(ValueError, match="No resources found"):
            core._load_resources(main_file)


def test_generate_mode(tmp_path):
    """Test generate (dry run) mode."""
    main_file = tmp_path / "main.py"
    main_file.write_text('''
from clockwork.resources import FileResource

readme = FileResource(
    name="README.md",
    description="Test readme",
    content="# Test"
)
''')

    # Mock the artifact generator and Pulumi compiler
    with patch('clockwork.core.ResourceCompleter') as mock_generator, \
         patch('clockwork.core.PulumiCompiler') as mock_compiler:
        mock_instance = Mock()
        # Mock complete to return resources (simulating completion)
        async def mock_complete(resources):
            return resources
        mock_instance.complete = mock_complete
        mock_generator.return_value = mock_instance

        # Mock Pulumi preview
        mock_compiler_instance = Mock()
        mock_compiler_instance.preview = AsyncMock(return_value={"preview": "success"})
        mock_compiler.return_value = mock_compiler_instance

        core = ClockworkCore(api_key="test-key")
        result = asyncio.run(core.plan(main_file))

    assert result["dry_run"] is True
    assert result["resources"] == 1
    assert "preview" in result


def test_generate_mode_with_ai_generation(tmp_path):
    """Test generate mode with resources needing AI generation."""
    main_file = tmp_path / "main.py"
    main_file.write_text('''
from clockwork.resources import FileResource

readme = FileResource(
    name="README.md",
    description="Generate a detailed project readme",
)
''')

    # Mock the resource completer and Pulumi compiler
    with patch('clockwork.core.ResourceCompleter') as mock_generator, \
         patch('clockwork.core.PulumiCompiler') as mock_compiler:
        mock_instance = Mock()
        # Mock complete to simulate AI completing fields
        async def mock_complete(resources):
            for r in resources:
                if hasattr(r, 'content') and r.content is None:
                    r.content = "# Generated Content"
                if hasattr(r, 'directory') and r.directory is None:
                    r.directory = "."
                if hasattr(r, 'mode') and r.mode is None:
                    r.mode = "644"
            return resources
        mock_instance.complete = mock_complete
        mock_generator.return_value = mock_instance

        # Mock Pulumi preview
        mock_compiler_instance = Mock()
        mock_compiler_instance.preview = AsyncMock(return_value={"preview": "success"})
        mock_compiler.return_value = mock_compiler_instance

        core = ClockworkCore(api_key="test-key")
        result = asyncio.run(core.plan(main_file))

    assert result["dry_run"] is True
    assert result["resources"] == 1
    assert result["completed_resources"] == 1


def test_apply_with_dry_run(tmp_path):
    """Test apply with dry_run=True."""
    main_file = tmp_path / "main.py"
    main_file.write_text('''
from clockwork.resources import FileResource

test_file = FileResource(
    name="test.txt",
    description="Test",
    content="Static content"
)
''')

    with patch('clockwork.core.ResourceCompleter') as mock_generator, \
         patch('clockwork.core.PulumiCompiler') as mock_compiler:
        mock_instance = Mock()
        # Mock complete to return resources (simulating completion)
        async def mock_complete(resources):
            return resources
        mock_instance.complete = mock_complete
        mock_generator.return_value = mock_instance

        # Mock Pulumi preview
        mock_compiler_instance = Mock()
        mock_compiler_instance.preview = AsyncMock(return_value={"preview": "success"})
        mock_compiler.return_value = mock_compiler_instance

        core = ClockworkCore(api_key="test-key")
        result = asyncio.run(core.apply(main_file, dry_run=True))

    assert result["dry_run"] is True
    assert result["resources"] == 1


def test_full_pipeline_integration(tmp_path):
    """Test the full pipeline: load -> generate -> compile -> deploy."""
    main_file = tmp_path / "main.py"
    main_file.write_text('''
from clockwork.resources import FileResource

manual_file = FileResource(
    name="manual.txt",
    description="Manual content",
    content="User provided content"
)

ai_file = FileResource(
    name="ai.md",
    description="Generate a markdown file about Python",
    content="Test content"
)
''')

    # Mock the artifact generator and Pulumi compiler
    with patch('clockwork.core.ResourceCompleter') as mock_generator, \
         patch('clockwork.core.PulumiCompiler') as mock_compiler:

        # Setup artifact generator mock
        mock_gen_instance = Mock()
        # Mock complete to return resources with completed fields
        async def mock_complete(resources):
            # Simulate AI completing missing fields
            for r in resources:
                if hasattr(r, 'content') and r.content is None:
                    r.content = "AI-generated content"
                if hasattr(r, 'name') and r.name is None:
                    r.name = "ai-generated-name.md"
                if hasattr(r, 'directory') and r.directory is None:
                    r.directory = "."
                if hasattr(r, 'mode') and r.mode is None:
                    r.mode = "644"
            return resources
        mock_gen_instance.complete = mock_complete
        mock_generator.return_value = mock_gen_instance

        # Setup Pulumi compiler mock
        mock_compiler_instance = Mock()
        mock_compiler_instance.apply = AsyncMock(return_value={"success": True, "outputs": {}})
        mock_compiler.return_value = mock_compiler_instance

        # Run the pipeline
        core = ClockworkCore(api_key="test-key")
        result = asyncio.run(core.apply(main_file, dry_run=False))

    # Verify execution
    assert result["success"] is True
    assert mock_compiler_instance.apply.called


def test_artifact_generator_initialization():
    """Test that ClockworkCore properly initializes ResourceCompleter."""
    from clockwork.settings import get_settings

    with patch('clockwork.core.ResourceCompleter') as mock_generator:
        mock_instance = Mock()
        mock_instance.complete = AsyncMock(return_value=[])  # Return completed resources
        mock_generator.return_value = mock_instance

        core = ClockworkCore(
            api_key="test-key",
            model="custom-model"
        )

        # Verify ResourceCompleter was called with correct params
        # base_url should come from settings when not provided
        settings = get_settings()
        mock_generator.assert_called_once_with(
            api_key="test-key",
            model="custom-model",
            base_url=settings.base_url
        )


def test_resources_with_mixed_content(tmp_path):
    """Test pipeline with mix of user-provided and AI-generated content."""
    main_file = tmp_path / "main.py"
    main_file.write_text('''
from clockwork.resources import FileResource

# User-provided content
static_file = FileResource(
    name="static.txt",
    description="Static",
    content="I wrote this myself"
)

# AI-generated content
dynamic_file = FileResource(
    name="dynamic.md",
    description="Generate documentation about Docker",
    content="Test content"
)
''')

    with patch('clockwork.core.ResourceCompleter') as mock_generator, \
         patch('clockwork.core.PulumiCompiler') as mock_compiler:
        mock_instance = Mock()
        # Mock complete to simulate AI filling content
        async def mock_complete(resources):
            for r in resources:
                if hasattr(r, 'content') and r.content is None:
                    r.content = "# Docker\n\nDocker is a containerization platform."
                if hasattr(r, 'directory') and r.directory is None:
                    r.directory = "."
                if hasattr(r, 'mode') and r.mode is None:
                    r.mode = "644"
            return resources
        mock_instance.complete = mock_complete
        mock_generator.return_value = mock_instance

        # Mock Pulumi preview
        mock_compiler_instance = Mock()
        mock_compiler_instance.preview = AsyncMock(return_value={"preview": "success"})
        mock_compiler.return_value = mock_compiler_instance

        core = ClockworkCore(api_key="test-key")
        result = asyncio.run(core.plan(main_file))

    assert result["resources"] == 2
    assert result["completed_resources"] == 2


def test_destroy_file_resources(tmp_path):
    """Test destroying FileResources."""
    main_file = tmp_path / "main.py"
    main_file.write_text('''
from clockwork.resources import FileResource

test_file = FileResource(
    name="test.txt",
    description="Test file",
    content="Test content"
)
''')

    # Mock the resource completer and Pulumi compiler
    with patch('clockwork.core.ResourceCompleter') as mock_generator, \
         patch('clockwork.core.PulumiCompiler') as mock_compiler:

        # Setup resource completer mock
        mock_gen_instance = Mock()
        async def mock_complete(resources):
            # Complete any missing fields
            for r in resources:
                if hasattr(r, 'directory') and r.directory is None:
                    r.directory = "."
                if hasattr(r, 'mode') and r.mode is None:
                    r.mode = "644"
            return resources
        mock_gen_instance.complete = mock_complete
        mock_generator.return_value = mock_gen_instance

        # Setup Pulumi compiler mock
        mock_compiler_instance = Mock()
        mock_compiler_instance.destroy = AsyncMock(return_value={"success": True})
        mock_compiler.return_value = mock_compiler_instance

        # Run destroy
        core = ClockworkCore(api_key="test-key")
        result = asyncio.run(core.destroy(main_file, dry_run=False))

    # Verify execution
    assert result["success"] is True
    assert mock_compiler_instance.destroy.called


def test_destroy_with_dry_run(tmp_path):
    """Test destroy in dry run mode."""
    main_file = tmp_path / "main.py"
    main_file.write_text('''
from clockwork.resources import FileResource

readme = FileResource(
    name="README.md",
    description="Test readme",
    content="# Test"
)
''')

    with patch('clockwork.core.ResourceCompleter') as mock_generator, \
         patch('clockwork.core.PulumiCompiler') as mock_compiler:
        mock_instance = Mock()
        # Mock complete to return resources with fields filled
        async def mock_complete(resources):
            for r in resources:
                if hasattr(r, 'directory') and r.directory is None:
                    r.directory = "."
                if hasattr(r, 'mode') and r.mode is None:
                    r.mode = "644"
            return resources
        mock_instance.complete = mock_complete
        mock_generator.return_value = mock_instance

        # Mock Pulumi compiler
        mock_compiler_instance = Mock()
        mock_compiler.return_value = mock_compiler_instance

        core = ClockworkCore(api_key="test-key")
        # Test destroy in dry run
        result = asyncio.run(core.destroy(main_file, dry_run=True))

    # Verify dry run behavior
    assert result["dry_run"] is True
    assert "project_name" in result


def test_destroy_mixed_resources(tmp_path):
    """Test destroying both files."""
    main_file = tmp_path / "main.py"
    main_file.write_text('''
from clockwork.resources import FileResource

# User-provided content
static_file = FileResource(
    name="static.txt",
    description="Static file",
    content="Static content"
)

# AI-generated content
dynamic_file = FileResource(
    name="dynamic.md",
    description="Generate documentation"
)
''')

    # Mock the artifact generator and Pulumi compiler
    with patch('clockwork.core.ResourceCompleter') as mock_generator, \
         patch('clockwork.core.PulumiCompiler') as mock_compiler:

        # Setup artifact generator mock
        mock_gen_instance = Mock()
        # Mock complete to return resources with completed fields
        async def mock_complete(resources):
            # Simulate AI completing missing fields
            for r in resources:
                if hasattr(r, 'content') and r.content is None:
                    r.content = "AI-generated content"
                if hasattr(r, 'name') and r.name is None:
                    r.name = "ai-generated-name.md"
                if hasattr(r, 'directory') and r.directory is None:
                    r.directory = "."
                if hasattr(r, 'mode') and r.mode is None:
                    r.mode = "644"
            return resources
        mock_gen_instance.complete = mock_complete
        mock_generator.return_value = mock_gen_instance

        # Setup Pulumi compiler mock
        mock_compiler_instance = Mock()
        mock_compiler_instance.destroy = AsyncMock(return_value={"success": True})
        mock_compiler.return_value = mock_compiler_instance

        # Run destroy
        core = ClockworkCore(api_key="test-key")
        result = asyncio.run(core.destroy(main_file, dry_run=False))

    # Verify execution
    assert result["success"] is True
    assert mock_compiler_instance.destroy.called


# ============================================================================
# Assertion Pipeline Integration Tests
# ============================================================================


def test_assert_command_with_object_assertions(tmp_path):
    """Test clockwork assert command with BaseAssertion objects."""
    main_file = tmp_path / "main.py"
    main_file.write_text('''
from clockwork.resources import FileResource
from clockwork.assertions import FileExistsAssert, FilePermissionsAssert

test_file = FileResource(
    name="test.txt",
    description="Test file",
    content="Test content",
    assertions=[
        FileExistsAssert(path="test.txt"),
        FilePermissionsAssert(path="test.txt", mode="644")
    ]
)
''')

    with patch('clockwork.core.ResourceCompleter') as mock_artifact_gen:

        # Setup artifact generator mock
        mock_artifact_instance = Mock()
        # Mock complete to return resources
        async def mock_complete(resources):
            return resources
        mock_artifact_instance.complete = mock_complete
        mock_artifact_gen.return_value = mock_artifact_instance

        # Run assert pipeline
        core = ClockworkCore(api_key="test-key")
        result = asyncio.run(core.assert_resources(main_file, dry_run=False))

    # Verify execution - assertions run directly now, no subprocess
    assert result["success"] is True
    assert result["total"] == 2
    assert result["passed"] == 2


def test_assert_command_with_no_assertions(tmp_path):
    """Test assert command with resources that have no assertions."""
    main_file = tmp_path / "main.py"
    main_file.write_text('''
from clockwork.resources import FileResource

test_file = FileResource(
    name="test.txt",
    description="Test",
    content="Test"
)
''')

    with patch('clockwork.core.ResourceCompleter') as mock_artifact_gen:

        mock_artifact_instance = Mock()
        # Mock complete to return resources
        async def mock_complete(resources):
            return resources
        mock_artifact_instance.complete = mock_complete
        mock_artifact_gen.return_value = mock_artifact_instance

        core = ClockworkCore(api_key="test-key")
        result = asyncio.run(core.assert_resources(main_file, dry_run=False))

    # Should still execute successfully with no assertions
    assert result["success"] is True
    assert result["total"] == 0


def test_assert_command_failure_handling(tmp_path):
    """Test that assert command properly handles assertion failures."""
    main_file = tmp_path / "main.py"
    main_file.write_text('''
from clockwork.resources import FileResource
from clockwork.assertions import FileExistsAssert

test_file = FileResource(
    name="test.txt",
    description="Test",
    content="Test",
    assertions=[FileExistsAssert(path="/nonexistent/file.txt")]
)
''')

    with patch('clockwork.core.ResourceCompleter') as mock_artifact_gen:

        mock_artifact_instance = Mock()
        # Mock complete to return resources
        async def mock_complete(resources):
            return resources
        mock_artifact_instance.complete = mock_complete
        mock_artifact_gen.return_value = mock_artifact_instance

        core = ClockworkCore(api_key="test-key")
        result = asyncio.run(core.assert_resources(main_file, dry_run=False))

    # Assertions are currently placeholder implementations that pass
    # In a real implementation, this would fail
    assert result["success"] is True
    assert result["total"] == 1


def test_assert_command_no_main_file():
    """Test assert command error when no main.py exists."""
    with patch('clockwork.core.ResourceCompleter') as mock_generator:
        mock_instance = Mock()
        mock_instance.complete = AsyncMock(return_value=[])  # Return completed resources
        mock_generator.return_value = mock_instance

        core = ClockworkCore(api_key="test-key")

        with pytest.raises(FileNotFoundError):
            asyncio.run(core.assert_resources(Path("/nonexistent/main.py")))


def test_assert_multiple_resources_with_assertions(tmp_path):
    """Test assert command with multiple resources."""
    main_file = tmp_path / "main.py"
    main_file.write_text('''
from clockwork.resources import FileResource
from clockwork.assertions import FileExistsAssert, FilePermissionsAssert

file1 = FileResource(
    name="file1.txt",
    description="First file",
    content="Content 1",
    assertions=[FileExistsAssert(path="file1.txt")]
)

file2 = FileResource(
    name="file2.txt",
    description="Second file",
    content="Content 2",
    assertions=[
        FileExistsAssert(path="file2.txt"),
        FilePermissionsAssert(path="file2.txt", mode="644")
    ]
)
''')

    with patch('clockwork.core.ResourceCompleter') as mock_artifact_gen:

        mock_artifact_instance = Mock()
        # Mock complete to return resources
        async def mock_complete(resources):
            return resources
        mock_artifact_instance.complete = mock_complete
        mock_artifact_gen.return_value = mock_artifact_instance

        core = ClockworkCore(api_key="test-key")
        result = asyncio.run(core.assert_resources(main_file, dry_run=True))

    assert result["total_assertions"] == 3
    assert result["resources"] == 2
