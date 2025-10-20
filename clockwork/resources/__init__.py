"""
Clockwork Resources - Pydantic models for composable infrastructure primitives.
"""

from .base import Resource
from .file import FileResource
from .apple_container import AppleContainerResource
from .docker import DockerResource
from .git import GitRepoResource
from .blank import BlankResource

# Import BaseAssertion to resolve forward references, then rebuild models
from clockwork.assertions.base import BaseAssertion  # noqa: F401
Resource.model_rebuild()
FileResource.model_rebuild()
AppleContainerResource.model_rebuild()
DockerResource.model_rebuild()
GitRepoResource.model_rebuild()
BlankResource.model_rebuild()

__all__ = ["Resource", "FileResource", "AppleContainerResource", "DockerResource", "GitRepoResource", "BlankResource"]
