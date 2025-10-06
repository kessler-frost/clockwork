"""Tests for PyInfra compiler."""

import pytest
from pathlib import Path
from clockwork.pyinfra_compiler import PyInfraCompiler
from clockwork.resources import FileResource, ArtifactSize


def test_pyinfra_compiler_initialization():
    """Test PyInfraCompiler initialization."""
    compiler = PyInfraCompiler()
    assert compiler.output_dir == Path(".clockwork/pyinfra")

    custom_compiler = PyInfraCompiler(output_dir="custom/path")
    assert custom_compiler.output_dir == Path("custom/path")


def test_inventory_generation():
    """Test inventory file generation."""
    compiler = PyInfraCompiler()
    inventory = compiler._generate_inventory()

    assert 'hosts = ["@local"]' in inventory
    assert "@local" in inventory


def test_deploy_generation():
    """Test deploy.py generation."""
    compiler = PyInfraCompiler()

    resources = [
        FileResource(
            name="test.txt",
            description="Test",
            size=ArtifactSize.SMALL,
            path="/tmp/test.txt"
        )
    ]

    artifacts = {"test.txt": "test content"}

    deploy = compiler._generate_deploy(resources, artifacts)

    assert "from pyinfra.operations import files" in deploy
    assert "from io import StringIO" in deploy
    assert "files.put" in deploy
    assert "test.txt" in deploy


def test_compile_creates_files(tmp_path):
    """Test that compile creates the necessary files."""
    compiler = PyInfraCompiler(output_dir=str(tmp_path))

    resources = [
        FileResource(
            name="example.md",
            description="Example",
            size=ArtifactSize.SMALL
        )
    ]

    artifacts = {"example.md": "# Example"}

    result_dir = compiler.compile(resources, artifacts)

    assert result_dir.exists()
    assert (result_dir / "inventory.py").exists()
    assert (result_dir / "deploy.py").exists()

    # Verify content
    deploy_content = (result_dir / "deploy.py").read_text()
    assert "files.put" in deploy_content


def test_compile_multiple_resources(tmp_path):
    """Test compile with multiple resources."""
    compiler = PyInfraCompiler(output_dir=str(tmp_path))

    resources = [
        FileResource(
            name="file1.txt",
            description="First file",
            size=ArtifactSize.SMALL,
            path="/tmp/file1.txt"
        ),
        FileResource(
            name="file2.md",
            description="Second file",
            size=ArtifactSize.MEDIUM,
            path="/tmp/file2.md"
        ),
        FileResource(
            name="file3.json",
            description="Third file",
            size=ArtifactSize.LARGE,
            path="/tmp/file3.json"
        )
    ]

    artifacts = {
        "file1.txt": "content1",
        "file2.md": "# content2",
        "file3.json": '{"key": "value"}'
    }

    result_dir = compiler.compile(resources, artifacts)

    deploy_content = (result_dir / "deploy.py").read_text()

    # Check all resources are in deploy
    assert "file1.txt" in deploy_content
    assert "file2.md" in deploy_content
    assert "file3.json" in deploy_content

    # Check all operations are present
    assert deploy_content.count("files.put") == 3


def test_compile_with_user_provided_content(tmp_path):
    """Test compile with resources that have user-provided content."""
    compiler = PyInfraCompiler(output_dir=str(tmp_path))

    resources = [
        FileResource(
            name="manual.txt",
            description="Manual file",
            size=ArtifactSize.SMALL,
            content="This is manually provided content"
        )
    ]

    # No artifacts needed for manual content
    artifacts = {}

    result_dir = compiler.compile(resources, artifacts)
    deploy_content = (result_dir / "deploy.py").read_text()

    assert "manually provided content" in deploy_content


def test_compile_creates_directory(tmp_path):
    """Test that compile creates output directory if it doesn't exist."""
    output_dir = tmp_path / "nested" / "path" / "pyinfra"
    compiler = PyInfraCompiler(output_dir=str(output_dir))

    assert not output_dir.exists()

    resources = [
        FileResource(
            name="test.txt",
            description="Test",
            size=ArtifactSize.SMALL
        )
    ]

    result_dir = compiler.compile(resources, {})

    assert output_dir.exists()
    assert result_dir == output_dir


def test_deploy_has_proper_structure(tmp_path):
    """Test that generated deploy.py has proper Python structure."""
    compiler = PyInfraCompiler(output_dir=str(tmp_path))

    resources = [
        FileResource(
            name="test.txt",
            description="Test",
            size=ArtifactSize.SMALL
        )
    ]

    result_dir = compiler.compile(resources, {"test.txt": "content"})
    deploy_path = result_dir / "deploy.py"

    # Verify the file is valid Python by compiling it
    deploy_code = deploy_path.read_text()
    compile(deploy_code, str(deploy_path), 'exec')


def test_inventory_has_proper_structure(tmp_path):
    """Test that generated inventory.py has proper Python structure."""
    compiler = PyInfraCompiler(output_dir=str(tmp_path))

    resources = [
        FileResource(
            name="test.txt",
            description="Test",
            size=ArtifactSize.SMALL
        )
    ]

    result_dir = compiler.compile(resources, {})
    inventory_path = result_dir / "inventory.py"

    # Verify the file is valid Python by compiling it
    inventory_code = inventory_path.read_text()
    compile(inventory_code, str(inventory_path), 'exec')
