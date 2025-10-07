"""
Clockwork Resources - Pydantic models for declarative infrastructure.
"""

from .base import Resource, ArtifactSize
from .file import FileResource
from .docker import DockerServiceResource

# Import BaseAssertion to resolve forward references, then rebuild models
from clockwork.assertions.base import BaseAssertion  # noqa: F401
Resource.model_rebuild()
FileResource.model_rebuild()
DockerServiceResource.model_rebuild()

__all__ = ["Resource", "ArtifactSize", "FileResource", "DockerServiceResource"]
