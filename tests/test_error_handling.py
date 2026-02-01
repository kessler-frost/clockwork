"""
Tests for Clockwork error handling.

Tests the custom exception classes and error formatting.
"""

import pytest

from clockwork.exceptions import (
    ClockworkError,
    CompletionError,
    CompletionRetryExhaustedError,
    CompletionTimeoutError,
    CompletionValidationError,
    format_completion_error,
)


class TestClockworkError:
    """Tests for base ClockworkError exception."""

    def test_is_exception(self):
        """ClockworkError should be an Exception."""
        assert issubclass(ClockworkError, Exception)

    def test_can_raise_and_catch(self):
        """ClockworkError can be raised and caught."""
        with pytest.raises(ClockworkError):
            raise ClockworkError("test error")

    def test_message(self):
        """ClockworkError should have the correct message."""
        error = ClockworkError("test message")
        assert str(error) == "test message"


class TestCompletionError:
    """Tests for CompletionError exception."""

    def test_is_clockwork_error(self):
        """CompletionError should be a ClockworkError."""
        assert issubclass(CompletionError, ClockworkError)

    def test_basic_error(self):
        """CompletionError can be raised with just a message."""
        error = CompletionError("completion failed")
        assert str(error) == "completion failed"
        assert error.resource_name is None
        assert error.raw_response is None
        assert error.suggestions == []
        assert error.debug_info == {}

    def test_with_resource_name(self):
        """CompletionError can include resource name."""
        error = CompletionError(
            "completion failed",
            resource_name="web-server",
        )
        assert error.resource_name == "web-server"

    def test_with_raw_response(self):
        """CompletionError can include raw response."""
        error = CompletionError(
            "completion failed",
            raw_response='{"error": "invalid"}',
        )
        assert error.raw_response == '{"error": "invalid"}'

    def test_with_suggestions(self):
        """CompletionError can include suggestions."""
        suggestions = ["try again", "use a different model"]
        error = CompletionError(
            "completion failed",
            suggestions=suggestions,
        )
        assert error.suggestions == suggestions

    def test_with_debug_info(self):
        """CompletionError can include debug info."""
        debug_info = {"model": "test-model", "timeout": 30}
        error = CompletionError(
            "completion failed",
            debug_info=debug_info,
        )
        assert error.debug_info == debug_info

    def test_full_error(self):
        """CompletionError can include all attributes."""
        error = CompletionError(
            "completion failed",
            resource_name="web-server",
            raw_response='{"error": "invalid"}',
            suggestions=["try again"],
            debug_info={"model": "test"},
        )
        assert str(error) == "completion failed"
        assert error.resource_name == "web-server"
        assert error.raw_response == '{"error": "invalid"}'
        assert error.suggestions == ["try again"]
        assert error.debug_info == {"model": "test"}


class TestCompletionTimeoutError:
    """Tests for CompletionTimeoutError exception."""

    def test_is_completion_error(self):
        """CompletionTimeoutError should be a CompletionError."""
        assert issubclass(CompletionTimeoutError, CompletionError)

    def test_basic_error(self):
        """CompletionTimeoutError can be raised with message."""
        error = CompletionTimeoutError("timeout after 30s")
        assert str(error) == "timeout after 30s"
        assert error.timeout_seconds is None

    def test_with_timeout_seconds(self):
        """CompletionTimeoutError can include timeout value."""
        error = CompletionTimeoutError(
            "timeout after 30s",
            timeout_seconds=30.0,
        )
        assert error.timeout_seconds == 30.0

    def test_default_suggestions(self):
        """CompletionTimeoutError has default suggestions."""
        error = CompletionTimeoutError("timeout")
        assert len(error.suggestions) > 0
        assert any("timeout" in s.lower() or "model" in s.lower() for s in error.suggestions)

    def test_with_resource_name(self):
        """CompletionTimeoutError can include resource name."""
        error = CompletionTimeoutError(
            "timeout",
            resource_name="web-server",
            timeout_seconds=30.0,
        )
        assert error.resource_name == "web-server"
        assert error.timeout_seconds == 30.0


class TestCompletionValidationError:
    """Tests for CompletionValidationError exception."""

    def test_is_completion_error(self):
        """CompletionValidationError should be a CompletionError."""
        assert issubclass(CompletionValidationError, CompletionError)

    def test_basic_error(self):
        """CompletionValidationError can be raised with message."""
        error = CompletionValidationError("invalid port format")
        assert str(error) == "invalid port format"

    def test_with_field_info(self):
        """CompletionValidationError can include field info."""
        error = CompletionValidationError(
            "invalid port format",
            field_name="ports",
            field_value="80",
            expected_format="host:container",
        )
        assert error.field_name == "ports"
        assert error.field_value == "80"
        assert error.expected_format == "host:container"

    def test_port_suggestions(self):
        """CompletionValidationError generates port-specific suggestions."""
        error = CompletionValidationError(
            "invalid port",
            field_name="ports",
            field_value="80",
        )
        assert len(error.suggestions) > 0
        # Should have port-related suggestions
        suggestions_text = " ".join(error.suggestions).lower()
        assert "port" in suggestions_text or ":" in suggestions_text

    def test_image_suggestions(self):
        """CompletionValidationError generates image-specific suggestions."""
        error = CompletionValidationError(
            "invalid image",
            field_name="image",
            field_value="unknown",
        )
        assert len(error.suggestions) > 0
        # Should have image-related suggestions
        suggestions_text = " ".join(error.suggestions).lower()
        assert "image" in suggestions_text or "tag" in suggestions_text

    def test_empty_field_suggestions(self):
        """CompletionValidationError generates suggestions for empty fields."""
        error = CompletionValidationError(
            "empty field",
            field_name="image",
            field_value=None,
        )
        assert len(error.suggestions) > 0


class TestCompletionRetryExhaustedError:
    """Tests for CompletionRetryExhaustedError exception."""

    def test_is_completion_error(self):
        """CompletionRetryExhaustedError should be a CompletionError."""
        assert issubclass(CompletionRetryExhaustedError, CompletionError)

    def test_basic_error(self):
        """CompletionRetryExhaustedError can be raised with message."""
        error = CompletionRetryExhaustedError("max retries exceeded")
        assert str(error) == "max retries exceeded"

    def test_with_retry_count(self):
        """CompletionRetryExhaustedError can include retry count."""
        error = CompletionRetryExhaustedError(
            "max retries exceeded",
            retry_count=3,
        )
        assert error.retry_count == 3

    def test_with_last_error(self):
        """CompletionRetryExhaustedError can include last error."""
        last_error = ValueError("validation failed")
        error = CompletionRetryExhaustedError(
            "max retries exceeded",
            last_error=last_error,
        )
        assert error.last_error is last_error

    def test_default_suggestions(self):
        """CompletionRetryExhaustedError has default suggestions."""
        error = CompletionRetryExhaustedError("max retries")
        assert len(error.suggestions) > 0
        # Should suggest trying a different model
        suggestions_text = " ".join(error.suggestions).lower()
        assert "model" in suggestions_text


class TestFormatCompletionError:
    """Tests for format_completion_error function."""

    def test_basic_formatting(self):
        """format_completion_error formats basic error."""
        error = CompletionError("test error")
        formatted = format_completion_error(error)
        assert "test error" in formatted
        assert "--debug" in formatted  # Should mention debug flag

    def test_with_resource_name(self):
        """format_completion_error includes resource name."""
        error = CompletionError(
            "test error",
            resource_name="web-server",
        )
        formatted = format_completion_error(error)
        assert "web-server" in formatted

    def test_with_suggestions(self):
        """format_completion_error includes suggestions."""
        error = CompletionError(
            "test error",
            suggestions=["try again", "use different model"],
        )
        formatted = format_completion_error(error)
        assert "Suggestions:" in formatted
        assert "try again" in formatted
        assert "use different model" in formatted

    def test_timeout_error_formatting(self):
        """format_completion_error formats timeout error."""
        error = CompletionTimeoutError(
            "timed out",
            resource_name="api-server",
            timeout_seconds=30.0,
        )
        formatted = format_completion_error(error)
        assert "timed out" in formatted
        assert "api-server" in formatted
        assert "30" in formatted  # timeout value

    def test_validation_error_formatting(self):
        """format_completion_error formats validation error."""
        error = CompletionValidationError(
            "invalid format",
            resource_name="nginx",
            field_name="ports",
            field_value="80",
            expected_format="host:container",
        )
        formatted = format_completion_error(error)
        assert "invalid format" in formatted
        assert "nginx" in formatted
        assert "ports" in formatted
        assert "80" in formatted
        assert "host:container" in formatted

    def test_retry_error_formatting(self):
        """format_completion_error formats retry error."""
        error = CompletionRetryExhaustedError(
            "all retries failed",
            resource_name="database",
            retry_count=3,
        )
        formatted = format_completion_error(error)
        assert "all retries failed" in formatted
        assert "database" in formatted
        assert "3" in formatted  # retry count

    def test_debug_mode_shows_raw_response(self):
        """format_completion_error shows raw response in debug mode."""
        error = CompletionError(
            "test error",
            raw_response='{"error": "test"}',
        )
        formatted_no_debug = format_completion_error(error, show_debug=False)
        formatted_debug = format_completion_error(error, show_debug=True)

        assert '{"error": "test"}' not in formatted_no_debug
        assert '{"error": "test"}' in formatted_debug

    def test_debug_mode_shows_debug_info(self):
        """format_completion_error shows debug info in debug mode."""
        error = CompletionError(
            "test error",
            debug_info={"model": "test-model", "base_url": "http://test"},
        )
        formatted_no_debug = format_completion_error(error, show_debug=False)
        formatted_debug = format_completion_error(error, show_debug=True)

        assert "test-model" not in formatted_no_debug
        assert "test-model" in formatted_debug
        assert "http://test" in formatted_debug


class TestExceptionHierarchy:
    """Tests for exception class hierarchy."""

    def test_all_completion_errors_are_clockwork_errors(self):
        """All completion errors should inherit from ClockworkError."""
        assert issubclass(CompletionError, ClockworkError)
        assert issubclass(CompletionTimeoutError, ClockworkError)
        assert issubclass(CompletionValidationError, ClockworkError)
        assert issubclass(CompletionRetryExhaustedError, ClockworkError)

    def test_catching_base_exception_catches_all(self):
        """Catching CompletionError catches all subtypes."""
        errors = [
            CompletionTimeoutError("timeout"),
            CompletionValidationError("invalid"),
            CompletionRetryExhaustedError("retries"),
        ]

        for error in errors:
            with pytest.raises(CompletionError):
                raise error

    def test_catching_clockwork_error_catches_all(self):
        """Catching ClockworkError catches all error types."""
        errors = [
            ClockworkError("base"),
            CompletionError("completion"),
            CompletionTimeoutError("timeout"),
            CompletionValidationError("invalid"),
            CompletionRetryExhaustedError("retries"),
        ]

        for error in errors:
            with pytest.raises(ClockworkError):
                raise error
