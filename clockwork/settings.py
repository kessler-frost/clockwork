"""
Clockwork Settings - Configuration management using Pydantic Settings.

Loads configuration from environment variables and .env files.
"""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Find project root (where .env file is located)
PROJECT_ROOT = Path(__file__).parent.parent


class ClockworkSettings(BaseSettings):
    """
    Clockwork configuration settings.

    Settings are loaded from:
    1. Environment variables (highest priority)
    2. .env file in current directory
    3. Default values (lowest priority)
    """

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        env_prefix="CW_",  # All Clockwork env vars must start with CW_
    )

    # AI Configuration (OpenAI-compatible API)
    api_key: str | None = Field(
        default=None, description="API key for AI service (env: CW_API_KEY)"
    )

    model: str = Field(
        default="meta-llama/llama-4-scout:free",
        description="Model name for AI resource completion (env: CW_MODEL)",
    )

    base_url: str = Field(
        default="https://openrouter.ai/api/v1",
        description="Base URL for OpenAI-compatible API endpoint (env: CW_BASE_URL)",
    )

    # Pulumi Configuration
    pulumi_config_passphrase: str = Field(
        default="clockwork",
        description="Pulumi passphrase for state encryption (env: CW_PULUMI_CONFIG_PASSPHRASE or PULUMI_CONFIG_PASSPHRASE)",
        validation_alias="PULUMI_CONFIG_PASSPHRASE",  # Also accept standard Pulumi env var
    )

    # Logging Configuration
    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR) (env: CW_LOG_LEVEL)",
    )

    # Resource Completion Configuration
    completion_max_retries: int = Field(
        default=3,
        description="Maximum retry attempts for AI resource completion (env: CW_COMPLETION_MAX_RETRIES)",
    )


# Global settings instance
_settings: ClockworkSettings | None = None


def get_settings() -> ClockworkSettings:
    """
    Get the global settings instance.

    Creates the settings instance on first call, then returns cached instance.

    Returns:
        ClockworkSettings instance
    """
    global _settings
    if _settings is None:
        _settings = ClockworkSettings()
    return _settings


def reload_settings() -> ClockworkSettings:
    """
    Reload settings from environment/files.

    Useful for testing or when .env file changes.

    Returns:
        Fresh ClockworkSettings instance
    """
    global _settings
    _settings = ClockworkSettings()
    return _settings
