"""Brew package resource for managing Homebrew packages and casks."""

from typing import Optional, Dict, Any, List
from .base import Resource


class BrewPackageResource(Resource):
    """Brew package resource - manages Homebrew packages and casks with AI suggestions.

    Declaratively define Homebrew packages and casks. When no packages are specified,
    AI suggests appropriate packages based on the description.

    Attributes:
        name: Resource identifier (required)
        description: Package purpose - used by AI for package suggestions (required)
        packages: List of packages/casks to install (optional - AI suggests if not provided)
        present: Whether packages should be installed (default: True)
        update: Run brew update before installing (default: False)
        cask: Use brew casks for GUI applications (default: False)

    Examples:
        AI-suggested packages:
        >>> BrewPackageResource(
        ...     name="dev-tools",
        ...     description="Essential development tools like jq, htop, and wget"
        ... )

        Explicit packages:
        >>> BrewPackageResource(
        ...     name="cli-tools",
        ...     description="CLI utilities",
        ...     packages=["jq", "htop", "wget"],
        ...     update=True
        ... )

        GUI applications via cask:
        >>> BrewPackageResource(
        ...     name="editors",
        ...     description="Code editors",
        ...     packages=["visual-studio-code", "sublime-text"],
        ...     cask=True
        ... )
    """

    name: str
    description: str
    packages: Optional[List[str]] = None
    present: bool = True
    update: bool = False
    cask: bool = False

    def needs_artifact_generation(self) -> bool:
        """Returns True if packages need to be AI-suggested.

        When no packages are specified, the AI will analyze the description and
        suggest appropriate Homebrew packages or casks to install.

        Returns:
            bool: True if packages is None, False otherwise
        """
        return self.packages is None

    def to_pyinfra_operations(self, artifacts: Dict[str, Any]) -> str:
        """Generate PyInfra brew.packages or brew.casks operation code.

        Creates a PyInfra operation that installs the specified Homebrew packages
        or casks. If the packages were AI-generated, they will be retrieved from
        the artifacts dictionary.

        Args:
            artifacts: Dict mapping resource names to generated content.
                      For BrewPackageResource, should contain {"name": ["pkg1", "pkg2"]}
                      or {"name": {"packages": ["pkg1", "pkg2"]}}

        Returns:
            str: PyInfra operation code as a string

        Example generated code:
            ```python
            brew.packages(
                name="Install dev-tools",
                packages=["jq", "htop", "wget"],
                present=True,
                update=False,
            )
            ```
        """
        # Get packages from artifacts if not provided
        packages = self.packages
        if packages is None:
            artifact_data = artifacts.get(self.name, [])
            if isinstance(artifact_data, dict):
                packages = artifact_data.get("packages", [])
            elif isinstance(artifact_data, list):
                packages = artifact_data
            else:
                packages = []

        # Use empty list as fallback
        packages = packages or []

        # Format packages as Python list
        packages_str = repr(packages)

        # Determine operation type
        operation = "brew.casks" if self.cask else "brew.packages"
        package_param = "casks" if self.cask else "packages"

        return f'''
# Install Homebrew {package_param}: {self.name}
{operation}(
    name="Install {self.name}",
    {package_param}={packages_str},
    present={self.present},
    update={self.update},
)
'''

    def to_pyinfra_destroy_operations(self, artifacts: Dict[str, Any]) -> str:
        """Generate PyInfra operations code to uninstall the packages/casks.

        Creates a PyInfra operation that removes the Homebrew packages or casks
        by setting present=False.

        Args:
            artifacts: Dict mapping resource names to generated content

        Returns:
            str: PyInfra operation code to remove the packages/casks

        Example generated code:
            ```python
            brew.packages(
                name="Uninstall dev-tools",
                packages=["jq", "htop", "wget"],
                present=False,
            )
            ```
        """
        # Get packages from artifacts if not provided
        packages = self.packages
        if packages is None:
            artifact_data = artifacts.get(self.name, [])
            if isinstance(artifact_data, dict):
                packages = artifact_data.get("packages", [])
            elif isinstance(artifact_data, list):
                packages = artifact_data
            else:
                packages = []

        # Use empty list as fallback
        packages = packages or []

        # Format packages as Python list
        packages_str = repr(packages)

        # Determine operation type
        operation = "brew.casks" if self.cask else "brew.packages"
        package_param = "casks" if self.cask else "packages"

        return f'''
# Uninstall Homebrew {package_param}: {self.name}
{operation}(
    name="Uninstall {self.name}",
    {package_param}={packages_str},
    present=False,
)
'''

    def to_pyinfra_assert_operations(self, artifacts: Dict[str, Any]) -> str:
        """Generate PyInfra operations code for brew package assertions.

        Provides default assertions for BrewPackageResource:
        - Each package/cask is installed

        These can be overridden by specifying custom assertions.

        Args:
            artifacts: Dict mapping resource names to generated content

        Returns:
            str: PyInfra assertion operation code

        Example generated code:
            ```python
            # Default assertions for brew packages: dev-tools

            # Assert: Package jq is installed
            server.shell(
                name="Assert: Package jq is installed",
                commands=[
                    "brew list jq || exit 1"
                ]
            )
            ```
        """
        # If custom assertions are defined, use the base implementation
        if self.assertions:
            return super().to_pyinfra_assert_operations(artifacts)

        # Get packages from artifacts if not provided
        packages = self.packages
        if packages is None:
            artifact_data = artifacts.get(self.name, [])
            if isinstance(artifact_data, dict):
                packages = artifact_data.get("packages", [])
            elif isinstance(artifact_data, list):
                packages = artifact_data
            else:
                packages = []

        # Use empty list as fallback
        packages = packages or []

        if not packages:
            return ""

        # Determine package type for assertion message
        package_type = "cask" if self.cask else "package"
        list_command = "brew list --cask" if self.cask else "brew list"

        operations = []
        operations.append(f"\n# Default assertions for brew {package_type}s: {self.name}")

        for package in packages:
            operations.append(f'''
# Assert: {package_type.capitalize()} {package} is installed
server.shell(
    name="Assert: {package_type.capitalize()} {package} is installed",
    commands=[
        "{list_command} {package} || exit 1"
    ],
)
''')

        return "\n".join(operations)
