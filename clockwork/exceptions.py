"""
Clockwork Exceptions - Custom exception classes for better error handling.

This module provides a hierarchy of exceptions for Clockwork operations,
with rich context for debugging and helpful suggestions for users.
"""

from typing import Any


class ClockworkError(Exception):
    """Base exception for all Clockwork errors."""

    pass


class CompletionError(ClockworkError):
    """Base class for completion failures.

    Provides rich context for debugging including:
    - Resource name that failed
    - Raw model response (when available)
    - Helpful suggestions for fixing the issue
    """

    def __init__(
        self,
        message: str,
        resource_name: str | None = None,
        raw_response: str | None = None,
        suggestions: list[str] | None = None,
        debug_info: dict[str, Any] | None = None,
    ):
        """
        Initialize CompletionError with context.

        Args:
            message: Human-readable error message
            resource_name: Name of the resource that failed completion
            raw_response: Raw response from the model (for debugging)
            suggestions: List of actionable suggestions for fixing the error
            debug_info: Additional debug information (request/response details)
        """
        self.resource_name = resource_name
        self.raw_response = raw_response
        self.suggestions = suggestions or []
        self.debug_info = debug_info or {}
        super().__init__(message)


class CompletionTimeoutError(CompletionError):
    """Timeout during completion.

    Raised when the model takes too long to respond.
    """

    def __init__(
        self,
        message: str,
        resource_name: str | None = None,
        timeout_seconds: float | None = None,
        **kwargs,
    ):
        """
        Initialize CompletionTimeoutError.

        Args:
            message: Human-readable error message
            resource_name: Name of the resource that failed completion
            timeout_seconds: The timeout value that was exceeded
            **kwargs: Additional arguments passed to CompletionError
        """
        self.timeout_seconds = timeout_seconds

        # Add timeout-specific suggestions
        suggestions = kwargs.pop("suggestions", []) or []
        if not suggestions:
            suggestions = [
                "Try a faster model: --model anthropic/claude-haiku-4.5",
                "Simplify the resource description",
                "Increase timeout: set CW_COMPLETION_TIMEOUT in .env",
                "Add explicit field values to reduce completion work",
            ]

        super().__init__(
            message,
            resource_name=resource_name,
            suggestions=suggestions,
            **kwargs,
        )


class CompletionValidationError(CompletionError):
    """Invalid response from model.

    Raised when the model returns a response that fails validation.
    """

    def __init__(
        self,
        message: str,
        resource_name: str | None = None,
        field_name: str | None = None,
        field_value: Any | None = None,
        expected_format: str | None = None,
        **kwargs,
    ):
        """
        Initialize CompletionValidationError.

        Args:
            message: Human-readable error message
            resource_name: Name of the resource that failed completion
            field_name: Name of the field that failed validation
            field_value: The invalid value returned by the model
            expected_format: Description of the expected format
            **kwargs: Additional arguments passed to CompletionError
        """
        self.field_name = field_name
        self.field_value = field_value
        self.expected_format = expected_format

        # Generate suggestions based on error type
        suggestions = kwargs.pop("suggestions", []) or []
        if not suggestions:
            suggestions = _generate_validation_suggestions(
                field_name, field_value, expected_format
            )

        super().__init__(
            message,
            resource_name=resource_name,
            suggestions=suggestions,
            **kwargs,
        )


class CompletionRetryExhaustedError(CompletionError):
    """Max retries exceeded.

    Raised when all retry attempts have been exhausted without success.
    """

    def __init__(
        self,
        message: str,
        resource_name: str | None = None,
        retry_count: int | None = None,
        last_error: Exception | None = None,
        **kwargs,
    ):
        """
        Initialize CompletionRetryExhaustedError.

        Args:
            message: Human-readable error message
            resource_name: Name of the resource that failed completion
            retry_count: Number of retries attempted
            last_error: The last error that occurred before giving up
            **kwargs: Additional arguments passed to CompletionError
        """
        self.retry_count = retry_count
        self.last_error = last_error

        # Add retry-specific suggestions
        suggestions = kwargs.pop("suggestions", []) or []
        if not suggestions:
            suggestions = [
                "Try a more capable model: --model anthropic/claude-haiku-4.5",
                "Add more explicit field values to reduce ambiguity",
                "Simplify the resource description",
                "Increase max retries: set CW_COMPLETION_MAX_RETRIES in .env",
            ]

        super().__init__(
            message,
            resource_name=resource_name,
            suggestions=suggestions,
            **kwargs,
        )


def _generate_validation_suggestions(
    field_name: str | None,
    field_value: Any | None,
    expected_format: str | None,
) -> list[str]:
    """Generate helpful suggestions based on validation error details.

    Args:
        field_name: Name of the field that failed validation
        field_value: The invalid value returned by the model
        expected_format: Description of the expected format

    Returns:
        List of actionable suggestions
    """
    suggestions = []

    # Port-specific suggestions
    if field_name and "port" in field_name.lower():
        if (
            field_value
            and isinstance(field_value, str)
            and ":" not in field_value
        ):
            suggestions.append(
                f'Add explicit port mapping: ports=["{field_value}:{field_value}"]'
            )
        suggestions.append("Use 'host:container' format like '8080:80'")
        suggestions.append("Example: ports=['8080:80', '443:443']")

    # Image-specific suggestions
    elif field_name and "image" in field_name.lower():
        suggestions.append(
            "Check that the image exists on Docker Hub or your registry"
        )
        suggestions.append(
            "Use a specific tag: 'nginx:1.25' instead of 'nginx'"
        )
        suggestions.append("For local images, ensure they're built first")

    # Empty/None field suggestions
    elif field_value is None or field_value == "":
        suggestions.append(f"Add explicit value for '{field_name}' field")
        suggestions.append("Provide more detail in the description")
        suggestions.append(
            "Try a more capable model: --model anthropic/claude-haiku-4.5"
        )

    # Generic suggestions with expected format
    elif expected_format:
        suggestions.append(f"Expected format: {expected_format}")
        suggestions.append(f"Add explicit value for '{field_name}' field")

    # Fallback suggestions
    if not suggestions:
        suggestions.append(
            "Try a more capable model: --model anthropic/claude-haiku-4.5"
        )
        suggestions.append("Add explicit field values to reduce ambiguity")
        suggestions.append("Provide more detail in the description")

    return suggestions


def format_completion_error(
    error: CompletionError, show_debug: bool = False
) -> str:
    """Format a CompletionError for display.

    Args:
        error: The CompletionError to format
        show_debug: If True, include raw response and debug info

    Returns:
        Formatted error string for display
    """
    lines = []

    # Header with resource name if available
    if error.resource_name:
        lines.append(f"Completion failed for resource: {error.resource_name}")
    else:
        lines.append("Completion failed")

    lines.append("")

    # Error message
    lines.append(f"Error: {error!s}")

    # Field-specific info for validation errors
    if isinstance(error, CompletionValidationError):
        if error.field_name and error.field_value is not None:
            lines.append(f"Field: {error.field_name}")
            lines.append(f"Value: {error.field_value}")
        if error.expected_format:
            lines.append(f"Expected: {error.expected_format}")

    # Timeout info
    if isinstance(error, CompletionTimeoutError) and error.timeout_seconds:
        lines.append(f"Timeout: {error.timeout_seconds}s")

    # Retry info
    if isinstance(error, CompletionRetryExhaustedError):
        if error.retry_count:
            lines.append(f"Attempts: {error.retry_count}")
        if error.last_error:
            lines.append(f"Last error: {error.last_error}")

    # Suggestions
    if error.suggestions:
        lines.append("")
        lines.append("Suggestions:")
        for suggestion in error.suggestions:
            lines.append(f"  - {suggestion}")

    # Debug information
    if show_debug:
        if error.raw_response:
            lines.append("")
            lines.append("Raw response:")
            lines.append(error.raw_response)

        if error.debug_info:
            lines.append("")
            lines.append("Debug info:")
            for key, value in error.debug_info.items():
                lines.append(f"  {key}: {value}")
    else:
        lines.append("")
        lines.append("Run with --debug to see the full API response.")

    return "\n".join(lines)
