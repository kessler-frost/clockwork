"""Base assertion classes for Clockwork."""

from typing import Any, Optional
from pydantic import BaseModel


class BaseAssertion(BaseModel):
    """Base class for all type-safe assertions.

    Assertions validate that deployed resources match their desired runtime state.
    Each assertion compiles to a PyInfra operation that returns success/failure.

    Attributes:
        description: Optional human-readable description of what this assertion checks
        timeout_seconds: Maximum time to wait for assertion to pass (default: 30)

    Example:
        >>> class MyAssertion(BaseAssertion):
        ...     def to_pyinfra_operation(self, resource):
        ...         return 'server.shell(name="Check", commands=["test -f /tmp/file"])'
    """

    description: Optional[str] = None
    timeout_seconds: int = 30

    def to_pyinfra_operation(self, resource: Any) -> str:
        """Generate PyInfra operation code for this assertion.

        The generated operation should return exit code 0 on success and non-zero
        on failure. PyInfra will handle the actual execution and reporting.

        Args:
            resource: Parent resource this assertion belongs to. Used to access
                     resource-specific properties like name, paths, etc.

        Returns:
            PyInfra operation code as string that exits 0 on success, 1 on failure

        Raises:
            NotImplementedError: If subclass doesn't implement this method

        Example:
            >>> assertion = FileExistsAssert(path="/tmp/test.txt")
            >>> code = assertion.to_pyinfra_operation(resource)
            >>> print(code)
            server.shell(
                name="Assert: File /tmp/test.txt exists",
                commands=["test -f /tmp/test.txt"]
            )
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement to_pyinfra_operation()"
        )
