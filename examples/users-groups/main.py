"""
User Management Example - Create and manage system users.

This example demonstrates:
- UserResource for creating users
- Platform-specific user management (macOS/Linux)
- Custom home directories and shells
- System vs regular users

IMPORTANT: User creation requires administrative privileges.
On macOS:
  - Run with sudo: sudo uv run clockwork apply
  - Or ensure your user has necessary permissions via dscl

Note: On macOS, user creation is more complex than Linux.
This example uses dscl (Directory Service Command Line) for proper
macOS user management. The operations are idempotent and safe to re-run.
"""

from clockwork.resources import UserResource

# Application service user with custom home and shell
app_user = UserResource(
    name="clockwork-app",
    description="Application service user for running Clockwork services",
    home="/Users/clockwork-app",
    shell="/bin/bash",
    group="staff",
    present=True,
)

# System user with nologin shell (common for service accounts)
service_user = UserResource(
    name="clockwork-service",
    description="System service user with restricted access",
    home="/var/lib/clockwork",
    shell="/usr/bin/false",  # No interactive login
    system=True,
    present=True,
)
