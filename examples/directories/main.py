"""
Directory Management Example - Create and manage directories.

This example demonstrates the AI completion architecture where you provide
minimal information and the AI intelligently determines names and permissions.
"""

from clockwork.resources import DirectoryResource

# Minimal - AI generates name and picks appropriate permissions
app_dir = DirectoryResource(
    description="Main application directory at scratch/myapp",
    path="scratch/myapp"
)

# AI recognizes "restricted access" and sets mode to 700
data_dir = DirectoryResource(
    description="Application data storage with restricted access",
    path="scratch/myapp/data"
)

# AI picks standard permissions for logs
logs_dir = DirectoryResource(
    description="Application logs directory",
    path="scratch/myapp/logs"
)

# Override mode if needed
config_dir = DirectoryResource(
    description="Application configuration files",
    path="scratch/myapp/config",
    mode="644"  # Explicit mode, AI generates name
)
