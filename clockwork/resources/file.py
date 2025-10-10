"""File resource for creating files with optional AI-generated content."""

from typing import Optional, Dict, Any
from pydantic import model_validator
from .base import Resource, ArtifactSize


class FileResource(Resource):
    """File resource - creates a file with content (AI-generated or user-provided)."""

    name: str  # filename (e.g., "game_of_life.md")
    description: Optional[str] = None  # what the file should contain (used by AI if content not provided)
    size: ArtifactSize = ArtifactSize.SMALL  # size hint for AI generation
    directory: Optional[str] = None  # directory to create file in (defaults to /tmp)
    path: Optional[str] = None  # full path (overrides directory + name if provided)
    content: Optional[str] = None  # if provided, AI generation is skipped
    mode: str = "644"  # file permissions

    @model_validator(mode='after')
    def validate_description_or_content(self):
        """Ensure either description or content is provided."""
        if self.description is None and self.content is None:
            raise ValueError("FileResource requires either 'description' (for AI generation) or 'content' (explicit content)")
        return self

    def needs_artifact_generation(self) -> bool:
        """Returns True if content needs to be AI-generated."""
        return self.content is None

    def _resolve_file_path(self) -> tuple[str, Optional[str]]:
        """Resolve file path and directory from resource configuration.

        Handles three cases:
        1. self.path is provided → use it (absolute or resolve relative)
        2. self.directory is provided → combine with self.name
        3. Default → /tmp/{self.name}

        Returns:
            tuple[str, Optional[str]]: (file_path, directory) where:
                - file_path: Absolute path to the file
                - directory: Absolute path to directory (if specified), None otherwise
        """
        from pathlib import Path
        cwd = Path.cwd()

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
            file_path = Path("/tmp") / self.name
            return (str(file_path), None)

    def to_pyinfra_operations(self, artifacts: Dict[str, Any]) -> str:
        """Generate PyInfra files.file operation.

        Args:
            artifacts: Dict with generated content (if any)

        Returns:
            PyInfra operation code as string
        """
        # Get content from artifacts or use provided content
        content = artifacts.get(self.name) or self.content or ""

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
    mode="{self.mode}",
)
'''

    def to_pyinfra_destroy_operations(self, artifacts: Dict[str, Any]) -> str:
        """Generate PyInfra operations code to destroy/remove the file.

        Args:
            artifacts: Dict with generated content (if any)

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

    def to_pyinfra_assert_operations(self, artifacts: Dict[str, Any]) -> str:
        """Generate PyInfra operations code for file assertions.

        Provides default assertions for FileResource:
        - File exists at the expected path
        - File has correct permissions (mode)

        These can be overridden by specifying custom assertions.

        Args:
            artifacts: Dict with generated content (if any)

        Returns:
            String of PyInfra assertion operation code
        """
        # If custom assertions are defined, use the base implementation
        if self.assertions:
            return super().to_pyinfra_assert_operations(artifacts)

        # Resolve file path (ignore directory for assertions)
        file_path, _ = self._resolve_file_path()

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
    name="Assert: File {file_path} has mode {self.mode}",
    commands=[
        "[ \\"$(stat -c '%a' {file_path})\\" = \\"{self.mode}\\" ] || exit 1"
    ],
)
'''
