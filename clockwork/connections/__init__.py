"""Clockwork Connections - First-class connection components."""

# Import BaseAssertion to make it available for forward reference resolution
try:
    from clockwork.assertions.base import BaseAssertion
except ImportError:
    # If assertions aren't available yet, that's okay
    BaseAssertion = None

from .base import Connection
from .database import DatabaseConnection
from .dependency import DependencyConnection
from .file import FileConnection
from .network import NetworkConnection
from .service_mesh import ServiceMeshConnection

__all__ = [
    "Connection",
    "DatabaseConnection",
    "DependencyConnection",
    "FileConnection",
    "NetworkConnection",
    "ServiceMeshConnection",
]

# Rebuild models after all imports to resolve forward references
if BaseAssertion is not None:
    Connection.model_rebuild()
    DatabaseConnection.model_rebuild()
    DependencyConnection.model_rebuild()
    FileConnection.model_rebuild()
    NetworkConnection.model_rebuild()
    ServiceMeshConnection.model_rebuild()
