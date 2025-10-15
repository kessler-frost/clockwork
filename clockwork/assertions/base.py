"""Base assertion classes for Clockwork."""

from typing import Any, Optional
from pydantic import BaseModel


class BaseAssertion(BaseModel):
    """Base class for all type-safe assertions.

    Assertions validate that deployed resources match their desired runtime state.

    Attributes:
        description: Optional human-readable description of what this assertion checks
        timeout_seconds: Maximum time to wait for assertion to pass (default: 30)

    Example:
        >>> class MyAssertion(BaseAssertion):
        ...     description: str = "Check file exists"
        ...     timeout_seconds: int = 5
    """

    description: Optional[str] = None
    timeout_seconds: int = 30

    async def check(self, resource: "Resource") -> bool:
        """Check if this assertion passes for the given resource.

        Args:
            resource: The resource to validate

        Returns:
            True if assertion passes, False otherwise
        """
        raise NotImplementedError("Subclasses must implement check()")
