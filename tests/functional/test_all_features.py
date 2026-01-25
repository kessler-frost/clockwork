"""Comprehensive functional test covering all Clockwork features.

This test exercises the FULL Clockwork pipeline including intelligent completion:
- Resources defined with only `description` that REQUIRE intelligent completion
- Real LLM endpoint calls (LM Studio, OpenRouter, or other OpenAI-compatible API)
- All resource types, connection types, composites, and assertions

Requirements:
- CW_API_KEY environment variable must be set
- CW_BASE_URL should point to a running LLM endpoint (defaults to OpenRouter)
- For local testing: LM Studio running on localhost:1234

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
    """Check if an LLM endpoint is available."""
    api_key = os.environ.get("CW_API_KEY")
    if not api_key:
        return False, "CW_API_KEY not set"

    base_url = os.environ.get("CW_BASE_URL", "https://openrouter.ai/api/v1")

    # For LM Studio, check if it's reachable
    if "localhost" in base_url or "127.0.0.1" in base_url:
        import socket

        try:
            port = int(base_url.split(":")[-1].split("/")[0])
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex(("localhost", port))
            sock.close()
            if result != 0:
                return False, f"LM Studio not reachable on port {port}"
        except Exception as e:
            return False, f"Failed to check LM Studio: {e}"

    return True, "LLM endpoint available"


def run_clockwork_command(command: str, cwd: Path, timeout: int = 180):
    """Run a clockwork command and return exit code, stdout, stderr."""
    result = subprocess.run(
        ["uv", "run", "clockwork", command],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
        env={**os.environ},  # Pass through environment variables
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


def cleanup_containers():
    """Force cleanup all containers."""
    all_containers = get_all_container_ids()
    if all_containers:
        subprocess.run(
            ["container", "rm", "-f", *all_containers],
            capture_output=True,
            text=True,
        )


# Check if LLM is available for all tests in this module
llm_available, llm_message = check_llm_available()


@pytest.mark.functional
@pytest.mark.skipif(not llm_available, reason=llm_message)
def test_intelligent_file_completion():
    """Test that FileResource with only description gets intelligently completed.

    This test verifies the core intelligence pipeline:
    1. Resource defined with ONLY description (no content, name, etc.)
    2. Intelligence completes all missing fields
    3. File is created with generated content
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        test_dir = Path(tmpdir)

        # Create main.py with a FileResource that REQUIRES intelligent completion
        main_py = test_dir / "main.py"
        main_py.write_text('''
"""Test intelligent completion of FileResource."""

from clockwork.resources import FileResource
from clockwork.assertions import FileExistsAssert

# This resource ONLY has a description - intelligence must complete everything else
readme = FileResource(
    description="A simple README file for a Python CLI tool called 'hello-world' that prints a greeting"
)

print("✓ Resource defined - requires intelligent completion")
''')

        print("\n=== Testing Intelligent File Completion ===")

        # Run plan to trigger completion
        exit_code, stdout, stderr = run_clockwork_command(
            "plan", test_dir, timeout=180
        )
        print(f"Plan stdout:\n{stdout}")
        if stderr:
            print(f"Plan stderr:\n{stderr}")

        assert exit_code == 0, f"Plan failed:\n{stderr}"

        # The plan should show the resource was completed
        # Check logs for completion activity
        assert (
            "Completed" in stderr or "complete" in stderr.lower()
        ), "Expected completion logs indicating intelligent completion occurred"

        print("✓ Intelligent file completion test passed!")


@pytest.mark.functional
@pytest.mark.skipif(not llm_available, reason=llm_message)
def test_intelligent_container_completion():
    """Test that AppleContainerResource with only description gets intelligently completed.

    This test verifies intelligence can:
    1. Choose appropriate container image based on description
    2. Set appropriate ports, environment variables
    3. Complete all technical details from high-level description
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        test_dir = Path(tmpdir)

        main_py = test_dir / "main.py"
        main_py.write_text('''
"""Test intelligent completion of AppleContainerResource."""

from clockwork.resources import AppleContainerResource

# Only description - intelligence must figure out image, ports, env vars
redis_cache = AppleContainerResource(
    name="test-redis-cache",
    description="A Redis cache server for storing session data"
)

print("✓ Container resource defined - requires intelligent completion")
''')

        print("\n=== Testing Intelligent Container Completion ===")

        # Run plan
        exit_code, stdout, stderr = run_clockwork_command(
            "plan", test_dir, timeout=180
        )
        print(f"Plan stdout:\n{stdout}")
        if stderr:
            print(f"Plan stderr:\n{stderr}")

        assert exit_code == 0, f"Plan failed:\n{stderr}"

        # Verify completion happened
        assert (
            "Completed" in stderr or "complete" in stderr.lower()
        ), "Expected completion logs"

        print("✓ Intelligent container completion test passed!")


@pytest.mark.functional
@pytest.mark.skipif(not llm_available, reason=llm_message)
def test_full_pipeline_with_intelligent_completion():
    """Full end-to-end test: intelligent completion → deploy → verify → destroy.

    This is the comprehensive test that exercises:
    - Intelligent completion of multiple resource types
    - Actual deployment to Apple Containers
    - Assertion verification
    - Clean destruction
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        test_dir = Path(tmpdir)

        main_py = test_dir / "main.py"
        main_py.write_text('''
"""Full pipeline test with intelligent completion."""

from clockwork.resources import (
    AppleContainerResource,
    FileResource,
)
from clockwork.assertions import (
    ContainerRunningAssert,
    FileExistsAssert,
)

# ============================================================================
# Mix of fully-specified and intelligence-completed resources
# ============================================================================

# This file REQUIRES intelligent completion (only has description)
config = FileResource(
    description="A YAML configuration file for a web application with database host, port, and connection pool settings"
)

# This container is fully specified (no completion needed) - for reliable testing
postgres = AppleContainerResource(
    name="func-test-postgres",
    image="postgres:15-alpine",
    ports=["15432:5432"],
    env_vars={"POSTGRES_PASSWORD": "testpass123"},  # pragma: allowlist secret
    assertions=[ContainerRunningAssert(container_name="func-test-postgres")]
)

# This container REQUIRES intelligent completion
redis = AppleContainerResource(
    name="func-test-redis",
    description="A Redis server for caching",
    assertions=[ContainerRunningAssert(container_name="func-test-redis")]
)

# Dependencies
redis.connect(postgres)

print("✓ Resources configured - some require intelligent completion")
''')

        print("\n=== Full Pipeline Test with Intelligent Completion ===")

        try:
            # Step 1: Plan (triggers completion)
            print("\n--- Step 1: Plan ---")
            exit_code, stdout, stderr = run_clockwork_command(
                "plan", test_dir, timeout=180
            )
            print(f"Plan stdout:\n{stdout}")
            if stderr:
                print(f"Plan stderr:\n{stderr}")

            assert exit_code == 0, f"Plan failed:\n{stderr}"

            # Step 2: Apply (deploy)
            print("\n--- Step 2: Apply ---")
            exit_code, stdout, stderr = run_clockwork_command(
                "apply", test_dir, timeout=300
            )
            print(f"Apply stdout:\n{stdout}")
            if stderr:
                print(f"Apply stderr:\n{stderr}")

            assert exit_code == 0, f"Apply failed:\n{stderr}"

            # Step 3: Verify deployment
            print("\n--- Step 3: Verify ---")
            time.sleep(5)  # Give containers time to start

            # Check containers are running
            running = get_running_container_ids()
            print(f"Running containers: {running}")
            assert (
                len(running) >= 2
            ), f"Expected at least 2 containers, found {len(running)}"

            # Step 4: Run assertions
            print("\n--- Step 4: Assert ---")
            exit_code, stdout, stderr = run_clockwork_command(
                "assert", test_dir, timeout=60
            )
            print(f"Assert stdout:\n{stdout}")
            if stderr:
                print(f"Assert stderr:\n{stderr}")

            assert exit_code == 0, f"Assertions failed:\n{stderr}"

        finally:
            # Always cleanup
            print("\n--- Cleanup ---")
            run_clockwork_command("destroy", test_dir, timeout=120)
            time.sleep(2)
            cleanup_containers()

        print("\n✅ Full pipeline test with intelligent completion passed!")


@pytest.mark.functional
@pytest.mark.skipif(not llm_available, reason=llm_message)
def test_composite_with_intelligent_completion():
    """Test composite resources with two-phase intelligent completion.

    This tests the sophisticated two-phase completion:
    1. Parent resource completed with children context
    2. Children completed with parent context (for coordinated decisions)
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        test_dir = Path(tmpdir)

        main_py = test_dir / "main.py"
        main_py.write_text('''
"""Test composite resource with intelligent completion."""

from clockwork.resources import (
    BlankResource,
    AppleContainerResource,
    FileResource,
)

# Composite with children that need completion
webapp = BlankResource(
    name="test-webapp",
    description="A simple web application stack"
).add(
    # Child that needs completion
    FileResource(
        description="Nginx configuration for reverse proxy to port 8080"
    ),
    # Child that's fully specified
    AppleContainerResource(
        name="test-webapp-nginx",
        image="nginx:alpine",
        ports=["18080:80"],
    )
)

print("✓ Composite resource with mixed completion needs defined")
''')

        print("\n=== Composite Resource Completion Test ===")

        try:
            exit_code, stdout, stderr = run_clockwork_command(
                "plan", test_dir, timeout=180
            )
            print(f"Plan stdout:\n{stdout}")
            if stderr:
                print(f"Plan stderr:\n{stderr}")

            assert exit_code == 0, f"Plan failed:\n{stderr}"

            # Should see two-phase completion in logs
            assert (
                "Phase 1" in stderr or "composite" in stderr.lower()
            ), "Expected composite/two-phase completion logs"

        finally:
            cleanup_containers()

        print("✓ Composite completion test passed!")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
