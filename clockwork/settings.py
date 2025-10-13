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
        env_prefix="CW_"  # All Clockwork env vars must start with CW_
    )

    # AI Configuration (OpenAI-compatible API)
    api_key: str | None = Field(
        default=None,
        description="API key for AI service (env: CW_API_KEY)"
    )

    model: str = Field(
        default="meta-llama/llama-4-scout:free",
        description="Model name for AI resource completion (env: CW_MODEL)"
    )

    base_url: str = Field(
        default="https://openrouter.ai/api/v1",
        description="Base URL for OpenAI-compatible API endpoint (env: CW_BASE_URL)"
    )

    # PyInfra Configuration
    pyinfra_output_dir: Path = Field(
        default=Path(".clockwork/pyinfra"),
        description="Directory for PyInfra generated files (env: CW_PYINFRA_OUTPUT_DIR)"
    )

    # Logging Configuration
    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR) (env: CW_LOG_LEVEL)"
    )

    # Service Configuration
    service_port: int = Field(
        default=8765,
        description="Service port (env: CW_SERVICE_PORT)"
    )

    service_check_interval_default: int = Field(
        default=30,
        description="Default check interval in seconds (env: CW_SERVICE_CHECK_INTERVAL_DEFAULT)"
    )

    service_max_remediation_attempts: int = Field(
        default=3,
        description="Max remediation attempts (env: CW_SERVICE_MAX_REMEDIATION_ATTEMPTS)"
    )

    service_log_file: str = Field(
        default=".clockwork/service/service.log",
        description="Service log file path (env: CW_SERVICE_LOG_FILE)"
    )

    service_log_max_bytes: int = Field(
        default=10 * 1024 * 1024,  # 10MB
        description="Max log file size in bytes before rotation (env: CW_SERVICE_LOG_MAX_BYTES)"
    )

    service_log_backup_count: int = Field(
        default=5,
        description="Number of backup log files to keep (env: CW_SERVICE_LOG_BACKUP_COUNT)"
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
