"""Shared utility functions for assertions."""

from typing import Any


def escape_shell_pattern(pattern: str) -> str:
    """Escape single quotes in a pattern for safe use in shell commands.

    Replaces single quotes with the escape sequence '\'' which closes the
    quoted string, adds an escaped quote, and reopens the quoted string.

    Args:
        pattern: Pattern string that may contain single quotes

    Returns:
        Pattern with escaped single quotes safe for shell interpolation

    Example:
        >>> escape_shell_pattern("it's working")
        "it'\\''s working"
    """
    return pattern.replace("'", "'\\''")


def resolve_container_name(assertion: Any, resource: Any) -> str:
    """Resolve container name from assertion or resource.

    Looks up the container name in this order:
    1. assertion.container_name (if set)
    2. resource.name (if available)
    3. "unknown" (fallback)

    Args:
        assertion: Assertion instance that may have container_name attribute
        resource: Resource instance that may have name attribute

    Returns:
        Resolved container name or "unknown" if neither is available

    Example:
        >>> resolve_container_name(assertion, resource)
        "nginx-web"
    """
    # Check assertion's container_name first
    container = getattr(assertion, "container_name", None)
    if container:
        return container

    # Fall back to resource's name
    return getattr(resource, "name", "unknown")
