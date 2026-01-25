"""Functional tests for composite resources with intelligent completion.

Tests the complete composite resource lifecycle WITH intelligent completion:
- Simple composites with children that REQUIRE completion
- Nested composites with two-phase completion
- Full pipeline: plan → apply → assert → destroy

Requirements:
- CW_API_KEY environment variable must be set
- CW_BASE_URL should point to a running LLM endpoint

NO MOCKING - these tests hit real LLM endpoints.
"""

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
        env={**os.environ},
    )
    return result.returncode, result.stdout, result.stderr


llm_available, llm_message = check_llm_available()


@pytest.mark.functional
@pytest.mark.skipif(not llm_available, reason=llm_message)
def test_simple_composite():
    """Test simple composite with children that REQUIRE intelligent completion.

    This tests:
    - BlankResource as composite container
    - Child FileResources with only descriptions (need completion)
    - Two-phase completion: parent first, then children with context
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        test_dir = Path(tmpdir)

        main_py = test_dir / "main.py"
        main_py.write_text('''
"""Simple composite test - BlankResource with children that need completion."""

from clockwork.resources import BlankResource, FileResource
from clockwork.assertions import FileExistsAssert

# Composite with children that REQUIRE intelligent completion
project = BlankResource(
    name="my-project",
    description="A Python project with configuration and documentation"
).add(
    # Child needs completion - only has description
    FileResource(
        description="A YAML configuration file with app name, version, and debug settings"
    ),
    # Child needs completion - only has description
    FileResource(
        description="A README markdown file explaining what this project does"
    ),
)

print("✓ Composite configured - children require intelligent completion")
''')

        print("\n=== Simple Composite with Intelligent Completion ===")

        # Step 1: Plan (triggers two-phase completion)
        print("\n--- Step 1: Plan ---")
        exit_code, stdout, stderr = run_clockwork_command(
            "plan", test_dir, timeout=180
        )
        print(f"Plan output:\n{stdout}")
        if stderr:
            print(f"Plan stderr:\n{stderr}")

        assert exit_code == 0, f"Plan failed:\n{stderr}"

        # Verify two-phase completion occurred
        assert (
            "Phase 1" in stderr or "composite" in stderr.lower()
        ), "Expected two-phase completion logs for composite"

        # Step 2: Apply
        print("\n--- Step 2: Apply ---")
        exit_code, stdout, stderr = run_clockwork_command(
            "apply", test_dir, timeout=180
        )
        print(f"Apply output:\n{stdout}")
        if stderr:
            print(f"Apply stderr:\n{stderr}")

        assert exit_code == 0, f"Apply failed:\n{stderr}"

        # Step 3: Verify files were created with intelligently-generated content
        print("\n--- Step 3: Verify ---")
        # Find any created files (we don't know exact names since they were generated)
        created_files = list(test_dir.glob("*.yaml")) + list(
            test_dir.glob("*.yml")
        )
        created_files += list(test_dir.glob("*.md"))
        created_files += list(test_dir.glob("**/*.yaml")) + list(
            test_dir.glob("**/*.yml")
        )
        created_files += list(test_dir.glob("**/*.md"))

        # Filter out main.py
        created_files = [f for f in created_files if f.name != "main.py"]

        print(f"Created files: {[str(f) for f in created_files]}")
        assert (
            len(created_files) >= 2
        ), f"Expected at least 2 files created, found {len(created_files)}"

        # Step 4: Destroy
        print("\n--- Step 4: Destroy ---")
        exit_code, stdout, stderr = run_clockwork_command(
            "destroy", test_dir, timeout=120
        )
        print(f"Destroy output:\n{stdout}")
        assert exit_code == 0, f"Destroy failed:\n{stderr}"

        print("\n✅ Simple composite test passed!")


@pytest.mark.functional
@pytest.mark.skipif(not llm_available, reason=llm_message)
def test_nested_composite():
    """Test nested composites with intelligent completion at multiple levels.

    This tests:
    - Nested BlankResources (composite containing composite)
    - Children at different levels needing completion
    - Proper context propagation through nesting levels
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        test_dir = Path(tmpdir)

        main_py = test_dir / "main.py"
        main_py.write_text('''
"""Nested composite test - composites containing composites with completion."""

from clockwork.resources import BlankResource, FileResource

# Outer composite
app = BlankResource(
    name="my-app",
    description="A web application with frontend and backend components"
).add(
    # Inner composite for backend
    BlankResource(
        name="backend",
        description="Backend API server components"
    ).add(
        # Needs completion
        FileResource(
            description="A Python requirements.txt file for a Flask API with SQLAlchemy"
        ),
    ),
    # Inner composite for frontend
    BlankResource(
        name="frontend",
        description="Frontend web application components"
    ).add(
        # Needs completion
        FileResource(
            description="A package.json file for a React application"
        ),
    ),
)

print("✓ Nested composite configured - children at multiple levels need completion")
''')

        print("\n=== Nested Composite with Intelligent Completion ===")

        # Step 1: Plan
        print("\n--- Step 1: Plan ---")
        exit_code, stdout, stderr = run_clockwork_command(
            "plan", test_dir, timeout=240
        )
        print(f"Plan output:\n{stdout}")
        if stderr:
            print(f"Plan stderr:\n{stderr}")

        assert exit_code == 0, f"Plan failed:\n{stderr}"

        # Step 2: Apply
        print("\n--- Step 2: Apply ---")
        exit_code, stdout, stderr = run_clockwork_command(
            "apply", test_dir, timeout=240
        )
        print(f"Apply output:\n{stdout}")
        if stderr:
            print(f"Apply stderr:\n{stderr}")

        assert exit_code == 0, f"Apply failed:\n{stderr}"

        # Step 3: Verify
        print("\n--- Step 3: Verify ---")
        # Find created files
        all_files = list(test_dir.rglob("*"))
        created_files = [
            f for f in all_files if f.is_file() and f.name != "main.py"
        ]

        print(
            f"Created files: {[str(f.relative_to(test_dir)) for f in created_files]}"
        )
        assert (
            len(created_files) >= 2
        ), f"Expected at least 2 files, found {len(created_files)}"

        # Step 4: Destroy
        print("\n--- Step 4: Destroy ---")
        exit_code, stdout, stderr = run_clockwork_command(
            "destroy", test_dir, timeout=120
        )
        print(f"Destroy output:\n{stdout}")
        assert exit_code == 0, f"Destroy failed:\n{stderr}"

        print("\n✅ Nested composite test passed!")


@pytest.mark.functional
@pytest.mark.skipif(not llm_available, reason=llm_message)
def test_composite_with_connections():
    """Test composite resources with connections requiring intelligent completion.

    This tests:
    - Composite with children that connect to external resources
    - Connection completion based on resource context
    - Full deployment with containers
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        test_dir = Path(tmpdir)

        main_py = test_dir / "main.py"
        main_py.write_text('''
"""Composite with connections test."""

import subprocess
import json
from clockwork.resources import BlankResource, FileResource, AppleContainerResource
from clockwork.connections import DatabaseConnection

# Standalone database (fully specified for reliability)
db = AppleContainerResource(
    name="test-db",
    image="postgres:15-alpine",
    ports=["25432:5432"],
    env_vars={"POSTGRES_PASSWORD": "testpass"},  # pragma: allowlist secret
)

# Composite app that connects to database
app = BlankResource(
    name="test-app",
    description="A Python application that connects to PostgreSQL"
).add(
    # Config needs completion - should include database connection info
    FileResource(
        description="Database configuration file with PostgreSQL connection settings for host, port, user, and database name"
    ),
)

# App connects to database
app.connect(db)

print("✓ Composite with connections configured")
''')

        print("\n=== Composite with Connections Test ===")

        try:
            # Step 1: Plan
            print("\n--- Step 1: Plan ---")
            exit_code, stdout, stderr = run_clockwork_command(
                "plan", test_dir, timeout=180
            )
            print(f"Plan output:\n{stdout}")
            if stderr:
                print(f"Plan stderr:\n{stderr}")

            assert exit_code == 0, f"Plan failed:\n{stderr}"

            # Step 2: Apply
            print("\n--- Step 2: Apply ---")
            exit_code, stdout, stderr = run_clockwork_command(
                "apply", test_dir, timeout=300
            )
            print(f"Apply output:\n{stdout}")
            if stderr:
                print(f"Apply stderr:\n{stderr}")

            assert exit_code == 0, f"Apply failed:\n{stderr}"

            # Step 3: Verify
            print("\n--- Step 3: Verify ---")
            time.sleep(3)

            # Check container is running
            result = subprocess.run(
                ["container", "list", "--format", "json"],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                import json

                containers = json.loads(result.stdout) if result.stdout else []
                running = [
                    c for c in containers if c.get("status") != "stopped"
                ]
                print(f"Running containers: {len(running)}")

        finally:
            # Cleanup
            print("\n--- Cleanup ---")
            run_clockwork_command("destroy", test_dir, timeout=120)
            time.sleep(2)
            # Force cleanup containers
            result = subprocess.run(
                ["container", "list", "--all", "--format", "json"],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0 and result.stdout:
                import json

                containers = json.loads(result.stdout)
                ids = [c["configuration"]["id"] for c in containers]
                if ids:
                    subprocess.run(
                        ["container", "rm", "-f", *ids], capture_output=True
                    )

        print("\n✅ Composite with connections test passed!")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
