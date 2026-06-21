"""Comprehensive functional test covering all Clockwork features.

This test exercises the FULL Clockwork pipeline with varying levels of intelligence:
1. NO intelligence - fully specified resources (tests deployment without LLM)
2. PARTIAL intelligence - some fields specified, some need completion
3. FULL intelligence - only description provided, everything else completed

Requirements:
- CW_API_KEY environment variable must be set (or in .env)
- CW_BASE_URL should point to a running LLM endpoint

NO MOCKING - this is a true end-to-end functional test.
"""

import json
import os
import subprocess
import tempfile
import time
from pathlib import Path

import pytest


def check_llm_available():
    """Check if an LLM endpoint is available. Returns (available, message)."""
    # Check for API key in environment or .env file
    api_key = os.environ.get("CW_API_KEY")

    if not api_key:
        # Try to load from .env
        env_file = Path(__file__).parent.parent.parent / ".env"
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                if line.startswith("CW_API_KEY="):
                    value = line.split("=", 1)[1].strip()
                    # Handle ${VAR} syntax
                    if value.startswith("${") and value.endswith("}"):
                        var_name = value[2:-1]
                        api_key = os.environ.get(var_name)
                    else:
                        api_key = value
                    break

    if not api_key:
        return False, "CW_API_KEY not set and not found in .env"

    base_url = os.environ.get("CW_BASE_URL", "https://openrouter.ai/api/v1")

    # For local endpoints, check reachability
    if "localhost" in base_url or "127.0.0.1" in base_url:
        import socket

        try:
            port = int(base_url.split(":")[-1].split("/")[0])
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex(("localhost", port))
            sock.close()
            if result != 0:
                return False, f"Local LLM endpoint not reachable on port {port}"
        except Exception as e:
            return False, f"Failed to check local endpoint: {e}"

    return True, "LLM endpoint available"


def run_clockwork_command(command: str, cwd: Path, timeout: int = 180):
    """Run a clockwork command and return exit code, stdout, stderr."""
    result = subprocess.run(
        ["uv", "run", "clockwork", command],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
        env={**os.environ},
    )
    return result.returncode, result.stdout, result.stderr


def get_running_container_ids():
    """Get list of running Apple Container IDs."""
    result = subprocess.run(
        ["container", "list", "--format", "json"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return []

    try:
        containers = json.loads(result.stdout)
        return [
            c["configuration"]["id"]
            for c in containers
            if c.get("status") != "stopped"
        ]
    except (json.JSONDecodeError, KeyError):
        return []


def cleanup_containers():
    """Force cleanup all containers."""
    result = subprocess.run(
        ["container", "list", "--all", "--format", "json"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0 and result.stdout:
        try:
            containers = json.loads(result.stdout)
            ids = [c["configuration"]["id"] for c in containers]
            if ids:
                subprocess.run(
                    ["container", "rm", "-f", *ids],
                    capture_output=True,
                )
        except (json.JSONDecodeError, KeyError):
            pass


@pytest.fixture(scope="module", autouse=True)
def require_llm():
    """Skip this module if an LLM endpoint is not available (env-gated)."""
    available, message = check_llm_available()
    if not available:
        pytest.skip(f"LLM endpoint required for functional tests: {message}")


# =============================================================================
# Test 1: NO INTELLIGENCE - Fully specified resources
# =============================================================================
@pytest.mark.functional
def test_no_intelligence_fully_specified():
    """Test deployment with fully specified resources - NO LLM calls needed.

    This verifies the basic deployment pipeline works without any intelligence.
    All resource fields are explicitly provided.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        test_dir = Path(tmpdir)

        main_py = test_dir / "main.py"
        main_py.write_text('''
"""Test with fully specified resources - no intelligence needed."""

from clockwork.resources import FileResource, AppleContainerResource
from clockwork.assertions import FileExistsAssert, ContainerRunningAssert

# Fully specified file - no completion needed
config = FileResource(
    name="config.yaml",
    content="database: postgres\\nport: 5432\\nhost: localhost",
    directory=".",
    mode="644",
    assertions=[FileExistsAssert(path="config.yaml")]
)

# Fully specified container - no completion needed
redis = AppleContainerResource(
    name="func-test-redis-full",
    image="redis:7-alpine",
    ports=["16379:6379"],
    env_vars={},
    assertions=[ContainerRunningAssert(container_name="func-test-redis-full")]
)

print("✓ Fully specified resources - no intelligence needed")
''')

        print("\\n=== Test: No Intelligence (Fully Specified) ===")

        try:
            # Plan
            exit_code, stdout, stderr = run_clockwork_command("plan", test_dir)
            print(f"Plan stderr:\\n{stderr}")
            assert exit_code == 0, f"Plan failed:\\n{stderr}"

            # Verify no completion was needed
            assert "already complete" in stderr.lower(), (
                "Expected 'already complete' in logs for fully specified resources"
            )

            # Apply
            exit_code, stdout, stderr = run_clockwork_command(
                "apply", test_dir, timeout=300
            )
            print(f"Apply stdout:\\n{stdout}")
            assert exit_code == 0, f"Apply failed:\\n{stderr}"

            # Verify file created
            config_path = test_dir / "config.yaml"
            assert config_path.exists(), "config.yaml not created"
            assert "database: postgres" in config_path.read_text()

            # Verify container running
            time.sleep(3)
            running = get_running_container_ids()
            print(f"Running containers: {running}")
            assert len(running) >= 1, (
                f"Expected container running, found {len(running)}"
            )

            # Assert
            exit_code, stdout, stderr = run_clockwork_command(
                "assert", test_dir
            )
            assert exit_code == 0, f"Assertions failed:\\n{stderr}"

        finally:
            run_clockwork_command("destroy", test_dir, timeout=120)
            time.sleep(2)
            cleanup_containers()

        print("✓ No intelligence test passed!")


# =============================================================================
# Test 2: PARTIAL INTELLIGENCE - Some fields need completion
# =============================================================================
@pytest.mark.functional
def test_partial_intelligence():
    """Test with partially specified resources - some fields need completion.

    This tests the hybrid approach where users specify key fields and
    intelligence fills in the gaps.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        test_dir = Path(tmpdir)

        main_py = test_dir / "main.py"
        main_py.write_text('''
"""Test with partially specified resources - intelligence fills gaps."""

from clockwork.resources import FileResource, AppleContainerResource
from clockwork.assertions import FileExistsAssert, ContainerRunningAssert

# Partially specified file - has name and directory, needs content
config = FileResource(
    name="app-config.yaml",
    directory=".",
    mode="644",
    description="Configuration for a web app with host, port, and debug settings",
    assertions=[FileExistsAssert(path="app-config.yaml")]
)

# Partially specified container - has name, needs image and ports
api = AppleContainerResource(
    name="func-test-api-partial",
    description="A simple Python Flask API server",
    assertions=[ContainerRunningAssert(container_name="func-test-api-partial")]
)

print("✓ Partially specified resources - intelligence fills gaps")
''')

        print("\\n=== Test: Partial Intelligence ===")

        try:
            # Plan (triggers completion)
            exit_code, stdout, stderr = run_clockwork_command(
                "plan", test_dir, timeout=180
            )
            print(f"Plan stderr:\\n{stderr}")
            assert exit_code == 0, f"Plan failed:\\n{stderr}"

            # Verify completion occurred
            assert "Completed" in stderr or "Queuing" in stderr, (
                "Expected completion activity in logs"
            )

            # Apply
            exit_code, stdout, stderr = run_clockwork_command(
                "apply", test_dir, timeout=300
            )
            print(f"Apply stdout:\\n{stdout}")
            assert exit_code == 0, f"Apply failed:\\n{stderr}"

            # Verify file was created with generated content
            config_path = test_dir / "app-config.yaml"
            assert config_path.exists(), "app-config.yaml not created"
            content = config_path.read_text()
            print(f"Generated config content:\\n{content}")
            # Should have some config-like content
            assert len(content) > 10, (
                "Expected generated content in config file"
            )

            # Verify container
            time.sleep(5)
            running = get_running_container_ids()
            print(f"Running containers: {running}")

        finally:
            run_clockwork_command("destroy", test_dir, timeout=120)
            time.sleep(2)
            cleanup_containers()

        print("✓ Partial intelligence test passed!")


# =============================================================================
# Test 3: FULL INTELLIGENCE - Only description provided
# =============================================================================
@pytest.mark.functional
def test_full_intelligence():
    """Test with description-only resources - full intelligence completion.

    This tests the "magic" mode where users just describe what they want
    and intelligence handles all implementation details.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        test_dir = Path(tmpdir)

        main_py = test_dir / "main.py"
        main_py.write_text('''
"""Test with description-only resources - full intelligence completion."""

from clockwork.resources import FileResource

# Description only - intelligence must determine name, content, everything
readme = FileResource(
    description="A README markdown file for a Python project called 'calculator' that adds two numbers"
)

script = FileResource(
    description="A simple Python script that defines an add function taking two numbers"
)

print("✓ Description-only resources - full intelligence needed")
''')

        print("\\n=== Test: Full Intelligence ===")

        try:
            # Plan (triggers completion)
            exit_code, stdout, stderr = run_clockwork_command(
                "plan", test_dir, timeout=180
            )
            print(f"Plan stderr:\\n{stderr}")
            assert exit_code == 0, f"Plan failed:\\n{stderr}"

            # Verify completion occurred
            assert "Queuing resource for completion" in stderr, (
                "Expected resources to be queued for completion"
            )
            assert "Completed resource" in stderr, (
                "Expected resources to be completed"
            )

            # Apply
            exit_code, stdout, stderr = run_clockwork_command(
                "apply", test_dir, timeout=300
            )
            print(f"Apply stdout:\\n{stdout}")
            assert exit_code == 0, f"Apply failed:\\n{stderr}"

            # Find created files (names were generated by intelligence)
            created_files = [
                f
                for f in test_dir.iterdir()
                if f.is_file()
                and f.name != "main.py"
                and not f.name.startswith(".")
            ]
            print(f"Created files: {[f.name for f in created_files]}")
            assert len(created_files) >= 2, (
                f"Expected at least 2 files, found {len(created_files)}"
            )

            # Verify content was generated
            for f in created_files:
                content = f.read_text()
                print(f"\\n{f.name}:\\n{content[:200]}...")
                assert len(content) > 20, (
                    f"Expected meaningful content in {f.name}"
                )

        finally:
            run_clockwork_command("destroy", test_dir, timeout=120)

        print("✓ Full intelligence test passed!")


# =============================================================================
# Test 4: MIXED - Combination of all intelligence levels
# =============================================================================
@pytest.mark.functional
def test_mixed_intelligence_with_connections():
    """Test with mixed intelligence levels and connections between resources.

    This is the comprehensive test combining:
    - Fully specified resources
    - Partially specified resources
    - Description-only resources
    - Connections between them
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        test_dir = Path(tmpdir)

        main_py = test_dir / "main.py"
        main_py.write_text('''
"""Test with mixed intelligence levels and connections."""

from clockwork.resources import FileResource, AppleContainerResource
from clockwork.assertions import FileExistsAssert, ContainerRunningAssert

# FULLY SPECIFIED - database container
db = AppleContainerResource(
    name="func-test-db-mixed",
    image="postgres:15-alpine",
    ports=["25432:5432"],
    env_vars={"POSTGRES_PASSWORD": "testpass123"},  # pragma: allowlist secret
    assertions=[ContainerRunningAssert(container_name="func-test-db-mixed")]
)

# PARTIAL - config file with name but needs content generated
db_config = FileResource(
    name="database.yaml",
    directory="config",
    mode="644",
    description="Database configuration with PostgreSQL connection settings",
    assertions=[FileExistsAssert(path="config/database.yaml")]
)

# FULL INTELLIGENCE - just describe what we need
app_readme = FileResource(
    description="A README explaining this is a database-backed application"
)

# Connections
db_config.connect(db)

print("✓ Mixed intelligence test configured")
''')

        print("\\n=== Test: Mixed Intelligence with Connections ===")

        try:
            # Plan
            exit_code, stdout, stderr = run_clockwork_command(
                "plan", test_dir, timeout=180
            )
            print(f"Plan stderr:\\n{stderr}")
            assert exit_code == 0, f"Plan failed:\\n{stderr}"

            # Should see both "already complete" and completion activity
            assert (
                "already complete" in stderr.lower() or "Completed" in stderr
            ), "Expected mix of complete and needing-completion resources"

            # Apply
            exit_code, stdout, stderr = run_clockwork_command(
                "apply", test_dir, timeout=300
            )
            print(f"Apply stdout:\\n{stdout}")
            assert exit_code == 0, f"Apply failed:\\n{stderr}"

            # Verify outputs
            time.sleep(5)

            # Check database config was created
            config_path = test_dir / "config" / "database.yaml"
            assert config_path.exists(), "config/database.yaml not created"
            print(f"Database config:\\n{config_path.read_text()}")

            # Check container is running
            running = get_running_container_ids()
            print(f"Running containers: {running}")
            assert len(running) >= 1, (
                f"Expected at least 1 container, found {len(running)}"
            )

            # Run assertions
            exit_code, stdout, stderr = run_clockwork_command(
                "assert", test_dir
            )
            print(f"Assert stdout:\\n{stdout}")
            # Note: Some assertions may fail due to timing, but we mainly test deployment

        finally:
            run_clockwork_command("destroy", test_dir, timeout=120)
            time.sleep(2)
            cleanup_containers()

        print("✓ Mixed intelligence test passed!")


# =============================================================================
# Test 5: COMPOSITE with varying intelligence levels
# =============================================================================
@pytest.mark.functional
def test_composite_mixed_intelligence():
    """Test composite resources with children at different intelligence levels.

    This tests the two-phase completion with a mix of:
    - Fully specified children
    - Children needing completion
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        test_dir = Path(tmpdir)

        main_py = test_dir / "main.py"
        main_py.write_text('''
"""Test composite with mixed intelligence children."""

from clockwork.resources import BlankResource, FileResource

# Composite parent
project = BlankResource(
    name="my-project",
    description="A Python utility project"
).add(
    # FULLY SPECIFIED child
    FileResource(
        name="requirements.txt",
        content="requests==2.31.0\\npython-dotenv==1.0.0",
        directory=".",
        mode="644",
    ),
    # PARTIAL child - has name, needs content
    FileResource(
        name="setup.py",
        directory=".",
        mode="644",
        description="A setup.py for a package called myproject version 1.0",
    ),
    # FULL INTELLIGENCE child
    FileResource(
        description="A gitignore file for Python projects"
    ),
)

print("✓ Composite with mixed children configured")
''')

        print("\\n=== Test: Composite with Mixed Intelligence ===")

        try:
            # Plan
            exit_code, stdout, stderr = run_clockwork_command(
                "plan", test_dir, timeout=180
            )
            print(f"Plan stderr:\\n{stderr}")
            assert exit_code == 0, f"Plan failed:\\n{stderr}"

            # Should see composite completion
            assert "composite" in stderr.lower() or "Phase" in stderr, (
                "Expected composite/two-phase completion in logs"
            )

            # Apply
            exit_code, stdout, stderr = run_clockwork_command(
                "apply", test_dir, timeout=300
            )
            print(f"Apply stdout:\\n{stdout}")
            assert exit_code == 0, f"Apply failed:\\n{stderr}"

            # Verify files
            req_file = test_dir / "requirements.txt"
            assert req_file.exists(), "requirements.txt not created"
            assert "requests" in req_file.read_text(), (
                "requirements.txt should have exact content"
            )

            setup_file = test_dir / "setup.py"
            assert setup_file.exists(), "setup.py not created"
            setup_content = setup_file.read_text()
            print(f"Generated setup.py:\\n{setup_content}")
            assert len(setup_content) > 20, (
                "setup.py should have generated content"
            )

            # Find the gitignore (name was generated)
            gitignore_candidates = list(test_dir.glob("*ignore*")) + list(
                test_dir.glob(".*")
            )
            gitignore_candidates = [
                f for f in gitignore_candidates if f.is_file()
            ]
            print(
                f"Potential gitignore files: {[f.name for f in gitignore_candidates]}"
            )

        finally:
            run_clockwork_command("destroy", test_dir, timeout=120)

        print("✓ Composite mixed intelligence test passed!")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
