"""
User Management Example - Create and manage system users.

This example demonstrates UserResource for platform-specific user management.

NOTE: UserResource does not support AI completion as user creation requires
explicit configuration for security reasons. All fields must be provided.

IMPORTANT: User creation requires administrative privileges.
On macOS:
  - Run with sudo: sudo uv run clockwork apply
  - Or ensure your user has necessary permissions via dscl
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
