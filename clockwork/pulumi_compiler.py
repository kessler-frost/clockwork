"""
Pulumi Compiler - Converts resources to Pulumi infrastructure using Automation API.

This compiler uses Pulumi's Automation API to manage infrastructure as code
programmatically, providing methods for deployment, preview, and destruction.
"""

import logging
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pulumi import automation as auto

from .settings import get_settings

logger = logging.getLogger(__name__)


class PulumiCompiler:
    """Compiles resources into Pulumi infrastructure using Automation API."""

    def __init__(self, project_dir: Path | None = None):
        """
        Initialize the Pulumi compiler.

        Args:
            project_dir: Base directory for the project (defaults to current directory)
        """
        settings = get_settings()
        self.project_dir = project_dir or Path.cwd()
        self.state_dir = settings.pulumi_state_dir
        if not isinstance(self.state_dir, Path):
            self.state_dir = Path(self.state_dir)

        # Set Pulumi passphrase from settings if not already set in environment
        if "PULUMI_CONFIG_PASSPHRASE" not in os.environ:
            os.environ["PULUMI_CONFIG_PASSPHRASE"] = settings.pulumi_config_passphrase
            logger.debug("Set PULUMI_CONFIG_PASSPHRASE from settings")

        logger.info(
            f"Initialized Pulumi compiler with state dir: {self.state_dir}"
        )

    def create_program(self, resources: list[Any]) -> Callable:
        """
        Create a Pulumi program function from resources.

        The program function is called by Pulumi's Automation API to define
        infrastructure. It iterates through resources and calls each resource's
        to_pulumi() method to create Pulumi resources.

        Args:
            resources: List of Resource objects with to_pulumi() methods

        Returns:
            Pulumi program function that can be passed to Automation API
        """

        def pulumi_program():
            """Generated Pulumi program that creates infrastructure."""
            logger.info(
                f"Executing Pulumi program with {len(resources)} resources"
            )

            for resource in resources:
                try:
                    if hasattr(resource, "to_pulumi"):
                        # Call resource's to_pulumi() method to create Pulumi resources
                        resource.to_pulumi()
                        logger.debug(
                            f"Created Pulumi resource: {resource.name}"
                        )
                    else:
                        logger.warning(
                            f"Resource {resource.name} does not implement to_pulumi()"
                        )
                except Exception as e:
                    logger.error(
                        f"Failed to create Pulumi resource {resource.name}: {e}"
                    )
                    raise

        return pulumi_program

    async def apply(
        self, resources: list[Any], project_name: str = "clockwork"
    ) -> dict[str, Any]:
        """
        Apply infrastructure changes using Pulumi.

        Creates or selects a stack, then performs a Pulumi up operation to
        deploy infrastructure. Returns a summary of the deployment.

        Args:
            resources: List of Resource objects to deploy
            project_name: Name of the Pulumi project (defaults to "clockwork")

        Returns:
            Dictionary with success status, summary, and outputs
        """
        logger.info(
            f"Applying {len(resources)} resources with Pulumi (project: {project_name})"
        )

        # Ensure state directory exists before applying
        self.state_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Create program function
            program = self.create_program(resources)

            # Create or select stack
            stack_name = "dev"
            stack = auto.create_or_select_stack(
                stack_name=stack_name,
                project_name=project_name,
                program=program,
            )
            logger.info(f"Using stack: {stack_name}")

            # Perform up operation
            logger.info("Running Pulumi up...")
            up_result = stack.up(on_output=lambda msg: logger.debug(msg))

            # Extract summary
            summary = up_result.summary
            outputs = up_result.outputs

            logger.info(
                f"Pulumi up completed: {summary.result} "
                f"(resources: +{summary.resource_changes.get('create', 0)} "
                f"~{summary.resource_changes.get('update', 0)} "
                f"-{summary.resource_changes.get('delete', 0)})"
            )

            return {
                "success": True,
                "summary": {
                    "result": summary.result,
                    "resource_changes": summary.resource_changes,
                },
                "outputs": {k: v.value for k, v in outputs.items()},
            }

        except Exception as e:
            logger.error(f"Pulumi apply failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "summary": None,
                "outputs": {},
            }

    async def destroy(self, project_name: str = "clockwork") -> dict[str, Any]:
        """
        Destroy infrastructure using Pulumi.

        Selects an existing stack and performs a Pulumi destroy operation to
        tear down all infrastructure. Returns a summary of the destruction.

        Args:
            project_name: Name of the Pulumi project (defaults to "clockwork")

        Returns:
            Dictionary with success status and summary
        """
        logger.info(f"Destroying infrastructure (project: {project_name})")

        # Ensure state directory exists before destroying
        self.state_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Select existing stack
            stack_name = "dev"

            # Note: For destroy, we need a minimal program
            # Pulumi doesn't require the full program for destroy operations
            def empty_program():
                """Empty Pulumi program for destroy operations."""
                pass

            stack = auto.select_stack(
                stack_name=stack_name,
                project_name=project_name,
                program=empty_program,
            )
            logger.info(f"Selected stack: {stack_name}")

            # Perform destroy operation
            logger.info("Running Pulumi destroy...")
            destroy_result = stack.destroy(
                on_output=lambda msg: logger.debug(msg)
            )

            # Extract summary
            summary = destroy_result.summary

            logger.info(
                f"Pulumi destroy completed: {summary.result}"
            )

            return {
                "success": True,
                "summary": {
                    "result": summary.result,
                    "resource_changes": summary.resource_changes or {},
                },
            }

        except Exception as e:
            logger.error(f"Pulumi destroy failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "summary": None,
            }

    async def preview(
        self, resources: list[Any], project_name: str = "clockwork"
    ) -> dict[str, Any]:
        """
        Preview infrastructure changes using Pulumi.

        Creates or selects a stack, then performs a Pulumi preview operation
        to show what changes would be made without actually applying them.

        Args:
            resources: List of Resource objects to preview
            project_name: Name of the Pulumi project (defaults to "clockwork")

        Returns:
            Dictionary with success status, summary, and change details
        """
        logger.info(
            f"Previewing {len(resources)} resources with Pulumi (project: {project_name})"
        )

        try:
            # Create program function
            program = self.create_program(resources)

            # Create or select stack
            stack_name = "dev"
            stack = auto.create_or_select_stack(
                stack_name=stack_name,
                project_name=project_name,
                program=program,
            )
            logger.info(f"Using stack: {stack_name}")

            # Perform preview operation
            logger.info("Running Pulumi preview...")
            preview_result = stack.preview(
                on_output=lambda msg: logger.debug(msg)
            )

            # Extract change summary
            change_summary = preview_result.change_summary

            # Calculate total changes
            total_changes = sum(
                change_summary.get(op, 0)
                for op in ["create", "update", "delete", "replace"]
            )

            logger.info(
                f"Pulumi preview completed: "
                f"{total_changes} total changes "
                f"(+{change_summary.get('create', 0)} "
                f"~{change_summary.get('update', 0)} "
                f"-{change_summary.get('delete', 0)})"
            )

            return {
                "success": True,
                "summary": {
                    "change_summary": change_summary,
                    "total_changes": total_changes,
                },
            }

        except Exception as e:
            logger.error(f"Pulumi preview failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "summary": None,
            }
