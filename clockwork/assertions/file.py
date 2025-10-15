"""File system assertions for validating file properties."""

import hashlib
import re
from typing import Any, Optional
from pathlib import Path
from .base import BaseAssertion
from .utils import escape_shell_pattern


def _resolve_path_for_assertion(path_str: str) -> str:
    """Resolve a path for use in assertion operations.

    Converts relative paths to absolute paths for consistent validation.

    Args:
        path_str: Original path (absolute or relative to project root)

    Returns:
        Path string usable in assertions
    """
    path = Path(path_str)
    if not path.is_absolute():
        # Convert relative to absolute
        path = Path.cwd() / path
    return str(path)


class FileExistsAssert(BaseAssertion):
    """Assert that a file or directory exists at the specified path.

    Validates that a file or directory exists on the filesystem.

    Attributes:
        path: Absolute or relative path to check
        timeout_seconds: Maximum time to wait (default: 5)

    Example:
        >>> FileExistsAssert(path="/tmp/myfile.txt")
        >>> FileExistsAssert(path="/var/log/app")
    """

    path: str
    timeout_seconds: int = 5

    async def check(self, resource) -> bool:
        """Check if the file or directory exists.

        Args:
            resource: The resource to validate

        Returns:
            True if file/directory exists, False otherwise
        """
        try:
            resolved_path = _resolve_path_for_assertion(self.path)
            return Path(resolved_path).exists()
        except Exception:
            return False


class FileContentMatchesAssert(BaseAssertion):
    """Assert that file content matches a pattern or checksum.

    Validates file content either by regex pattern matching or SHA256 checksum.
    Only one of pattern or sha256 should be specified.

    Attributes:
        path: Path to the file to check
        pattern: Regular expression pattern to search for (optional)
        sha256: Expected SHA256 checksum of the file (optional)
        timeout_seconds: Maximum time to wait (default: 10)

    Example:
        >>> # Pattern matching
        >>> FileContentMatchesAssert(
        ...     path="/etc/hosts",
        ...     pattern="127.0.0.1.*localhost"
        ... )
        >>>
        >>> # Checksum validation
        >>> FileContentMatchesAssert(
        ...     path="/etc/config.json",
        ...     sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        ... )
    """

    path: str
    pattern: str | None = None
    sha256: str | None = None
    timeout_seconds: int = 10

    async def check(self, resource) -> bool:
        """Check if file content matches pattern or checksum.

        Args:
            resource: The resource to validate

        Returns:
            True if content matches, False otherwise
        """
        try:
            resolved_path = _resolve_path_for_assertion(self.path)
            path = Path(resolved_path)

            if self.pattern is not None:
                content = path.read_text()
                return re.search(self.pattern, content) is not None

            if self.sha256 is not None:
                content = path.read_bytes()
                file_hash = hashlib.sha256(content).hexdigest()
                return file_hash.lower() == self.sha256.lower()

            return False
        except Exception:
            return False
