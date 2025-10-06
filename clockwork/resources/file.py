"""File resource for creating files with optional AI-generated content."""

from typing import Optional, Dict, Any
from .base import Resource, ArtifactSize


class FileResource(Resource):
    """File resource - creates a file with content (AI-generated or user-provided)."""

    name: str  # filename (e.g., "game_of_life.md")
    description: str  # what the file should contain (used by AI if content not provided)
    size: ArtifactSize = ArtifactSize.SMALL  # size hint for AI generation
    path: Optional[str] = None  # where to create the file (defaults to /tmp/{name})
    content: Optional[str] = None  # if provided, AI generation is skipped
    mode: str = "644"  # file permissions

    def needs_artifact_generation(self) -> bool:
        """Returns True if content needs to be AI-generated."""
        return self.content is None

    def to_pyinfra_operations(self, artifacts: Dict[str, Any]) -> str:
        """Generate PyInfra file.put operation.

        Args:
            artifacts: Dict with generated content (if any)

        Returns:
            PyInfra operation code as string
        """
        # Get content from artifacts or use provided content
        content = artifacts.get(self.name) or self.content or ""

        # Default path if not provided
        file_path = self.path or f"/tmp/{self.name}"

        # Escape content for Python string
        escaped_content = content.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')

        return f'''
# Create file: {self.name}
files.put(
    name="Create {self.name}",
    src=StringIO("""{escaped_content}"""),
    dest="{file_path}",
    mode="{self.mode}",
)
'''
