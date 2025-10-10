"""
Clockwork Settings - Configuration management using Pydantic Settings.

Loads configuration from environment variables and .env files.
"""

from pathlib import Path
from typing import Optional

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
        env_prefix="CW_"  # All Clockwork env vars must start with CW_
    )

    # OpenRouter Configuration
    openrouter_api_key: Optional[str] = Field(
        default=None,
        description="OpenRouter API key for AI artifact generation (env: CW_OPENROUTER_API_KEY)"
    )

    openrouter_model: str = Field(
        default="meta-llama/llama-4-scout:free",
        description="OpenRouter model to use for artifact generation (env: CW_OPENROUTER_MODEL)"
    )

    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1",
        description="OpenRouter API base URL (env: CW_OPENROUTER_BASE_URL)"
    )

    # PyInfra Configuration
    pyinfra_output_dir: str = Field(
        default=".clockwork/pyinfra",
        description="Directory for PyInfra generated files (env: CW_PYINFRA_OUTPUT_DIR)"
    )

    # Logging Configuration
    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR) (env: CW_LOG_LEVEL)"
    )



# Global settings instance
_settings: Optional[ClockworkSettings] = None


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
