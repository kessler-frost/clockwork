"""
Clockwork Service - Simple FastAPI application for health checking.

This module provides a basic FastAPI application with a health endpoint.
"""

from typing import Any

from fastapi import FastAPI


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application instance
    """
    app = FastAPI(
        title="Clockwork Service",
        description="Simple health check service",
        version="0.4.0",
    )

    @app.get("/health")
    async def health() -> dict[str, Any]:
        """
        Health check endpoint.

        Returns:
            Dictionary with status
        """
        return {"status": "healthy"}

    return app


# Create default app instance
app = create_app()
