"""Tests for LM Studio model loader."""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from clockwork.model_loader import LMStudioModelLoader


@pytest.fixture(autouse=True)
def event_loop():
    """Create an event loop for each test."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop

    # Clean up pending tasks to avoid warnings
    try:
        pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()
        if pending:
            loop.run_until_complete(
                asyncio.gather(*pending, return_exceptions=True)
            )
    except Exception:
        pass
    finally:
        loop.close()


def test_is_lmstudio_endpoint_localhost():
    """Test LM Studio endpoint detection for localhost."""
    assert LMStudioModelLoader.is_lmstudio_endpoint("http://localhost:1234/v1")
    assert LMStudioModelLoader.is_lmstudio_endpoint("http://localhost:1234")
    assert LMStudioModelLoader.is_lmstudio_endpoint("https://localhost:1234/v1")


def test_is_lmstudio_endpoint_127():
    """Test LM Studio endpoint detection for 127.0.0.1."""
    assert LMStudioModelLoader.is_lmstudio_endpoint("http://127.0.0.1:1234/v1")
    assert LMStudioModelLoader.is_lmstudio_endpoint("http://127.0.0.1:1234")


def test_is_lmstudio_endpoint_ipv6():
    """Test LM Studio endpoint detection for IPv6 localhost."""
    assert LMStudioModelLoader.is_lmstudio_endpoint("http://[::1]:1234/v1")
    assert LMStudioModelLoader.is_lmstudio_endpoint("http://[::1]:1234")


def test_is_lmstudio_endpoint_wrong_port():
    """Test LM Studio endpoint detection rejects wrong ports."""
    assert not LMStudioModelLoader.is_lmstudio_endpoint(
        "http://localhost:8080/v1"
    )
    assert not LMStudioModelLoader.is_lmstudio_endpoint("http://localhost:3000")


def test_is_lmstudio_endpoint_remote():
    """Test LM Studio endpoint detection rejects remote hosts."""
    assert not LMStudioModelLoader.is_lmstudio_endpoint(
        "https://openrouter.ai/api/v1"
    )
    assert not LMStudioModelLoader.is_lmstudio_endpoint(
        "https://api.openai.com/v1"
    )
    assert not LMStudioModelLoader.is_lmstudio_endpoint(
        "http://192.168.1.100:1234"
    )


@pytest.mark.asyncio
async def test_load_model_success():
    """Test successful model loading."""
    loader = LMStudioModelLoader()

    # Mock the lmstudio module
    mock_lmstudio = MagicMock()
    mock_model = MagicMock()
    mock_lmstudio.llm.return_value = mock_model

    with patch.dict("sys.modules", {"lmstudio": mock_lmstudio}):
        await loader.load_model("qwen/qwen3-4b-2507")

    # Verify model was loaded
    mock_lmstudio.llm.assert_called_once_with("qwen/qwen3-4b-2507")
    assert loader._loaded_model == "qwen/qwen3-4b-2507"


@pytest.mark.asyncio
async def test_load_model_idempotent():
    """Test that loading the same model twice is idempotent."""
    loader = LMStudioModelLoader()

    # Mock the lmstudio module
    mock_lmstudio = MagicMock()
    mock_model = MagicMock()
    mock_lmstudio.llm.return_value = mock_model

    with patch.dict("sys.modules", {"lmstudio": mock_lmstudio}):
        # Load model first time
        await loader.load_model("qwen/qwen3-4b-2507")
        assert mock_lmstudio.llm.call_count == 1

        # Load same model second time - should skip
        await loader.load_model("qwen/qwen3-4b-2507")
        # Still only called once
        assert mock_lmstudio.llm.call_count == 1


@pytest.mark.asyncio
async def test_load_model_import_error():
    """Test error handling when lmstudio package is not installed."""
    loader = LMStudioModelLoader()

    # Mock missing lmstudio package
    with (
        patch.dict("sys.modules", {"lmstudio": None}),
        pytest.raises(ImportError, match="lmstudio package required"),
    ):
        await loader.load_model("qwen/qwen3-4b-2507")


@pytest.mark.asyncio
async def test_load_model_connection_error():
    """Test error handling when LM Studio is not running."""
    loader = LMStudioModelLoader()

    # Mock the lmstudio module
    mock_lmstudio = MagicMock()
    mock_lmstudio.llm.side_effect = ConnectionError("Connection refused")

    with (
        patch.dict("sys.modules", {"lmstudio": mock_lmstudio}),
        pytest.raises(ConnectionError, match="Cannot connect to LM Studio"),
    ):
        await loader.load_model("qwen/qwen3-4b-2507")


@pytest.mark.asyncio
async def test_load_model_not_found():
    """Test error handling when model is not downloaded."""
    loader = LMStudioModelLoader()

    # Mock the lmstudio module
    mock_lmstudio = MagicMock()
    mock_lmstudio.llm.side_effect = FileNotFoundError("Model not found")

    with (
        patch.dict("sys.modules", {"lmstudio": mock_lmstudio}),
        pytest.raises(ValueError, match="Model .* not found in LM Studio"),
    ):
        await loader.load_model("qwen/qwen3-4b-2507")


@pytest.mark.asyncio
async def test_load_model_invalid_identifier():
    """Test error handling for invalid model identifier."""
    loader = LMStudioModelLoader()

    # Mock the lmstudio module
    mock_lmstudio = MagicMock()
    mock_lmstudio.llm.side_effect = ValueError("Invalid model identifier")

    with (
        patch.dict("sys.modules", {"lmstudio": mock_lmstudio}),
        pytest.raises(ValueError, match="Invalid model identifier"),
    ):
        await loader.load_model("invalid-model-id")


@pytest.mark.asyncio
async def test_load_model_unexpected_error():
    """Test error handling for unexpected errors."""
    loader = LMStudioModelLoader()

    # Mock the lmstudio module
    mock_lmstudio = MagicMock()
    mock_lmstudio.llm.side_effect = RuntimeError("Unexpected error")

    with (
        patch.dict("sys.modules", {"lmstudio": mock_lmstudio}),
        pytest.raises(RuntimeError, match="Failed to load model"),
    ):
        await loader.load_model("qwen/qwen3-4b-2507")


def test_reset():
    """Test resetting the loader state."""
    loader = LMStudioModelLoader()
    loader._loaded_model = "test-model"

    loader.reset()

    assert loader._loaded_model is None


@pytest.mark.asyncio
async def test_load_different_models():
    """Test loading different models sequentially."""
    loader = LMStudioModelLoader()

    # Mock the lmstudio module
    mock_lmstudio = MagicMock()
    mock_model = MagicMock()
    mock_lmstudio.llm.return_value = mock_model

    with patch.dict("sys.modules", {"lmstudio": mock_lmstudio}):
        # Load first model
        await loader.load_model("qwen/qwen3-4b-2507")
        assert mock_lmstudio.llm.call_count == 1

        # Load different model - should load again
        await loader.load_model("meta-llama/llama-3.2-1b")
        assert mock_lmstudio.llm.call_count == 2
        assert loader._loaded_model == "meta-llama/llama-3.2-1b"
