"""
Centralized error handling for Clockwork.

This module provides consistent error types and error handling patterns
across all Clockwork components.
"""

from typing import Optional, Dict, Any, List
from pathlib import Path


class ClockworkError(Exception):
    """Base exception for all Clockwork errors."""
    
    def __init__(
        self, 
        message: str, 
        error_code: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        suggestions: Optional[List[str]] = None
    ):
        self.message = message
        self.error_code = error_code or "CLOCKWORK_ERROR"
        self.context = context or {}
        self.suggestions = suggestions or []
        
        super().__init__(self._format_message())
    
    def _format_message(self) -> str:
        """Format error message with context and suggestions."""
        msg = f"[{self.error_code}] {self.message}"
        
        if self.context:
            context_str = ", ".join([f"{k}={v}" for k, v in self.context.items()])
            msg += f" (Context: {context_str})"
        
        if self.suggestions:
            suggestions_str = "; ".join(self.suggestions)
            msg += f" | Suggestions: {suggestions_str}"
        
        return msg


# =============================================================================
# Phase-specific Errors
# =============================================================================

class IntakeError(ClockworkError):
    """Errors during the intake phase."""
    
    def __init__(self, message: str, **kwargs):
        if 'error_code' not in kwargs:
            kwargs['error_code'] = "INTAKE_ERROR"
        super().__init__(message, **kwargs)


class ParseError(IntakeError):
    """Errors during parsing of .cw files."""
    
    def __init__(
        self, 
        message: str, 
        file_path: Optional[str] = None, 
        line_number: Optional[int] = None,
        **kwargs
    ):
        context = kwargs.get('context', {})
        if file_path:
            context['file_path'] = file_path
        if line_number:
            context['line_number'] = line_number
        
        kwargs['context'] = context
        # Don't override error_code if it's already in kwargs
        if 'error_code' not in kwargs:
            kwargs['error_code'] = "PARSE_ERROR"
        
        super().__init__(message, **kwargs)


class ValidationError(IntakeError):
    """Errors during IR validation."""
    
    def __init__(
        self, 
        message: str, 
        field_path: Optional[str] = None,
        validation_issues: Optional[List[str]] = None,
        **kwargs
    ):
        context = kwargs.get('context', {})
        if field_path:
            context['field_path'] = field_path
        if validation_issues:
            context['validation_issues'] = validation_issues
        
        kwargs['context'] = context
        if 'error_code' not in kwargs:
            kwargs['error_code'] = "VALIDATION_ERROR"
        
        super().__init__(message, **kwargs)


class ResolutionError(IntakeError):
    """Errors during module/provider resolution."""
    
    def __init__(
        self, 
        message: str, 
        module_name: Optional[str] = None,
        provider_name: Optional[str] = None,
        **kwargs
    ):
        context = kwargs.get('context', {})
        if module_name:
            context['module_name'] = module_name
        if provider_name:
            context['provider_name'] = provider_name
        
        kwargs['context'] = context
        if 'error_code' not in kwargs:
            kwargs['error_code'] = "RESOLUTION_ERROR"
        
        super().__init__(message, **kwargs)


class AssemblyError(ClockworkError):
    """Errors during the assembly phase."""
    
    def __init__(self, message: str, **kwargs):
        if 'error_code' not in kwargs:
            kwargs['error_code'] = "ASSEMBLY_ERROR"
        super().__init__(message, **kwargs)


class PlanningError(AssemblyError):
    """Errors during action planning."""
    
    def __init__(
        self, 
        message: str, 
        resource_id: Optional[str] = None,
        dependency_cycle: Optional[List[str]] = None,
        **kwargs
    ):
        context = kwargs.get('context', {})
        if resource_id:
            context['resource_id'] = resource_id
        if dependency_cycle:
            context['dependency_cycle'] = dependency_cycle
        
        kwargs['context'] = context
        if 'error_code' not in kwargs:
            kwargs['error_code'] = "PLANNING_ERROR"
        
        super().__init__(message, **kwargs)


class ForgeError(ClockworkError):
    """Errors during the forge phase."""
    
    def __init__(self, message: str, **kwargs):
        # Don't override error_code if it's already provided
        if 'error_code' not in kwargs:
            kwargs['error_code'] = "FORGE_ERROR"
        super().__init__(message, **kwargs)


class CompilerError(ForgeError):
    """Errors during artifact compilation."""
    
    def __init__(
        self, 
        message: str, 
        action_name: Optional[str] = None,
        compilation_stage: Optional[str] = None,
        **kwargs
    ):
        context = kwargs.get('context', {})
        if action_name:
            context['action_name'] = action_name
        if compilation_stage:
            context['compilation_stage'] = compilation_stage
        
        kwargs['context'] = context
        if 'error_code' not in kwargs:
            kwargs['error_code'] = "COMPILER_ERROR"
        
        super().__init__(message, **kwargs)


class ExecutionError(ForgeError):
    """Errors during artifact execution."""
    
    def __init__(
        self, 
        message: str, 
        artifact_name: Optional[str] = None,
        runner_type: Optional[str] = None,
        exit_code: Optional[int] = None,
        **kwargs
    ):
        context = kwargs.get('context', {})
        if artifact_name:
            context['artifact_name'] = artifact_name
        if runner_type:
            context['runner_type'] = runner_type
        if exit_code is not None:
            context['exit_code'] = exit_code
        
        kwargs['context'] = context
        if 'error_code' not in kwargs:
            kwargs['error_code'] = "EXECUTION_ERROR"
        
        super().__init__(message, **kwargs)


class SecurityValidationError(ForgeError):
    """Errors during security validation."""
    
    def __init__(
        self, 
        message: str, 
        security_violations: Optional[List[str]] = None,
        **kwargs
    ):
        context = kwargs.get('context', {})
        if security_violations:
            context['security_violations'] = security_violations
        
        kwargs['context'] = context
        if 'error_code' not in kwargs:
            kwargs['error_code'] = "SECURITY_ERROR"
        
        super().__init__(message, **kwargs)


# =============================================================================
# Infrastructure Errors
# =============================================================================

class StateError(ClockworkError):
    """Errors related to state management."""
    
    def __init__(
        self, 
        message: str, 
        state_file: Optional[str] = None,
        corruption_detected: bool = False,
        **kwargs
    ):
        context = kwargs.get('context', {})
        if state_file:
            context['state_file'] = state_file
        if corruption_detected:
            context['corruption_detected'] = corruption_detected
        
        kwargs['context'] = context
        if 'error_code' not in kwargs:
            kwargs['error_code'] = "STATE_ERROR"
        
        super().__init__(message, **kwargs)


class DaemonError(ClockworkError):
    """Errors in daemon operations."""
    
    def __init__(
        self, 
        message: str, 
        daemon_state: Optional[str] = None,
        **kwargs
    ):
        context = kwargs.get('context', {})
        if daemon_state:
            context['daemon_state'] = daemon_state
        
        kwargs['context'] = context
        if 'error_code' not in kwargs:
            kwargs['error_code'] = "DAEMON_ERROR"
        
        super().__init__(message, **kwargs)


class RunnerError(ClockworkError):
    """Errors in runner systems."""
    
    def __init__(
        self, 
        message: str, 
        runner_type: Optional[str] = None,
        environment_issue: Optional[str] = None,
        **kwargs
    ):
        context = kwargs.get('context', {})
        if runner_type:
            context['runner_type'] = runner_type
        if environment_issue:
            context['environment_issue'] = environment_issue
        
        kwargs['context'] = context
        if 'error_code' not in kwargs:
            kwargs['error_code'] = "RUNNER_ERROR"
        
        super().__init__(message, **kwargs)


class ConfigurationError(ClockworkError):
    """Errors in configuration."""
    
    def __init__(
        self, 
        message: str, 
        config_file: Optional[str] = None,
        config_field: Optional[str] = None,
        **kwargs
    ):
        context = kwargs.get('context', {})
        if config_file:
            context['config_file'] = config_file
        if config_field:
            context['config_field'] = config_field
        
        kwargs['context'] = context
        if 'error_code' not in kwargs:
            kwargs['error_code'] = "CONFIG_ERROR"
        
        super().__init__(message, **kwargs)


# =============================================================================
# Error Handling Utilities
# =============================================================================

def format_error_chain(error: Exception) -> str:
    """Format an error with its full chain of causes."""
    error_chain = []
    current = error
    
    while current:
        if isinstance(current, ClockworkError):
            error_chain.append(str(current))
        else:
            error_chain.append(f"{type(current).__name__}: {current}")
        
        current = current.__cause__ if hasattr(current, '__cause__') else None
    
    return " → ".join(error_chain)


def wrap_external_error(
    external_error: Exception, 
    clockwork_error_type: type = ClockworkError,
    message: Optional[str] = None,
    **kwargs
) -> ClockworkError:
    """Wrap an external error in a Clockwork error."""
    error_message = message or f"External error: {external_error}"
    
    context = kwargs.get('context', {})
    context['external_error_type'] = type(external_error).__name__
    context['external_error_message'] = str(external_error)
    kwargs['context'] = context
    
    wrapped_error = clockwork_error_type(error_message, **kwargs)
    wrapped_error.__cause__ = external_error
    
    return wrapped_error


def create_user_friendly_error(error: ClockworkError) -> str:
    """Create a user-friendly error message."""
    msg = f"❌ {error.message}"
    
    if error.context:
        # Add relevant context in user-friendly format
        if 'file_path' in error.context:
            msg += f"\n📁 File: {error.context['file_path']}"
        if 'line_number' in error.context:
            msg += f" (line {error.context['line_number']})"
        if 'runner_type' in error.context:
            msg += f"\n🏃 Runner: {error.context['runner_type']}"
        if 'exit_code' in error.context:
            msg += f" (exit code: {error.context['exit_code']})"
    
    if error.suggestions:
        msg += f"\n💡 Suggestions:"
        for suggestion in error.suggestions:
            msg += f"\n   • {suggestion}"
    
    return msg


# =============================================================================
# Common Error Scenarios and Suggestions
# =============================================================================

COMMON_SUGGESTIONS = {
    "PARSE_ERROR": [
        "Check the HCL syntax in your .cw files",
        "Verify that all quotes and brackets are properly closed",
        "Run 'clockwork validate' to check your configuration"
    ],
    "VALIDATION_ERROR": [
        "Review the validation errors and fix the indicated issues",
        "Check that all required fields are present",
        "Verify that resource names are unique"
    ],
    "RESOLUTION_ERROR": [
        "Check that module/provider sources are accessible",
        "Verify version constraints are correct",
        "Try clearing the resolver cache with 'clockwork cache clear'"
    ],
    "COMPILER_ERROR": [
        "Check the action list for invalid configurations",
        "Verify that all required parameters are provided",
        "Review the compilation logs for detailed error information"
    ],
    "EXECUTION_ERROR": [
        "Check that the execution environment has required dependencies",
        "Verify that the selected runner is properly configured",
        "Review execution logs for specific failure details"
    ],
    "RUNNER_ERROR": [
        "Verify that the selected runner (Docker, Podman, etc.) is installed",
        "Check runner configuration and permissions",
        "Try using a different runner type"
    ],
    "STATE_ERROR": [
        "Check that the state file is not corrupted",
        "Verify filesystem permissions",
        "Consider backing up and reinitializing the state"
    ]
}


def get_suggestions_for_error(error_code: str) -> List[str]:
    """Get common suggestions for an error code."""
    return COMMON_SUGGESTIONS.get(error_code, [
        "Check the Clockwork documentation for troubleshooting",
        "Run with verbose logging for more details",
        "Report this issue if the problem persists"
    ])


# =============================================================================
# Error Context Helpers
# =============================================================================

def create_error_context(
    file_path: Optional[str] = None,
    line_number: Optional[int] = None,
    component: Optional[str] = None,
    operation: Optional[str] = None,
    **additional_context
) -> Dict[str, Any]:
    """Create a standardized error context dictionary."""
    context = {}
    
    if file_path:
        context['file_path'] = str(file_path)
    if line_number:
        context['line_number'] = line_number
    if component:
        context['component'] = component
    if operation:
        context['operation'] = operation
    
    context.update(additional_context)
    return context


# Export all error types
__all__ = [
    # Base errors
    'ClockworkError',
    
    # Phase-specific errors
    'IntakeError', 'ParseError', 'ValidationError', 'ResolutionError',
    'AssemblyError', 'PlanningError',
    'ForgeError', 'CompilerError', 'ExecutionError', 'SecurityValidationError',
    
    # Infrastructure errors
    'StateError', 'DaemonError', 'RunnerError', 'ConfigurationError',
    
    # Utilities
    'format_error_chain', 'wrap_external_error', 'create_user_friendly_error',
    'get_suggestions_for_error', 'create_error_context'
]