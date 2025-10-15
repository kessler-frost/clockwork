"""Pulumi dynamic provider for TemplateFile resources."""

import os
from pathlib import Path
from typing import Any, Optional

import pulumi
from jinja2 import Template
from pulumi import Input, Output
from pulumi.dynamic import CheckResult, CreateResult, DiffResult, ResourceProvider, UpdateResult


class TemplateFileInputs:
    """Inputs for TemplateFile dynamic provider."""

    def __init__(
        self,
        path: Input[str],
        template_content: Input[str],
        variables: Input[dict[str, Any]],
        mode: Input[str] = "644",
    ):
        """
        Initialize TemplateFile inputs.

        Args:
            path: Absolute path to the file
            template_content: Jinja2 template content
            variables: Template variables
            mode: File permissions (default: "644")
        """
        self.path = path
        self.template_content = template_content
        self.variables = variables
        self.mode = mode


class TemplateFileProvider(ResourceProvider):
    """Dynamic provider for TemplateFile resources using Jinja2 and pure Python file I/O."""

    def _render_template(self, template_content: str, variables: dict[str, Any]) -> str:
        """
        Render Jinja2 template with variables.

        Args:
            template_content: Jinja2 template string
            variables: Template variables

        Returns:
            Rendered content
        """
        try:
            template = Template(template_content)
            return template.render(**variables)
        except Exception as e:
            raise Exception(f"Failed to render template: {e}")

    def create(self, props: dict[str, Any]) -> CreateResult:
        """
        Create a file from template.

        Args:
            props: Resource properties

        Returns:
            CreateResult with ID and outputs
        """
        path = props["path"]
        template_content = props["template_content"]
        variables = props.get("variables", {})
        mode = props.get("mode", "644")

        try:
            # Render template
            content = self._render_template(template_content, variables)

            # Ensure parent directory exists
            file_path = Path(path)
            file_path.parent.mkdir(parents=True, exist_ok=True)

            # Write file content
            file_path.write_text(content, encoding="utf-8")

            # Set file permissions
            mode_int = int(mode, 8)
            os.chmod(path, mode_int)

            # Return CreateResult with file path as ID
            return CreateResult(
                id_=path,
                outs={
                    "path": path,
                    "template_content": template_content,
                    "variables": variables,
                    "mode": mode,
                    "rendered_content": content,
                    "size": len(content),
                },
            )
        except Exception as e:
            raise Exception(f"Failed to create template file {path}: {e}")

    def update(
        self, id: str, old_props: dict[str, Any], new_props: dict[str, Any]
    ) -> UpdateResult:
        """
        Update a file from template.

        Args:
            id: Resource ID (file path)
            old_props: Old resource properties
            new_props: New resource properties

        Returns:
            UpdateResult with outputs
        """
        path = new_props["path"]
        template_content = new_props["template_content"]
        variables = new_props.get("variables", {})
        mode = new_props.get("mode", "644")

        try:
            # Render template
            content = self._render_template(template_content, variables)

            # Ensure parent directory exists
            file_path = Path(path)
            file_path.parent.mkdir(parents=True, exist_ok=True)

            # Write file content
            file_path.write_text(content, encoding="utf-8")

            # Set file permissions
            mode_int = int(mode, 8)
            os.chmod(path, mode_int)

            # Return UpdateResult with updated outputs
            return UpdateResult(
                outs={
                    "path": path,
                    "template_content": template_content,
                    "variables": variables,
                    "mode": mode,
                    "rendered_content": content,
                    "size": len(content),
                }
            )
        except Exception as e:
            raise Exception(f"Failed to update template file {path}: {e}")

    def delete(self, id: str, props: dict[str, Any]) -> None:
        """
        Delete a file.

        Args:
            id: Resource ID (file path)
            props: Resource properties
        """
        path = props["path"]

        try:
            file_path = Path(path)
            if file_path.exists():
                file_path.unlink()
        except Exception as e:
            raise Exception(f"Failed to delete template file {path}: {e}")

    def diff(
        self, id: str, old_props: dict[str, Any], new_props: dict[str, Any]
    ) -> DiffResult:
        """
        Check if template file needs update.

        Args:
            id: Resource ID (file path)
            old_props: Old resource properties
            new_props: New resource properties

        Returns:
            DiffResult indicating if changes are needed
        """
        # Check if any property changed
        changes = []
        replaces = []

        # Path change requires replacement
        if old_props.get("path") != new_props.get("path"):
            replaces.append("path")

        # Template content or variables changes require update
        if old_props.get("template_content") != new_props.get("template_content"):
            changes.append("template_content")

        if old_props.get("variables") != new_props.get("variables"):
            changes.append("variables")

        if old_props.get("mode") != new_props.get("mode"):
            changes.append("mode")

        has_changes = len(changes) > 0 or len(replaces) > 0

        return DiffResult(
            changes=has_changes,
            replaces=replaces,
            stables=[],
            delete_before_replace=True,
        )


class TemplateFile(pulumi.dynamic.Resource):
    """
    A Pulumi dynamic resource for managing template files.

    This resource creates a file from a Jinja2 template with the specified
    variables and permissions using pure Python file I/O operations.

    Args:
        name: Resource name
        path: Absolute path to the file
        template_content: Jinja2 template content
        variables: Template variables
        mode: File permissions (default: "644")
        opts: Standard Pulumi resource options
    """

    path: Output[str]
    template_content: Output[str]
    variables: Output[dict[str, Any]]
    mode: Output[str]
    rendered_content: Output[str]
    size: Output[int]

    def __init__(
        self,
        name: str,
        path: Input[str],
        template_content: Input[str],
        variables: Input[dict[str, Any]],
        mode: Input[str] = "644",
        opts: Optional[pulumi.ResourceOptions] = None,
    ):
        """
        Initialize TemplateFile resource.

        Args:
            name: Resource name
            path: Absolute path to the file
            template_content: Jinja2 template content
            variables: Template variables
            mode: File permissions (default: "644")
            opts: Standard Pulumi resource options
        """
        self.path = Output.from_input(path)
        self.template_content = Output.from_input(template_content)
        self.variables = Output.from_input(variables)
        self.mode = Output.from_input(mode)

        super().__init__(
            TemplateFileProvider(),
            name,
            {
                "path": path,
                "template_content": template_content,
                "variables": variables,
                "mode": mode,
                "rendered_content": "",  # Will be computed on create
                "size": 0,  # Will be computed on create
            },
            opts,
        )
