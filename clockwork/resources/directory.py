"""Directory resource for creating and managing directories."""

from typing import Optional, Dict, Any
from pathlib import Path
from .base import Resource


class DirectoryResource(Resource):
    """Directory resource - creates directories with specified permissions.

    Declaratively define directories. No AI generation is needed for directories.

    Attributes:
        name: Directory name (required)
        description: Optional description of the directory's purpose
        path: Full path to the directory (required)
        mode: Directory permissions as octal string (default: "755")
        user: Owner username (optional)
        group: Group name (optional)
        present: Whether directory should exist (default: True)
        recursive: Create parent directories if needed (default: True)

    Examples:
        Basic directory creation:
        >>> DirectoryResource(
        ...     name="app_data",
        ...     path="/var/app/data",
        ...     mode="755"
        ... )

        Directory with owner and group:
        >>> DirectoryResource(
        ...     name="web_root",
        ...     description="Web server document root",
        ...     path="/var/www/html",
        ...     mode="755",
        ...     user="www-data",
        ...     group="www-data"
        ... )

        Ensure directory is absent:
        >>> DirectoryResource(
        ...     name="temp_dir",
        ...     path="/tmp/old_data",
        ...     present=False
        ... )
    """

    name: str
    description: Optional[str] = None
    path: str
    mode: Optional[str] = "755"
    user: Optional[str] = None
    group: Optional[str] = None
    present: bool = True
    recursive: bool = True

    def needs_artifact_generation(self) -> bool:
        """Returns False as directories do not need AI-generated content.

        Directory creation is a straightforward filesystem operation that
        does not require any AI assistance.

        Returns:
            bool: Always returns False
        """
        return False

    def _resolve_directory_path(self) -> str:
        """Resolve directory path to absolute path.

        Converts relative paths to absolute based on current working directory.

        Returns:
            str: Absolute path to the directory
        """
        dir_path = Path(self.path)
        if not dir_path.is_absolute():
            dir_path = Path.cwd() / dir_path
        return str(dir_path)

    def to_pyinfra_operations(self, artifacts: Dict[str, Any]) -> str:
        """Generate PyInfra files.directory operation code.

        Creates a PyInfra operation that creates the directory with the
        specified configuration including permissions, owner, and group.

        Args:
            artifacts: Dict mapping resource names to generated content (unused for directories)

        Returns:
            str: PyInfra operation code as a string

        Example generated code:
            ```python
            files.directory(
                name="Create directory /var/app/data",
                path="/var/app/data",
                mode="755",
                user="appuser",
                group="appgroup",
                present=True,
                recursive=True,
            )
            ```
        """
        # Resolve absolute path
        abs_path = self._resolve_directory_path()

        # Build operation parameters
        params = [
            f'    name="Create directory {abs_path}",',
            f'    path="{abs_path}",',
            f'    present={self.present},',
            f'    recursive={self.recursive},',
        ]

        # Add optional parameters
        if self.mode is not None:
            params.append(f'    mode="{self.mode}",')
        if self.user is not None:
            params.append(f'    user="{self.user}",')
        if self.group is not None:
            params.append(f'    group="{self.group}",')

        params_str = "\n".join(params)

        return f'''
# Create directory: {self.name}
files.directory(
{params_str}
)
'''

    def to_pyinfra_destroy_operations(self, artifacts: Dict[str, Any]) -> str:
        """Generate PyInfra operations code to destroy/remove the directory.

        Creates a PyInfra operation that removes the directory by setting
        present=False. This will only succeed if the directory is empty or
        PyInfra is configured to force removal.

        Args:
            artifacts: Dict mapping resource names to generated content (unused for destroy)

        Returns:
            str: PyInfra operation code to remove the directory

        Example generated code:
            ```python
            files.directory(
                name="Remove directory /var/app/data",
                path="/var/app/data",
                present=False,
            )
            ```
        """
        # Resolve absolute path
        abs_path = self._resolve_directory_path()

        return f'''
# Remove directory: {self.name}
files.directory(
    name="Remove directory {abs_path}",
    path="{abs_path}",
    present=False,
)
'''

    def to_pyinfra_assert_operations(self, artifacts: Dict[str, Any]) -> str:
        """Generate PyInfra operations code for directory assertions.

        Provides default assertions for DirectoryResource:
        - Directory exists at the expected path (if present=True)
        - Directory has correct permissions (if mode is specified)
        - Directory has correct owner (if user is specified)
        - Directory has correct group (if group is specified)

        These can be overridden by specifying custom assertions.

        Args:
            artifacts: Dict mapping resource names to generated content

        Returns:
            str: PyInfra assertion operation code

        Example generated code:
            ```python
            # Default assertions for directory: app_data

            # Assert: Directory exists
            server.shell(
                name="Assert: Directory /var/app/data exists",
                commands=[
                    "test -d /var/app/data || exit 1"
                ],
            )

            # Assert: Directory has correct permissions
            server.shell(
                name="Assert: Directory /var/app/data has mode 755",
                commands=[
                    '[ "$(stat -c \'%a\' /var/app/data)" = "755" ] || exit 1'
                ],
            )
            ```
        """
        # If custom assertions are defined, use the base implementation
        if self.assertions:
            return super().to_pyinfra_assert_operations(artifacts)

        # Resolve absolute path
        abs_path = self._resolve_directory_path()

        operations = []
        operations.append(f"\n# Default assertions for directory: {self.name}")

        # Only add assertions if directory should be present
        if self.present:
            # Assert: Directory exists
            operations.append(f'''
# Assert: Directory exists
server.shell(
    name="Assert: Directory {abs_path} exists",
    commands=[
        "test -d {abs_path} || exit 1"
    ],
)
''')

            # Assert: Directory has correct permissions (if specified)
            if self.mode is not None:
                operations.append(f'''
# Assert: Directory has correct permissions
server.shell(
    name="Assert: Directory {abs_path} has mode {self.mode}",
    commands=[
        "[ \\"$(stat -c '%a' {abs_path})\\" = \\"{self.mode}\\" ] || exit 1"
    ],
)
''')

            # Assert: Directory has correct owner (if specified)
            if self.user is not None:
                operations.append(f'''
# Assert: Directory has correct owner
server.shell(
    name="Assert: Directory {abs_path} has owner {self.user}",
    commands=[
        "[ \\"$(stat -c '%U' {abs_path})\\" = \\"{self.user}\\" ] || exit 1"
    ],
)
''')

            # Assert: Directory has correct group (if specified)
            if self.group is not None:
                operations.append(f'''
# Assert: Directory has correct group
server.shell(
    name="Assert: Directory {abs_path} has group {self.group}",
    commands=[
        "[ \\"$(stat -c '%G' {abs_path})\\" = \\"{self.group}\\" ] || exit 1"
    ],
)
''')

        return "\n".join(operations)
