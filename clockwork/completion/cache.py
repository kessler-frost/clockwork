"""
Completion Cache - SQLite-based caching for AI completion results.

Provides reproducible completions by caching results based on resource
configuration, description, and model used.
"""

import hashlib
import json
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class CompletionCache:
    """
    SQLite-based cache for AI completion results.

    Stores completion results keyed by a hash of resource configuration,
    enabling reproducible completions and faster subsequent runs.
    """

    def __init__(self, cache_dir: str = ".clockwork/cache", ttl_days: int = 7):
        """
        Initialize the completion cache.

        Args:
            cache_dir: Directory to store the cache database
            ttl_days: Time-to-live for cache entries in days
        """
        self.cache_dir = Path(cache_dir)
        self.ttl_days = ttl_days
        self.db_path = self.cache_dir / "completions.db"

        # Ensure cache directory exists
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Initialize database
        self._init_db()

        logger.debug(f"CompletionCache initialized at {self.db_path}")

    def _init_db(self) -> None:
        """Initialize the SQLite database with required schema."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS completions (
                    cache_key TEXT PRIMARY KEY,
                    resource_type TEXT NOT NULL,
                    data TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP NOT NULL
                )
            """)
            # Create index for expiration cleanup
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_expires_at ON completions(expires_at)
            """)
            conn.commit()

    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection with row factory configured."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def compute_cache_key(self, resource: Any, model: str) -> str:
        """
        Compute a cache key for a resource based on its configuration.

        The cache key is a SHA256 hash of:
        - resource_type: The class name of the resource
        - description: The resource description
        - model: The AI model name used for completion
        - user_fields: All non-None field values (excluding tools, assertions, connections)

        Args:
            resource: The resource object to compute key for
            model: The model name used for completion

        Returns:
            A 16-character hexadecimal cache key
        """
        # Get user-provided fields (excluding non-serializable/completion-related fields)
        resource_data = resource.model_dump()
        user_fields = {
            k: v
            for k, v in resource_data.items()
            if v is not None and k not in ("tools", "assertions", "connections")
        }

        key_data = {
            "resource_type": resource.__class__.__name__,
            "description": resource.description,
            "model": model,
            "user_fields": user_fields,
        }

        # Create deterministic JSON string
        json_str = json.dumps(key_data, sort_keys=True, default=str)
        return hashlib.sha256(json_str.encode()).hexdigest()[:16]

    def get(self, cache_key: str) -> dict | None:
        """
        Retrieve a cached completion result.

        Args:
            cache_key: The cache key to look up

        Returns:
            The cached completion data as a dict, or None if not found/expired
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Fetch entry and check expiration
            cursor.execute(
                """
                SELECT data, expires_at FROM completions
                WHERE cache_key = ?
            """,
                (cache_key,),
            )

            row = cursor.fetchone()
            if row is None:
                logger.debug(f"Cache miss: {cache_key}")
                return None

            # Parse expiration time
            expires_at = datetime.fromisoformat(row["expires_at"])
            if expires_at < datetime.now():
                # Entry expired, remove it
                cursor.execute(
                    "DELETE FROM completions WHERE cache_key = ?", (cache_key,)
                )
                conn.commit()
                logger.debug(f"Cache expired: {cache_key}")
                return None

            logger.debug(f"Cache hit: {cache_key}")
            return json.loads(row["data"])

    def set(self, cache_key: str, data: dict, resource_type: str) -> None:
        """
        Store a completion result in the cache.

        Args:
            cache_key: The cache key to store under
            data: The completion data to cache (must be JSON-serializable)
            resource_type: The resource type name for reference
        """
        expires_at = datetime.now() + timedelta(days=self.ttl_days)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO completions
                (cache_key, resource_type, data, created_at, expires_at)
                VALUES (?, ?, ?, ?, ?)
            """,
                (
                    cache_key,
                    resource_type,
                    json.dumps(data, default=str),
                    datetime.now().isoformat(),
                    expires_at.isoformat(),
                ),
            )
            conn.commit()

        logger.debug(f"Cache set: {cache_key} (expires: {expires_at})")

    def clear(self) -> int:
        """
        Clear all entries from the cache.

        Returns:
            Number of entries deleted
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM completions")
            count = cursor.fetchone()[0]

            cursor.execute("DELETE FROM completions")
            conn.commit()

        logger.info(f"Cache cleared: {count} entries deleted")
        return count

    def cleanup_expired(self) -> int:
        """
        Remove all expired entries from the cache.

        Returns:
            Number of expired entries deleted
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                DELETE FROM completions
                WHERE expires_at < ?
            """,
                (datetime.now().isoformat(),),
            )
            count = cursor.rowcount
            conn.commit()

        if count > 0:
            logger.info(f"Cache cleanup: {count} expired entries deleted")
        return count

    def stats(self) -> dict:
        """
        Get cache statistics.

        Returns:
            Dict containing:
            - total_entries: Total number of cached entries
            - valid_entries: Number of non-expired entries
            - expired_entries: Number of expired entries
            - resource_types: Dict mapping resource type to count
            - cache_dir: Path to cache directory
            - db_size_bytes: Size of database file in bytes
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Total entries
            cursor.execute("SELECT COUNT(*) FROM completions")
            total = cursor.fetchone()[0]

            # Valid entries (not expired)
            cursor.execute(
                """
                SELECT COUNT(*) FROM completions
                WHERE expires_at >= ?
            """,
                (datetime.now().isoformat(),),
            )
            valid = cursor.fetchone()[0]

            # Expired entries
            expired = total - valid

            # Resource type breakdown
            cursor.execute("""
                SELECT resource_type, COUNT(*) as count
                FROM completions
                GROUP BY resource_type
            """)
            resource_types = {row["resource_type"]: row["count"] for row in cursor}

        # Database file size
        db_size = self.db_path.stat().st_size if self.db_path.exists() else 0

        return {
            "total_entries": total,
            "valid_entries": valid,
            "expired_entries": expired,
            "resource_types": resource_types,
            "cache_dir": str(self.cache_dir),
            "db_size_bytes": db_size,
        }
