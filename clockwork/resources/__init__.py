"""
Clockwork Resources - Pydantic models for composable infrastructure primitives.
"""

# Import BaseAssertion to resolve forward references, then rebuild models
from clockwork.assertions.base import BaseAssertion  # noqa: F401

from .apple_container import AppleContainerResource
from .base import Resource
from .blank import BlankResource
from .docker_resource import DockerResource
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

# Conditionally export S3BucketResource if pulumi-aws is available
try:
    from .s3_resource import S3BucketResource
    from .s3_resource import WebsiteConfig as WebsiteConfig

    S3BucketResource.model_rebuild()
    __all__.append("S3BucketResource")
    __all__.append("WebsiteConfig")
except ImportError:
    # pulumi-aws not installed, S3BucketResource not available
    pass
