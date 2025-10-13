"""
Clockwork Core - Intelligent Infrastructure Orchestration in Python.

Apply Pipeline: Load resources → Complete resources (AI) → Compile (deploy.py + destroy.py) → Execute deploy
Destroy Pipeline: Execute pre-generated destroy.py (from apply)
Assert Pipeline: Load resources → Complete resources (AI) → Compile assertions → Execute assert
"""

import asyncio
import importlib.util
import logging
import subprocess
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional

from .resource_completer import ResourceCompleter
from .pyinfra_compiler import PyInfraCompiler
from .settings import get_settings

logger = logging.getLogger(__name__)


class ClockworkCore:
    """Main orchestrator for the Clockwork pipeline."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None
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
        self.pyinfra_compiler = PyInfraCompiler(
            output_dir=settings.pyinfra_output_dir
        )

        logger.info("ClockworkCore initialized")

    def apply(self, main_file: Path, dry_run: bool = False) -> Dict[str, Any]:
        """
        Full pipeline: load → complete → compile → deploy.

        Args:
            main_file: Path to main.py file with resource definitions
            dry_run: If True, only compile without executing

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
        completed_resources = self._complete_resources_safe(resources)

        # 4. Set compiler output directory relative to main.py location
        settings = get_settings()
        self.pyinfra_compiler.output_dir = main_file.parent / settings.pyinfra_output_dir

        # 5. Compile to PyInfra (template stage)
        pyinfra_dir = self.pyinfra_compiler.compile(completed_resources)
        logger.info(f"Compiled to PyInfra: {pyinfra_dir}")

        # 5.5. Generate per-resource assert files for health monitoring
        # These are used by the health checker to monitor individual resources
        logger.info("Generating per-resource assertion files for health monitoring...")
        for resource in completed_resources:
            try:
                self.pyinfra_compiler.compile_assert_single_resource(resource)
            except Exception as e:
                resource_name = resource.name or resource.__class__.__name__
                logger.warning(
                    f"Failed to generate per-resource assert file for {resource_name}: {e}"
                )
        logger.info(f"Generated per-resource assertion files in: {pyinfra_dir}")

        # 6. Execute PyInfra deploy (unless dry run)
        if dry_run:
            logger.info("Dry run - skipping execution")
            return {
                "dry_run": True,
                "resources": len(resources),
                "completed_resources": len(completed_resources),
                "pyinfra_dir": str(pyinfra_dir)
            }

        result = self._execute_pyinfra(pyinfra_dir)
        logger.info("Clockwork pipeline complete")

        return result

    def plan(self, main_file: Path) -> Dict[str, Any]:
        """
        Plan mode: complete resources and compile without deploying.

        Args:
            main_file: Path to main.py file

        Returns:
            Dict with planning information
        """
        return self.apply(main_file, dry_run=True)

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

    def _complete_resources_safe(self, resources: List[Any]) -> List[Any]:
        """Complete resources with error handling and logging.

        Args:
            resources: List of partial Resource objects

        Returns:
            List of completed Resource objects

        Raises:
            RuntimeError: If resource completion fails
        """
        try:
            completed_resources = asyncio.run(self.resource_completer.complete(resources))
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

    def destroy(self, main_file: Path, dry_run: bool = False) -> Dict[str, Any]:
        """
        Destroy pipeline: execute pre-generated destroy.py.

        The destroy.py file is generated during 'apply' to ensure consistency.
        This method simply executes the pre-generated destroy operations.

        Args:
            main_file: Path to main.py file (used to locate .clockwork directory)
            dry_run: If True, skip execution

        Returns:
            Dict with execution results
        """
        logger.info(f"Starting Clockwork destroy pipeline for: {main_file}")

        # Get the PyInfra directory (should exist from apply)
        settings = get_settings()
        pyinfra_dir = main_file.parent / settings.pyinfra_output_dir

        # Check if destroy.py exists (generated during apply)
        destroy_file = pyinfra_dir / "destroy.py"
        if not destroy_file.exists():
            raise FileNotFoundError(
                f"destroy.py not found at {destroy_file}. "
                "Please run 'clockwork apply' first to generate destroy operations."
            )

        logger.info(f"Using pre-generated destroy operations from: {pyinfra_dir}")

        # Execute PyInfra destroy (unless dry run)
        if dry_run:
            logger.info("Dry run - skipping execution")
            return {
                "dry_run": True,
                "pyinfra_dir": str(pyinfra_dir)
            }

        result = self._execute_pyinfra(pyinfra_dir, deploy_file="destroy.py")
        logger.info("Clockwork destroy pipeline complete")

        return result

    def assert_resources(self, main_file: Path, dry_run: bool = False) -> Dict[str, Any]:
        """
        Full assertion pipeline: load → complete → compile assertions → execute.

        Args:
            main_file: Path to main.py file with resource definitions
            dry_run: If True, only compile without executing

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
        completed_resources = self._complete_resources_safe(resources)

        # 4. Set compiler output directory relative to main.py location
        settings = get_settings()
        self.pyinfra_compiler.output_dir = main_file.parent / settings.pyinfra_output_dir

        # 5. Compile to PyInfra using compile_assert()
        pyinfra_dir = self.pyinfra_compiler.compile_assert(completed_resources)
        logger.info(f"Compiled assertions to PyInfra: {pyinfra_dir}")

        # 6. Execute PyInfra assert.py (unless dry run)
        if dry_run:
            logger.info("Dry run - skipping execution")
            return {
                "dry_run": True,
                "resources": len(resources),
                "pyinfra_dir": str(pyinfra_dir)
            }

        result = self._execute_pyinfra(pyinfra_dir, deploy_file="assert.py")
        logger.info("Clockwork assertion pipeline complete")

        return result

    def _execute_pyinfra(self, pyinfra_dir: Path, deploy_file: str = "deploy.py") -> Dict[str, Any]:
        """
        Execute the PyInfra deployment or destroy operation.

        Args:
            pyinfra_dir: Path to directory with inventory.py and deploy/destroy file
            deploy_file: Name of the deployment file (default: "deploy.py", can be "destroy.py")

        Returns:
            Dict with execution results
        """
        operation_type = "destroy" if deploy_file == "destroy.py" else "deployment"
        if deploy_file == "assert.py":
            operation_type = "assertions"
        logger.info(f"Executing PyInfra {operation_type} from: {pyinfra_dir}")

        # Run: pyinfra -y inventory.py <deploy_file> (auto-approve changes)
        cmd = ["pyinfra", "-y", "inventory.py", deploy_file]

        try:
            result = subprocess.run(
                cmd,
                cwd=pyinfra_dir,
                capture_output=True,
                text=True,
                check=True
            )

            logger.info(f"PyInfra {operation_type} successful")
            return {
                "success": True,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode
            }

        except subprocess.CalledProcessError as e:
            logger.error(f"PyInfra {operation_type} failed: {e.stderr}")
            raise RuntimeError(f"PyInfra {operation_type} failed: {e.stderr}") from e
