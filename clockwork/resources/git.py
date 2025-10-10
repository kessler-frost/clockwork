"""Git repository resource for cloning and managing repositories with optional AI-suggested URLs."""

from typing import Optional, Dict, Any
from .base import Resource


class GitRepoResource(Resource):
    """Git repository resource - clones and manages Git repositories.

    Declaratively define Git repository clones. When no repository URL is specified,
    AI suggests an appropriate repository based on the description using PydanticAI's
    structured output.

    Attributes:
        name: Repository identifier (required)
        description: Repository description - used by AI for URL suggestions (required)
        repo_url: Git repository URL (optional - AI suggests if not provided)
        dest: Destination directory for cloning (required)
        branch: Git branch to checkout (default: "main")
        pull: Update repository if it already exists (default: True)
        present: Whether repository should exist (default: True)

    Examples:
        AI-suggested repository:
        >>> GitRepoResource(
        ...     name="flask-repo",
        ...     description="Python Flask web framework",
        ...     dest="/opt/flask"
        ... )

        Explicit repository URL:
        >>> GitRepoResource(
        ...     name="django-repo",
        ...     description="Django web framework",
        ...     repo_url="https://github.com/django/django.git",
        ...     dest="/opt/django",
        ...     branch="stable/4.2.x"
        ... )
    """

    name: str
    description: str
    repo_url: Optional[str] = None
    dest: str
    branch: Optional[str] = "main"
    pull: bool = True
    present: bool = True

    def needs_artifact_generation(self) -> bool:
        """Returns True if repository URL needs to be AI-suggested.

        When no repo_url is specified, the AI will analyze the description and
        suggest an appropriate Git repository URL to clone.

        Returns:
            bool: True if repo_url is None, False otherwise
        """
        return self.repo_url is None

    def to_pyinfra_operations(self, artifacts: Dict[str, Any]) -> str:
        """Generate PyInfra git.repo operation code.

        Creates a PyInfra operation that clones or updates the Git repository with
        the specified configuration. If the repo_url was AI-generated, it will be
        retrieved from the artifacts dictionary.

        Args:
            artifacts: Dict mapping resource names to generated content.
                      For GitRepoResource, should contain {"name": {"repo_url": "https://..."}}

        Returns:
            str: PyInfra operation code as a string

        Example generated code:
            ```python
            git.repo(
                name="Clone flask-repo",
                src="https://github.com/pallets/flask.git",
                dest="/opt/flask",
                branch="main",
                pull=True,
                present=True,
            )
            ```
        """
        # Get repo_url from artifacts if not provided
        repo_url = self.repo_url
        if repo_url is None:
            artifact_data = artifacts.get(self.name, {})
            repo_url = artifact_data.get("repo_url") if isinstance(artifact_data, dict) else artifact_data

        # Use empty string as fallback (should not happen in practice)
        repo_url = repo_url or ""

        # Use "main" as default branch if None
        branch = self.branch or "main"

        return f'''
# Clone/update Git repository: {self.name}
git.repo(
    name="Clone {self.name}",
    src="{repo_url}",
    dest="{self.dest}",
    branch="{branch}",
    pull={self.pull},
)
'''

    def to_pyinfra_destroy_operations(self, artifacts: Dict[str, Any]) -> str:
        """Generate PyInfra operations code to destroy/remove the repository.

        Creates a PyInfra operation that removes the cloned repository by deleting
        the destination directory.

        Args:
            artifacts: Dict mapping resource names to generated content (unused for destroy)

        Returns:
            str: PyInfra operation code to remove the repository

        Example generated code:
            ```python
            files.directory(
                name="Remove flask-repo",
                path="/opt/flask",
                present=False,
            )
            ```
        """
        return f'''
# Remove Git repository: {self.name}
files.directory(
    name="Remove {self.name}",
    path="{self.dest}",
    present=False,
)
'''

    def to_pyinfra_assert_operations(self, artifacts: Dict[str, Any]) -> str:
        """Generate PyInfra operations code for Git repository assertions.

        Provides default assertions for GitRepoResource:
        - Repository directory exists (if present=True)
        - Directory is a valid Git repository (.git directory exists)

        These can be overridden by specifying custom assertions.

        Args:
            artifacts: Dict mapping resource names to generated content

        Returns:
            str: PyInfra assertion operation code

        Example generated code:
            ```python
            # Default assertions for Git repository: flask-repo
            server.shell(
                name="Assert: Directory /opt/flask exists",
                commands=[
                    "test -d /opt/flask || exit 1"
                ]
            )
            server.shell(
                name="Assert: /opt/flask is a Git repository",
                commands=[
                    "test -d /opt/flask/.git || exit 1"
                ]
            )
            ```
        """
        # If custom assertions are defined, use the base implementation
        if self.assertions:
            return super().to_pyinfra_assert_operations(artifacts)

        operations = []
        operations.append(f"\n# Default assertions for Git repository: {self.name}")

        # Check if repository directory should exist
        if self.present:
            operations.append(f'''
# Assert: Repository directory exists
server.shell(
    name="Assert: Directory {self.dest} exists",
    commands=[
        "test -d {self.dest} || exit 1"
    ],
)
''')

            # Check if directory is a Git repository
            operations.append(f'''
# Assert: Directory is a Git repository
server.shell(
    name="Assert: {self.dest} is a Git repository",
    commands=[
        "test -d {self.dest}/.git || exit 1"
    ],
)
''')

        return "\n".join(operations)
