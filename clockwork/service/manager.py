"""Project state management for Clockwork service."""

import asyncio
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from clockwork.service.models import ProjectState
from clockwork.resources.base import Resource


class ProjectManager:
    """Singleton manager for project state.

    Manages in-memory storage of project states and provides thread-safe
    operations for registration, status tracking, and health monitoring.

    Attributes:
        _instance: Singleton instance
        _projects: In-memory storage of project states (project_id -> ProjectState)
        _lock: Asyncio lock for thread-safe operations
    """

    _instance: Optional["ProjectManager"] = None
    _projects: Dict[str, ProjectState]
    _lock: asyncio.Lock

    def __new__(cls) -> "ProjectManager":
        """Ensure singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._projects = {}
            cls._instance._lock = asyncio.Lock()
        return cls._instance

    async def register_project(
        self,
        main_file: Path,
        resources: List[Resource]
    ) -> str:
        """Register a project for monitoring.

        Args:
            main_file: Path to the project's main.py file
            resources: List of resources to monitor

        Returns:
            project_id: Unique identifier for the registered project

        Example:
            manager = ProjectManager()
            project_id = await manager.register_project(
                Path("examples/my-app/main.py"),
                [nginx_resource, postgres_resource]
            )
        """
        async with self._lock:
            project_id = str(uuid.uuid4())

            # Initialize health status for all resources
            health_status = {resource.name: True for resource in resources if resource.name}
            remediation_attempts = {resource.name: 0 for resource in resources if resource.name}

            state = ProjectState(
                project_id=project_id,
                main_file=main_file,
                resources=resources,
                last_check={},
                health_status=health_status,
                remediation_attempts=remediation_attempts,
                registered_at=datetime.now()
            )

            self._projects[project_id] = state
            return project_id

    async def unregister_project(self, project_id: str) -> bool:
        """Unregister a project from monitoring.

        Args:
            project_id: Unique project identifier

        Returns:
            True if project was unregistered, False if not found
        """
        async with self._lock:
            if project_id in self._projects:
                del self._projects[project_id]
                return True
            return False

    async def get_project(self, project_id: str) -> Optional[ProjectState]:
        """Get project state by ID.

        Args:
            project_id: Unique project identifier

        Returns:
            ProjectState if found, None otherwise
        """
        async with self._lock:
            return self._projects.get(project_id)

    async def list_projects(self) -> List[ProjectState]:
        """List all registered projects.

        Returns:
            List of all ProjectState objects
        """
        async with self._lock:
            return list(self._projects.values())

    async def update_health_status(
        self,
        project_id: str,
        resource_name: str,
        healthy: bool
    ) -> bool:
        """Update health status for a resource.

        Args:
            project_id: Unique project identifier
            resource_name: Name of the resource
            healthy: Health status (True=healthy, False=unhealthy)

        Returns:
            True if updated, False if project not found
        """
        async with self._lock:
            project = self._projects.get(project_id)
            if not project:
                return False

            project.health_status[resource_name] = healthy
            project.last_check[resource_name] = datetime.now()
            return True

    async def increment_remediation_attempt(
        self,
        project_id: str,
        resource_name: str
    ) -> bool:
        """Increment remediation attempt counter for a resource.

        Args:
            project_id: Unique project identifier
            resource_name: Name of the resource

        Returns:
            True if incremented, False if project not found
        """
        async with self._lock:
            project = self._projects.get(project_id)
            if not project:
                return False

            current = project.remediation_attempts.get(resource_name, 0)
            project.remediation_attempts[resource_name] = current + 1
            return True

    async def reset_remediation_attempts(
        self,
        project_id: str,
        resource_name: str
    ) -> bool:
        """Reset remediation attempt counter for a resource.

        Args:
            project_id: Unique project identifier
            resource_name: Name of the resource

        Returns:
            True if reset, False if project not found
        """
        async with self._lock:
            project = self._projects.get(project_id)
            if not project:
                return False

            project.remediation_attempts[resource_name] = 0
            return True

    async def get_health_summary(self, project_id: str) -> Optional[Dict[str, int]]:
        """Get health summary for a project.

        Args:
            project_id: Unique project identifier

        Returns:
            Dictionary with 'healthy', 'unhealthy', 'total' counts, or None if not found
        """
        async with self._lock:
            project = self._projects.get(project_id)
            if not project:
                return None

            healthy_count = sum(1 for status in project.health_status.values() if status)
            total_count = len(project.health_status)
            unhealthy_count = total_count - healthy_count

            return {
                "healthy": healthy_count,
                "unhealthy": unhealthy_count,
                "total": total_count
            }
