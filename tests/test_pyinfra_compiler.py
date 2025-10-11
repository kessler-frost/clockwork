"""Tests for PyInfra compiler."""

import pytest
from pathlib import Path
from clockwork.pyinfra_compiler import PyInfraCompiler
from clockwork.resources import FileResource


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

    # Resources must be completed (all fields set)
    resources = [
        FileResource(
            name="test.txt",
            description="Test",
            path="/tmp/test.txt",
            content="test content"
        )
    ]

    deploy = compiler._generate_deploy(resources)

    assert "from pyinfra.operations import files" in deploy
    assert "files.put" in deploy
    assert "test.txt" in deploy


def test_compile_creates_files(tmp_path):
    """Test that compile creates the necessary files."""
    compiler = PyInfraCompiler(output_dir=str(tmp_path))

    # Resources must be completed (all fields set)
    resources = [
        FileResource(
            name="example.md",
            description="Example",
            content="# Example"
        )
    ]

    result_dir = compiler.compile(resources)

    assert result_dir.exists()
    assert (result_dir / "inventory.py").exists()
    assert (result_dir / "deploy.py").exists()
    assert (result_dir / "destroy.py").exists()

    # Verify content
    deploy_content = (result_dir / "deploy.py").read_text()
    assert "files.put" in deploy_content


def test_compile_multiple_resources(tmp_path):
    """Test compile with multiple resources."""
    compiler = PyInfraCompiler(output_dir=str(tmp_path))

    # Resources must be completed (all fields set)
    resources = [
        FileResource(
            name="file1.txt",
            description="First file",
            path="/tmp/file1.txt",
            content="content1"
        ),
        FileResource(
            name="file2.md",
            description="Second file",
            path="/tmp/file2.md",
            content="# content2"
        ),
        FileResource(
            name="file3.json",
            description="Third file",
            path="/tmp/file3.json",
            content='{"key": "value"}'
        )
    ]

    result_dir = compiler.compile(resources)

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
            content="This is manually provided content"
        )
    ]

    result_dir = compiler.compile(resources)
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
            content="test content"
        )
    ]

    result_dir = compiler.compile(resources)

    assert output_dir.exists()
    assert result_dir == output_dir


def test_deploy_has_proper_structure(tmp_path):
    """Test that generated deploy.py has proper Python structure."""
    compiler = PyInfraCompiler(output_dir=str(tmp_path))

    resources = [
        FileResource(
            name="test.txt",
            description="Test",
            content="content"
        )
    ]

    result_dir = compiler.compile(resources)
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
            content="content"
        )
    ]

    result_dir = compiler.compile(resources)
    inventory_path = result_dir / "inventory.py"

    # Verify the file is valid Python by compiling it
    inventory_code = inventory_path.read_text()
    compile(inventory_code, str(inventory_path), 'exec')
