"""
Clockwork Service - FastAPI application for monitoring and remediation.

This module provides the main FastAPI application with health checks,
startup validation, project management, and remediation endpoints.
"""

import logging
from contextlib import asynccontextmanager
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, List

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from clockwork.resource_completer import ResourceCompleter
from clockwork.settings import get_settings
from clockwork.service.models import (
    ProjectRegistrationRequest,
    ProjectStatusResponse,
    RemediationRequest,
)
from clockwork.service.manager import ProjectManager
from clockwork.service.health import HealthChecker
from clockwork.service.remediation import RemediationEngine
from clockwork.core import ClockworkCore

logger = logging.getLogger(__name__)


class HealthResponse(BaseModel):
    """Health check response model."""

    status: str
    model: str
    base_url: str
    ai_connection: str


async def validate_ai_connection() -> bool:
    """
    Validate AI connection by creating a ResourceCompleter instance.

    Returns:
        True if connection is successful, False otherwise
    """
    try:
        settings = get_settings()
        logger.info(
            f"Validating AI connection to {settings.base_url} "
            f"with model {settings.model}"
        )

        # Create ResourceCompleter to validate connection
        # This will raise ValueError if API key is missing
        _ = ResourceCompleter(
            api_key=settings.api_key,
            model=settings.model,
            base_url=settings.base_url,
        )

        logger.info("AI connection validated successfully")
        return True

    except ValueError as e:
        logger.error(f"AI connection validation failed: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error during AI validation: {e}")
        return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events.

    Handles:
    - Startup: Validate AI connection, start monitoring
    - Shutdown: Stop monitoring, cleanup resources

    Args:
        app: FastAPI application instance
    """
    # Startup
    logger.info("Starting Clockwork service...")

    # Validate AI connection
    ai_ok = await validate_ai_connection()
    if not ai_ok:
        logger.warning(
            "AI connection validation failed - "
            "service will start but AI features may not work"
        )

    # Initialize monitoring components
    logger.info("Initializing monitoring components...")
    manager = ProjectManager()
    health_checker = HealthChecker(project_manager=manager)
    remediation_engine = RemediationEngine()

    # Wire up remediation callback
    async def remediation_callback(project_state, resource):
        """Callback for remediation when health check fails."""
        resource_name = resource.name or resource.__class__.__name__
        try:
            logger.warning(f"🔧 REMEDIATION CALLBACK INVOKED for {resource_name} in project {project_state.project_id}")
            logger.info(f"Resource type: {resource.__class__.__name__}")
            logger.info(f"Resource details: {resource.model_dump_json(indent=2)}")

            success = await remediation_engine.remediate_resource(resource, project_state)

            if success:
                logger.info(f"✅ Remediation successful for {resource_name}")
            else:
                logger.error(f"❌ Remediation failed for {resource_name}")
        except Exception as e:
            logger.error(f"💥 Remediation error for {resource_name}: {e}", exc_info=True)

    health_checker.set_remediation_callback(remediation_callback)

    # Store in app state for access by endpoints
    app.state.manager = manager
    app.state.health_checker = health_checker
    app.state.remediation_engine = remediation_engine

    # Start background monitoring
    logger.info("Starting background health monitoring...")
    await health_checker.start_monitoring()

    logger.info("Clockwork service started successfully")

    yield

    # Shutdown
    logger.info("Shutting down Clockwork service...")

    # Stop background monitoring
    logger.info("Stopping background health monitoring...")
    await health_checker.stop_monitoring()

    logger.info("Clockwork service shut down successfully")


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application instance
    """
    settings = get_settings()

    # Configure logging with both console and file handlers
    log_level = getattr(logging, settings.log_level.upper())
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove any existing handlers to avoid duplicates
    root_logger.handlers.clear()

    # Console handler (stdout)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(logging.Formatter(log_format))
    root_logger.addHandler(console_handler)

    # File handler with rotation
    log_file_path = Path.cwd() / settings.service_log_file
    log_file_path.parent.mkdir(parents=True, exist_ok=True)

    file_handler = RotatingFileHandler(
        filename=log_file_path,
        maxBytes=settings.service_log_max_bytes,
        backupCount=settings.service_log_backup_count,
        encoding="utf-8",
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(logging.Formatter(log_format))
    root_logger.addHandler(file_handler)

    logger.info(f"Logging configured: console + file ({log_file_path})")

    app = FastAPI(
        title="Clockwork Service",
        description="Intelligent Infrastructure Monitoring and Remediation",
        version="0.2.0",
        lifespan=lifespan,
    )

    # Initialize core (needed for loading resources during registration)
    core = ClockworkCore()

    @app.get("/health", response_model=HealthResponse)
    async def health() -> dict[str, Any]:
        """
        Health check endpoint.

        Returns service status and AI connection information.

        Returns:
            HealthResponse with status, model info, and AI connection status
        """
        settings = get_settings()

        # Check AI connection status
        try:
            ai_ok = await validate_ai_connection()
            ai_status = "connected" if ai_ok else "disconnected"
        except Exception as e:
            logger.error(f"Error checking AI connection: {e}")
            ai_status = "error"

        return {
            "status": "healthy",
            "model": settings.model,
            "base_url": settings.base_url,
            "ai_connection": ai_status,
        }

    @app.post("/projects/register", status_code=status.HTTP_201_CREATED)
    async def register_project(request: ProjectRegistrationRequest) -> dict[str, str]:
        """
        Register a project for monitoring.

        Args:
            request: ProjectRegistrationRequest with main_file path

        Returns:
            Dictionary with project_id

        Raises:
            HTTPException: If main_file doesn't exist or can't be loaded
        """
        main_file = Path(request.main_file)

        # Validate file exists
        if not main_file.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"File not found: {main_file}"
            )

        # Load resources from main.py
        try:
            resources = core._load_resources(main_file)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to load resources: {str(e)}"
            )

        # Register project with the manager from app.state
        manager = app.state.manager
        project_id = await manager.register_project(main_file, resources)

        return {"project_id": project_id}

    @app.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def unregister_project(project_id: str):
        """
        Unregister a project from monitoring.

        Args:
            project_id: Unique project identifier

        Raises:
            HTTPException: If project not found
        """
        manager = app.state.manager
        success = await manager.unregister_project(project_id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project not found: {project_id}"
            )

        return JSONResponse(status_code=status.HTTP_204_NO_CONTENT, content=None)

    @app.get("/projects")
    async def list_projects() -> List[dict[str, Any]]:
        """
        List all registered projects.

        Returns:
            List of project summaries
        """
        manager = app.state.manager
        projects = await manager.list_projects()

        return [
            {
                "project_id": project.project_id,
                "main_file": str(project.main_file),
                "resource_count": len(project.resources),
                "registered_at": project.registered_at.isoformat()
            }
            for project in projects
        ]

    @app.get("/projects/{project_id}/status")
    async def get_project_status(project_id: str) -> ProjectStatusResponse:
        """
        Get project health status.

        Args:
            project_id: Unique project identifier

        Returns:
            ProjectStatusResponse with health statistics

        Raises:
            HTTPException: If project not found
        """
        manager = app.state.manager
        project = await manager.get_project(project_id)

        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project not found: {project_id}"
            )

        # Calculate health statistics
        healthy_count = sum(1 for status in project.health_status.values() if status)
        total_count = len(project.health_status)
        unhealthy_count = total_count - healthy_count

        # Get most recent check time
        last_check = None
        if project.last_check:
            last_check = max(project.last_check.values())

        return ProjectStatusResponse(
            project_id=project.project_id,
            resource_count=total_count,
            healthy_count=healthy_count,
            unhealthy_count=unhealthy_count,
            last_check=last_check
        )

    @app.post("/projects/{project_id}/remediate")
    async def remediate_project(
        project_id: str,
        request: RemediationRequest = RemediationRequest()
    ) -> dict[str, Any]:
        """
        Trigger remediation for unhealthy resources.

        This is a placeholder endpoint that will be implemented by Agent 3.
        Currently returns a success response with the resources that would be remediated.

        Args:
            project_id: Unique project identifier
            request: Optional RemediationRequest specifying resource_name

        Returns:
            Dictionary with remediation status

        Raises:
            HTTPException: If project not found
        """
        manager = app.state.manager
        project = await manager.get_project(project_id)

        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project not found: {project_id}"
            )

        # Determine which resources to remediate
        if request.resource_name:
            # Specific resource
            if request.resource_name not in project.health_status:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Resource not found: {request.resource_name}"
                )
            resources_to_remediate = [request.resource_name]
        else:
            # All unhealthy resources
            resources_to_remediate = [
                name for name, healthy in project.health_status.items()
                if not healthy
            ]

        # Placeholder response - actual remediation will be implemented by Agent 3
        return {
            "status": "remediation_scheduled",
            "project_id": project_id,
            "resources": resources_to_remediate,
            "message": "Remediation placeholder - to be implemented by Agent 3"
        }

    @app.get("/projects/{project_id}/resources")
    async def get_project_resources(project_id: str) -> List[dict[str, Any]]:
        """
        Get detailed information about project resources.

        Args:
            project_id: Unique project identifier

        Returns:
            List of resource details with health status

        Raises:
            HTTPException: If project not found
        """
        manager = app.state.manager
        project = await manager.get_project(project_id)

        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project not found: {project_id}"
            )

        return [
            {
                "name": resource.name,
                "type": resource.__class__.__name__,
                "healthy": project.health_status.get(resource.name, True),
                "last_check": project.last_check.get(resource.name).isoformat()
                    if resource.name in project.last_check else None,
                "remediation_attempts": project.remediation_attempts.get(resource.name, 0)
            }
            for resource in project.resources
            if resource.name
        ]

    return app


# Create default app instance
app = create_app()
