"""Base resource classes for Clockwork."""

from typing import Dict, Any, Optional, List, Union, TYPE_CHECKING
from pydantic import BaseModel
from enum import Enum

if TYPE_CHECKING:
    from clockwork.assertions.base import BaseAssertion


class ArtifactSize(str, Enum):
    """Size hint for AI artifact generation."""
    SMALL = "small"      # ~100-500 words
    MEDIUM = "medium"    # ~500-2000 words
    LARGE = "large"      # ~2000+ words


class Resource(BaseModel):
    """Base resource class - all resources inherit from this."""

    name: str
    description: Optional[str] = None
    assertions: Optional[List["BaseAssertion"]] = None

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

    def to_pyinfra_assert_operations(self, artifacts: Dict[str, Any]) -> str:
        """Generate PyInfra operations code for assertions.

        Only processes BaseAssertion objects (type-safe assertions).

        Args:
            artifacts: Dict mapping resource names to generated content

        Returns:
            String of PyInfra assertion operation code
        """
        if not self.assertions:
            return ""

        # Import here to avoid circular imports
        from clockwork.assertions.base import BaseAssertion

        operations = []
        has_object_assertions = any(isinstance(a, BaseAssertion) for a in self.assertions)

        if not has_object_assertions:
            return ""

        operations.append(f"\n# Assertions for resource: {self.name}")

        for assertion in self.assertions:
            # Only handle BaseAssertion objects
            if isinstance(assertion, BaseAssertion):
                operations.append(assertion.to_pyinfra_operation(self))

        return "\n".join(operations)
