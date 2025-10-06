"""
Clockwork Resources - Pydantic models for declarative infrastructure.
"""

from .base import Resource, ArtifactSize
from .file import FileResource
from .docker import DockerServiceResource

__all__ = ["Resource", "ArtifactSize", "FileResource", "DockerServiceResource"]
