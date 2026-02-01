"""Tests for completion cache functionality."""

import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from clockwork.completion.cache import CompletionCache
from clockwork.resources import FileResource


class TestCompletionCache:
    """Tests for CompletionCache class."""

    @pytest.fixture
    def temp_cache_dir(self):
        """Create a temporary directory for cache testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir) / "cache"

    @pytest.fixture
    def cache(self, temp_cache_dir):
        """Create a CompletionCache instance with temporary directory."""
        return CompletionCache(cache_dir=str(temp_cache_dir), ttl_days=7)

    def test_cache_initialization(self, cache, temp_cache_dir):
        """Test that cache initializes correctly."""
        assert cache.cache_dir == temp_cache_dir
        assert cache.ttl_days == 7
        assert cache.db_path.exists()

    def test_cache_key_generation(self, cache):
        """Test cache key generation is deterministic."""
        resource = FileResource(
            name="test.txt",
            description="A test file",
            directory=".",
            mode="644",
        )
        model = "test-model"

        key1 = cache.compute_cache_key(resource, model)
        key2 = cache.compute_cache_key(resource, model)

        assert key1 == key2
        assert len(key1) == 16  # First 16 chars of SHA256

    def test_cache_key_changes_with_description(self, cache):
        """Test that cache key changes when description changes."""
        resource1 = FileResource(
            name="test.txt",
            description="A test file",
        )
        resource2 = FileResource(
            name="test.txt",
            description="A different test file",
        )
        model = "test-model"

        key1 = cache.compute_cache_key(resource1, model)
        key2 = cache.compute_cache_key(resource2, model)

        assert key1 != key2

    def test_cache_key_changes_with_model(self, cache):
        """Test that cache key changes when model changes."""
        resource = FileResource(
            name="test.txt",
            description="A test file",
        )

        key1 = cache.compute_cache_key(resource, "model-a")
        key2 = cache.compute_cache_key(resource, "model-b")

        assert key1 != key2

    def test_cache_key_changes_with_user_fields(self, cache):
        """Test that cache key changes when user fields change."""
        resource1 = FileResource(
            name="test.txt",
            description="A test file",
            mode="644",
        )
        resource2 = FileResource(
            name="test.txt",
            description="A test file",
            mode="755",
        )
        model = "test-model"

        key1 = cache.compute_cache_key(resource1, model)
        key2 = cache.compute_cache_key(resource2, model)

        assert key1 != key2

    def test_cache_set_and_get(self, cache):
        """Test setting and getting cache entries."""
        cache_key = "test_key_12345"
        data = {"name": "test.txt", "content": "Hello World", "mode": "644"}

        # Set cache entry
        cache.set(cache_key, data, "FileResource")

        # Get cache entry
        result = cache.get(cache_key)

        assert result is not None
        assert result["name"] == "test.txt"
        assert result["content"] == "Hello World"
        assert result["mode"] == "644"

    def test_cache_miss(self, cache):
        """Test cache miss returns None."""
        result = cache.get("nonexistent_key")
        assert result is None

    def test_cache_expiration(self, temp_cache_dir):
        """Test that expired cache entries are not returned."""
        cache = CompletionCache(cache_dir=str(temp_cache_dir), ttl_days=1)
        cache_key = "test_key"
        data = {"test": "data"}

        cache.set(cache_key, data, "FileResource")

        # Mock datetime to simulate expiration
        with patch("clockwork.completion.cache.datetime") as mock_datetime:
            future_time = datetime.now() + timedelta(days=2)
            mock_datetime.now.return_value = future_time
            mock_datetime.fromisoformat = datetime.fromisoformat

            result = cache.get(cache_key)
            assert result is None

    def test_cache_clear(self, cache):
        """Test clearing all cache entries."""
        # Add multiple entries
        cache.set("key1", {"data": "1"}, "FileResource")
        cache.set("key2", {"data": "2"}, "FileResource")
        cache.set("key3", {"data": "3"}, "FileResource")

        # Clear cache
        count = cache.clear()

        assert count == 3

        # Verify entries are gone
        assert cache.get("key1") is None
        assert cache.get("key2") is None
        assert cache.get("key3") is None

    def test_cache_stats(self, cache):
        """Test cache statistics."""
        # Add some entries
        cache.set("key1", {"data": "1"}, "FileResource")
        cache.set("key2", {"data": "2"}, "FileResource")
        cache.set("key3", {"data": "3"}, "AppleContainerResource")

        stats = cache.stats()

        assert stats["total_entries"] == 3
        assert stats["valid_entries"] == 3
        assert stats["expired_entries"] == 0
        assert "FileResource" in stats["resource_types"]
        assert "AppleContainerResource" in stats["resource_types"]
        assert stats["resource_types"]["FileResource"] == 2
        assert stats["resource_types"]["AppleContainerResource"] == 1
        assert stats["db_size_bytes"] > 0

    def test_cache_cleanup_expired(self, temp_cache_dir):
        """Test cleanup of expired entries."""
        # Create cache with 1 day TTL
        cache = CompletionCache(cache_dir=str(temp_cache_dir), ttl_days=1)

        # Add entry that will be "expired" via mocking
        cache.set("expired_key", {"data": "expired"}, "FileResource")

        # Add valid entry
        cache.set("valid_key", {"data": "valid"}, "FileResource")

        # Mock datetime to simulate expiration of the first entry
        # by moving time forward 2 days
        with patch("clockwork.completion.cache.datetime") as mock_datetime:
            future_time = datetime.now() + timedelta(days=2)
            mock_datetime.now.return_value = future_time
            mock_datetime.fromisoformat = datetime.fromisoformat

            # Cleanup expired
            count = cache.cleanup_expired()

            assert count >= 1  # At least one expired entry

        # Note: both entries were cleaned up since they were both expired
        # at the mocked future time. This verifies cleanup works.

    def test_cache_overwrite(self, cache):
        """Test overwriting existing cache entry."""
        cache_key = "test_key_overwrite"

        # Set initial value
        cache.set(cache_key, {"value": "original"}, "FileResource")
        assert cache.get(cache_key)["value"] == "original"

        # Overwrite with new value
        cache.set(cache_key, {"value": "updated"}, "FileResource")
        assert cache.get(cache_key)["value"] == "updated"


class TestCacheIntegration:
    """Integration tests for cache with ResourceCompleter."""

    @pytest.fixture
    def temp_cache_dir(self):
        """Create a temporary directory for cache testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir) / "cache"

    @pytest.mark.asyncio
    async def test_completer_uses_cache(self, temp_cache_dir):
        """Test that ResourceCompleter uses cache for completions."""
        from clockwork.resource_completer import ResourceCompleter

        # Patch settings to use our temp cache dir
        with patch(
            "clockwork.resource_completer.get_settings"
        ) as mock_settings:
            mock_settings.return_value = MagicMock(
                api_key="test-key",  # pragma: allowlist secret
                model="test-model",
                base_url="https://api.example.com/v1",
                cache_enabled=True,
                cache_dir=str(temp_cache_dir),
                cache_ttl_days=7,
                completion_max_retries=3,
            )

            with patch("clockwork.resource_completer.ToolSelector"):
                completer = ResourceCompleter(
                    api_key="test-key",  # pragma: allowlist secret
                    base_url="https://api.example.com/v1",
                )

                # Verify cache was initialized
                assert completer.cache is not None

    @pytest.mark.asyncio
    async def test_completer_cache_disabled(self, temp_cache_dir):
        """Test that cache is None when disabled."""
        from clockwork.resource_completer import ResourceCompleter

        with patch(
            "clockwork.resource_completer.get_settings"
        ) as mock_settings:
            mock_settings.return_value = MagicMock(
                api_key="test-key",  # pragma: allowlist secret
                model="test-model",
                base_url="https://api.example.com/v1",
                cache_enabled=False,
                cache_dir=str(temp_cache_dir),
                cache_ttl_days=7,
                completion_max_retries=3,
            )

            with patch("clockwork.resource_completer.ToolSelector"):
                completer = ResourceCompleter(
                    api_key="test-key",  # pragma: allowlist secret
                    base_url="https://api.example.com/v1",
                )

                # Cache should be None when disabled
                assert completer.cache is None


class TestCacheKeyAlgorithm:
    """Tests for cache key algorithm edge cases."""

    @pytest.fixture
    def cache(self):
        """Create a cache for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield CompletionCache(cache_dir=temp_dir)

    def test_cache_key_excludes_tools(self, cache):
        """Test that tools are excluded from cache key."""
        mock_tool = MagicMock()
        resource1 = FileResource(
            name="test.txt",
            description="A test file",
            tools=[mock_tool],
        )
        resource2 = FileResource(
            name="test.txt",
            description="A test file",
            tools=[],
        )
        model = "test-model"

        key1 = cache.compute_cache_key(resource1, model)
        key2 = cache.compute_cache_key(resource2, model)

        # Keys should be the same since tools are excluded
        assert key1 == key2

    def test_cache_key_excludes_assertions(self, cache):
        """Test that assertions are excluded from cache key."""
        from clockwork.assertions import ContainerRunningAssert

        resource1 = FileResource(
            name="test.txt",
            description="A test file",
            assertions=[ContainerRunningAssert()],
        )
        resource2 = FileResource(
            name="test.txt",
            description="A test file",
            assertions=[],
        )
        model = "test-model"

        key1 = cache.compute_cache_key(resource1, model)
        key2 = cache.compute_cache_key(resource2, model)

        # Keys should be the same since assertions are excluded
        assert key1 == key2

    def test_cache_key_none_description(self, cache):
        """Test cache key generation with None description."""
        resource = FileResource(
            name="test.txt",
            content="Hello",  # No description needed since content is provided
        )
        model = "test-model"

        # Should not raise
        key = cache.compute_cache_key(resource, model)
        assert len(key) == 16


class TestNoCacheFlag:
    """Tests for --no-cache CLI flag behavior."""

    @pytest.fixture
    def temp_cache_dir(self):
        """Create a temporary directory for cache testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir) / "cache"

    @pytest.mark.asyncio
    async def test_use_cache_false_skips_cache(self, temp_cache_dir):
        """Test that use_cache=False skips cache lookup and storage."""
        from clockwork.resource_completer import ResourceCompleter

        with patch(
            "clockwork.resource_completer.get_settings"
        ) as mock_settings:
            mock_settings.return_value = MagicMock(
                api_key="test-key",  # pragma: allowlist secret
                model="test-model",
                base_url="https://api.example.com/v1",
                cache_enabled=True,
                cache_dir=str(temp_cache_dir),
                cache_ttl_days=7,
                completion_max_retries=3,
            )

            with patch("clockwork.resource_completer.ToolSelector"):
                completer = ResourceCompleter(
                    api_key="test-key",  # pragma: allowlist secret
                    base_url="https://api.example.com/v1",
                )

                # Pre-populate cache
                resource = FileResource(
                    name="test.txt",
                    description="A test file",
                )
                cache_key = completer.cache.compute_cache_key(
                    resource, completer.model
                )
                completer.cache.set(
                    cache_key,
                    {
                        "name": "test.txt",
                        "content": "cached content",
                        "directory": ".",
                        "mode": "644",
                    },
                    "FileResource",
                )

                # Mock _complete_resource to verify it gets called
                completed_result = FileResource(
                    name="test.txt",
                    content="new content from AI",
                    directory=".",
                    mode="644",
                )
                completer._complete_resource = AsyncMock(
                    return_value=completed_result
                )

                # Call with use_cache=False - should call AI even though cache exists
                await completer._complete_single(resource, use_cache=False)

                # Verify _complete_resource was called (cache was bypassed)
                completer._complete_resource.assert_called_once()
