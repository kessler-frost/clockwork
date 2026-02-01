"""
Completion Cache - Caching layer for AI completions.

Provides deterministic caching of completion results based on resource
state and model configuration for reproducible infrastructure.
"""

import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class CompletionCache:
    """Cache for completion results to enable reproducible completions."""

    def __init__(
        self,
        cache_dir: str = ".clockwork/cache",
        ttl_days: int = 7,
    ):
        """
        Initialize the completion cache.

        Args:
            cache_dir: Directory to store cache files
            ttl_days: Time-to-live for cache entries in days
        """
        self.cache_dir = Path(cache_dir)
        self.ttl_seconds = ttl_days * 24 * 60 * 60

        # Ensure cache directory exists
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Initialized CompletionCache at {self.cache_dir}")

    def compute_cache_key(self, resource: Any, model: str) -> str:
        """
        Compute a cache key for a resource and model combination.

        The key is based on:
        - Resource type
        - Resource description
        - User-provided field values (non-None)
        - Model name

        Args:
            resource: Resource object to compute key for
            model: Model name being used for completion

        Returns:
            SHA256 hash string as cache key
        """
        # Get resource data for hashing
        resource_data = resource.model_dump(
            exclude={"tools", "assertions", "connections"}
        )

        # Only include non-None user-provided values
        relevant_data = {
            "type": resource.__class__.__name__,
            "model": model,
            "fields": {k: v for k, v in resource_data.items() if v is not None},
        }

        # Create deterministic JSON string
        json_str = json.dumps(relevant_data, sort_keys=True, default=str)

        # Compute SHA256 hash
        return hashlib.sha256(json_str.encode()).hexdigest()[:16]

    def _get_cache_path(self, cache_key: str) -> Path:
        """Get the file path for a cache key."""
        return self.cache_dir / f"{cache_key}.json"

    def get(self, cache_key: str) -> dict[str, Any] | None:
        """
        Get a cached completion result.

        Args:
            cache_key: Cache key to look up

        Returns:
            Cached data dict or None if not found/expired
        """
        cache_path = self._get_cache_path(cache_key)

        if not cache_path.exists():
            return None

        try:
            with open(cache_path) as f:
                cached = json.load(f)

            # Check TTL
            cached_time = cached.get("_cached_at", 0)
            if time.time() - cached_time > self.ttl_seconds:
                logger.debug(f"Cache entry expired: {cache_key}")
                cache_path.unlink(missing_ok=True)
                return None

            # Return the data without metadata
            data = cached.get("data")
            logger.debug(f"Cache hit: {cache_key}")
            return data

        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Invalid cache entry {cache_key}: {e}")
            cache_path.unlink(missing_ok=True)
            return None

    def set(
        self, cache_key: str, data: dict[str, Any], resource_type: str
    ) -> None:
        """
        Store a completion result in the cache.

        Args:
            cache_key: Cache key to store under
            data: Completed resource data to cache
            resource_type: Type of resource for metadata
        """
        cache_path = self._get_cache_path(cache_key)

        cached = {
            "_cached_at": time.time(),
            "_resource_type": resource_type,
            "data": data,
        }

        try:
            with open(cache_path, "w") as f:
                json.dump(cached, f, indent=2, default=str)
            logger.debug(f"Cached completion: {cache_key}")
        except OSError as e:
            logger.warning(f"Failed to cache completion {cache_key}: {e}")

    def clear(self) -> int:
        """
        Clear all cache entries.

        Returns:
            Number of entries cleared
        """
        count = 0
        for cache_file in self.cache_dir.glob("*.json"):
            try:
                cache_file.unlink()
                count += 1
            except OSError:
                pass

        logger.info(f"Cleared {count} cache entries")
        return count

    def cleanup_expired(self) -> int:
        """
        Remove expired cache entries.

        Returns:
            Number of entries removed
        """
        count = 0
        current_time = time.time()

        for cache_file in self.cache_dir.glob("*.json"):
            try:
                with open(cache_file) as f:
                    cached = json.load(f)

                cached_time = cached.get("_cached_at", 0)
                if current_time - cached_time > self.ttl_seconds:
                    cache_file.unlink()
                    count += 1
            except (json.JSONDecodeError, OSError):
                # Invalid or inaccessible file, remove it
                try:
                    cache_file.unlink()
                    count += 1
                except OSError:
                    pass

        logger.info(f"Cleaned up {count} expired cache entries")
        return count
