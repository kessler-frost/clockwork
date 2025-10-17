"""
Clockwork Core - Intelligent, Composable Primitives for Infrastructure.

Apply Pipeline: Load primitives → Complete primitives (AI) → Deploy with Pulumi
Destroy Pipeline: Destroy infrastructure using Pulumi
Assert Pipeline: Load primitives → Complete primitives (AI) → Run assertions directly
Plan Pipeline: Load primitives → Complete primitives (AI) → Preview with Pulumi
"""

import importlib.util
import logging
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional

from .resource_completer import ResourceCompleter
from .pulumi_compiler import PulumiCompiler
from .settings import get_settings

logger = logging.getLogger(__name__)


class ClockworkCore:
    """Main coordinator for the Clockwork pipeline."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None
    ):
        """
        Initialize ClockworkCore.

        Args:
            api_key: API key for AI service (overrides settings/.env)
            model: Model to use for resource completion (overrides settings/.env)
            base_url: Base URL for API endpoint (overrides settings/.env)
        """
        # Load settings
        settings = get_settings()

        # Use provided values or fall back to settings
        api_key = api_key or settings.api_key
        model = model or settings.model
        base_url = base_url or settings.base_url

        self.resource_completer = ResourceCompleter(
            api_key=api_key,
            model=model,
            base_url=base_url
        )
        self.pulumi_compiler = PulumiCompiler()

        logger.info("ClockworkCore initialized")

    async def apply(self, main_file: Path, dry_run: bool = False) -> Dict[str, Any]:
        """
        Full pipeline: load → complete → deploy with Pulumi.

        Args:
            main_file: Path to main.py file with resource definitions
            dry_run: If True, only preview without executing

        Returns:
            Dict with execution results
        """
        logger.info(f"Starting Clockwork pipeline for: {main_file}")

        # 1. Load resources from main.py
        resources = self._load_resources(main_file)
        logger.info(f"Loaded {len(resources)} resources")

        # 2. Resolve dependency order (checks for cycles and sorts topologically)
        resources = self._resolve_dependency_order(resources)
        logger.info(f"Resolved resource dependencies in deployment order")

        # 3. Complete resources (AI stage)
        completed_resources = await self._complete_resources_safe(resources)

        # 4. Get project name from directory
        project_name = main_file.parent.name

        # 5. Execute Pulumi deploy (or preview if dry run)
        if dry_run:
            logger.info("Dry run - running preview only")
            result = await self.pulumi_compiler.preview(completed_resources, project_name)
            return {
                "dry_run": True,
                "resources": len(resources),
                "completed_resources": len(completed_resources),
                "preview": result
            }

        result = await self.pulumi_compiler.apply(completed_resources, project_name)
        logger.info("Clockwork pipeline complete")

        return result

    async def plan(self, main_file: Path) -> Dict[str, Any]:
        """
        Plan mode: complete resources and preview Pulumi changes without deploying.

        Args:
            main_file: Path to main.py file

        Returns:
            Dict with planning information
        """
        return await self.apply(main_file, dry_run=True)

    def _load_resources(self, main_file: Path) -> List[Any]:
        """
        Load resources from main.py by executing it.

        Args:
            main_file: Path to main.py

        Returns:
            List of Resource objects
        """
        if not main_file.exists():
            raise FileNotFoundError(f"File not found: {main_file}")

        # Load the module dynamically
        spec = importlib.util.spec_from_file_location("user_main", main_file)
        if spec is None or spec.loader is None:
            raise ImportError(f"Could not load {main_file}")

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Collect all Resource instances from module globals
        from .resources.base import Resource

        resources = []
        for name, obj in vars(module).items():
            if isinstance(obj, Resource):
                resources.append(obj)
                logger.debug(f"Found resource: {name} ({type(obj).__name__})")

        if not resources:
            raise ValueError(f"No resources found in {main_file}")

        return resources

    async def _complete_resources_safe(self, resources: List[Any]) -> List[Any]:
        """Complete resources with error handling and logging.

        Args:
            resources: List of partial Resource objects

        Returns:
            List of completed Resource objects

        Raises:
            RuntimeError: If resource completion fails
        """
        try:
            completed_resources = await self.resource_completer.complete(resources)
            logger.info(f"Completed {len(completed_resources)} resources")
            return completed_resources
        except Exception as e:
            logger.error(f"Failed to complete resources: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise RuntimeError(f"Resource completion failed: {e}") from e

    def _resolve_dependency_order(self, resources: List[Any]) -> List[Any]:
        """Resolve resource dependencies and return them in correct deployment order.

        This method performs two critical operations:
        1. Cycle Detection: Uses DFS to detect circular dependencies
        2. Topological Sort: Orders resources so dependencies are deployed first

        Args:
            resources: List of Resource objects (may have connections)

        Returns:
            List of Resource objects in dependency order (dependencies first)

        Raises:
            ValueError: If a dependency cycle is detected

        Example:
            # Given: A depends on B, B depends on C
            # Returns: [C, B, A]  (C deployed first, then B, then A)
        """
        if not resources:
            return resources

        # First, detect cycles using DFS
        visited = set()
        rec_stack = set()

        def detect_cycle_dfs(resource: Any, path: List[str]) -> None:
            """DFS to detect cycles in resource dependencies.

            Args:
                resource: Current resource being visited
                path: Current path of resource names (for error reporting)

            Raises:
                ValueError: If a cycle is detected
            """
            visited.add(id(resource))
            rec_stack.add(id(resource))
            resource_name = resource.name or resource.__class__.__name__
            path.append(resource_name)

            # Use _connection_resources for actual Resource objects
            for connected in resource._connection_resources:
                connected_id = id(connected)
                if connected_id not in visited:
                    detect_cycle_dfs(connected, path)
                elif connected_id in rec_stack:
                    # Cycle detected
                    connected_name = connected.name or connected.__class__.__name__
                    cycle_path = path + [connected_name]
                    raise ValueError(
                        f"Dependency cycle detected: {' → '.join(cycle_path)}"
                    )

            rec_stack.remove(id(resource))
            path.pop()

        # Check for cycles in all resources
        for resource in resources:
            if id(resource) not in visited:
                detect_cycle_dfs(resource, [])

        logger.debug("No dependency cycles detected")

        # Now perform topological sort using DFS
        visited_topo = set()
        result = []

        def topological_dfs(resource: Any) -> None:
            """DFS to perform topological sort.

            Args:
                resource: Current resource being visited
            """
            resource_id = id(resource)
            visited_topo.add(resource_id)

            # Visit all dependencies first (use _connection_resources for actual Resource objects)
            for connected in resource._connection_resources:
                if id(connected) not in visited_topo:
                    topological_dfs(connected)

            # Add current resource after its dependencies
            result.append(resource)

        # Process all resources
        for resource in resources:
            if id(resource) not in visited_topo:
                topological_dfs(resource)

        logger.debug(
            f"Topological sort complete: {[r.name or r.__class__.__name__ for r in result]}"
        )

        return result

    async def destroy(self, main_file: Path, dry_run: bool = False) -> Dict[str, Any]:
        """
        Destroy pipeline: destroy infrastructure using Pulumi.

        Args:
            main_file: Path to main.py file (used to determine project name)
            dry_run: If True, skip execution

        Returns:
            Dict with execution results
        """
        logger.info(f"Starting Clockwork destroy pipeline for: {main_file}")

        # Get project name from directory
        project_name = main_file.parent.name

        # Execute Pulumi destroy (unless dry run)
        if dry_run:
            logger.info("Dry run - skipping execution")
            return {
                "dry_run": True,
                "project_name": project_name
            }

        result = await self.pulumi_compiler.destroy(project_name)
        logger.info("Clockwork destroy pipeline complete")

        return result

    async def assert_resources(self, main_file: Path, dry_run: bool = False) -> Dict[str, Any]:
        """
        Full assertion pipeline: load → complete → run assertions directly.

        Args:
            main_file: Path to main.py file with resource definitions
            dry_run: If True, only list assertions without executing

        Returns:
            Dict with execution results including passed/failed counts
        """
        logger.info(f"Starting Clockwork assertion pipeline for: {main_file}")

        # 1. Load resources from main.py
        resources = self._load_resources(main_file)
        logger.info(f"Loaded {len(resources)} resources")

        # 2. Resolve dependency order (checks for cycles and sorts topologically)
        resources = self._resolve_dependency_order(resources)
        logger.info(f"Resolved resource dependencies in deployment order")

        # 3. Complete resources if needed (AI stage)
        completed_resources = await self._complete_resources_safe(resources)

        # 4. Run assertions directly (no file generation)
        if dry_run:
            # Count assertions without running them
            assertion_count = sum(
                len(r.assertions) if r.assertions else 0
                for r in completed_resources
            )
            logger.info("Dry run - skipping execution")
            return {
                "dry_run": True,
                "resources": len(resources),
                "total_assertions": assertion_count
            }

        # Import assertion base class
        from .assertions.base import BaseAssertion

        # Run assertions for each resource
        results = {
            "passed": [],
            "failed": [],
            "total": 0
        }

        for resource in completed_resources:
            if not resource.assertions:
                continue

            resource_name = resource.name or resource.__class__.__name__
            logger.info(f"Running assertions for resource: {resource_name}")

            for assertion in resource.assertions:
                if not isinstance(assertion, BaseAssertion):
                    logger.warning(f"Skipping non-BaseAssertion: {type(assertion)}")
                    continue

                results["total"] += 1
                assertion_desc = assertion.description or assertion.__class__.__name__

                try:
                    logger.info(f"  Checking: {assertion_desc}")

                    passed = await assertion.check(resource)

                    if passed:
                        results["passed"].append({
                            "resource": resource_name,
                            "assertion": assertion_desc
                        })
                        logger.info(f"  ✓ Passed: {assertion_desc}")
                    else:
                        results["failed"].append({
                            "resource": resource_name,
                            "assertion": assertion_desc,
                            "error": "Assertion check returned False"
                        })
                        logger.error(f"  ✗ Failed: {assertion_desc}")

                except Exception as e:
                    results["failed"].append({
                        "resource": resource_name,
                        "assertion": assertion_desc,
                        "error": str(e)
                    })
                    logger.error(f"  ✗ Failed: {assertion_desc} - {e}")

        logger.info("Clockwork assertion pipeline complete")

        # Return results
        return {
            "success": len(results["failed"]) == 0,
            "passed": len(results["passed"]),
            "failed": len(results["failed"]),
            "total": results["total"],
            "details": results
        }

