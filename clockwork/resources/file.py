"""File resource for creating files with optional AI-generated content."""

from typing import Optional, Dict, Any
from .base import Resource, ArtifactSize


class FileResource(Resource):
    """File resource - creates a file with content (AI-generated or user-provided)."""

    name: str  # filename (e.g., "game_of_life.md")
    description: str  # what the file should contain (used by AI if content not provided)
    size: ArtifactSize = ArtifactSize.SMALL  # size hint for AI generation
    directory: Optional[str] = None  # directory to create file in (defaults to /tmp)
    path: Optional[str] = None  # full path (overrides directory + name if provided)
    content: Optional[str] = None  # if provided, AI generation is skipped
    mode: str = "644"  # file permissions

    def needs_artifact_generation(self) -> bool:
        """Returns True if content needs to be AI-generated."""
        return self.content is None

    def to_pyinfra_operations(self, artifacts: Dict[str, Any]) -> str:
        """Generate PyInfra files.file operation.

        Args:
            artifacts: Dict with generated content (if any)

        Returns:
            PyInfra operation code as string
        """
        # Get content from artifacts or use provided content
        content = artifacts.get(self.name) or self.content or ""

        # Determine file path: use path if provided, else directory + name, else /tmp + name
        if self.path:
            file_path = self.path
        elif self.directory:
            file_path = f"{self.directory.rstrip('/')}/{self.name}"
        else:
            file_path = f"/tmp/{self.name}"

        # Escape content for Python triple-quoted string
        escaped_content = content.replace('\\', '\\\\').replace('"""', r'\"""')

        return f'''
# Create file: {self.name}
with open("_temp_{self.name}", "w") as f:
    f.write("""{escaped_content}""")

files.put(
    name="Create {self.name}",
    src="_temp_{self.name}",
    dest="{file_path}",
    mode="{self.mode}",
)
'''
