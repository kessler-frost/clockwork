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

        # 2. Complete resources (AI stage)
        completed_resources = self._complete_resources_safe(resources)

        # 3. Set compiler output directory relative to main.py location
        settings = get_settings()
        self.pyinfra_compiler.output_dir = main_file.parent / settings.pyinfra_output_dir

        # 4. Compile to PyInfra (template stage)
        pyinfra_dir = self.pyinfra_compiler.compile(completed_resources)
        logger.info(f"Compiled to PyInfra: {pyinfra_dir}")

        # 5. Execute PyInfra deploy (unless dry run)
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

        # 2. Complete resources if needed (AI stage)
        completed_resources = self._complete_resources_safe(resources)

        # 3. Set compiler output directory relative to main.py location
        settings = get_settings()
        self.pyinfra_compiler.output_dir = main_file.parent / settings.pyinfra_output_dir

        # 4. Compile to PyInfra using compile_assert()
        pyinfra_dir = self.pyinfra_compiler.compile_assert(completed_resources)
        logger.info(f"Compiled assertions to PyInfra: {pyinfra_dir}")

        # 5. Execute PyInfra assert.py (unless dry run)
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
