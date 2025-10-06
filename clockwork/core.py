"""
Clockwork Core - Main pipeline orchestrator for PyInfra-based infrastructure.

Pipeline: Load resources → Generate artifacts (AI) → Compile to PyInfra → Execute deploy
"""

import logging
import subprocess
import importlib.util
from pathlib import Path
from typing import List, Dict, Any, Optional

from .artifact_generator import ArtifactGenerator
from .pyinfra_compiler import PyInfraCompiler

logger = logging.getLogger(__name__)


class ClockworkCore:
    """Main orchestrator for the Clockwork pipeline."""

    def __init__(
        self,
        openrouter_api_key: Optional[str] = None,
        openrouter_model: str = "openai/gpt-oss-20b:free"
    ):
        """
        Initialize ClockworkCore.

        Args:
            openrouter_api_key: OpenRouter API key (defaults to env var)
            openrouter_model: Model to use for artifact generation
        """
        self.artifact_generator = ArtifactGenerator(
            api_key=openrouter_api_key,
            model=openrouter_model
        )
        self.pyinfra_compiler = PyInfraCompiler()

        logger.info("ClockworkCore initialized")

    def apply(self, main_file: Path, dry_run: bool = False) -> Dict[str, Any]:
        """
        Full pipeline: load → generate → compile → deploy.

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

        # 2. Generate artifacts (AI stage)
        artifacts = self.artifact_generator.generate(resources)
        logger.info(f"Generated {len(artifacts)} artifacts")

        # 3. Compile to PyInfra (template stage)
        pyinfra_dir = self.pyinfra_compiler.compile(resources, artifacts)
        logger.info(f"Compiled to PyInfra: {pyinfra_dir}")

        # 4. Execute PyInfra deploy (unless dry run)
        if dry_run:
            logger.info("Dry run - skipping execution")
            return {
                "dry_run": True,
                "resources": len(resources),
                "artifacts": len(artifacts),
                "pyinfra_dir": str(pyinfra_dir)
            }

        result = self._execute_pyinfra(pyinfra_dir)
        logger.info("Clockwork pipeline complete")

        return result

    def plan(self, main_file: Path) -> Dict[str, Any]:
        """
        Plan mode: show what would be deployed without executing.

        Args:
            main_file: Path to main.py file

        Returns:
            Dict with plan information
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

    def _execute_pyinfra(self, pyinfra_dir: Path) -> Dict[str, Any]:
        """
        Execute the PyInfra deployment.

        Args:
            pyinfra_dir: Path to directory with inventory.py and deploy.py

        Returns:
            Dict with execution results
        """
        logger.info(f"Executing PyInfra deployment from: {pyinfra_dir}")

        # Run: pyinfra -y inventory.py deploy.py (auto-approve changes)
        cmd = ["pyinfra", "-y", "inventory.py", "deploy.py"]

        try:
            result = subprocess.run(
                cmd,
                cwd=pyinfra_dir,
                capture_output=True,
                text=True,
                check=True
            )

            logger.info("PyInfra deployment successful")
            return {
                "success": True,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode
            }

        except subprocess.CalledProcessError as e:
            logger.error(f"PyInfra deployment failed: {e.stderr}")
            raise RuntimeError(f"PyInfra deployment failed: {e.stderr}") from e
