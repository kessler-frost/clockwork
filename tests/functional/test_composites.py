"""Functional tests for composite resources with varying intelligence levels.

Tests composite resources with:
- Fully specified children (no intelligence)
- Partially specified children (some intelligence)
- Description-only children (full intelligence)
- Two-phase completion verification

Requirements:
- CW_API_KEY environment variable must be set (or in .env)
- CW_BASE_URL should point to a running LLM endpoint

NO MOCKING - these tests hit real LLM endpoints.
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
    api_key = os.environ.get("CW_API_KEY")

    if not api_key:
        env_file = Path(__file__).parent.parent.parent / ".env"
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                if line.startswith("CW_API_KEY="):
                    value = line.split("=", 1)[1].strip()
                    if value.startswith("${") and value.endswith("}"):
                        var_name = value[2:-1]
                        api_key = os.environ.get(var_name)
                    else:
                        api_key = value
                    break

    if not api_key:
        return False, "CW_API_KEY not set and not found in .env"

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
# Test 1: Composite with fully specified children (NO intelligence)
# =============================================================================
@pytest.mark.functional
def test_composite_no_intelligence():
    """Test composite with fully specified children - no LLM needed.

    Verifies that composites work correctly even without any intelligence.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        test_dir = Path(tmpdir)

        main_py = test_dir / "main.py"
        main_py.write_text('''
"""Composite with fully specified children - no intelligence needed."""

from clockwork.resources import BlankResource, FileResource
from clockwork.assertions import FileExistsAssert

project = BlankResource(
    name="static-project",
    description="A project with static files"
).add(
    FileResource(
        name="config.yaml",
        content="app: myapp\\nversion: 1.0",
        directory=".",
        mode="644",
        assertions=[FileExistsAssert(path="config.yaml")]
    ),
    FileResource(
        name="README.md",
        content="# My App\\n\\nThis is my application.",
        directory=".",
        mode="644",
        assertions=[FileExistsAssert(path="README.md")]
    ),
)

print("✓ Composite with fully specified children")
''')

        print("\\n=== Test: Composite No Intelligence ===")

        try:
            # Plan
            exit_code, stdout, stderr = run_clockwork_command("plan", test_dir)
            print(f"Plan stderr:\\n{stderr}")
            assert exit_code == 0, f"Plan failed:\\n{stderr}"

            # Apply
            exit_code, stdout, stderr = run_clockwork_command(
                "apply", test_dir, timeout=180
            )
            print(f"Apply stdout:\\n{stdout}")
            assert exit_code == 0, f"Apply failed:\\n{stderr}"

            # Verify files
            assert (test_dir / "config.yaml").exists()
            assert (test_dir / "README.md").exists()
            assert "app: myapp" in (test_dir / "config.yaml").read_text()
            assert "My App" in (test_dir / "README.md").read_text()

            # Assert
            exit_code, stdout, stderr = run_clockwork_command(
                "assert", test_dir
            )
            assert exit_code == 0, f"Assertions failed:\\n{stderr}"

        finally:
            run_clockwork_command("destroy", test_dir, timeout=120)

        print("✓ Composite no intelligence test passed!")


# =============================================================================
# Test 2: Nested composites with mixed intelligence
# =============================================================================
@pytest.mark.functional
def test_nested_composite_mixed_intelligence():
    """Test nested composites with varying intelligence levels.

    Outer composite contains inner composites, each with children
    at different intelligence levels.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        test_dir = Path(tmpdir)

        main_py = test_dir / "main.py"
        main_py.write_text('''
"""Nested composites with mixed intelligence levels."""

from clockwork.resources import BlankResource, FileResource

# Outer composite
app = BlankResource(
    name="fullstack-app",
    description="A fullstack application with backend and frontend"
).add(
    # Backend composite - mixed intelligence
    BlankResource(
        name="backend",
        description="Python backend API"
    ).add(
        # Fully specified
        FileResource(
            name="requirements.txt",
            content="flask==3.0.0\\nsqlalchemy==2.0.0",
            directory="backend",
            mode="644",
        ),
        # Needs completion - partial
        FileResource(
            name="app.py",
            directory="backend",
            mode="755",
            description="A Flask app with a single /health endpoint returning JSON",
        ),
    ),
    # Frontend composite - needs completion
    BlankResource(
        name="frontend",
        description="React frontend application"
    ).add(
        # Full intelligence
        FileResource(
            description="A package.json for a React app named frontend"
        ),
    ),
)

print("✓ Nested composites configured")
''')

        print("\\n=== Test: Nested Composite Mixed Intelligence ===")

        try:
            # Plan
            exit_code, stdout, stderr = run_clockwork_command(
                "plan", test_dir, timeout=240
            )
            print(f"Plan stderr:\\n{stderr}")
            assert exit_code == 0, f"Plan failed:\\n{stderr}"

            # Should see composite/two-phase completion
            assert "composite" in stderr.lower() or "Phase" in stderr, (
                "Expected composite completion logs"
            )

            # Apply
            exit_code, stdout, stderr = run_clockwork_command(
                "apply", test_dir, timeout=300
            )
            print(f"Apply stdout:\\n{stdout}")
            assert exit_code == 0, f"Apply failed:\\n{stderr}"

            # Verify fully specified file
            req_file = test_dir / "backend" / "requirements.txt"
            assert req_file.exists(), "backend/requirements.txt not created"
            assert "flask" in req_file.read_text().lower()

            # Verify partially specified file was completed
            app_file = test_dir / "backend" / "app.py"
            assert app_file.exists(), "backend/app.py not created"
            app_content = app_file.read_text()
            print(f"Generated app.py:\\n{app_content}")
            assert len(app_content) > 20, "app.py should have generated content"

            # Find generated frontend files
            frontend_files = list((test_dir).rglob("package.json")) + list(
                (test_dir).rglob("*.json")
            )
            frontend_files = [
                f for f in frontend_files if "package" in f.name.lower()
            ]
            print(f"Frontend files: {[str(f) for f in frontend_files]}")

        finally:
            run_clockwork_command("destroy", test_dir, timeout=120)

        print("✓ Nested composite mixed intelligence test passed!")


# =============================================================================
# Test 3: Composite with containers (deployment test)
# =============================================================================
@pytest.mark.functional
def test_composite_with_container():
    """Test composite containing both files and containers.

    Verifies that composites can orchestrate mixed resource types.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        test_dir = Path(tmpdir)

        main_py = test_dir / "main.py"
        main_py.write_text('''
"""Composite with file and container resources."""

from clockwork.resources import BlankResource, FileResource, AppleContainerResource
from clockwork.assertions import FileExistsAssert, ContainerRunningAssert

service = BlankResource(
    name="web-service",
    description="A web service with config and nginx"
).add(
    # Fully specified config
    FileResource(
        name="nginx.conf",
        content="server { listen 80; location / { return 200 'OK'; } }",
        directory=".",
        mode="644",
        assertions=[FileExistsAssert(path="nginx.conf")]
    ),
    # Partially specified - needs image completed
    AppleContainerResource(
        name="func-test-nginx-comp",
        image="nginx:alpine",  # Fully specified for reliability
        ports=["18080:80"],
        assertions=[ContainerRunningAssert(container_name="func-test-nginx-comp")]
    ),
)

print("✓ Composite with container configured")
''')

        print("\\n=== Test: Composite with Container ===")

        try:
            # Plan
            exit_code, stdout, stderr = run_clockwork_command(
                "plan", test_dir, timeout=180
            )
            print(f"Plan stderr:\\n{stderr}")
            assert exit_code == 0, f"Plan failed:\\n{stderr}"

            # Apply
            exit_code, stdout, stderr = run_clockwork_command(
                "apply", test_dir, timeout=300
            )
            print(f"Apply stdout:\\n{stdout}")
            assert exit_code == 0, f"Apply failed:\\n{stderr}"

            # Verify file
            assert (test_dir / "nginx.conf").exists(), "nginx.conf not created"

            # Verify container
            time.sleep(5)
            result = subprocess.run(
                ["container", "list", "--format", "json"],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0 and result.stdout:
                containers = json.loads(result.stdout)
                running = [
                    c for c in containers if c.get("status") != "stopped"
                ]
                print(f"Running containers: {len(running)}")
                assert len(running) >= 1, (
                    "Expected at least 1 container running"
                )

            # Assert
            exit_code, stdout, stderr = run_clockwork_command(
                "assert", test_dir
            )
            print(f"Assert result: exit_code={exit_code}")

        finally:
            run_clockwork_command("destroy", test_dir, timeout=120)
            time.sleep(2)
            cleanup_containers()

        print("✓ Composite with container test passed!")


# =============================================================================
# Test 4: Deep nesting with full intelligence
# =============================================================================
@pytest.mark.functional
def test_deep_nesting_full_intelligence():
    """Test deeply nested composites with full intelligence completion.

    Verifies that two-phase completion works correctly through multiple levels.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        test_dir = Path(tmpdir)

        main_py = test_dir / "main.py"
        main_py.write_text('''
"""Deeply nested composite with full intelligence."""

from clockwork.resources import BlankResource, FileResource

# Three levels of nesting
monorepo = BlankResource(
    name="monorepo",
    description="A monorepo with multiple packages"
).add(
    BlankResource(
        name="packages",
        description="Container for packages"
    ).add(
        BlankResource(
            name="core",
            description="Core library package"
        ).add(
            # Full intelligence - deeply nested
            FileResource(
                description="A Python __init__.py that exports a version string"
            ),
        ),
    ),
)

print("✓ Deeply nested composite configured")
''')

        print("\\n=== Test: Deep Nesting Full Intelligence ===")

        try:
            # Plan
            exit_code, stdout, stderr = run_clockwork_command(
                "plan", test_dir, timeout=240
            )
            print(f"Plan stderr:\\n{stderr}")
            assert exit_code == 0, f"Plan failed:\\n{stderr}"

            # Apply
            exit_code, stdout, stderr = run_clockwork_command(
                "apply", test_dir, timeout=300
            )
            print(f"Apply stdout:\\n{stdout}")
            assert exit_code == 0, f"Apply failed:\\n{stderr}"

            # Find created files
            all_files = list(test_dir.rglob("*"))
            created_files = [
                f for f in all_files if f.is_file() and f.name != "main.py"
            ]
            print(
                f"Created files: {[str(f.relative_to(test_dir)) for f in created_files]}"
            )

            # Should have at least the __init__.py
            assert len(created_files) >= 1, "Expected at least 1 file created"

        finally:
            run_clockwork_command("destroy", test_dir, timeout=120)

        print("✓ Deep nesting test passed!")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
