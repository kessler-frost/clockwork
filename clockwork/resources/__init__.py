"""
Clockwork Resources - Pydantic models for declarative infrastructure.
"""

from .base import Resource
from .file import FileResource
from .template_file import TemplateFileResource
from .apple_container import AppleContainerResource
from .docker import DockerResource
from .directory import DirectoryResource
from .git import GitRepoResource
from .user import UserResource
from .brew import BrewPackageResource

# Import BaseAssertion to resolve forward references, then rebuild models
from clockwork.assertions.base import BaseAssertion  # noqa: F401
Resource.model_rebuild()
FileResource.model_rebuild()
TemplateFileResource.model_rebuild()
AppleContainerResource.model_rebuild()
DockerResource.model_rebuild()
DirectoryResource.model_rebuild()
GitRepoResource.model_rebuild()
UserResource.model_rebuild()
BrewPackageResource.model_rebuild()

__all__ = ["Resource", "FileResource", "TemplateFileResource", "AppleContainerResource", "DockerResource", "DirectoryResource", "GitRepoResource", "UserResource", "BrewPackageResource"]
