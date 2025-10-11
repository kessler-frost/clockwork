"""Integration tests for the full pipeline."""

import pytest
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from clockwork.core import ClockworkCore
from clockwork.resources import FileResource, ArtifactSize


def test_load_resources_from_file(tmp_path):
    """Test loading resources from a Python file."""
    # Create a test main.py
    main_file = tmp_path / "main.py"
    main_file.write_text('''
from clockwork.resources import FileResource, ArtifactSize

test_file = FileResource(
    name="test.md",
    description="Test file",
    size=ArtifactSize.SMALL
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
from clockwork.resources import FileResource, ArtifactSize

readme = FileResource(
    name="README.md",
    description="Project readme",
    size=ArtifactSize.MEDIUM
)

config = FileResource(
    name="config.json",
    description="Configuration file",
    size=ArtifactSize.SMALL
)

script = FileResource(
    name="setup.sh",
    description="Setup script",
    size=ArtifactSize.SMALL,
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
from clockwork.resources import FileResource, ArtifactSize

readme = FileResource(
    name="README.md",
    description="Test readme",
    size=ArtifactSize.SMALL,
    content="# Test"
)
''')

    # Mock the artifact generator
    with patch('clockwork.core.ResourceCompleter') as mock_generator:
        mock_instance = Mock()
        # Mock complete to return resources (simulating completion)
        async def mock_complete(resources):
            return resources
        mock_instance.complete = mock_complete
        mock_generator.return_value = mock_instance

        core = ClockworkCore(api_key="test-key")
        result = core.plan(main_file)

    assert result["dry_run"] is True
    assert result["resources"] == 1
    assert "pyinfra_dir" in result


def test_generate_mode_with_ai_generation(tmp_path):
    """Test generate mode with resources needing AI generation."""
    main_file = tmp_path / "main.py"
    main_file.write_text('''
from clockwork.resources import FileResource, ArtifactSize

readme = FileResource(
    name="README.md",
    description="Generate a detailed project readme",
    size=ArtifactSize.LARGE
)
''')

    # Mock the resource completer
    with patch('clockwork.core.ResourceCompleter') as mock_generator:
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

        core = ClockworkCore(api_key="test-key")
        result = core.plan(main_file)

    assert result["dry_run"] is True
    assert result["resources"] == 1
    assert result["completed_resources"] == 1


def test_apply_with_dry_run(tmp_path):
    """Test apply with dry_run=True."""
    main_file = tmp_path / "main.py"
    main_file.write_text('''
from clockwork.resources import FileResource, ArtifactSize

test_file = FileResource(
    name="test.txt",
    description="Test",
    size=ArtifactSize.SMALL,
    content="Static content"
)
''')

    with patch('clockwork.core.ResourceCompleter') as mock_generator:
        mock_instance = Mock()
        # Mock complete to return resources (simulating completion)
        async def mock_complete(resources):
            return resources
        mock_instance.complete = mock_complete
        mock_generator.return_value = mock_instance

        core = ClockworkCore(api_key="test-key")
        result = core.apply(main_file, dry_run=True)

    assert result["dry_run"] is True
    assert result["resources"] == 1


def test_full_pipeline_integration(tmp_path):
    """Test the full pipeline: load -> generate -> compile -> deploy."""
    main_file = tmp_path / "main.py"
    main_file.write_text('''
from clockwork.resources import FileResource, ArtifactSize

manual_file = FileResource(
    name="manual.txt",
    description="Manual content",
    size=ArtifactSize.SMALL,
    content="User provided content"
)

ai_file = FileResource(
    name="ai.md",
    description="Generate a markdown file about Python",
    size=ArtifactSize.SMALL
)
''')

    # Mock the artifact generator and PyInfra execution
    with patch('clockwork.core.ResourceCompleter') as mock_generator, \
         patch('clockwork.core.subprocess.run') as mock_subprocess:

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
        # Old artifact-style return value for reference
        old_artifacts = {"ai.md": "# Python\n\nPython is great!"}
        mock_generator.return_value = mock_gen_instance

        # Setup subprocess mock
        mock_result = Mock()
        mock_result.stdout = "PyInfra output"
        mock_result.stderr = ""
        mock_result.returncode = 0
        mock_subprocess.return_value = mock_result

        # Run the pipeline
        core = ClockworkCore(api_key="test-key")
        result = core.apply(main_file, dry_run=False)

    # Verify execution
    assert result["success"] is True
    assert mock_subprocess.called


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


def test_pyinfra_compiler_integration(tmp_path):
    """Test that the PyInfra compiler is properly integrated."""
    main_file = tmp_path / "main.py"
    main_file.write_text('''
from clockwork.resources import FileResource, ArtifactSize

test_file = FileResource(
    name="test.txt",
    description="Test",
    size=ArtifactSize.SMALL,
    content="Test content"
)
''')

    with patch('clockwork.core.ResourceCompleter') as mock_generator:
        mock_instance = Mock()
        # Mock complete to return resources (simulating completion)
        async def mock_complete(resources):
            return resources
        mock_instance.complete = mock_complete
        mock_generator.return_value = mock_instance

        core = ClockworkCore(api_key="test-key")
        result = core.plan(main_file)

    # Verify PyInfra files were generated
    pyinfra_dir = Path(result["pyinfra_dir"])
    assert pyinfra_dir.exists()
    assert (pyinfra_dir / "inventory.py").exists()
    assert (pyinfra_dir / "deploy.py").exists()


def test_resources_with_mixed_content(tmp_path):
    """Test pipeline with mix of user-provided and AI-generated content."""
    main_file = tmp_path / "main.py"
    main_file.write_text('''
from clockwork.resources import FileResource, ArtifactSize

# User-provided content
static_file = FileResource(
    name="static.txt",
    description="Static",
    size=ArtifactSize.SMALL,
    content="I wrote this myself"
)

# AI-generated content
dynamic_file = FileResource(
    name="dynamic.md",
    description="Generate documentation about Docker",
    size=ArtifactSize.MEDIUM
)
''')

    with patch('clockwork.core.ResourceCompleter') as mock_generator:
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

        core = ClockworkCore(api_key="test-key")
        result = core.plan(main_file)

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

    # Mock the resource completer and PyInfra execution
    with patch('clockwork.core.ResourceCompleter') as mock_generator, \
         patch('clockwork.core.subprocess.run') as mock_subprocess:

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

        # Setup subprocess mock
        mock_result = Mock()
        mock_result.stdout = "PyInfra output"
        mock_result.stderr = ""
        mock_result.returncode = 0
        mock_subprocess.return_value = mock_result

        # First run apply to generate destroy.py
        core = ClockworkCore(api_key="test-key")
        core.apply(main_file, dry_run=True)

        # Now run destroy
        result = core.destroy(main_file, dry_run=False)

    # Verify execution
    assert result["success"] is True
    assert mock_subprocess.called

    # Verify destroy.py was used
    call_args = mock_subprocess.call_args
    assert "destroy.py" in call_args[0][0]


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

    with patch('clockwork.core.ResourceCompleter') as mock_generator:
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

        core = ClockworkCore(api_key="test-key")
        # First run apply to generate destroy.py
        core.apply(main_file, dry_run=True)
        # Now test destroy in dry run
        result = core.destroy(main_file, dry_run=True)

    # Verify dry run behavior
    assert result["dry_run"] is True
    assert "pyinfra_dir" in result

    # Verify destroy.py was generated
    pyinfra_dir = Path(result["pyinfra_dir"])
    assert pyinfra_dir.exists()
    assert (pyinfra_dir / "destroy.py").exists()


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

    # Mock the artifact generator and PyInfra execution
    with patch('clockwork.core.ResourceCompleter') as mock_generator, \
         patch('clockwork.core.subprocess.run') as mock_subprocess:

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
        # Old artifact-style return value for reference
        old_artifacts = {"dynamic.md": "# Generated Doc"}
        mock_generator.return_value = mock_gen_instance

        # Setup subprocess mock
        mock_result = Mock()
        mock_result.stdout = "Destroy complete"
        mock_result.stderr = ""
        mock_result.returncode = 0
        mock_subprocess.return_value = mock_result

        # First run apply to generate destroy.py
        core = ClockworkCore(api_key="test-key")
        core.apply(main_file, dry_run=True)

        # Now run destroy
        result = core.destroy(main_file, dry_run=False)

    # Verify execution
    assert result["success"] is True

    # Verify PyInfra was called with correct arguments
    call_args = mock_subprocess.call_args
    assert call_args[0][0] == ["pyinfra", "-y", "inventory.py", "destroy.py"]


def test_destroy_compiler_integration(tmp_path):
    """Test that the PyInfra compiler properly generates destroy operations."""
    main_file = tmp_path / "main.py"
    main_file.write_text('''
from clockwork.resources import FileResource

test_file = FileResource(
    name="test.txt",
    description="Test",
    content="Test content"
)
''')

    with patch('clockwork.core.ResourceCompleter') as mock_generator:
        mock_instance = Mock()
        # Mock complete to return resources with completed fields
        async def mock_complete(resources):
            for r in resources:
                if hasattr(r, 'directory') and r.directory is None:
                    r.directory = "."
                if hasattr(r, 'mode') and r.mode is None:
                    r.mode = "644"
            return resources
        mock_instance.complete = mock_complete
        mock_generator.return_value = mock_instance

        core = ClockworkCore(api_key="test-key")
        # First run apply to generate destroy.py
        core.apply(main_file, dry_run=True)
        # Now test destroy
        result = core.destroy(main_file, dry_run=True)

    # Verify PyInfra destroy files were generated
    pyinfra_dir = Path(result["pyinfra_dir"])
    assert pyinfra_dir.exists()
    assert (pyinfra_dir / "inventory.py").exists()
    assert (pyinfra_dir / "destroy.py").exists()

    # Verify destroy.py has correct structure
    destroy_content = (pyinfra_dir / "destroy.py").read_text()
    assert "PyInfra destroy - generated by Clockwork" in destroy_content
    assert "from pyinfra.operations import files" in destroy_content


# ============================================================================
# Assertion Pipeline Integration Tests
# ============================================================================


def test_assert_command_with_object_assertions(tmp_path):
    """Test clockwork assert command with BaseAssertion objects."""
    main_file = tmp_path / "main.py"
    main_file.write_text('''
from clockwork.resources import FileResource, ArtifactSize
from clockwork.assertions import FileExistsAssert, FilePermissionsAssert

test_file = FileResource(
    name="test.txt",
    description="Test file",
    size=ArtifactSize.SMALL,
    content="Test content",
    assertions=[
        FileExistsAssert(path="test.txt"),
        FilePermissionsAssert(path="test.txt", mode="644")
    ]
)
''')

    with patch('clockwork.core.ResourceCompleter') as mock_artifact_gen, \
         patch('clockwork.core.subprocess.run') as mock_subprocess:

        # Setup artifact generator mock
        mock_artifact_instance = Mock()
        # Mock complete to return resources
        async def mock_complete(resources):
            return resources
        mock_artifact_instance.complete = mock_complete
        mock_artifact_gen.return_value = mock_artifact_instance

        # Setup subprocess mock
        mock_result = Mock()
        mock_result.stdout = "All assertions passed"
        mock_result.stderr = ""
        mock_result.returncode = 0
        mock_subprocess.return_value = mock_result

        # Run assert pipeline
        core = ClockworkCore(api_key="test-key")
        result = core.assert_resources(main_file, dry_run=False)

    # Verify execution
    assert result["success"] is True
    assert mock_subprocess.called

    # Verify assert.py was used
    call_args = mock_subprocess.call_args
    assert "assert.py" in call_args[0][0]


def test_assert_command_generates_correct_pyinfra_files(tmp_path):
    """Test that assert command generates correct PyInfra files."""
    main_file = tmp_path / "main.py"
    main_file.write_text('''
from clockwork.resources import FileResource, ArtifactSize
from clockwork.assertions import FileExistsAssert

test_file = FileResource(
    name="test.txt",
    description="Test",
    size=ArtifactSize.SMALL,
    content="Test",
    assertions=[FileExistsAssert(path="test.txt")]
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
        result = core.assert_resources(main_file, dry_run=True)

    # Verify PyInfra files were generated
    pyinfra_dir = Path(result["pyinfra_dir"])
    assert (pyinfra_dir / "inventory.py").exists()
    assert (pyinfra_dir / "assert.py").exists()

    # Verify assert.py has correct structure
    assert_content = (pyinfra_dir / "assert.py").read_text()
    assert "PyInfra assert - generated by Clockwork" in assert_content
    assert "from pyinfra.operations import" in assert_content
    assert "test -e ../../test.txt" in assert_content  # Path resolution adds ../../


def test_assert_command_with_no_assertions(tmp_path):
    """Test assert command with resources that have no assertions."""
    main_file = tmp_path / "main.py"
    main_file.write_text('''
from clockwork.resources import FileResource, ArtifactSize

test_file = FileResource(
    name="test.txt",
    description="Test",
    size=ArtifactSize.SMALL,
    content="Test"
)
''')

    with patch('clockwork.core.ResourceCompleter') as mock_artifact_gen, \
         patch('clockwork.core.subprocess.run') as mock_subprocess:

        mock_artifact_instance = Mock()
        # Mock complete to return resources
        async def mock_complete(resources):
            return resources
        mock_artifact_instance.complete = mock_complete
        mock_artifact_gen.return_value = mock_artifact_instance

        # No assertions to process

        mock_result = Mock()
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_result.returncode = 0
        mock_subprocess.return_value = mock_result

        core = ClockworkCore(api_key="test-key")
        result = core.assert_resources(main_file, dry_run=False)

    # Should still execute successfully
    assert result["success"] is True


def test_assert_command_failure_handling(tmp_path):
    """Test that assert command properly handles assertion failures."""
    main_file = tmp_path / "main.py"
    main_file.write_text('''
from clockwork.resources import FileResource, ArtifactSize
from clockwork.assertions import FileExistsAssert

test_file = FileResource(
    name="test.txt",
    description="Test",
    size=ArtifactSize.SMALL,
    content="Test",
    assertions=[FileExistsAssert(path="/nonexistent/file.txt")]
)
''')

    with patch('clockwork.core.ResourceCompleter') as mock_artifact_gen, \
         patch('clockwork.core.subprocess.run') as mock_subprocess:

        mock_artifact_instance = Mock()
        # Mock complete to return resources
        async def mock_complete(resources):
            return resources
        mock_artifact_instance.complete = mock_complete
        mock_artifact_gen.return_value = mock_artifact_instance

        # Mock PyInfra failure
        mock_subprocess.side_effect = subprocess.CalledProcessError(
            1, ["pyinfra"], stderr="Assertion failed: File does not exist"
        )

        core = ClockworkCore(api_key="test-key")

        with pytest.raises(RuntimeError, match="assertions failed"):
            core.assert_resources(main_file, dry_run=False)


def test_assert_command_no_main_file():
    """Test assert command error when no main.py exists."""
    with patch('clockwork.core.ResourceCompleter') as mock_generator:
        mock_instance = Mock()
        mock_instance.complete = AsyncMock(return_value=[])  # Return completed resources
        mock_generator.return_value = mock_instance

        core = ClockworkCore(api_key="test-key")

        with pytest.raises(FileNotFoundError):
            core.assert_resources(Path("/nonexistent/main.py"))


def test_assert_multiple_resources_with_assertions(tmp_path):
    """Test assert command with multiple resources."""
    main_file = tmp_path / "main.py"
    main_file.write_text('''
from clockwork.resources import FileResource, ArtifactSize
from clockwork.assertions import FileExistsAssert, FilePermissionsAssert

file1 = FileResource(
    name="file1.txt",
    description="First file",
    size=ArtifactSize.SMALL,
    content="Content 1",
    assertions=[FileExistsAssert(path="file1.txt")]
)

file2 = FileResource(
    name="file2.txt",
    description="Second file",
    size=ArtifactSize.SMALL,
    content="Content 2",
    assertions=[
        FileExistsAssert(path="file2.txt"),
        FilePermissionsAssert(path="file2.txt", mode="644")
    ]
)
''')

    with patch('clockwork.core.ResourceCompleter') as mock_artifact_gen, \
         patch('clockwork.core.subprocess.run') as mock_subprocess:

        mock_artifact_instance = Mock()
        # Mock complete to return resources
        async def mock_complete(resources):
            return resources
        mock_artifact_instance.complete = mock_complete
        mock_artifact_gen.return_value = mock_artifact_instance

        mock_result = Mock()
        mock_result.stdout = "All assertions passed"
        mock_result.stderr = ""
        mock_result.returncode = 0
        mock_subprocess.return_value = mock_result

        core = ClockworkCore(api_key="test-key")
        result = core.assert_resources(main_file, dry_run=True)

    assert result["resources"] == 2
