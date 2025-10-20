"""Git repository resource for cloning and managing repositories with optional AI-suggested URLs."""

from typing import Any

import pulumi
from pydantic import Field

from clockwork.pulumi_providers.git_repo import GitRepo, GitRepoInputs

from .base import Resource


class GitRepoResource(Resource):
    """Git repository resource - clones and manages Git repositories with AI completion.

    Minimal usage (AI completes everything):
        GitRepoResource(description="FastAPI Python web framework repository")
        # AI generates: name="fastapi", repo_url="https://github.com/tiangolo/fastapi.git",
        #               dest="./fastapi", branch="master"

    Advanced usage (override specific fields):
        GitRepoResource(
            description="Django web framework",
            dest="/opt/django"  # Override destination
        )
        # AI generates: name="django", repo_url="https://github.com/django/django.git",
        #               branch="main"

    Attributes:
        description: Repository description - used by AI for completion (required)
        name: Repository identifier (optional - AI generates if not provided)
        repo_url: Git repository URL (optional - AI suggests if not provided)
        dest: Destination directory for cloning (optional - AI picks if not provided)
        branch: Git branch to checkout (optional - AI picks main/master if not provided)
        pull: Update repository if it already exists (default: True)
        present: Whether repository should exist (default: True)
    """

    description: str
    name: str | None = Field(
        None,
        description="Repository identifier/short name",
        examples=["fastapi", "django", "flask"],
    )
    repo_url: str | None = Field(
        None,
        description="Git repository URL - prefer official GitHub repos",
        examples=[
            "https://github.com/tiangolo/fastapi.git",
            "https://github.com/django/django.git",
        ],
    )
    dest: str | None = Field(
        None,
        description="Destination directory for cloned repository",
        examples=["./repos/fastapi", "/opt/django", "scratch/repos/flask"],
    )
    branch: str | None = Field(
        None,
        description="Git branch to checkout - usually main or master",
        examples=["main", "master", "develop"],
    )
    pull: bool = True
    present: bool = True

    # Store Pulumi resource for dependency tracking
    _pulumi_resource: pulumi.Resource | None = None

    def needs_completion(self) -> bool:
        """Returns True if any field needs AI completion.

        When any of name, repo_url, dest, or branch are None, the AI will analyze
        the description and suggest appropriate values.

        Returns:
            bool: True if any field needs completion, False otherwise
        """
        return (
            self.name is None
            or self.repo_url is None
            or self.dest is None
            or self.branch is None
        )

    def to_pulumi(self) -> pulumi.Resource:
        """Convert to Pulumi GitRepo resource for git operations.

        Uses custom dynamic provider to execute git clone/pull operations.
        All required fields should be populated by AI completion before this is called.

        Returns:
            pulumi.Resource: Pulumi GitRepo resource

        Raises:
            ValueError: If required fields are not completed

        Example:
            >>> repo = GitRepoResource(
            ...     name="flask-repo",
            ...     repo_url="https://github.com/pallets/flask.git",
            ...     dest="/opt/flask",
            ...     branch="main"
            ... )
            >>> pulumi_resource = repo.to_pulumi()
        """
        # Validate required fields
        if (
            self.name is None
            or self.repo_url is None
            or self.dest is None
            or self.branch is None
        ):
            raise ValueError(
                f"Resource not completed: name={self.name}, repo_url={self.repo_url}, dest={self.dest}, branch={self.branch}"
            )

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

        # Create GitRepoInputs
        inputs = GitRepoInputs(
            repo_url=self.repo_url,
            dest=self.dest,
            branch=self.branch,
            pull=self.pull,
            repo_name=self.name,
        )

        # Create Pulumi GitRepo resource
        git_resource = GitRepo(
            resource_name=self.name,
            inputs=inputs,
            opts=opts,
        )

        # Store for dependency tracking
        self._pulumi_resource = git_resource

        return git_resource

    def get_connection_context(self) -> dict[str, Any]:
        """Get connection context for this Git repository resource.

        Returns shareable fields that other resources can use when connected.
        This includes repository name, URL, branch, and destination path.

        Returns:
            Dict[str, Any]: Connection context with the following keys:
                - name: Repository identifier (always present)
                - type: Resource type name (always present)
                - repo_url: Git repository URL (if available)
                - branch: Git branch name (if available)
                - dest: Destination path for cloned repository (if available)
        """
        context = {
            "name": self.name,
            "type": self.__class__.__name__,
        }

        # Add repo_url if specified
        if self.repo_url:
            context["repo_url"] = self.repo_url

        # Add branch if specified
        if self.branch:
            context["branch"] = self.branch

        # Add destination path if specified
        if self.dest:
            context["dest"] = self.dest

        return context
