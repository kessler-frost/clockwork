"""Template file resource for creating files from Jinja2 templates."""

from typing import Optional, Dict, Any
from pydantic import model_validator
from .base import Resource


class TemplateFileResource(Resource):
    """Template file resource - creates a file from a Jinja2 template with variables.

    Minimal usage (AI completes everything):
        TemplateFileResource(
            description="Nginx config for serving static files on port 8080",
            template_content="server { listen {{ port }}; }"
        )

    Advanced usage (with explicit variables):
        TemplateFileResource(
            description="Nginx config for serving static files",
            template_content="server { listen {{ port }}; root {{ root_dir }}; }",
            variables={"port": 8080, "root_dir": "/var/www/html"},
            name="nginx.conf",
            directory="/etc/nginx"
        )
    """

    description: str  # what the file should contain (required)
    template_content: str | None = None  # Jinja2 template - AI generates if not provided
    variables: Dict[str, Any] | None = None  # template variables - AI generates if not provided
    name: str | None = None  # filename - AI generates if not provided
    directory: str | None = None  # directory - AI picks best location (default: ".")
    mode: str | None = None  # file permissions - AI picks (default: "644")
    path: str | None = None  # full path (overrides directory + name if provided)
    user: str | None = None  # file owner (optional)
    group: str | None = None  # file group (optional)

    @model_validator(mode='after')
    def validate_description(self):
        """Description is always required."""
        if not self.description:
            raise ValueError("TemplateFileResource requires 'description'")
        return self

    def needs_completion(self) -> bool:
        """Returns True if any field needs AI completion."""
        # If user provides both template and variables, only check for name/mode/directory
        if self.template_content is not None and self.variables is not None:
            return self.name is None or self.directory is None or self.mode is None

        # Otherwise, need completion for template_content and/or variables
        return (
            self.template_content is None or
            self.variables is None or
            self.name is None or
            self.directory is None or
            self.mode is None
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
        cwd = Path.cwd()

        # Ensure we have a name (should be set after AI completion)
        if not self.name:
            raise ValueError("TemplateFileResource.name must be set before resolving path")

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

    def to_pulumi(self):
        """Create Pulumi TemplateFile resource using custom dynamic provider.

        Returns:
            Pulumi TemplateFile resource
        """
        from clockwork.pulumi_providers import TemplateFile

        # Resolve file path and directory
        file_path, directory = self._resolve_file_path()

        # Use template_content (should be set after AI completion)
        template_content = self.template_content or ""

        # Use variables (should be set after AI completion)
        variables = self.variables or {}

        # Ensure mode is set (should be set after AI completion)
        mode = self.mode or "644"

        # Create TemplateFile resource using dynamic provider
        return TemplateFile(
            self.name,
            path=file_path,
            template_content=template_content,
            variables=variables,
            mode=mode,
        )

    def get_connection_context(self) -> Dict[str, Any]:
        """Get connection context for this TemplateFile resource.

        Returns shareable fields that other resources can use when connected.
        This includes file name, path, directory, and template variables for
        resources that need to reference or interact with this template file.

        Returns:
            Dict[str, Any]: Connection context with the following keys:
                - name: File name (always present)
                - type: Resource type name (always present)
                - path: Full file path (if available after resolution)
                - directory: Directory path (if specified)
                - variables: Template variables (if specified)
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

        # Add variables if specified
        if self.variables:
            context["variables"] = self.variables

        return context
