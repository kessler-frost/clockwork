"""Base resource classes for Clockwork."""

from typing import Dict, Any, Optional
from pydantic import BaseModel
from enum import Enum


class ArtifactSize(str, Enum):
    """Size hint for AI artifact generation."""
    SMALL = "small"      # ~100-500 words
    MEDIUM = "medium"    # ~500-2000 words
    LARGE = "large"      # ~2000+ words


class Resource(BaseModel):
    """Base resource class - all resources inherit from this."""

    name: str
    description: Optional[str] = None

    def needs_artifact_generation(self) -> bool:
        """Does this resource need AI to generate content?"""
        raise NotImplementedError(f"{self.__class__.__name__} must implement needs_artifact_generation()")

    def to_pyinfra_operations(self, artifacts: Dict[str, Any]) -> str:
        """Generate PyInfra operations code (template-based).

        Args:
            artifacts: Dict mapping resource names to generated content

        Returns:
            String of PyInfra operation code
        """
        raise NotImplementedError(f"{self.__class__.__name__} must implement to_pyinfra_operations()")

    def to_pyinfra_destroy_operations(self, artifacts: Dict[str, Any]) -> str:
        """Generate PyInfra operations code to destroy/remove this resource.

        Args:
            artifacts: Dict mapping resource names to generated content

        Returns:
            String of PyInfra operation code to destroy the resource
        """
        raise NotImplementedError(f"{self.__class__.__name__} must implement to_pyinfra_destroy_operations()")
