"""Git repository resource for cloning and managing repositories with optional AI-suggested URLs."""

from typing import Optional, Dict, Any
import pulumi
import pulumi_command as command
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
    name: str | None = None
    repo_url: str | None = None
    dest: str | None = None
    branch: str | None = None
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
            self.name is None or
            self.repo_url is None or
            self.dest is None or
            self.branch is None
        )

    def to_pulumi(self) -> pulumi.Resource:
        """Convert to Pulumi Command resource for git operations.

        Uses pulumi-command to execute git clone/pull operations locally.
        All required fields should be populated by AI completion before this is called.

        Returns:
            pulumi.Resource: Pulumi Command resource

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
        if self.name is None or self.repo_url is None or self.dest is None or self.branch is None:
            raise ValueError(f"Resource not completed: name={self.name}, repo_url={self.repo_url}, dest={self.dest}, branch={self.branch}")

        # Build resource options for dependencies
        opts = None
        if self.connections:
            # Get Pulumi resources from connected resources for dependency tracking
            depends_on = []
            for conn_resource in getattr(self, '_connection_resources', []):
                if hasattr(conn_resource, '_pulumi_resource') and conn_resource._pulumi_resource is not None:
                    depends_on.append(conn_resource._pulumi_resource)
            if depends_on:
                opts = pulumi.ResourceOptions(depends_on=depends_on)

        # Build git clone/pull command
        # Check if repo exists, if yes and pull=True then pull, else clone
        if self.pull:
            # If directory exists and is a git repo, pull; otherwise clone
            git_command = f"""
if [ -d "{self.dest}/.git" ]; then
    echo "Repository exists, pulling latest changes..."
    cd "{self.dest}" && git checkout {self.branch} && git pull origin {self.branch}
else
    echo "Cloning repository..."
    git clone --branch {self.branch} {self.repo_url} {self.dest}
fi
"""
        else:
            # Just clone if doesn't exist
            git_command = f"""
if [ ! -d "{self.dest}/.git" ]; then
    echo "Cloning repository..."
    git clone --branch {self.branch} {self.repo_url} {self.dest}
else
    echo "Repository already exists at {self.dest}"
fi
"""

        # Create Pulumi Command resource to execute git operations
        git_resource = command.local.Command(
            self.name,
            create=git_command.strip(),
            update=git_command.strip() if self.pull else None,
            opts=opts
        )

        # Store for dependency tracking
        self._pulumi_resource = git_resource

        return git_resource

    def get_connection_context(self) -> Dict[str, Any]:
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
