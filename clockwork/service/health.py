"""Background health checking system for Clockwork resources.

This module provides continuous health monitoring of deployed resources with
resource-specific check intervals and automatic remediation triggering.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, Any, TYPE_CHECKING

from clockwork.resources.base import Resource
from clockwork.resources.file import FileResource
from clockwork.resources.directory import DirectoryResource
from clockwork.resources.docker import DockerResource
from clockwork.resources.apple_container import AppleContainerResource
from clockwork.resources.git import GitRepoResource
from clockwork.settings import get_settings

if TYPE_CHECKING:
    from clockwork.core import ClockworkCore
    from .models import ProjectState

logger = logging.getLogger(__name__)


class HealthChecker:
    """Background health checking system with resource-specific intervals.

    This class manages continuous health monitoring of infrastructure resources.
    Different resource types have different check intervals:
    - FileResource/DirectoryResource: Check once after registration, then skip
    - DockerResource/AppleContainerResource: Every 30s (configurable)
    - GitRepoResource: Every 5 minutes (300s)
    - Default: service_check_interval_default from settings

    The health checker integrates with ClockworkCore.assert_resources() to
    validate resource health and triggers remediation on failures.

    Attributes:
        core: ClockworkCore instance for running assertions
        running: Flag indicating if monitoring loop is active
        monitor_task: Background asyncio task for monitoring loop
        last_checks: Dict tracking last check time per project/resource
    """

    # Resource-specific check intervals (in seconds)
    INTERVAL_FILE = float('inf')  # Check once, then skip
    INTERVAL_DIRECTORY = float('inf')  # Check once, then skip
    INTERVAL_CONTAINER = 30  # Container resources (Docker/AppleContainer)
    INTERVAL_GIT = 300  # Git repository resources (5 minutes)

    def __init__(
        self,
        project_manager: Optional[Any] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None
    ):
        """Initialize HealthChecker.

        Args:
            project_manager: ProjectManager instance for accessing project state
            api_key: Optional API key override for ClockworkCore
            model: Optional model override for ClockworkCore
            base_url: Optional base URL override for ClockworkCore
        """
        # Import ClockworkCore lazily to avoid circular imports
        from clockwork.core import ClockworkCore

        self.core = ClockworkCore(api_key=api_key, model=model, base_url=base_url)
        self.project_manager = project_manager
        self.running = False
        self.monitor_task: Optional[asyncio.Task] = None
        self.last_checks: Dict[str, Dict[str, datetime]] = {}  # project_id -> resource_name -> timestamp
        self._remediation_callback = None  # Optional callback for remediation
        logger.info("HealthChecker initialized")

    def get_check_interval(self, resource: Resource) -> float:
        """Get check interval in seconds for a resource type.

        Different resource types have different monitoring needs:
        - Static resources (files, directories) are checked once
        - Dynamic resources (containers) are checked frequently
        - Repository resources are checked periodically

        Args:
            resource: Resource instance to determine interval for

        Returns:
            float: Seconds until next check (float('inf') means check once only)
        """
        settings = get_settings()

        # Check resource type and return appropriate interval
        if isinstance(resource, (FileResource, DirectoryResource)):
            return self.INTERVAL_FILE

        if isinstance(resource, (DockerResource, AppleContainerResource)):
            return self.INTERVAL_CONTAINER

        if isinstance(resource, GitRepoResource):
            return self.INTERVAL_GIT

        # Default interval from settings
        return float(settings.service_check_interval_default)

    def should_check(self, project_id: str, resource: Resource) -> bool:
        """Determine if a resource should be checked now.

        Checks are scheduled based on resource type and last check time.
        Resources with infinite interval (files, directories) are only
        checked once.

        Args:
            project_id: Project identifier
            resource: Resource to check

        Returns:
            bool: True if resource should be checked now, False otherwise
        """
        resource_name = resource.name or resource.__class__.__name__

        # Get last check time for this resource
        if project_id not in self.last_checks:
            self.last_checks[project_id] = {}

        last_check = self.last_checks[project_id].get(resource_name)

        # If never checked, check now
        if last_check is None:
            return True

        # Get check interval for this resource type
        interval = self.get_check_interval(resource)

        # If interval is infinite, skip (already checked once)
        if interval == float('inf'):
            return False

        # Check if enough time has passed since last check
        elapsed = (datetime.now() - last_check).total_seconds()
        return elapsed >= interval

    async def check_resource_health(
        self,
        project_state: "ProjectState",
        resource: Resource
    ) -> bool:
        """Check health of a single resource using PyInfra assertions.

        Uses the pre-generated assert_<resource-name>.py file from the project's
        .clockwork directory instead of regenerating it. This is faster and avoids
        race conditions.

        Args:
            project_state: Project state containing resource context
            resource: Resource to check

        Returns:
            bool: True if resource is healthy, False if unhealthy
        """
        try:
            resource_name = resource.name or resource.__class__.__name__
            logger.debug(f"Checking health for resource: {resource_name}")

            # Use pre-generated assert_<resource-name>.py from .clockwork directory
            settings = get_settings()
            pyinfra_dir = project_state.main_file.parent / settings.pyinfra_output_dir
            assert_file = pyinfra_dir / f"assert_{resource_name}.py"

            if not assert_file.exists():
                logger.warning(
                    f"assert_{resource_name}.py not found at {assert_file}. "
                    "Per-resource assertions may not have been generated yet."
                )
                return False

            # Execute PyInfra assertions directly
            import subprocess
            cmd = ["pyinfra", "-y", "inventory.py", f"assert_{resource_name}.py"]

            result = subprocess.run(
                cmd,
                cwd=pyinfra_dir,
                capture_output=True,
                text=True,
                timeout=30  # 30 second timeout for assertions
            )

            is_healthy = result.returncode == 0

            logger.debug(
                f"Health check result for {resource_name}: "
                f"{'healthy' if is_healthy else 'unhealthy'} "
                f"(exit code: {result.returncode})"
            )

            if not is_healthy:
                logger.debug(f"Assertion output for {resource_name}: {result.stdout}")
                logger.debug(f"Assertion errors for {resource_name}: {result.stderr}")

            return is_healthy

        except subprocess.TimeoutExpired:
            logger.error(f"Health check timed out after 30 seconds for {resource_name}")
            return False
        except Exception as e:
            logger.error(f"Health check failed for resource {resource_name}: {e}", exc_info=True)
            return False

    async def check_project_health(
        self,
        project_state: "ProjectState"
    ) -> Dict[str, bool]:
        """Run assertions for all resources in a project.

        Checks health for resources that are due for checking based on
        their interval schedule. Runs assertions individually for each resource
        to accurately identify which resources are healthy vs unhealthy.

        Args:
            project_state: Project state with resources to check

        Returns:
            Dict mapping resource names to health status (True=healthy)
        """
        health_results = {}
        project_id = project_state.project_id
        resources_to_check = []

        logger.info(f"Checking health for project: {project_id}")

        # Determine which resources are due for checking
        for resource in project_state.resources:
            resource_name = resource.name or resource.__class__.__name__

            # Check if this resource is due for checking
            if not self.should_check(project_id, resource):
                logger.debug(
                    f"Skipping health check for {resource_name} "
                    "(not due based on interval)"
                )
                # Use last known health status
                health_results[resource_name] = project_state.health_status.get(
                    resource_name,
                    True  # Default to healthy if unknown
                )
            else:
                resources_to_check.append(resource)

        # If no resources need checking, return current status
        if not resources_to_check:
            logger.debug("No resources due for health check")
            return health_results

        # Run assertions individually for each resource
        logger.info(f"Running health check for {len(resources_to_check)} resources")
        check_time = datetime.now()

        for resource in resources_to_check:
            resource_name = resource.name or resource.__class__.__name__

            # Check this resource's health individually
            is_healthy = await self.check_resource_health(project_state, resource)
            health_results[resource_name] = is_healthy

            # Update last check timestamp
            if project_id not in self.last_checks:
                self.last_checks[project_id] = {}
            self.last_checks[project_id][resource_name] = check_time

            logger.info(
                f"Resource {resource_name}: {'✓ healthy' if is_healthy else '✗ unhealthy'}"
            )

        return health_results


    def set_remediation_callback(self, callback) -> None:
        """Set callback function for triggering remediation.

        The callback should accept (project_state, resource) arguments.

        Args:
            callback: Async function to call when remediation is needed
        """
        self._remediation_callback = callback
        logger.info("Remediation callback registered")

    async def _trigger_remediation(
        self,
        project_state: "ProjectState",
        resource: Resource
    ) -> None:
        """Trigger remediation for a failed resource.

        Calls the registered remediation callback if available.
        This is typically handled by Agent 4 (RemediationEngine).

        Args:
            project_state: Project containing the resource
            resource: Failed resource needing remediation
        """
        resource_name = resource.name or resource.__class__.__name__

        if self._remediation_callback is None:
            logger.warning(
                f"No remediation callback registered for {resource_name}. "
                "Resource failure will not be remediated automatically."
            )
            return

        try:
            logger.info(f"Triggering remediation for resource: {resource_name}")
            await self._remediation_callback(project_state, resource)
        except Exception as e:
            logger.error(f"Remediation callback failed for {resource_name}: {e}")

    async def _monitoring_loop(self) -> None:
        """Background monitoring loop.

        Continuously monitors all registered projects and checks resource
        health based on their intervals. Triggers remediation for failed
        resources.

        This loop runs until stop_monitoring() is called.
        """
        if self.project_manager is None:
            logger.error("Cannot start monitoring loop without ProjectManager")
            return

        logger.info("Health monitoring loop started")

        while self.running:
            try:
                # Get all projects from ProjectManager
                projects = await self.project_manager.list_projects()

                # Check health for all registered projects
                for project_state in projects:
                    project_id = project_state.project_id
                    try:
                        # Check project health
                        health_results = await self.check_project_health(project_state)

                        # Update project health status via ProjectManager
                        for resource_name, is_healthy in health_results.items():
                            await self.project_manager.update_health_status(
                                project_id,
                                resource_name,
                                is_healthy
                            )

                            # Trigger remediation for failed resources
                            if not is_healthy:
                                logger.warning(f"⚠️  Resource {resource_name} is UNHEALTHY, triggering remediation")
                                # Find the resource object
                                resource = next(
                                    (r for r in project_state.resources
                                     if (r.name or r.__class__.__name__) == resource_name),
                                    None
                                )
                                if resource:
                                    logger.info(f"Found resource object for {resource_name}, calling remediation")
                                    await self._trigger_remediation(
                                        project_state,
                                        resource
                                    )
                                else:
                                    logger.error(f"Could not find resource object for {resource_name}")

                    except Exception as e:
                        logger.error(
                            f"Error checking project {project_id}: {e}",
                            exc_info=True
                        )

                # Sleep for 1 second between monitoring cycles
                await asyncio.sleep(1)

            except Exception as e:
                logger.error(f"Unexpected error in monitoring loop: {e}", exc_info=True)
                # Continue running even after errors
                await asyncio.sleep(1)

        logger.info("Health monitoring loop stopped")

    async def start_monitoring(self) -> None:
        """Start background health monitoring task.

        Launches the monitoring loop as an asyncio task. The loop
        will run until stop_monitoring() is called.

        Raises:
            RuntimeError: If monitoring is already running
        """
        if self.running:
            raise RuntimeError("Health monitoring is already running")

        self.running = True
        self.monitor_task = asyncio.create_task(self._monitoring_loop())
        logger.info("Health monitoring started")

    async def stop_monitoring(self) -> None:
        """Stop background health monitoring task.

        Gracefully stops the monitoring loop and waits for it to complete.
        """
        if not self.running:
            logger.warning("Health monitoring is not running")
            return

        self.running = False

        if self.monitor_task:
            try:
                # Wait for monitoring loop to complete
                await asyncio.wait_for(self.monitor_task, timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning("Monitoring task did not stop within timeout, cancelling")
                self.monitor_task.cancel()
                try:
                    await self.monitor_task
                except asyncio.CancelledError:
                    pass

        logger.info("Health monitoring stopped")

    async def get_status(self) -> Dict[str, Any]:
        """Get current health checker status.

        Returns:
            Dict with monitoring status information
        """
        projects_count = 0
        if self.project_manager:
            projects = await self.project_manager.list_projects()
            projects_count = len(projects)

        return {
            "running": self.running,
            "projects_monitored": projects_count,
            "total_checks": sum(len(checks) for checks in self.last_checks.values()),
        }
