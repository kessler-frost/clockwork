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
    template_content: Optional[str] = None  # Jinja2 template - AI generates if not provided
    variables: Optional[Dict[str, Any]] = None  # template variables - AI generates if not provided
    name: Optional[str] = None  # filename - AI generates if not provided
    directory: Optional[str] = None  # directory - AI picks best location (default: ".")
    mode: Optional[str] = None  # file permissions - AI picks (default: "644")
    path: Optional[str] = None  # full path (overrides directory + name if provided)
    user: Optional[str] = None  # file owner (optional)
    group: Optional[str] = None  # file group (optional)

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

    def to_pyinfra_operations(self) -> str:
        """Generate PyInfra files.template operation.

        Returns:
            PyInfra operation code as string
        """
        # Use template_content (should be set after AI completion)
        template_content = self.template_content or ""

        # Use variables (should be set after AI completion)
        variables = self.variables or {}

        # Ensure mode is set (should be set after AI completion)
        mode = self.mode or "644"

        # Resolve file path and directory
        file_path, directory = self._resolve_file_path()

        # Escape template content for Python triple-quoted string
        escaped_template = template_content.replace('\\', '\\\\').replace('"""', r'\"""')

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

        # Build variable assignments
        var_assignments = ""
        var_kwargs = ""
        if variables:
            for var_name, var_value in variables.items():
                # Escape string values
                if isinstance(var_value, str):
                    escaped_value = var_value.replace('\\', '\\\\').replace('"', '\\"')
                    var_assignments += f'{var_name} = "{escaped_value}"\n'
                else:
                    var_assignments += f'{var_name} = {repr(var_value)}\n'
                var_kwargs += f"    {var_name}={var_name},\n"

        # Build user/group parameters
        ownership_params = ""
        if self.user:
            ownership_params += f'    user="{self.user}",\n'
        if self.group:
            ownership_params += f'    group="{self.group}",\n'

        return f'''
{dir_operation}# Create template file: {self.name}
with open("_temp_{self.name}.j2", "w") as f:
    f.write("""{escaped_template}""")

{var_assignments}
files.template(
    name="Create {self.name} from template",
    src="_temp_{self.name}.j2",
    dest="{file_path}",
    mode="{mode}",
{ownership_params}{var_kwargs})
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

        Provides default assertions for TemplateFileResource:
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

        # Default assertions for TemplateFileResource
        return f'''
# Default assertions for template file: {self.name}

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
        "[ \\"$(stat -c '%a' {file_path} 2>/dev/null || stat -f '%A' {file_path})\\" = \\"{mode}\\" ] || exit 1"
    ],
)
'''
