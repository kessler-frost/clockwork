"""File resource for creating files with optional AI-generated content."""

from typing import Any

from pydantic import Field, model_validator

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

    description: str
    name: str | None = Field(
        None,
        description="Filename with extension",
        examples=["config.yaml", "README.md", "script.sh"],
    )
    content: str | None = Field(
        None,
        description="File content - can be markdown, code, config, or any text",
    )
    directory: str | None = Field(
        None,
        description="Directory path where file will be created",
        examples=[".", "scratch", "config"],
    )
    mode: str | None = Field(
        None,
        description="Unix file permissions in octal",
        examples=["644", "755", "600"],
    )
    path: str | None = Field(
        None,
        description="Full file path - overrides directory + name if provided",
    )

    @model_validator(mode="after")
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
            self.content is None
            or self.name is None
            or self.directory is None
            or self.mode is None
        )

    def _resolve_file_path(self) -> tuple[str, str | None]:
        """Resolve file path and directory from resource configuration.

        Handles three cases:
        1. self.path is provided → use it (absolute or resolve relative)
        2. self.directory is provided → combine with self.name
        3. Default → current directory (./)

        Returns:
            tuple[str, str | None]: (file_path, directory) where:
                - file_path: Absolute path to the file
                - directory: Absolute path to directory (if specified), None otherwise
        """
        from pathlib import Path

        # Ensure we have a name (should be set after AI completion)
        if not self.name:
            raise ValueError(
                "FileResource.name must be set before resolving path"
            )

        cwd = Path.cwd()

        # Case 1: Explicit path provided (highest priority)
        if self.path:
            file_path = Path(self.path)
            if not file_path.is_absolute():
                file_path = cwd / file_path
            return (str(file_path), None)

        # Case 2: Directory provided (combine with name)
        if self.directory:
            directory = Path(self.directory)
            if not directory.is_absolute():
                directory = cwd / directory
            return (str(directory / self.name), str(directory))

        # Case 3: Default to current directory
        return (str(cwd / self.name), None)

    def to_pulumi(self):
        """Create Pulumi File resource using custom dynamic provider.

        Returns:
            Pulumi File resource
        """

        from clockwork.pulumi_providers import File

        # Resolve file path and directory
        file_path, _directory = self._resolve_file_path()

        # Use content directly (should be set after AI completion)
        content = self.content or ""

        # Ensure mode is set (should be set after AI completion)
        mode = self.mode or "644"

        # Build resource options for dependencies
        dep_opts = self._build_dependency_options()

        # Check if we have temporary compile options (from _compile_with_opts)
        # This allows this resource to be a child in a composite
        if hasattr(self, "_temp_compile_opts"):
            # Merge with dependency options
            opts = self._merge_resource_options(
                self._temp_compile_opts, dep_opts
            )
        else:
            opts = dep_opts

        # Create File resource using dynamic provider
        file_resource = File(
            self.name, path=file_path, content=content, mode=mode, opts=opts
        )

        # Store for dependency tracking
        self._pulumi_resource = file_resource

        return file_resource

    def get_connection_context(self) -> dict[str, Any]:
        """Get connection context for this File resource.

        Returns shareable fields that other resources can use when connected.
        This includes file name, path, and directory information for resources
        that need to reference or interact with this file.

        Returns:
            Dict[str, Any]: Connection context with the following keys:
                - name: File name (always present)
                - type: Resource type name (always present)
                - path: Full file path (if available after resolution)
                - directory: Directory path (if specified)
        """
        context = {
            "name": self.name,
            "type": self.__class__.__name__,
        }

        # Add path if it can be resolved
        if self.path:
            context["path"] = self.path
        elif self.name and self.directory:
            # Can construct a relative path if both are available
            from pathlib import Path

            context["path"] = str(Path(self.directory) / self.name)

        # Add directory if specified
        if self.directory:
            context["directory"] = self.directory

        return context
