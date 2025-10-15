"""Clockwork service package - Simple FastAPI health check service."""

__all__ = [
    "get_app",
    "create_app",
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
