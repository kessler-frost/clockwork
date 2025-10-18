"""Pulumi dynamic provider for Git repository resources.

This module provides a Pulumi dynamic provider for managing Git repositories
using subprocess to execute git commands directly.
"""

import asyncio
import shutil
from pathlib import Path
from typing import Any, Dict, List

import pulumi
from pulumi.dynamic import CreateResult, DiffResult, ResourceProvider, UpdateResult


class GitRepoInputs:
    """Input properties for GitRepo resource.

    Attributes:
        repo_url: Git repository URL
        dest: Destination directory for cloning
        branch: Git branch to checkout
        pull: Update repository if it already exists
        repo_name: Logical repository name for tracking
    """

    def __init__(
        self,
        repo_url: str,
        dest: str,
        branch: str,
        pull: bool,
        repo_name: str,
    ):
        """Initialize GitRepoInputs.

        Args:
            repo_url: Git repository URL
            dest: Destination directory for cloning
            branch: Git branch to checkout
            pull: Update repository if it already exists
            repo_name: Logical repository name for tracking
        """
        self.repo_url = repo_url
        self.dest = dest
        self.branch = branch
        self.pull = pull
        self.repo_name = repo_name


class GitRepoProvider(ResourceProvider):
    """Pulumi dynamic provider for Git repositories.

    This provider manages Git repositories using subprocess to execute
    git commands. It supports create, update, delete, and diff operations.
    """

    async def _run_command(self, cmd: List[str], cwd: str | None = None) -> Dict[str, Any]:
        """Run a git command and return the result.

        Args:
            cmd: Command parts to execute
            cwd: Working directory for command execution

        Returns:
            Dict with 'returncode', 'stdout', 'stderr'

        Raises:
            Exception: If command fails
        """
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )
            stdout_bytes, stderr_bytes = await process.communicate()

            return {
                "returncode": process.returncode,
                "stdout": stdout_bytes.decode().strip(),
                "stderr": stderr_bytes.decode().strip(),
            }
        except Exception as e:
            raise Exception(f"Failed to run command {' '.join(cmd)}: {str(e)}")

    async def _create_async(self, props: Dict[str, Any]) -> CreateResult:
        """Async implementation of create.

        Args:
            props: Repository properties

        Returns:
            CreateResult with repository path as ID

        Raises:
            Exception: If creation fails
        """
        repo_url = props["repo_url"]
        dest = props["dest"]
        branch = props["branch"]
        pull = props.get("pull", True)

        dest_path = Path(dest)
        git_dir = dest_path / ".git"

        # Check if repository already exists
        if git_dir.exists():
            if pull:
                # Pull latest changes
                result = await self._run_command(
                    ["git", "checkout", branch],
                    cwd=dest
                )
                if result["returncode"] != 0:
                    raise Exception(f"Failed to checkout branch {branch}: {result['stderr']}")

                result = await self._run_command(
                    ["git", "pull", "origin", branch],
                    cwd=dest
                )
                if result["returncode"] != 0:
                    raise Exception(f"Failed to pull latest changes: {result['stderr']}")
            # Repository exists, return existing path
            return CreateResult(id_=dest, outs=props)

        # Clone repository
        result = await self._run_command(
            ["git", "clone", "--branch", branch, repo_url, dest]
        )

        if result["returncode"] != 0:
            raise Exception(f"Failed to clone repository: {result['stderr']}")

        return CreateResult(id_=dest, outs=props)

    def create(self, props: Dict[str, Any]) -> CreateResult:
        """Create a new repository clone.

        Args:
            props: Repository properties

        Returns:
            CreateResult with repository path as ID

        Raises:
            Exception: If creation fails
        """
        return asyncio.run(self._create_async(props))

    async def _update_async(
        self,
        id: str,
        old_props: Dict[str, Any],
        new_props: Dict[str, Any]
    ) -> UpdateResult:
        """Async implementation of update.

        Args:
            id: Repository path
            old_props: Old properties
            new_props: New properties

        Returns:
            UpdateResult with new properties
        """
        dest = new_props["dest"]
        branch = new_props["branch"]
        pull = new_props.get("pull", True)

        if not pull:
            # No updates needed
            return UpdateResult(outs=new_props)

        dest_path = Path(dest)
        git_dir = dest_path / ".git"

        if not git_dir.exists():
            # Repository doesn't exist, nothing to update
            return UpdateResult(outs=new_props)

        # Pull latest changes
        result = await self._run_command(
            ["git", "checkout", branch],
            cwd=dest
        )
        if result["returncode"] != 0:
            raise Exception(f"Failed to checkout branch {branch}: {result['stderr']}")

        result = await self._run_command(
            ["git", "pull", "origin", branch],
            cwd=dest
        )
        if result["returncode"] != 0:
            raise Exception(f"Failed to pull latest changes: {result['stderr']}")

        return UpdateResult(outs=new_props)

    def update(
        self,
        id: str,
        old_props: Dict[str, Any],
        new_props: Dict[str, Any]
    ) -> UpdateResult:
        """Update a repository by pulling latest changes.

        Args:
            id: Repository path
            old_props: Old properties
            new_props: New properties

        Returns:
            UpdateResult with new properties
        """
        return asyncio.run(self._update_async(id, old_props, new_props))

    async def _delete_async(self, id: str, props: Dict[str, Any]) -> None:
        """Async implementation of delete.

        Args:
            id: Repository path
            props: Repository properties
        """
        dest = props["dest"]
        dest_path = Path(dest)

        if dest_path.exists():
            shutil.rmtree(dest_path)

    def delete(self, id: str, props: Dict[str, Any]) -> None:
        """Delete a repository.

        Args:
            id: Repository path
            props: Repository properties
        """
        asyncio.run(self._delete_async(id, props))

    def diff(
        self,
        id: str,
        old_props: Dict[str, Any],
        new_props: Dict[str, Any]
    ) -> DiffResult:
        """Check what changed between old and new properties.

        Args:
            id: Repository path
            old_props: Old properties
            new_props: New properties

        Returns:
            DiffResult indicating if changes require replacement
        """
        changes = []
        replaces = []

        # Fields that require replacement (re-clone)
        replacement_fields = ["repo_url", "branch", "dest"]

        for field in replacement_fields:
            old_val = old_props.get(field)
            new_val = new_props.get(field)
            if old_val != new_val:
                changes.append(field)
                replaces.append(field)

        # Pull flag change doesn't require replacement
        if old_props.get("pull") != new_props.get("pull"):
            changes.append("pull")

        return DiffResult(
            changes=len(changes) > 0,
            replaces=replaces,
            stables=[],
            delete_before_replace=True,
        )


class GitRepo(pulumi.dynamic.Resource):
    """Pulumi resource for managing Git repositories.

    This is a dynamic resource that wraps the GitRepoProvider to manage
    Git repositories using subprocess git commands.

    Attributes:
        repo_url: Git repository URL
        dest: Destination directory
        branch: Git branch
        pull: Whether to pull updates
        repo_name: Repository name
    """

    repo_url: pulumi.Output[str]
    dest: pulumi.Output[str]
    branch: pulumi.Output[str]
    pull: pulumi.Output[bool]
    repo_name: pulumi.Output[str]

    def __init__(
        self,
        resource_name: str,
        inputs: GitRepoInputs,
        opts: pulumi.ResourceOptions | None = None,
    ):
        """Initialize GitRepo resource.

        Args:
            resource_name: Pulumi resource name
            inputs: Repository input properties
            opts: Pulumi resource options
        """
        # Convert inputs to dict for dynamic provider
        props = {
            "repo_url": inputs.repo_url,
            "dest": inputs.dest,
            "branch": inputs.branch,
            "pull": inputs.pull,
            "repo_name": inputs.repo_name,
        }

        super().__init__(
            GitRepoProvider(),
            resource_name,
            props,
            opts,
        )
