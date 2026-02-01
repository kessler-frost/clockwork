"""
Clockwork Core - Intelligent, Composable Primitives for Infrastructure.

Apply Pipeline: Load primitives → Intelligent completion → Deploy with Pulumi
Destroy Pipeline: Destroy infrastructure using Pulumi
Assert Pipeline: Load primitives → Intelligent completion → Run assertions directly
Plan Pipeline: Load primitives → Intelligent completion → Preview with Pulumi
Status Pipeline: Query Pulumi state and actual system state
"""

import importlib.util
import logging
import os
import shutil
import time
import traceback
from pathlib import Path
from typing import Any

from pulumi import automation as auto

from .connection_completer import ConnectionCompleter
from .exceptions import CompletionError
from .pulumi_compiler import PulumiCompiler
from .resource_completer import ResourceCompleter
from .settings import get_settings
from .state_checkers import check_all_resources_state

logger = logging.getLogger(__name__)


class ClockworkCore:
    """Main coordinator for the Clockwork pipeline."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        debug: bool = False,
    ):
        """
        Initialize ClockworkCore.

        Args:
            api_key: API key for completion service (overrides settings/.env)
            model: Model to use for resource completion (overrides settings/.env)
            base_url: Base URL for API endpoint (overrides settings/.env)
            debug: Whether to enable debug mode for detailed error info
        """
        # Load settings
        settings = get_settings()

        # Use provided values or fall back to settings
        api_key = api_key or settings.api_key
        model = model or settings.model
        base_url = base_url or settings.base_url

        self.resource_completer = ResourceCompleter(
            api_key=api_key, model=model, base_url=base_url, debug=debug
        )
        self.connection_completer = ConnectionCompleter(
            api_key=api_key, model=model, base_url=base_url
        )
        self.pulumi_compiler = PulumiCompiler()

        logger.info("ClockworkCore initialized")

    async def apply(
        self, main_file: Path, dry_run: bool = False, use_cache: bool = True
    ) -> dict[str, Any]:
        """
        Full pipeline: load → complete → deploy with Pulumi.

        Args:
            main_file: Path to main.py file with resource definitions
            dry_run: If True, only preview without executing
            use_cache: Whether to use completion cache (default: True)

        Returns:
            Dict with execution results including timings
        """
        logger.info(f"Starting Clockwork pipeline for: {main_file}")
        timings: dict[str, float] = {}
        pipeline_start = time.perf_counter()

        # 1. Load resources from main.py
        start = time.perf_counter()
        resources = self._load_resources(main_file)
        timings["load"] = time.perf_counter() - start
        logger.info(f"Loaded {len(resources)} resources")

        # 2. Resolve dependency order (checks for cycles and sorts topologically)
        resources = self._resolve_dependency_order(resources)
        logger.info("Resolved resource dependencies in deployment order")

        # 3. Complete resources (intelligent completion stage)
        start = time.perf_counter()
        completed_resources = await self._complete_resources_safe(
            resources, use_cache=use_cache
        )
        timings["complete"] = time.perf_counter() - start

        # 4. Extract and complete connections
        connections = self._extract_connections(completed_resources)
        logger.info(f"Extracted {len(connections)} connections")

        if connections:
            completed_connections = await self._complete_connections_safe(
                connections, completed_resources
            )
            logger.info(f"Completed {len(completed_connections)} connections")

            # Deploy connection setup resources
            await self._deploy_connection_setup(completed_connections)

        # 5. Get project name from directory
        project_name = main_file.parent.name

        # 6. Execute Pulumi deploy (or preview if dry run)
        start = time.perf_counter()
        if dry_run:
            logger.info("Dry run - running preview only")
            result = await self.pulumi_compiler.preview(
                completed_resources, project_name
            )
            timings["deploy"] = time.perf_counter() - start
            timings["total"] = time.perf_counter() - pipeline_start
            return {
                "dry_run": True,
                "resources": len(resources),
                "completed_resources": len(completed_resources),
                "preview": result,
                "timings": timings,
            }

        result = await self.pulumi_compiler.apply(
            completed_resources, project_name
        )
        timings["deploy"] = time.perf_counter() - start
        timings["total"] = time.perf_counter() - pipeline_start
        logger.info("Clockwork pipeline complete")

        return {**result, "timings": timings}

    async def plan(
        self, main_file: Path, use_cache: bool = True
    ) -> dict[str, Any]:
        """
        Plan mode: complete resources and preview Pulumi changes without deploying.

        Args:
            main_file: Path to main.py file
            use_cache: Whether to use completion cache (default: True)

        Returns:
            Dict with planning information
        """
        return await self.apply(main_file, dry_run=True, use_cache=use_cache)

    async def show(
        self,
        main_file: Path,
        resource_name: str | None = None,
        use_cache: bool = True,
    ) -> dict[str, Any]:
        """
        Show completed resources BEFORE deployment.

        This method runs the completion pipeline (load -> resolve -> complete)
        but stops before Pulumi deployment. It shows users exactly what the AI
        decided for each resource field.

        Args:
            main_file: Path to main.py file with resource definitions
            resource_name: Optional name of specific resource to show
            use_cache: Whether to use completion cache (default: True)

        Returns:
            Dict with:
                - resources: List of completed resource dicts with AI field tracking
                - resource_count: Total number of resources
                - ai_completed_count: Number of resources that had AI completion
        """
        logger.info(f"Starting Clockwork show pipeline for: {main_file}")

        # 1. Load resources from main.py
        resources = self._load_resources(main_file)
        logger.info(f"Loaded {len(resources)} resources")

        # 2. Resolve dependency order (checks for cycles and sorts topologically)
        resources = self._resolve_dependency_order(resources)
        logger.info("Resolved resource dependencies in deployment order")

        # 3. Complete resources (intelligent completion stage)
        completed_resources = await self._complete_resources_safe(
            resources, use_cache=use_cache
        )

        # 4. Format resources for output
        result_resources = []
        ai_completed_count = 0

        for resource in completed_resources:
            resource_data = self._format_resource_for_show(resource)

            # Filter by name if specified
            if (
                resource_name is not None
                and resource_data["name"] != resource_name
            ):
                continue

            result_resources.append(resource_data)

            if resource_data.get("ai_completed_fields"):
                ai_completed_count += 1

        logger.info("Clockwork show pipeline complete")

        return {
            "resources": result_resources,
            "resource_count": len(result_resources),
            "ai_completed_count": ai_completed_count,
        }

    def _format_resource_for_show(self, resource: Any) -> dict[str, Any]:
        """
        Format a resource for show output.

        Extracts resource data including which fields were AI-completed.

        Args:
            resource: Completed Resource object

        Returns:
            Dict with resource data and AI completion metadata
        """
        # Get resource data, excluding internal fields
        resource_data = resource.model_dump(
            exclude={"tools", "assertions", "connections"}
        )

        # Get AI-completed fields if available
        ai_completed_fields = set()
        if hasattr(resource, "_ai_completed_fields"):
            ai_completed_fields = resource._ai_completed_fields

        # Build formatted output
        formatted = {
            "name": resource.name or resource.__class__.__name__,
            "type": resource.__class__.__name__,
            "fields": {},
            "ai_completed_fields": list(ai_completed_fields),
            "children": [],
        }

        # Add each field with AI completion status
        for field_name, value in resource_data.items():
            if field_name in ("name", "description"):
                continue  # Already handled separately

            formatted["fields"][field_name] = {
                "value": value,
                "ai_completed": field_name in ai_completed_fields,
            }

        # Add description if present
        if resource.description:
            formatted["description"] = resource.description

        # Handle children for composite resources
        if hasattr(resource, "_children") and resource._children:
            for child in resource._children:
                formatted["children"].append(
                    self._format_resource_for_show(child)
                )

        return formatted

    def _load_resources(self, main_file: Path) -> list[Any]:
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

    def _extract_connections(self, resources: list[Any]) -> list[Any]:
        """
        Extract all Connection objects from resources.

        Args:
            resources: List of Resource objects

        Returns:
            List of Connection objects extracted from resources
        """
        from .connections import Connection

        connections = []
        for resource in resources:
            if hasattr(resource, "_connections"):
                for conn in resource._connections:
                    if isinstance(conn, Connection):
                        connections.append(conn)
                        logger.debug(
                            f"Found connection: {conn.__class__.__name__} "
                            f"from {resource.name} to {conn.to_resource.name}"
                        )

        return connections

    async def _complete_resources_safe(
        self, resources: list[Any], use_cache: bool = True
    ) -> list[Any]:
        """Complete resources with error handling and logging.

        Args:
            resources: List of partial Resource objects
            use_cache: Whether to use completion cache (default: True)

        Returns:
            List of completed Resource objects

        Raises:
            CompletionError: If resource completion fails with a completion error
            RuntimeError: If resource completion fails with other errors
        """
        try:
            completed_resources = await self.resource_completer.complete(
                resources, use_cache=use_cache
            )
            logger.info(f"Completed {len(completed_resources)} resources")
            return completed_resources
        except CompletionError:
            # Re-raise CompletionError as-is for proper error display
            raise
        except Exception as e:
            logger.error(f"Failed to complete resources: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise RuntimeError(f"Resource completion failed: {e}") from e

    async def _complete_connections_safe(
        self, connections: list[Any], resources: list[Any]
    ) -> list[Any]:
        """Complete connections with error handling and logging.

        Args:
            connections: List of partial Connection objects
            resources: List of all Resource objects (for context)

        Returns:
            List of completed Connection objects

        Raises:
            RuntimeError: If connection completion fails
        """
        try:
            completed_connections = await self.connection_completer.complete(
                connections, resources
            )
            logger.info(f"Completed {len(completed_connections)} connections")
            return completed_connections
        except Exception as e:
            logger.error(f"Failed to complete connections: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise RuntimeError(f"Connection completion failed: {e}") from e

    async def _deploy_connection_setup(self, connections: list[Any]) -> None:
        """Deploy setup resources for connections.

        Calls to_pulumi() on each connection to deploy any setup resources
        (e.g., config files, network bridges).

        Args:
            connections: List of completed Connection objects

        Raises:
            RuntimeError: If any connection setup fails

        Side Effects:
            Stores Pulumi resources in connection._pulumi_resources
        """
        failed_connections: list[tuple[str, str]] = []
        for connection in connections:
            try:
                pulumi_resources = connection.to_pulumi()
                if pulumi_resources:
                    logger.info(
                        f"Deployed {len(pulumi_resources)} setup resources for "
                        f"{connection.__class__.__name__}"
                    )
            except Exception as e:
                logger.error(
                    f"Failed to deploy setup for {connection.__class__.__name__}: {e}"
                )
                failed_connections.append(
                    (connection.__class__.__name__, str(e))
                )

        if failed_connections:
            raise RuntimeError(
                f"Failed to deploy {len(failed_connections)} connection setup(s): "
                + ", ".join(
                    f"{name}: {err}" for name, err in failed_connections
                )
            )

    def _flatten_resources(self, resources: list[Any]) -> list[Any]:
        """Flatten resource hierarchy by recursively extracting all children.

        This method handles composite resources by:
        1. Recursively extracting all children from the children dict
        2. Preserving parent-child relationships (stored in _parent/_children attrs)
        3. Returning a flat list with hierarchy intact

        Args:
            resources: List of Resource objects (may include composites with children)

        Returns:
            Flattened list: [parent1, child1, child2, parent2, child3, ...]

        Example:
            # Given: parent1 has [child1, child2], parent2 has [child3]
            # Returns: [parent1, child1, child2, parent2, child3]
        """
        flattened = []

        for resource in resources:
            # Add the parent resource
            flattened.append(resource)
            logger.debug(
                f"Flattened resource: {resource.name or resource.__class__.__name__}"
            )

            # Recursively add all children
            if hasattr(resource, "_children"):
                children = resource._children  # _children is already a list
                if children:
                    logger.debug(f"  Found {len(children)} children")
                    # Recursively flatten children (in case of nested composites)
                    flattened_children = self._flatten_resources(children)
                    flattened.extend(flattened_children)

        return flattened

    def _add_implicit_parent_child_dependencies(
        self, resources: list[Any]
    ) -> None:
        """Add implicit dependencies from children to parents.

        For each resource with a parent, this creates a DependencyConnection
        from child to parent. This ensures parents are deployed before children.

        Args:
            resources: Flattened list of Resource objects

        Side Effects:
            Modifies _connections in-place for resources with parents
        """
        from .connections import DependencyConnection

        for resource in resources:
            parent = resource._parent if hasattr(resource, "_parent") else None
            if parent is None:
                continue

            # Check if connection to parent already exists
            has_parent_connection = False
            if hasattr(resource, "_connections"):
                for conn in resource._connections:
                    if conn.to_resource == parent:
                        has_parent_connection = True
                        break

            # Add parent connection if not already present
            if not has_parent_connection:
                parent_conn = DependencyConnection(
                    from_resource=resource, to_resource=parent
                )
                resource._connections.append(parent_conn)
                logger.debug(
                    f"Added implicit dependency: {resource.name or resource.__class__.__name__} "
                    f"→ {parent.name or parent.__class__.__name__} (parent)"
                )

    def _resolve_dependency_order(self, resources: list[Any]) -> list[Any]:
        """Resolve resource dependencies and return them in correct deployment order.

        This method performs the following operations:
        1. Flatten Resources: Extract all children from composite resources
        2. Add Implicit Dependencies: Ensure children depend on their parents
        3. Cycle Detection: Uses DFS to detect circular dependencies
        4. Topological Sort: Orders resources so dependencies are deployed first

        Args:
            resources: List of Resource objects (may have connections and children)

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

        # Step 1: Flatten composite resources
        logger.debug("Flattening composite resources...")
        resources = self._flatten_resources(resources)
        logger.info(f"Flattened to {len(resources)} total resources")

        # Step 2: Add implicit parent-child dependencies
        logger.debug("Adding implicit parent-child dependencies...")
        self._add_implicit_parent_child_dependencies(resources)

        # Step 3: Detect cycles using DFS
        visited = set()
        rec_stack = set()

        def detect_cycle_dfs(resource: Any, path: list[str]) -> None:
            """DFS to detect cycles in resource dependencies.

            Args:
                resource: Current resource being visited
                path: Current path of resource names (for error reporting)

            Raises:
                ValueError: If a cycle is detected
            """
            visited.add(id(resource))
            rec_stack.add(id(resource))

            # Format resource name with parent context if available
            resource_name = resource.name or resource.__class__.__name__
            parent = resource._parent if hasattr(resource, "_parent") else None
            if parent is not None:
                parent_name = parent.name or parent.__class__.__name__
                resource_name = f"{parent_name}.{resource_name}"

            path.append(resource_name)

            # Use _connections for dependency tracking
            if hasattr(resource, "_connections"):
                for conn in resource._connections:
                    connected = conn.to_resource
                    connected_id = id(connected)
                    if connected_id not in visited:
                        detect_cycle_dfs(connected, path)
                    elif connected_id in rec_stack:
                        # Cycle detected - format connected name with parent context
                        connected_name = (
                            connected.name or connected.__class__.__name__
                        )
                        connected_parent = (
                            connected._parent
                            if hasattr(connected, "_parent")
                            else None
                        )
                        if connected_parent is not None:
                            connected_parent_name = (
                                connected_parent.name
                                or connected_parent.__class__.__name__
                            )
                            connected_name = (
                                f"{connected_parent_name}.{connected_name}"
                            )

                        cycle_path = [*path, connected_name]
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

        # Step 4: Perform topological sort using DFS
        visited_topo = set()
        result = []

        def topological_dfs(resource: Any) -> None:
            """DFS to perform topological sort.

            Args:
                resource: Current resource being visited
            """
            resource_id = id(resource)
            visited_topo.add(resource_id)

            # Visit all dependencies first (use _connections)
            if hasattr(resource, "_connections"):
                for conn in resource._connections:
                    connected = conn.to_resource
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

    def _extract_working_directories(self, resources: list[Any]) -> set[Path]:
        """Extract unique top-level working directories from resources.

        Args:
            resources: List of resource objects

        Returns:
            Set of Path objects representing top-level working directories
        """
        directories = set()
        cwd = Path.cwd()

        for resource in resources:
            # Extract directory from FileResource
            if hasattr(resource, "directory") and resource.directory:
                dir_path = Path(resource.directory)
                if not dir_path.is_absolute():
                    dir_path = cwd / dir_path
                # Get top-level directory relative to cwd
                try:
                    rel_path = dir_path.relative_to(cwd)
                    top_level = (
                        cwd / rel_path.parts[0] if rel_path.parts else None
                    )
                    if top_level and top_level != cwd:
                        directories.add(top_level)
                except ValueError:
                    # Path is not relative to cwd, skip it
                    pass

            # Extract directory from GitRepoResource
            if hasattr(resource, "dest") and resource.dest:
                dest_path = Path(resource.dest)
                if not dest_path.is_absolute():
                    dest_path = cwd / dest_path
                # Get top-level directory relative to cwd
                try:
                    rel_path = dest_path.relative_to(cwd)
                    top_level = (
                        cwd / rel_path.parts[0] if rel_path.parts else None
                    )
                    if top_level and top_level != cwd:
                        directories.add(top_level)
                except ValueError:
                    # Path is not relative to cwd, skip it
                    pass

        return directories

    async def destroy(
        self, main_file: Path, dry_run: bool = False, keep_files: bool = False
    ) -> dict[str, Any]:
        """
        Destroy pipeline: destroy infrastructure using Pulumi and clean up working directories.

        Args:
            main_file: Path to main.py file (used to determine project name)
            dry_run: If True, skip execution
            keep_files: If True, keep working directories (do not delete files)

        Returns:
            Dict with execution results
        """
        logger.info(f"Starting Clockwork destroy pipeline for: {main_file}")

        # Get project name from directory
        project_name = main_file.parent.name

        # Load resources to extract working directories
        resources = self._load_resources(main_file)
        working_dirs = self._extract_working_directories(resources)

        # Execute Pulumi destroy (unless dry run)
        if dry_run:
            logger.info("Dry run - skipping execution")
            return {
                "dry_run": True,
                "project_name": project_name,
                "working_directories_to_delete": [str(d) for d in working_dirs],
            }

        result = await self.pulumi_compiler.destroy(project_name)

        # Clean up working directories after successful destroy (unless keep_files is True)
        if result.get("success", False):
            if keep_files:
                logger.info(
                    "Keeping working directories (--keep-files flag set)"
                )
                result["working_directories_kept"] = [
                    str(d) for d in working_dirs
                ]
            else:
                for directory in working_dirs:
                    if directory.exists():
                        logger.info(f"Removing working directory: {directory}")
                        shutil.rmtree(directory)
                        logger.info(f"Deleted: {directory}")

        logger.info("Clockwork destroy pipeline complete")

        return result

    async def assert_resources(
        self, main_file: Path, dry_run: bool = False
    ) -> dict[str, Any]:
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
        logger.info("Resolved resource dependencies in deployment order")

        # 3. Complete resources if needed (intelligent completion stage)
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
                "total_assertions": assertion_count,
            }

        # Import assertion base class
        from .assertions.base import BaseAssertion

        # Run assertions for each resource
        results = {"passed": [], "failed": [], "total": 0}

        for resource in completed_resources:
            if not resource.assertions:
                continue

            resource_name = resource.name or resource.__class__.__name__
            logger.info(f"Running assertions for resource: {resource_name}")

            for assertion in resource.assertions:
                if not isinstance(assertion, BaseAssertion):
                    logger.warning(
                        f"Skipping non-BaseAssertion: {type(assertion)}"
                    )
                    continue

                results["total"] += 1
                assertion_desc = (
                    assertion.description or assertion.__class__.__name__
                )

                try:
                    logger.info(f"  Checking: {assertion_desc}")

                    passed = await assertion.check(resource)

                    if passed:
                        results["passed"].append(
                            {
                                "resource": resource_name,
                                "assertion": assertion_desc,
                            }
                        )
                        logger.info(f"  ✓ Passed: {assertion_desc}")
                    else:
                        results["failed"].append(
                            {
                                "resource": resource_name,
                                "assertion": assertion_desc,
                                "error": "Assertion check returned False",
                            }
                        )
                        logger.error(f"  ✗ Failed: {assertion_desc}")

                except Exception as e:
                    results["failed"].append(
                        {
                            "resource": resource_name,
                            "assertion": assertion_desc,
                            "error": str(e),
                        }
                    )
                    logger.error(f"  ✗ Failed: {assertion_desc} - {e}")

        logger.info("Clockwork assertion pipeline complete")

        # Return results
        return {
            "success": len(results["failed"]) == 0,
            "passed": len(results["passed"]),
            "failed": len(results["failed"]),
            "total": results["total"],
            "details": results,
        }

    async def status(self, main_file: Path) -> dict[str, Any]:
        """
        Status pipeline: Query Pulumi state and actual system state.

        This method:
        1. Loads Pulumi stack state for the project
        2. Loads resources from main.py
        3. Queries actual system state for each resource
        4. Returns combined state information

        Args:
            main_file: Path to main.py file with resource definitions

        Returns:
            Dict with:
                - success: Whether status check succeeded
                - pulumi_state: Pulumi stack state information
                - resources: List of resource states with actual system status
                - error: Error message if status check failed
        """
        logger.info(f"Starting Clockwork status pipeline for: {main_file}")

        # Get project name from directory
        project_name = main_file.parent.name

        result: dict[str, Any] = {
            "success": True,
            "project_name": project_name,
            "pulumi_state": None,
            "resources": [],
            "error": None,
        }

        # 1. Try to load Pulumi state
        try:
            pulumi_state = self._get_pulumi_state(project_name)
            result["pulumi_state"] = pulumi_state
            logger.info(f"Loaded Pulumi state for project: {project_name}")
        except Exception as e:
            logger.warning(f"Could not load Pulumi state: {e}")
            result["pulumi_state"] = {
                "available": False,
                "error": str(e),
            }

        # 2. Load resources from main.py
        try:
            resources = self._load_resources(main_file)
            logger.info(f"Loaded {len(resources)} resources")

            # Resolve dependency order (flattens composites)
            resources = self._resolve_dependency_order(resources)
            logger.info(f"Flattened to {len(resources)} total resources")
        except Exception as e:
            logger.error(f"Failed to load resources: {e}")
            result["success"] = False
            result["error"] = f"Failed to load resources: {e}"
            return result

        # 3. Query actual system state for each resource
        try:
            resource_states = await check_all_resources_state(resources)
            result["resources"] = [state.to_dict() for state in resource_states]
            logger.info(f"Checked state for {len(resource_states)} resources")
        except Exception as e:
            logger.error(f"Failed to check resource states: {e}")
            result["success"] = False
            result["error"] = f"Failed to check resource states: {e}"

        logger.info("Clockwork status pipeline complete")
        return result

    def _get_pulumi_state(self, project_name: str) -> dict[str, Any]:
        """Get Pulumi stack state for the project.

        Args:
            project_name: Name of the Pulumi project

        Returns:
            Dict with Pulumi state information:
                - available: Whether stack exists and is accessible
                - stack_name: Name of the stack
                - resource_count: Number of resources in stack
                - outputs: Stack outputs
                - last_update: Last update time (if available)

        Raises:
            Exception: If stack cannot be accessed
        """
        settings = get_settings()

        # Set Pulumi passphrase from settings
        os.environ["PULUMI_CONFIG_PASSPHRASE"] = (
            settings.pulumi_config_passphrase
        )

        stack_name = "dev"

        # Create minimal program for selecting stack
        def empty_program():
            """Empty Pulumi program for status operations."""
            pass

        try:
            # Try to select existing stack
            stack = auto.select_stack(
                stack_name=stack_name,
                project_name=project_name,
                program=empty_program,
            )

            # Get stack info
            info = stack.info()
            outputs = stack.outputs()

            state: dict[str, Any] = {
                "available": True,
                "stack_name": stack_name,
                "outputs": {k: v.value for k, v in outputs.items()},
            }

            # Add resource count from info if available
            if info:
                state["resource_count"] = info.resource_count
                if info.last_update:
                    state["last_update"] = info.last_update.isoformat()

            return state

        except auto.errors.StackNotFoundError:
            return {
                "available": False,
                "error": f"Stack '{stack_name}' not found for project '{project_name}'",
            }
        except Exception as e:
            return {
                "available": False,
                "error": str(e),
            }
