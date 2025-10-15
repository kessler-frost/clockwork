"""File system assertions for validating file properties."""

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


class FilePermissionsAssert(BaseAssertion):
    """Assert that a file has specific permissions and ownership.

    Validates file mode (permissions), owner, and/or group. All specified
    attributes must match for the assertion to pass.

    Attributes:
        path: Path to the file to check
        mode: Expected file mode in octal (e.g., "644", "755")
        owner: Expected owner username (optional)
        group: Expected group name (optional)
        timeout_seconds: Maximum time to wait (default: 5)

    Example:
        >>> FilePermissionsAssert(
        ...     path="/etc/app/config.json",
        ...     mode="644",
        ...     owner="root",
        ...     group="root"
        ... )
    """

    path: str
    mode: str
    owner: Optional[str] = None
    group: Optional[str] = None
    timeout_seconds: int = 5


class FileSizeAssert(BaseAssertion):
    """Assert that a file size is within specified bounds.

    Validates that a file's size falls within minimum and/or maximum limits.
    At least one of min_bytes or max_bytes must be specified.

    Attributes:
        path: Path to the file to check
        min_bytes: Minimum file size in bytes (optional)
        max_bytes: Maximum file size in bytes (optional)
        timeout_seconds: Maximum time to wait (default: 5)

    Example:
        >>> FileSizeAssert(
        ...     path="/var/log/app.log",
        ...     min_bytes=100,
        ...     max_bytes=1048576  # 1 MB
        ... )
    """

    path: str
    min_bytes: Optional[int] = None
    max_bytes: Optional[int] = None
    timeout_seconds: int = 5


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
    pattern: Optional[str] = None
    sha256: Optional[str] = None
    timeout_seconds: int = 10
