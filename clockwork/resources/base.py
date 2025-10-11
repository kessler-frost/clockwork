"""Base resource classes for Clockwork."""

from typing import Dict, Any, Optional, List, TYPE_CHECKING
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
    """Base resource class - all resources inherit from this.

    The new completion-based architecture allows resources to have optional fields
    that can be filled in by AI during the completion stage. Instead of generating
    separate "artifacts", the AI directly populates missing fields on the resource
    objects themselves.

    Completion Flow:
    1. User creates resource with some fields set to None (e.g., name=None, image=None)
    2. needs_completion() checks if any completable fields are None
    3. AI fills in the missing fields by creating a new completed resource instance
    4. PyInfra operations use self.* fields directly (no artifacts dict needed)

    Attributes:
        name: Optional unique identifier (can be AI-completed if None)
        description: Optional human-readable description (used as context for AI)
        assertions: Optional list of type-safe assertion objects for validation
        tools: Optional list of PydanticAI tools (duckduckgo_search_tool(), MCPServerStdio, etc.)
               for AI-powered completion operations
    """

    name: Optional[str] = None
    description: Optional[str] = None
    assertions: Optional[List["BaseAssertion"]] = None

    # AI and integration capabilities
    tools: Optional[List[Any]] = None  # PydanticAI tools (duckduckgo_search_tool(), MCPServerStdio, etc.)

    def needs_completion(self) -> bool:
        """Check if this resource needs AI completion for any fields.

        Override this method in subclasses to define which fields can be AI-completed.
        The default implementation only checks if name is None.

        Returns:
            True if any completable fields are None, False otherwise

        Example:
            class MyResource(Resource):
                content: Optional[str] = None

                def needs_completion(self) -> bool:
                    return self.name is None or self.content is None
        """
        return self.name is None

    def to_pyinfra_operations(self) -> str:
        """Generate PyInfra operations code (template-based).

        This method is called after AI completion, so all required fields should
        be populated. Access fields directly via self.* instead of using an
        artifacts dict.

        Returns:
            String of PyInfra operation code

        Example:
            def to_pyinfra_operations(self) -> str:
                return f'''
files.file(
    name="Create {self.name}",
    path="/tmp/{self.name}",
    content="{self.content}"
)
'''
        """
        raise NotImplementedError(f"{self.__class__.__name__} must implement to_pyinfra_operations()")

    def to_pyinfra_destroy_operations(self) -> str:
        """Generate PyInfra operations code to destroy/remove this resource.

        Access resource fields directly via self.* to generate cleanup operations.

        Returns:
            String of PyInfra operation code to destroy the resource

        Example:
            def to_pyinfra_destroy_operations(self) -> str:
                return f'''
files.file(
    name="Remove {self.name}",
    path="/tmp/{self.name}",
    present=False
)
'''
        """
        raise NotImplementedError(f"{self.__class__.__name__} must implement to_pyinfra_destroy_operations()")

    def to_pyinfra_assert_operations(self) -> str:
        """Generate PyInfra operations code for assertions.

        Only processes BaseAssertion objects (type-safe assertions).
        Access resource fields directly via self.* when generating assertions.

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
