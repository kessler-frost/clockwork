"""File resource for creating files with optional AI-generated content."""

from typing import Optional, Dict, Any
from pydantic import model_validator
from .base import Resource


class FileResource(Resource):
    """File resource - creates a file with AI-generated or user-provided content.

    Minimal usage (AI completes everything):
        FileResource(description="Comprehensive article about Conway's Game of Life")

    Advanced usage (override specific fields):
        FileResource(
            description="Comprehensive article about Conway's Game of Life",
            directory="scratch",
            name="game.md"
        )
    """

    description: str  # what the file should contain (required)
    name: Optional[str] = None  # filename - AI generates if not provided
    content: Optional[str] = None  # content - AI generates if not provided
    directory: Optional[str] = None  # directory - AI picks best location (default: ".")
    mode: Optional[str] = None  # file permissions - AI picks (default: "644")
    path: Optional[str] = None  # full path (overrides directory + name if provided)

    @model_validator(mode='after')
    def validate_description(self):
        """Description is always required."""
        if not self.description:
            raise ValueError("FileResource requires 'description'")
        return self

    def needs_completion(self) -> bool:
        """Returns True if any field needs AI completion."""
        # If user provides explicit content, no completion needed
        if self.content is not None:
            return False

        # Otherwise, need completion for content at minimum
        # Also check if name, directory, mode need completion
        return (
            self.content is None or
            self.name is None or
            self.directory is None or
            self.mode is None
        )

    def _resolve_file_path(self) -> tuple[str, Optional[str]]:
        """Resolve file path and directory from resource configuration.

        Handles three cases:
        1. self.path is provided → use it (absolute or resolve relative)
        2. self.directory is provided → combine with self.name
        3. Default → current directory (./)

        Returns:
            tuple[str, Optional[str]]: (file_path, directory) where:
                - file_path: Absolute path to the file
                - directory: Absolute path to directory (if specified), None otherwise
        """
        from pathlib import Path
        cwd = Path.cwd()

        # Ensure we have a name (should be set after AI completion)
        if not self.name:
            raise ValueError("FileResource.name must be set before resolving path")

        if self.path:
            file_path = Path(self.path)
            file_path = file_path if file_path.is_absolute() else cwd / file_path
            return (str(file_path), None)
        elif self.directory:
            abs_directory = Path(self.directory)
            abs_directory = abs_directory if abs_directory.is_absolute() else cwd / abs_directory
            file_path = abs_directory / self.name
            return (str(file_path), str(abs_directory))
        else:
            # Default to current directory
            file_path = cwd / self.name
            return (str(file_path), None)

    def to_pyinfra_operations(self) -> str:
        """Generate PyInfra files.file operation.

        Returns:
            PyInfra operation code as string
        """
        # Use content directly (should be set after AI completion)
        content = self.content or ""

        # Ensure mode is set (should be set after AI completion)
        mode = self.mode or "644"

        # Resolve file path and directory
        file_path, directory = self._resolve_file_path()

        # Escape content for Python triple-quoted string
        escaped_content = content.replace('\\', '\\\\').replace('"""', r'\"""')

        # Generate directory creation if needed
        dir_operation = ""
        if directory:
            dir_operation = f'''
# Create directory: {directory}
files.directory(
    name="Create directory {directory}",
    path="{directory}",
    present=True,
)

'''

        return f'''
{dir_operation}# Create file: {self.name}
with open("_temp_{self.name}", "w") as f:
    f.write("""{escaped_content}""")

files.put(
    name="Create {self.name}",
    src="_temp_{self.name}",
    dest="{file_path}",
    mode="{mode}",
)
'''

    def to_pyinfra_destroy_operations(self) -> str:
        """Generate PyInfra operations code to destroy/remove the file.

        Returns:
            PyInfra operation code to remove the file and its directory if specified
        """
        # Resolve file path and directory
        file_path, directory = self._resolve_file_path()

        # Remove file first, then directory if specified
        operations = f'''
# Remove file: {self.name}
files.file(
    name="Remove {self.name}",
    path="{file_path}",
    present=False,
)
'''

        # If directory was specified, also remove it
        # Note: This will only succeed if directory is empty after all files are removed
        if directory:
            operations += f'''
# Remove directory if empty: {directory}
files.directory(
    name="Remove directory {directory}",
    path="{directory}",
    present=False,
)
'''

        return operations

    def to_pyinfra_assert_operations(self) -> str:
        """Generate PyInfra operations code for file assertions.

        Provides default assertions for FileResource:
        - File exists at the expected path
        - File has correct permissions (mode)

        These can be overridden by specifying custom assertions.

        Returns:
            String of PyInfra assertion operation code
        """
        # If custom assertions are defined, use the base implementation
        if self.assertions:
            return super().to_pyinfra_assert_operations()

        # Resolve file path (ignore directory for assertions)
        file_path, _ = self._resolve_file_path()

        # Ensure mode is set
        mode = self.mode or "644"

        # Default assertions for FileResource
        return f'''
# Default assertions for file: {self.name}

# Assert: File exists
server.shell(
    name="Assert: File {file_path} exists",
    commands=[
        "test -f {file_path} || exit 1"
    ],
)

# Assert: File has correct permissions
server.shell(
    name="Assert: File {file_path} has mode {mode}",
    commands=[
        "[ \\"$(stat -c '%a' {file_path})\\" = \\"{mode}\\" ] || exit 1"
    ],
)
'''
