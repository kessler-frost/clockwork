"""Clockwork service package for monitoring and remediation."""

# Avoid circular imports by using lazy imports for app
from clockwork.service.health import HealthChecker
from clockwork.service.manager import ProjectManager
from clockwork.service.models import (
    ProjectRegistrationRequest,
    ProjectState,
    ProjectStatusResponse,
    RemediationRequest,
)
from clockwork.service.tools import ToolSelector

__all__ = [
    "HealthChecker",
    "ProjectManager",
    "ProjectState",
    "ProjectRegistrationRequest",
    "ProjectStatusResponse",
    "RemediationEngine",
    "RemediationRequest",
    "ToolSelector",
]

# Lazy imports to avoid circular dependencies
def get_app():
    """Get the FastAPI app instance (lazy import)."""
    from clockwork.service.app import app
    return app

def create_app():
    """Create a new FastAPI app instance (lazy import)."""
    from clockwork.service.app import create_app as _create_app
    return _create_app()

def __getattr__(name):
    """Lazy import for modules that cause circular dependencies."""
    if name == "RemediationEngine":
        from clockwork.service.remediation import RemediationEngine
        return RemediationEngine
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
