"""Directory resource for creating and managing directories."""

from typing import Optional, Dict, Any
from pathlib import Path
from .base import Resource


class DirectoryResource(Resource):
    """Directory resource - creates directories with AI-completed permissions.

    Minimal usage (AI completes name and mode):
        DirectoryResource(description="Main application directory at scratch/myapp")
        # AI generates: name="app-directory", mode="755"

    Advanced usage (override specific fields):
        DirectoryResource(
            description="Application data storage with restricted access",
            path="scratch/myapp/data",
            mode="700"  # Override permissions
        )
        # AI generates: name="data-directory"

    Attributes:
        description: Directory purpose - used by AI for completion (required)
        path: Full path to the directory (required)
        name: Directory identifier (optional - AI generates if not provided)
        mode: Directory permissions as octal string (optional - AI picks if not provided)
        user: Owner username (optional)
        group: Group name (optional)
        present: Whether directory should exist (default: True)
        recursive: Create parent directories if needed (default: True)
    """

    description: str
    path: str
    name: Optional[str] = None
    mode: Optional[str] = None
    user: Optional[str] = None
    group: Optional[str] = None
    present: bool = True
    recursive: bool = True

    def needs_completion(self) -> bool:
        """Returns True if name or mode need AI completion.

        When name or mode are None, the AI will analyze the description
        and path to suggest appropriate values.

        Returns:
            bool: True if name or mode is None, False otherwise
        """
        return self.name is None or self.mode is None

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

    def to_pyinfra_operations(self) -> str:
        """Generate PyInfra files.directory operation code.

        Creates a PyInfra operation that creates the directory with the
        specified configuration including permissions, owner, and group.
        All fields should be populated by AI completion before this is called.

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
        # Name should be populated by AI completion
        if self.name is None:
            raise ValueError(f"Resource name not completed. name={self.name}")

        # Resolve absolute path
        abs_path = self._resolve_directory_path()

        # Ensure mode is set (should be populated by AI completion)
        mode = self.mode or "755"

        # Build operation parameters
        params = [
            f'    name="Create directory {abs_path}",',
            f'    path="{abs_path}",',
            f'    present={self.present},',
            f'    recursive={self.recursive},',
        ]

        # Add mode parameter
        params.append(f'    mode="{mode}",')

        # Add optional parameters
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

    def to_pyinfra_destroy_operations(self) -> str:
        """Generate PyInfra operations code to destroy/remove the directory.

        Creates a PyInfra operation that removes the directory by setting
        present=False. This will only succeed if the directory is empty or
        PyInfra is configured to force removal.

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
        # Name should be populated by AI completion
        if self.name is None:
            raise ValueError(f"Resource name not completed. name={self.name}")

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

    def get_connection_context(self) -> Dict[str, Any]:
        """Get connection context for this Directory resource.

        Returns shareable fields that other resources can use when connected.
        This includes directory path and permissions for resources that need to
        reference or interact with this directory.

        Returns:
            Dict[str, Any]: Connection context with the following keys:
                - name: Directory name (always present)
                - type: Resource type name (always present)
                - path: Full directory path (always present)
                - mode: Directory permissions (if specified)
        """
        context = {
            "name": self.name,
            "type": self.__class__.__name__,
            "path": self.path,
        }

        # Add mode if specified
        if self.mode:
            context["mode"] = self.mode

        return context

    def to_pyinfra_assert_operations(self) -> str:
        """Generate PyInfra operations code for directory assertions.

        Provides default assertions for DirectoryResource:
        - Directory exists at the expected path (if present=True)
        - Directory has correct permissions (if mode is specified)
        - Directory has correct owner (if user is specified)
        - Directory has correct group (if group is specified)

        These can be overridden by specifying custom assertions.

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
        # Name should be populated by AI completion
        if self.name is None:
            raise ValueError(f"Resource name not completed. name={self.name}")

        # If custom assertions are defined, use the base implementation
        if self.assertions:
            return super().to_pyinfra_assert_operations()

        # Resolve absolute path
        abs_path = self._resolve_directory_path()

        # Ensure mode is set
        mode = self.mode or "755"

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

            # Assert: Directory has correct permissions
            operations.append(f'''
# Assert: Directory has correct permissions
server.shell(
    name="Assert: Directory {abs_path} has mode {mode}",
    commands=[
        "[ \\"$(stat -c '%a' {abs_path})\\" = \\"{mode}\\" ] || exit 1"
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
