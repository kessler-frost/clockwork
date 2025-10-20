"""
Clockwork Resources - Pydantic models for composable infrastructure primitives.
"""

# Import BaseAssertion to resolve forward references, then rebuild models
from clockwork.assertions.base import BaseAssertion  # noqa: F401

from .apple_container import AppleContainerResource
from .base import Resource
from .blank import BlankResource
from .docker import DockerResource
from .file import FileResource
from .git import GitRepoResource

Resource.model_rebuild()
FileResource.model_rebuild()
AppleContainerResource.model_rebuild()
DockerResource.model_rebuild()
GitRepoResource.model_rebuild()
BlankResource.model_rebuild()

__all__ = [
    "AppleContainerResource",
    "BlankResource",
    "DockerResource",
    "FileResource",
    "GitRepoResource",
    "Resource",
]
