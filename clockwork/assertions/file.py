"""File system assertions for validating file properties."""

from typing import Any, Optional
from pathlib import Path
from .base import BaseAssertion


def _resolve_path_for_pyinfra(path_str: str) -> str:
    """Resolve a path for use in PyInfra operations.

    PyInfra runs from .clockwork/pyinfra/, so we need to adjust relative paths
    to be relative to that directory (../../path).

    Args:
        path_str: Original path (absolute or relative to project root)

    Returns:
        Path string usable from PyInfra execution directory
    """
    path = Path(path_str)
    if not path.is_absolute():
        # Make relative to PyInfra dir (which is .clockwork/pyinfra/)
        path = Path("../..") / path
    return str(path)


class FileExistsAssert(BaseAssertion):
    """Assert that a file or directory exists at the specified path.

    Validates that a file or directory exists on the filesystem using test -e.

    Attributes:
        path: Absolute or relative path to check
        timeout_seconds: Maximum time to wait (default: 5)

    Example:
        >>> FileExistsAssert(path="/tmp/myfile.txt")
        >>> FileExistsAssert(path="/var/log/app")
    """

    path: str
    timeout_seconds: int = 5

    def to_pyinfra_operation(self, resource: Any) -> str:
        """Generate PyInfra operation to check file existence.

        Args:
            resource: Parent resource (typically a FileResource)

        Returns:
            PyInfra server.shell operation that tests if path exists
        """
        resolved_path = _resolve_path_for_pyinfra(self.path)
        desc = self.description or f"File {self.path} exists"

        return f'''
# Assert: {desc}
server.shell(
    name="Assert: {desc}",
    commands=[
        "test -e {resolved_path} || exit 1"
    ],
)
'''


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

    def to_pyinfra_operation(self, resource: Any) -> str:
        """Generate PyInfra operation to check file permissions.

        Args:
            resource: Parent resource (typically a FileResource)

        Returns:
            PyInfra server.shell operation that checks permissions, owner, group
        """
        resolved_path = _resolve_path_for_pyinfra(self.path)
        desc = self.description or f"File {self.path} has correct permissions"

        # Build validation commands
        checks = []

        # Check mode (permissions)
        checks.append(f"[ \"$(stat -c '%a' {resolved_path})\" = \"{self.mode}\" ]")

        # Check owner if specified (cross-platform: try Linux -c first, then macOS -f)
        if self.owner:
            checks.append(f"[ \"$(stat -c '%U' {resolved_path} 2>/dev/null || stat -f '%Su' {resolved_path})\" = \"{self.owner}\" ]")

        # Check group if specified (cross-platform: try Linux -c first, then macOS -f)
        if self.group:
            checks.append(f"[ \"$(stat -c '%G' {resolved_path} 2>/dev/null || stat -f '%Sg' {resolved_path})\" = \"{self.group}\" ]")

        # Join all checks with AND operator
        check_cmd = " && ".join(checks) + " || exit 1"

        return f'''
# Assert: {desc}
server.shell(
    name="Assert: {desc}",
    commands=[
        "{check_cmd}"
    ],
)
'''


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

    def to_pyinfra_operation(self, resource: Any) -> str:
        """Generate PyInfra operation to check file size.

        Args:
            resource: Parent resource (typically a FileResource)

        Returns:
            PyInfra server.shell operation that validates file size
        """
        desc = self.description or f"File {self.path} size is within bounds"

        # Build size checks
        checks = []

        if self.min_bytes is not None:
            checks.append(f"[ $SIZE -ge {self.min_bytes} ]")

        if self.max_bytes is not None:
            checks.append(f"[ $SIZE -le {self.max_bytes} ]")

        check_cmd = " && ".join(checks) if checks else "true"

        # Cross-platform stat command (Linux -c, macOS -f)
        resolved_path = _resolve_path_for_pyinfra(self.path)
        return f'''
# Assert: {desc}
server.shell(
    name="Assert: {desc}",
    commands=[
        "SIZE=$(stat -c '%s' {resolved_path} 2>/dev/null || stat -f '%z' {resolved_path} 2>/dev/null || echo 0); {check_cmd} || exit 1"
    ],
)
'''


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

    def to_pyinfra_operation(self, resource: Any) -> str:
        """Generate PyInfra operation to check file content.

        Args:
            resource: Parent resource (typically a FileResource)

        Returns:
            PyInfra server.shell operation that validates content via grep or sha256sum
        """
        resolved_path = _resolve_path_for_pyinfra(self.path)

        if self.pattern:
            desc = self.description or f"File {self.path} matches pattern"
            # Escape single quotes in pattern for shell command
            escaped_pattern = self.pattern.replace("'", "'\\''")

            return f'''
# Assert: {desc}
server.shell(
    name="Assert: {desc}",
    commands=[
        "grep -q '{escaped_pattern}' {resolved_path} || exit 1"
    ],
)
'''
        elif self.sha256:
            desc = self.description or f"File {self.path} matches checksum"

            return f'''
# Assert: {desc}
server.shell(
    name="Assert: {desc}",
    commands=[
        "echo '{self.sha256}  {resolved_path}' | sha256sum -c - || exit 1"
    ],
)
'''
        else:
            # No validation specified - always pass
            desc = self.description or f"File {self.path} content check (no pattern/checksum)"

            return f'''
# Assert: {desc}
server.shell(
    name="Assert: {desc}",
    commands=[
        "true"
    ],
)
'''
