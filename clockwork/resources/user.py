"""User resource for creating and managing system users."""

from typing import Optional, Dict, Any
from .base import Resource


class UserResource(Resource):
    """User resource - creates and manages system users.

    Declaratively define system users with optional home directories, shells,
    and group assignments. Supports both regular users and system users.
    On macOS, uses dscl commands for proper user management.

    Attributes:
        name: Username for the system user (required)
        description: Optional human-readable description of the user
        home: Home directory path (optional - defaults to system default)
        shell: User's login shell (default: /bin/bash)
        group: Primary group name (optional - defaults to system default)
        present: Whether user should exist (default: True)
        system: Whether this is a system user vs regular user (default: False)

    Examples:
        Basic user creation:
        >>> UserResource(name="appuser", description="Application service user")

        User with custom home and shell:
        >>> UserResource(
        ...     name="developer",
        ...     description="Developer account",
        ...     home="/home/developer",
        ...     shell="/bin/zsh",
        ...     group="developers"
        ... )

        System user:
        >>> UserResource(
        ...     name="nginx",
        ...     description="Nginx web server user",
        ...     system=True,
        ...     shell="/usr/sbin/nologin"
        ... )
    """

    name: str
    description: Optional[str] = None
    home: Optional[str] = None
    shell: Optional[str] = "/bin/bash"
    group: Optional[str] = None
    present: bool = True
    system: bool = False

    def needs_completion(self) -> bool:
        """Returns False - user resources do not need AI completion.

        User creation requires explicit configuration and doesn't benefit from
        AI completion. All fields should be provided by the user.

        Returns:
            bool: Always False
        """
        return False

    def to_pyinfra_operations(self) -> str:
        """Generate PyInfra operations code for user creation.

        Creates platform-specific commands for user management. On macOS (Darwin),
        uses dscl commands for proper user creation. On Linux, uses standard
        server.user operations.

        Returns:
            str: PyInfra operation code for creating/managing the user

        Example generated code (Linux):
            ```python
            server.user(
                name="Create user appuser",
                user="appuser",
                home="/home/appuser",
                shell="/bin/bash",
                group="users",
                present=True,
                system=False,
            )
            ```

        Example generated code (macOS):
            ```python
            server.shell(
                name="Create user appuser on macOS",
                commands=[
                    "dscl . -create /Users/appuser",
                    "dscl . -create /Users/appuser UserShell /bin/bash",
                    # ... additional dscl commands
                ]
            )
            ```
        """
        if not self.present:
            # If user should not exist, use destroy operation logic
            return self._generate_removal_operations()

        # macOS requires special handling with dscl
        macos_operation = self._generate_macos_user_creation()
        linux_operation = self._generate_linux_user_creation()

        return f'''
# Create user: {self.name}
# Detect platform and use appropriate user creation method
server.shell(
    name="Create user {self.name} (platform-specific)",
    commands=[
        # Detect OS and create user accordingly
        """
if [ "$(uname)" = "Darwin" ]; then
    # macOS user creation with dscl
{self._indent_commands(self._get_macos_commands(), 4)}
else
    # Linux user creation - use adduser/useradd
{self._indent_commands(self._get_linux_commands(), 4)}
fi
        """
    ],
)
'''

    def _generate_linux_user_creation(self) -> str:
        """Generate Linux-specific user creation using server.user.

        Returns:
            str: PyInfra server.user operation code
        """
        # Build parameters
        params = {
            'user': self.name,
            'present': self.present,
            'system': self.system,
        }

        if self.home:
            params['home'] = self.home
        if self.shell:
            params['shell'] = self.shell
        if self.group:
            params['group'] = self.group

        # Format parameters as Python code
        params_str = ",\n    ".join(f'{k}="{v}"' if isinstance(v, str) else f'{k}={v}'
                                     for k, v in params.items())

        return f'''
server.user(
    name="Create user {self.name}",
    {params_str},
)
'''

    def _generate_macos_user_creation(self) -> str:
        """Generate macOS-specific user creation using dscl commands.

        Returns:
            str: PyInfra server.shell operation with dscl commands
        """
        commands = self._get_macos_commands()
        commands_str = ",\n        ".join(f'"{cmd}"' for cmd in commands)

        return f'''
server.shell(
    name="Create user {self.name} on macOS",
    commands=[
        {commands_str}
    ],
)
'''

    def _get_macos_commands(self) -> list:
        """Generate macOS dscl commands for user creation.

        Returns:
            list: List of shell commands for macOS user creation
        """
        commands = []

        # Check if user already exists, skip if so
        commands.append(f'dscl . -read /Users/{self.name} >/dev/null 2>&1 && exit 0')

        # Create user
        commands.append(f'dscl . -create /Users/{self.name}')

        # Set shell
        if self.shell:
            commands.append(f'dscl . -create /Users/{self.name} UserShell {self.shell}')

        # Set home directory
        home_dir = self.home or f'/Users/{self.name}'
        commands.append(f'dscl . -create /Users/{self.name} NFSHomeDirectory {home_dir}')

        # Find next available UID (starting from 501 for regular users, 200 for system users)
        uid_start = '200' if self.system else '501'
        commands.append(
            f'uid=$(dscl . -list /Users UniqueID | awk \'{{print $2}}\' | sort -n | '
            f'awk \'BEGIN{{uid={uid_start}}} {{if($1==uid){{uid++}}}} END{{print uid}}\'); '
            f'dscl . -create /Users/{self.name} UniqueID $uid'
        )

        # Set primary group
        if self.group:
            # Get GID for the group
            commands.append(
                f'gid=$(dscl . -read /Groups/{self.group} PrimaryGroupID 2>/dev/null | '
                f'awk \'{{print $2}}\') && '
                f'dscl . -create /Users/{self.name} PrimaryGroupID $gid || '
                f'dscl . -create /Users/{self.name} PrimaryGroupID 20'
            )
        else:
            # Default to staff group (GID 20)
            commands.append(f'dscl . -create /Users/{self.name} PrimaryGroupID 20')

        # Create home directory if specified
        if self.home:
            commands.append(f'mkdir -p {self.home}')
            commands.append(f'chown {self.name}:staff {self.home}')

        return commands

    def _get_linux_commands(self) -> list:
        """Generate Linux commands for user creation.

        Returns:
            list: List of shell commands for Linux user creation
        """
        commands = []

        # Check if user exists, skip if so
        commands.append(f'id -u {self.name} >/dev/null 2>&1 && exit 0')

        # Build useradd command
        useradd_cmd = ['useradd']

        if self.system:
            useradd_cmd.append('--system')

        if self.home:
            useradd_cmd.extend(['-d', self.home])

        if self.shell:
            useradd_cmd.extend(['-s', self.shell])

        if self.group:
            useradd_cmd.extend(['-g', self.group])

        useradd_cmd.append(self.name)

        commands.append(' '.join(useradd_cmd))

        # Create home directory if specified and doesn't exist
        if self.home:
            commands.append(f'mkdir -p {self.home}')
            commands.append(f'chown {self.name}:{self.group or self.name} {self.home}')

        return commands

    def _indent_commands(self, commands: list, indent: int) -> str:
        """Indent commands for embedded shell scripts.

        Args:
            commands: List of shell commands
            indent: Number of spaces to indent

        Returns:
            str: Indented commands joined with newlines
        """
        indent_str = ' ' * indent
        return '\n'.join(f'{indent_str}{cmd}' for cmd in commands)

    def _generate_removal_operations(self) -> str:
        """Generate operations for user removal.

        Returns:
            str: PyInfra operation code for removing the user
        """
        return f'''
# Remove user: {self.name}
server.shell(
    name="Remove user {self.name} (platform-specific)",
    commands=[
        """
if [ "$(uname)" = "Darwin" ]; then
    # macOS user removal with dscl
    dscl . -delete /Users/{self.name} 2>/dev/null || true
else
    # Linux user removal
    userdel -r {self.name} 2>/dev/null || true
fi
        """
    ],
)
'''

    def to_pyinfra_destroy_operations(self) -> str:
        """Generate PyInfra operations code to destroy/remove the user.

        Creates platform-specific commands for user removal. On macOS, uses dscl
        to delete the user. On Linux, uses userdel with -r to remove home directory.

        Returns:
            str: PyInfra operation code to remove the user

        Example generated code:
            ```python
            server.shell(
                name="Remove user appuser (platform-specific)",
                commands=[
                    # Platform detection and appropriate removal command
                ]
            )
            ```
        """
        return f'''
# Remove user: {self.name}
server.shell(
    name="Remove user {self.name} (platform-specific)",
    commands=[
        """
if [ "$(uname)" = "Darwin" ]; then
    # macOS user removal with dscl
    dscl . -delete /Users/{self.name} 2>/dev/null || true
    # Remove home directory if it exists
    [ -d "{self.home or f'/Users/{self.name}'}" ] && rm -rf "{self.home or f'/Users/{self.name}'}" || true
else
    # Linux user removal with home directory
    userdel -r {self.name} 2>/dev/null || userdel {self.name} 2>/dev/null || true
fi
        """
    ],
)
'''

    def to_pyinfra_assert_operations(self) -> str:
        """Generate PyInfra operations code for user assertions.

        Provides default assertions for UserResource:
        - User exists in the system (via id -u command)
        - Home directory exists (if home is specified)

        These can be overridden by specifying custom assertions.

        Returns:
            str: PyInfra assertion operation code

        Example generated code:
            ```python
            # Default assertions for user: appuser

            # Assert: User exists
            server.shell(
                name="Assert: User appuser exists",
                commands=["id -u appuser || exit 1"]
            )

            # Assert: Home directory exists
            server.shell(
                name="Assert: Home directory /home/appuser exists",
                commands=["test -d /home/appuser || exit 1"]
            )
            ```
        """
        # If custom assertions are defined, use the base implementation
        if self.assertions:
            return super().to_pyinfra_assert_operations()

        # Only assert if user should be present
        if not self.present:
            return f'''
# Default assertions for user: {self.name}

# Assert: User does not exist
server.shell(
    name="Assert: User {self.name} does not exist",
    commands=[
        "! id -u {self.name} >/dev/null 2>&1 || exit 1"
    ],
)
'''

        operations = []
        operations.append(f"\n# Default assertions for user: {self.name}")

        # Assert user exists
        operations.append(f'''
# Assert: User exists
server.shell(
    name="Assert: User {self.name} exists",
    commands=[
        "id -u {self.name} >/dev/null 2>&1 || exit 1"
    ],
)
''')

        # Assert home directory exists if specified
        if self.home:
            operations.append(f'''
# Assert: Home directory exists
server.shell(
    name="Assert: Home directory {self.home} exists",
    commands=[
        "test -d {self.home} || exit 1"
    ],
)
''')

        # Assert shell is correct if specified
        if self.shell:
            operations.append(f'''
# Assert: User has correct shell
server.shell(
    name="Assert: User {self.name} has shell {self.shell}",
    commands=[
        """
if [ "$(uname)" = "Darwin" ]; then
    # macOS: check with dscl
    [ "$(dscl . -read /Users/{self.name} UserShell | awk '{{print $2}}')" = "{self.shell}" ] || exit 1
else
    # Linux: check with getent
    [ "$(getent passwd {self.name} | cut -d: -f7)" = "{self.shell}" ] || exit 1
fi
        """
    ],
)
''')

        return "\n".join(operations)

    def get_connection_context(self) -> Dict[str, Any]:
        """Get connection context for this User resource.

        Returns shareable fields that other resources can use when connected.
        This includes username, home directory, shell, and group information.

        Returns:
            Dict[str, Any]: Connection context with the following keys:
                - name: Username (always present)
                - type: Resource type name (always present)
                - home: Home directory path (if available)
                - shell: User's shell (if available)
                - group: Primary group (if available)
                - system: Whether this is a system user (always present)
        """
        context = {
            "name": self.name,
            "type": self.__class__.__name__,
            "system": self.system,
        }

        # Add home directory if specified
        if self.home:
            context["home"] = self.home

        # Add shell if specified
        if self.shell:
            context["shell"] = self.shell

        # Add group if specified
        if self.group:
            context["group"] = self.group

        return context
