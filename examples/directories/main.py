"""
Directory Management Example - Create and manage directories.

This example demonstrates:
- DirectoryResource for creating directories
- Setting directory permissions
- Nested directory structures
- Recursive directory creation
"""

from clockwork.resources import DirectoryResource
from clockwork.assertions import FileExistsAssert

# Simple directory - main application directory
app_dir = DirectoryResource(
    name="app-directory",
    description="Main application directory",
    path="scratch/myapp",
    mode="755",
    recursive=True,
    assertions=[
        FileExistsAssert(path="scratch/myapp"),
    ]
)

# Data directory with restricted permissions
data_dir = DirectoryResource(
    name="data-directory",
    description="Application data storage with restricted access",
    path="scratch/myapp/data",
    mode="700",  # Only owner can read/write/execute
    recursive=True,
    assertions=[
        FileExistsAssert(path="scratch/myapp/data"),
    ]
)

# Logs directory with standard permissions
logs_dir = DirectoryResource(
    name="logs-directory",
    description="Application logs directory",
    path="scratch/myapp/logs",
    mode="755",
    recursive=True,
    assertions=[
        FileExistsAssert(path="scratch/myapp/logs"),
    ]
)

# Config directory
config_dir = DirectoryResource(
    name="config-directory",
    description="Application configuration files",
    path="scratch/myapp/config",
    mode="755",
    recursive=True,
    assertions=[
        FileExistsAssert(path="scratch/myapp/config"),
    ]
)

# Cache directory with read-write permissions
cache_dir = DirectoryResource(
    name="cache-directory",
    description="Temporary cache storage",
    path="scratch/myapp/cache",
    mode="755",
    recursive=True,
    assertions=[
        FileExistsAssert(path="scratch/myapp/cache"),
    ]
)
