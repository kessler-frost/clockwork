"""
Clockwork Resources - Pydantic models for declarative infrastructure.
"""

from .base import Resource, ArtifactSize
from .file import FileResource

__all__ = ["Resource", "ArtifactSize", "FileResource"]
