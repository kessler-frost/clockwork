"""Pulumi dynamic provider for File resources."""

import os
import stat
from pathlib import Path
from typing import Any, Optional

import pulumi
from pulumi import Input, Output
from pulumi.dynamic import CheckResult, CreateResult, DiffResult, ResourceProvider, UpdateResult


class FileInputs:
    """Inputs for File dynamic provider."""

    def __init__(
        self,
        path: Input[str],
        content: Input[str],
        mode: Input[str] = "644",
    ):
        """
        Initialize File inputs.

        Args:
            path: Absolute path to the file
            content: File content
            mode: File permissions (default: "644")
        """
        self.path = path
        self.content = content
        self.mode = mode


class FileProvider(ResourceProvider):
    """Dynamic provider for File resources using pure Python file I/O."""

    def create(self, props: dict[str, Any]) -> CreateResult:
        """
        Create a file.

        Args:
            props: Resource properties

        Returns:
            CreateResult with ID and outputs
        """
        path = props["path"]
        content = props["content"]
        mode = props.get("mode", "644")

        try:
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
                    "content": content,
                    "mode": mode,
                    "size": len(content),
                },
            )
        except Exception as e:
            raise Exception(f"Failed to create file {path}: {e}")

    def update(
        self, id: str, old_props: dict[str, Any], new_props: dict[str, Any]
    ) -> UpdateResult:
        """
        Update a file.

        Args:
            id: Resource ID (file path)
            old_props: Old resource properties
            new_props: New resource properties

        Returns:
            UpdateResult with outputs
        """
        path = new_props["path"]
        content = new_props["content"]
        mode = new_props.get("mode", "644")

        try:
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
                    "content": content,
                    "mode": mode,
                    "size": len(content),
                }
            )
        except Exception as e:
            raise Exception(f"Failed to update file {path}: {e}")

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
            raise Exception(f"Failed to delete file {path}: {e}")

    def diff(
        self, id: str, old_props: dict[str, Any], new_props: dict[str, Any]
    ) -> DiffResult:
        """
        Check if file needs update.

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

        # Content or mode changes require update
        if old_props.get("content") != new_props.get("content"):
            changes.append("content")

        if old_props.get("mode") != new_props.get("mode"):
            changes.append("mode")

        has_changes = len(changes) > 0 or len(replaces) > 0

        return DiffResult(
            changes=has_changes,
            replaces=replaces,
            stables=[],
            delete_before_replace=True,
        )


class File(pulumi.dynamic.Resource):
    """
    A Pulumi dynamic resource for managing files.

    This resource creates a file with the specified content and permissions
    using pure Python file I/O operations.

    Args:
        name: Resource name
        path: Absolute path to the file
        content: File content
        mode: File permissions (default: "644")
        opts: Standard Pulumi resource options
    """

    path: Output[str]
    content: Output[str]
    mode: Output[str]
    size: Output[int]

    def __init__(
        self,
        name: str,
        path: Input[str],
        content: Input[str],
        mode: Input[str] = "644",
        opts: Optional[pulumi.ResourceOptions] = None,
    ):
        """
        Initialize File resource.

        Args:
            name: Resource name
            path: Absolute path to the file
            content: File content
            mode: File permissions (default: "644")
            opts: Standard Pulumi resource options
        """
        self.path = Output.from_input(path)
        self.content = Output.from_input(content)
        self.mode = Output.from_input(mode)

        super().__init__(
            FileProvider(),
            name,
            {
                "path": path,
                "content": content,
                "mode": mode,
                "size": 0,  # Will be computed on create
            },
            opts,
        )
