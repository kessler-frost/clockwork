"""
Model Loader - Automatic model loading for LM Studio.

This module provides automatic model loading when using LM Studio as the completion backend.
When a localhost:1234 endpoint is detected, the specified model is loaded automatically.
"""

import json
import logging
from urllib.parse import urlparse

import httpx

try:
    import lmstudio as lms

    HAS_LMSTUDIO = True
except ImportError:
    HAS_LMSTUDIO = False
    lms = None

logger = logging.getLogger(__name__)


class LMStudioModelLoader:
    """Handles automatic model loading for LM Studio endpoints."""

    def __init__(self):
        """Initialize the LM Studio model loader."""
        self._loaded_model: str | None = None

    async def _is_model_loaded_via_api(self, model_identifier: str) -> bool:
        """
        Check if a model is already loaded in LM Studio via the OpenAI API.

        Args:
            model_identifier: Model identifier to check

        Returns:
            True if model is available in the /v1/models endpoint
        """
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get("http://localhost:1234/v1/models")
                if response.status_code == 200:
                    data = response.json()
                    # Case-insensitive comparison since LM Studio normalizes to lowercase
                    loaded_models = [
                        m.get("id", "").lower() for m in data.get("data", [])
                    ]
                    return model_identifier.lower() in loaded_models
                else:
                    # Log non-200 responses
                    logger.warning(
                        f"LM Studio API returned status {response.status_code}: "
                        f"{response.text[:200] if response.text else 'no response body'}"
                    )
                    return False
        except httpx.ConnectError:
            logger.info("LM Studio not running, will attempt to load model")
            return False
        except httpx.TimeoutException:
            logger.warning("LM Studio API timed out, assuming model not loaded")
            return False
        except json.JSONDecodeError as e:
            logger.error(f"LM Studio API returned invalid JSON: {e}")
            return False

    @staticmethod
    def is_lmstudio_endpoint(base_url: str) -> bool:
        """
        Detect if the base URL points to a local LM Studio instance.

        Args:
            base_url: The base URL to check (e.g., "http://localhost:1234/v1")

        Returns:
            True if URL is localhost:1234, False otherwise
        """
        parsed = urlparse(base_url)
        hostname = parsed.hostname or ""
        port = parsed.port

        # Check for localhost variants on port 1234
        is_localhost = hostname in ["localhost", "127.0.0.1", "::1"]
        is_lmstudio_port = port == 1234

        return is_localhost and is_lmstudio_port

    async def load_model(self, model_identifier: str) -> None:
        """
        Load a model in LM Studio if not already loaded.

        This method is idempotent - if the model is already loaded,
        it will skip loading and return immediately.

        Args:
            model_identifier: Model identifier (e.g., "qwen/qwen3-4b-2507")

        Raises:
            ImportError: If lmstudio package is not installed
            ConnectionError: If LM Studio is not running or unreachable
            ValueError: If model identifier is invalid or model not downloaded
            RuntimeError: For other unexpected errors during model loading
        """
        # Skip if already loaded this model in this session
        if self._loaded_model == model_identifier:
            logger.debug(f"Model {model_identifier} already loaded, skipping")
            return

        # Check if model is already loaded via OpenAI API (from lms load command)
        if await self._is_model_loaded_via_api(model_identifier):
            logger.info(
                f"Model {model_identifier} already loaded in LM Studio (via API check)"
            )
            self._loaded_model = model_identifier
            return

        if not HAS_LMSTUDIO:
            logger.error(
                "lmstudio package not installed. Install with: uv add lmstudio"
            )
            raise ImportError(
                "lmstudio package required for automatic model loading. "
                "Install with: uv add lmstudio"
            )

        logger.info(f"Loading model in LM Studio: {model_identifier}")

        try:
            # Load the model (this is idempotent in lmstudio SDK)
            # If model is already loaded, returns existing instance
            # If not loaded, loads it and returns new instance
            lms.llm(model_identifier)

            # Track that we've loaded this model
            self._loaded_model = model_identifier
            logger.info(
                f"Successfully loaded model in LM Studio: {model_identifier}"
            )

        except ConnectionError as e:
            logger.error(
                f"Failed to connect to LM Studio. Is LM Studio running? Error: {e}"
            )
            raise ConnectionError(
                "Cannot connect to LM Studio. Please ensure LM Studio is running "
                "and the API server is started (Server tab in LM Studio UI)."
            ) from e

        except FileNotFoundError as e:
            logger.error(
                f"Model {model_identifier} not found in LM Studio. "
                f"Please download it first. Error: {e}"
            )
            raise ValueError(
                f"Model '{model_identifier}' not found in LM Studio. "
                f"Please download the model using the LM Studio UI first. "
                f"Go to the 'Search' tab, find the model, and click 'Download'."
            ) from e

        except ValueError as e:
            logger.error(
                f"Invalid model identifier: {model_identifier}. Error: {e}"
            )
            raise ValueError(
                f"Invalid model identifier: '{model_identifier}'. "
                f"Model identifiers should follow the format 'org/model-name' "
                f"(e.g., 'qwen/qwen3-4b-2507', 'meta-llama/llama-3.2-1b')."
            ) from e

        except Exception as e:
            logger.error(
                f"Unexpected error loading model {model_identifier}: {e}"
            )
            raise RuntimeError(
                f"Failed to load model '{model_identifier}' in LM Studio: {e}"
            ) from e

    def reset(self) -> None:
        """
        Reset the loaded model tracker.

        Useful for testing or when you want to force a reload.
        """
        self._loaded_model = None
        logger.debug("Model loader state reset")
