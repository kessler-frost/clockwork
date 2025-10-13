#!/usr/bin/env python3
"""
Test script to verify per-resource assertion checking.

This script demonstrates that the health checker can identify which specific
resource failed when one container is down.
"""
import asyncio
import subprocess
from pathlib import Path

from clockwork.service import HealthChecker, ProjectManager, ProjectState


async def test_per_resource_checking():
    """Test that health checker correctly identifies individual resource failures."""
    print("=" * 80)
    print("Testing Per-Resource Assertion Checking")
    print("=" * 80)

    # Setup paths
    main_file = Path(__file__).parent / "main.py"

    # Load resources from main.py
    from clockwork.core import ClockworkCore
    core = ClockworkCore()
    resources = core._load_resources(main_file)
    print(f"\n✓ Loaded {len(resources)} resources from main.py")

    # Initialize project manager and health checker
    project_manager = ProjectManager()
    health_checker = HealthChecker(project_manager=project_manager)

    # Register the project
    await project_manager.register_project(main_file, resources)
    projects = await project_manager.list_projects()

    if not projects:
        print("❌ ERROR: No projects registered")
        return False

    project_state = projects[0]
    print(f"\n✓ Project registered: {project_state.project_id}")
    print(f"  Resources: {[r.name for r in project_state.resources]}")

    # Check current container states
    print("\n" + "=" * 80)
    print("Current Container Status")
    print("=" * 80)

    result = subprocess.run(
        ["docker", "ps", "-a", "--filter", "name=monitored",
         "--format", "table {{.Names}}\t{{.Status}}"],
        capture_output=True,
        text=True
    )
    print(result.stdout)

    # Check health for each resource individually
    print("=" * 80)
    print("Per-Resource Health Check Results")
    print("=" * 80)

    health_results = await health_checker.check_project_health(project_state)

    all_healthy = True
    for resource_name, is_healthy in health_results.items():
        status = "✓ HEALTHY" if is_healthy else "✗ UNHEALTHY"
        print(f"  {resource_name}: {status}")
        if not is_healthy:
            all_healthy = False

    # Verify the expected results
    print("\n" + "=" * 80)
    print("Test Results")
    print("=" * 80)

    # Get actual container states
    redis_container_up = "Up" in subprocess.run(
        ["docker", "ps", "--filter", "name=redis-monitored", "--format", "{{.Status}}"],
        capture_output=True,
        text=True
    ).stdout

    nginx_container_up = "Up" in subprocess.run(
        ["docker", "ps", "--filter", "name=nginx-monitored", "--format", "{{.Status}}"],
        capture_output=True,
        text=True
    ).stdout

    redis_healthy = health_results.get("redis-monitored", False)
    nginx_healthy = health_results.get("nginx-monitored", False)

    success = True

    # Verify redis health matches actual state
    if redis_container_up == redis_healthy:
        status = "HEALTHY" if redis_healthy else "UNHEALTHY"
        print(f"✓ PASS: Redis correctly identified as {status}")
    else:
        print(f"✗ FAIL: Redis container is {'up' if redis_container_up else 'down'} "
              f"but marked {'healthy' if redis_healthy else 'unhealthy'}")
        success = False

    # Verify nginx health matches actual state
    if nginx_container_up == nginx_healthy:
        status = "HEALTHY" if nginx_healthy else "UNHEALTHY"
        print(f"✓ PASS: Nginx correctly identified as {status}")
    else:
        print(f"✗ FAIL: Nginx container is {'up' if nginx_container_up else 'down'} "
              f"but marked {'healthy' if nginx_healthy else 'unhealthy'}")
        success = False

    # Verify per-resource checking can distinguish between resources
    if redis_healthy != nginx_healthy or (redis_healthy and nginx_healthy):
        print("✓ PASS: Per-resource checking can distinguish individual resource states")
    else:
        print("✗ FAIL: Per-resource checking did not distinguish between resources")
        success = False

    if success:
        print("\n" + "=" * 80)
        print("✓ SUCCESS: Per-resource assertion checking works correctly!")
        print("=" * 80)
        print("\nThe health checker successfully verified that:")
        print(f"  - Redis is {'healthy' if redis_healthy else 'unhealthy'} "
              f"({'container running' if redis_container_up else 'container stopped'})")
        print(f"  - Nginx is {'healthy' if nginx_healthy else 'unhealthy'} "
              f"({'container running' if nginx_container_up else 'container stopped'})")
        print("\nThis enables targeted remediation - only failed resources")
        print("trigger remediation, not healthy resources.")
    else:
        print("\n" + "=" * 80)
        print("✗ FAILURE: Per-resource assertion checking did not work as expected")
        print("=" * 80)

    return success


if __name__ == "__main__":
    success = asyncio.run(test_per_resource_checking())
    exit(0 if success else 1)
