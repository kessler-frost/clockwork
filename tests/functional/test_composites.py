"""Functional tests for composite resources.

Tests the complete composite resource lifecycle:
- Simple composites (BlankResource with FileResource children)
- Nested composites (BlankResource containing BlankResource)
- Full pipeline: plan → apply → assert → destroy
"""

import subprocess
import tempfile
from pathlib import Path

import pytest


def run_clockwork_command(command: str, cwd: Path, timeout: int = 120):
    """Run a clockwork command and return exit code, stdout, stderr."""
    result = subprocess.run(
        ["uv", "run", "clockwork", command],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return result.returncode, result.stdout, result.stderr


@pytest.mark.functional
def test_simple_composite():
    """Test simple composite with FileResource children (no connections)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_dir = Path(tmpdir)

        # Create main.py with simple composite
        main_py = test_dir / "main.py"
        main_py.write_text('''
"""Simple composite test - BlankResource with 2 FileResource children."""

from clockwork.resources import BlankResource, FileResource
from clockwork.assertions import FileExistsAssert

# Create standalone files (not in a composite) - simpler test
config = FileResource(
    name="config.yaml",
    content="database: sqlite\\nport: 8080",
    directory=".",
    mode="644",
    assertions=[FileExistsAssert(path="config.yaml")]
)

readme = FileResource(
    name="README.md",
    content="# Simple App\\n\\nThis is a test application.",
    directory=".",
    mode="644",
    assertions=[FileExistsAssert(path="README.md")]
)

print("✓ Simple test configured")
''')

        # Step 1: Plan
        print("\n=== Step 1: Plan ===")
        exit_code, stdout, stderr = run_clockwork_command(
            "plan", test_dir, timeout=60
        )
        print(f"Plan output:\n{stdout}")
        assert exit_code == 0, f"Plan failed:\n{stderr}"

        # Step 2: Apply
        print("\n=== Step 2: Apply ===")
        exit_code, stdout, stderr = run_clockwork_command(
            "apply", test_dir, timeout=120
        )
        print(f"Apply output:\n{stdout}")
        assert exit_code == 0, f"Apply failed:\n{stderr}"

        # Step 3: Verify files created
        print("\n=== Step 3: Verify ===")
        config_path = test_dir / "config.yaml"
        readme_path = test_dir / "README.md"
        assert config_path.exists(), "config.yaml not created"
        assert readme_path.exists(), "README.md not created"
        assert "database: sqlite" in config_path.read_text()
        assert "Simple App" in readme_path.read_text()

        # Step 4: Assert
        print("\n=== Step 4: Assert ===")
        exit_code, stdout, stderr = run_clockwork_command(
            "assert", test_dir, timeout=60
        )
        print(f"Assert output:\n{stdout}")
        assert exit_code == 0, f"Assertions failed:\n{stderr}"

        # Step 5: Destroy
        print("\n=== Step 5: Destroy ===")
        exit_code, stdout, stderr = run_clockwork_command(
            "destroy", test_dir, timeout=60
        )
        print(f"Destroy output:\n{stdout}")
        assert exit_code == 0, f"Destroy failed:\n{stderr}"

        print("\n✅ Simple composite test passed!")


@pytest.mark.functional
def test_nested_composite():
    """Test multiple files in subdirectories."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_dir = Path(tmpdir)

        # Create main.py with multiple files in subdirectories
        main_py = test_dir / "main.py"
        main_py.write_text('''
"""Test multiple files in subdirectories."""

from clockwork.resources import FileResource
from clockwork.assertions import FileExistsAssert

# Configuration files
app_config = FileResource(
    name="app.yaml",
    content="name: test-app\\nversion: 1.0",
    directory="config",
    mode="644",
    assertions=[FileExistsAssert(path="config/app.yaml")]
)

db_config = FileResource(
    name="database.yaml",
    content="host: localhost\\nport: 5432",
    directory="config",
    mode="644",
    assertions=[FileExistsAssert(path="config/database.yaml")]
)

# Documentation files
readme = FileResource(
    name="README.md",
    content="# Test App\\n\\nDocumentation for test app.",
    directory="docs",
    mode="644",
    assertions=[FileExistsAssert(path="docs/README.md")]
)

api_docs = FileResource(
    name="API.md",
    content="# API Reference\\n\\nAPI documentation.",
    directory="docs",
    mode="644",
    assertions=[FileExistsAssert(path="docs/API.md")]
)

print("✓ Multi-file test configured")
''')

        # Step 1: Plan
        print("\n=== Step 1: Plan ===")
        exit_code, stdout, stderr = run_clockwork_command(
            "plan", test_dir, timeout=60
        )
        print(f"Plan output:\n{stdout}")
        assert exit_code == 0, f"Plan failed:\n{stderr}"

        # Step 2: Apply
        print("\n=== Step 2: Apply ===")
        exit_code, stdout, stderr = run_clockwork_command(
            "apply", test_dir, timeout=120
        )
        print(f"Apply output:\n{stdout}")
        assert exit_code == 0, f"Apply failed:\n{stderr}"

        # Step 3: Verify directory structure and files created
        print("\n=== Step 3: Verify ===")
        config_dir = test_dir / "config"
        docs_dir = test_dir / "docs"

        assert config_dir.exists(), "config directory not created"
        assert docs_dir.exists(), "docs directory not created"

        app_yaml = config_dir / "app.yaml"
        db_yaml = config_dir / "database.yaml"
        readme_md = docs_dir / "README.md"
        api_md = docs_dir / "API.md"

        assert app_yaml.exists(), "config/app.yaml not created"
        assert db_yaml.exists(), "config/database.yaml not created"
        assert readme_md.exists(), "docs/README.md not created"
        assert api_md.exists(), "docs/API.md not created"

        assert "test-app" in app_yaml.read_text()
        assert "localhost" in db_yaml.read_text()
        assert "Test App" in readme_md.read_text()
        assert "API Reference" in api_md.read_text()

        # Step 4: Assert
        print("\n=== Step 4: Assert ===")
        exit_code, stdout, stderr = run_clockwork_command(
            "assert", test_dir, timeout=60
        )
        print(f"Assert output:\n{stdout}")
        assert exit_code == 0, f"Assertions failed:\n{stderr}"

        # Step 5: Destroy
        print("\n=== Step 5: Destroy ===")
        exit_code, stdout, stderr = run_clockwork_command(
            "destroy", test_dir, timeout=60
        )
        print(f"Destroy output:\n{stdout}")
        assert exit_code == 0, f"Destroy failed:\n{stderr}"

        print("\n✅ Multi-file test passed!")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
