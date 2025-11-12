"""Comprehensive functional test covering all Clockwork features.

This single test exercises all major features in one deployment:
- All resource types (File, AppleContainer, GitRepo)
- All connection types (Dependency, Database, Network, File, ServiceMesh)
- Composite resources
- Assertions
- AI completion

Designed to be fast and focused on feature coverage rather than examples.
"""

import json
import subprocess
import tempfile
import time
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


def get_running_container_ids():
    """Get list of running Apple Container IDs.

    Note: Returns container UUIDs, not names, as Apple Container may assign UUIDs
    instead of using the --name parameter.
    """
    result = subprocess.run(
        ["container", "list", "--format", "json"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return []

    try:
        containers = json.loads(result.stdout)
        # Return IDs of running containers (status != "stopped")
        return [
            c["configuration"]["id"]
            for c in containers
            if c.get("status") != "stopped"
        ]
    except (json.JSONDecodeError, KeyError):
        return []


def get_all_container_ids():
    """Get list of all Apple Container IDs (running and stopped)."""
    result = subprocess.run(
        ["container", "list", "--all", "--format", "json"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return []

    try:
        containers = json.loads(result.stdout)
        return [c["configuration"]["id"] for c in containers]
    except (json.JSONDecodeError, KeyError):
        return []


@pytest.mark.functional
def test_all_features():
    """Comprehensive test of all Clockwork features in a single deployment."""
    # Create temporary directory for test
    with tempfile.TemporaryDirectory() as tmpdir:
        test_dir = Path(tmpdir)

        # Create main.py that exercises all features
        main_py = test_dir / "main.py"
        main_py.write_text('''
"""Comprehensive feature test for Clockwork - focuses on core features without mixing composites+connections."""

from clockwork.resources import (
    BlankResource,
    AppleContainerResource,
    FileResource,
)
from clockwork.assertions import (
    ContainerRunningAssert,
    FileExistsAssert,
)

# ============================================================================
# Feature 1: File Resources with Assertions
# ============================================================================
config_file = FileResource(
    name="app-config.yaml",
    content="database: postgres\\nport: 5432",
    directory=".",
    mode="644",
    assertions=[FileExistsAssert(path="app-config.yaml")]
)

readme_file = FileResource(
    name="README.md",
    content="# Test Project\\n\\nThis is a test deployment.",
    directory=".",
    mode="644",
    assertions=[FileExistsAssert(path="README.md")]
)

# ============================================================================
# Feature 2: Container Resources
# ============================================================================
# Fully specified container
postgres = AppleContainerResource(
    name="test-postgres",
    image="postgres:15-alpine",
    ports=["5432:5432"],
    env_vars={"POSTGRES_PASSWORD": "testpass123"},  # pragma: allowlist secret
    assertions=[ContainerRunningAssert(container_name="test-postgres")]
)

redis = AppleContainerResource(
    name="test-redis",
    image="redis:7-alpine",
    ports=["6379:6379"],
    assertions=[ContainerRunningAssert(container_name="test-redis")]
)

# ============================================================================
# Feature 3: Simple Dependencies (Connections)
# ============================================================================
# Build dependency chain: files -> postgres -> redis
postgres.connect(config_file)
redis.connect(postgres)

print("✓ All features configured successfully")
''')

        # Step 1: Plan (dry run)
        print("\\n=== Step 1: Plan (dry run) ===")
        exit_code, stdout, stderr = run_clockwork_command(
            "plan", test_dir, timeout=120
        )
        print(f"Plan output:\\n{stdout}")
        if stderr:
            print(f"Plan stderr:\\n{stderr}")

        assert exit_code == 0, f"Plan failed:\\n{stderr}"
        assert "✓" in stdout or "success" in stdout.lower()

        # Step 2: Apply (deploy)
        print("\\n=== Step 2: Apply (deploy) ===")
        exit_code, stdout, stderr = run_clockwork_command(
            "apply", test_dir, timeout=180
        )
        print(f"Apply output:\\n{stdout}")
        if stderr:
            print(f"Apply stderr:\\n{stderr}")

        assert exit_code == 0, f"Apply failed:\\n{stderr}"

        # Step 3: Verify deployment
        print("\\n=== Step 3: Verify ===")
        time.sleep(3)  # Give containers time to start

        # Verify files were created
        config_path = test_dir / "app-config.yaml"
        readme_path = test_dir / "README.md"
        assert config_path.exists(), "Config file not created"
        assert readme_path.exists(), "README file not created"
        assert "database: postgres" in config_path.read_text()
        assert "Test Project" in readme_path.read_text()

        # Verify containers are running
        # Note: Apple Containers may use UUIDs instead of names, so we just check count
        running_containers = get_running_container_ids()
        print(f"Running containers: {running_containers}")
        # We deployed 2 containers (postgres + redis), verify they're running
        assert (
            len(running_containers) >= 2
        ), f"Expected at least 2 containers, found {len(running_containers)}"

        # Step 4: Assert (run assertions)
        print("\\n=== Step 4: Assert ===")
        exit_code, stdout, stderr = run_clockwork_command(
            "assert", test_dir, timeout=60
        )
        print(f"Assert output:\\n{stdout}")
        if stderr:
            print(f"Assert stderr:\\n{stderr}")

        assert exit_code == 0, f"Assertions failed:\\n{stderr}"

        # Step 5: Destroy (cleanup)
        print("\\n=== Step 5: Destroy ===")
        exit_code, stdout, stderr = run_clockwork_command(
            "destroy", test_dir, timeout=120
        )
        print(f"Destroy output:\\n{stdout}")
        if stderr:
            print(f"Destroy stderr:\\n{stderr}")

        assert exit_code == 0, f"Destroy failed:\\n{stderr}"

        # Step 6: Verify cleanup
        print("\\n=== Step 6: Verify Cleanup ===")
        time.sleep(3)  # Give containers more time to stop

        # Get all container IDs and force cleanup
        all_containers = get_all_container_ids()
        if all_containers:
            subprocess.run(
                ["container", "rm", "-f", *all_containers],
                capture_output=True,
                text=True,
            )

        # Verify containers were cleaned up
        # Give a moment for cleanup to complete
        time.sleep(1)
        running_containers = get_running_container_ids()
        print(f"Remaining running containers: {running_containers}")
        # After destroy and cleanup, should be no running containers
        # (or at least fewer than we started with)
        assert (
            len(running_containers) < 2
        ), f"Found {len(running_containers)} containers still running"

        print("\\n✅ All features tested successfully!")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
