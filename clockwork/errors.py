"""
Clockwork errors - Simplified for new architecture.
"""

class ClockworkError(Exception):
    """Base exception for all Clockwork errors."""
    pass

class DeploymentError(ClockworkError):
    """Errors during deployment."""
    pass

class ConfigurationError(ClockworkError):
    """Errors in configuration."""
    pass
