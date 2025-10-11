"""Brew package resource for managing Homebrew packages and casks."""

from typing import Optional, Dict, Any, List
from .base import Resource


class BrewPackageResource(Resource):
    """Brew package resource - manages Homebrew packages and casks with AI completion.

    Minimal usage (AI completes everything):
        BrewPackageResource(description="essential development tools like jq and htop")
        # AI generates: name="dev-tools", packages=["jq", "htop", "wget"], cask=False

    Advanced usage (override specific fields):
        BrewPackageResource(
            description="code editors",
            cask=True  # Force GUI apps
        )
        # AI generates: name="editors", packages=["visual-studio-code", "sublime-text"]

    Attributes:
        description: Package purpose - used by AI for completion (required)
        name: Resource identifier (optional - AI generates if not provided)
        packages: List of packages/casks to install (optional - AI suggests if not provided)
        cask: Use brew casks for GUI applications (optional - AI determines if not provided)
        present: Whether packages should be installed (default: True)
        update: Run brew update before installing (default: False)
    """

    description: str
    name: Optional[str] = None
    packages: Optional[List[str]] = None
    cask: Optional[bool] = None
    present: bool = True
    update: bool = False

    def needs_completion(self) -> bool:
        """Returns True if any field needs AI completion.

        When any of name, packages, or cask are None, the AI will analyze the
        description and suggest appropriate values.

        Returns:
            bool: True if any field needs completion, False otherwise
        """
        return (
            self.name is None or
            self.packages is None or
            self.cask is None
        )

    def to_pyinfra_operations(self) -> str:
        """Generate PyInfra brew.packages or brew.casks operation code.

        Creates a PyInfra operation that installs the specified Homebrew packages
        or casks. All fields should be populated by AI completion before this is called.

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
        # All fields should be populated by AI completion
        if self.name is None or self.packages is None or self.cask is None:
            raise ValueError(f"Resource fields not completed. name={self.name}, packages={self.packages}, cask={self.cask}")

        # Format packages as Python list
        packages_str = repr(self.packages)

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

    def to_pyinfra_destroy_operations(self) -> str:
        """Generate PyInfra operations code to uninstall the packages/casks.

        Creates a PyInfra operation that removes the Homebrew packages or casks
        by setting present=False.

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
        # All fields should be populated by AI completion
        if self.name is None or self.packages is None or self.cask is None:
            raise ValueError(f"Resource fields not completed. name={self.name}, packages={self.packages}, cask={self.cask}")

        # Format packages as Python list
        packages_str = repr(self.packages)

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

    def to_pyinfra_assert_operations(self) -> str:
        """Generate PyInfra operations code for brew package assertions.

        Provides default assertions for BrewPackageResource:
        - Each package/cask is installed

        These can be overridden by specifying custom assertions.

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
            return super().to_pyinfra_assert_operations()

        # All fields should be populated by AI completion
        if self.name is None or self.packages is None or self.cask is None:
            raise ValueError(f"Resource fields not completed. name={self.name}, packages={self.packages}, cask={self.cask}")

        if not self.packages:
            return ""

        # Determine package type for assertion message
        package_type = "cask" if self.cask else "package"
        list_command = "brew list --cask" if self.cask else "brew list"

        operations = []
        operations.append(f"\n# Default assertions for brew {package_type}s: {self.name}")

        for package in self.packages:
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
