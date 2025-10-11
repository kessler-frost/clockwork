"""Git repository resource for cloning and managing repositories with optional AI-suggested URLs."""

from typing import Optional, Dict, Any
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
    name: Optional[str] = None
    repo_url: Optional[str] = None
    dest: Optional[str] = None
    branch: Optional[str] = None
    pull: bool = True
    present: bool = True

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

    def to_pyinfra_operations(self) -> str:
        """Generate PyInfra git.repo operation code.

        Creates a PyInfra operation that clones or updates the Git repository with
        the specified configuration. All fields should be populated by AI completion
        before this is called.

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
            )
            ```
        """
        # All fields should be populated by AI completion
        if self.name is None or self.repo_url is None or self.dest is None or self.branch is None:
            raise ValueError(f"Resource fields not completed. name={self.name}, repo_url={self.repo_url}, dest={self.dest}, branch={self.branch}")

        return f'''
# Clone/update Git repository: {self.name}
git.repo(
    name="Clone {self.name}",
    src="{self.repo_url}",
    dest="{self.dest}",
    branch="{self.branch}",
    pull={self.pull},
)
'''

    def to_pyinfra_destroy_operations(self) -> str:
        """Generate PyInfra operations code to destroy/remove the repository.

        Creates a PyInfra operation that removes the cloned repository by deleting
        the destination directory.

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
        # Name and dest should be populated by AI completion
        if self.name is None or self.dest is None:
            raise ValueError(f"Resource fields not completed. name={self.name}, dest={self.dest}")

        return f'''
# Remove Git repository: {self.name}
files.directory(
    name="Remove {self.name}",
    path="{self.dest}",
    present=False,
)
'''

    def to_pyinfra_assert_operations(self) -> str:
        """Generate PyInfra operations code for Git repository assertions.

        Provides default assertions for GitRepoResource:
        - Repository directory exists (if present=True)
        - Directory is a valid Git repository (.git directory exists)

        These can be overridden by specifying custom assertions.

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
        # Name and dest should be populated by AI completion
        if self.name is None or self.dest is None:
            raise ValueError(f"Resource fields not completed. name={self.name}, dest={self.dest}")

        # If custom assertions are defined, use the base implementation
        if self.assertions:
            return super().to_pyinfra_assert_operations()

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
