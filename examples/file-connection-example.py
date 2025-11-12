"""Example demonstrating FileConnection usage.

This example shows different ways to use FileConnection for sharing
files and volumes between resources.
"""

from clockwork.connections import FileConnection
from clockwork.resources import (
    AppleContainerResource,
    BlankResource,
    FileResource,
)

# Example 1: Share a volume between two containers
# AI can complete mount_path and volume_name based on description
storage = AppleContainerResource(
    name="storage", description="data storage container"
)
app = AppleContainerResource(name="app", description="application container")

connection = FileConnection(
    to_resource=storage, description="shared data volume for app and storage"
)
app.connect(connection)

# Example 2: Mount a config file into a container
# FileResource provides the config file, FileConnection mounts it
config = FileResource(
    description="nginx configuration file",
    name="nginx.conf",
    directory="./config",
    content="""
events {
    worker_connections 1024;
}

http {
    server {
        listen 80;
        location / {
            return 200 'Hello World';
        }
    }
}
""",
    mode="644",
)

nginx = AppleContainerResource(
    description="nginx web server",
    name="nginx",
    image="nginx:alpine",
    ports=["8080:80"],
)

config_connection = FileConnection(
    to_resource=config, mount_path="/etc/nginx/nginx.conf", read_only=True
)
nginx.connect(config_connection)

# Example 3: Bind mount a host directory
web = AppleContainerResource(
    description="static web server",
    name="web",
    image="nginx:alpine",
    ports=["8081:80"],
)

# Use a BlankResource as a placeholder for the host directory
host_dir = BlankResource(name="host-html", description="host html directory")

bind_mount = FileConnection(
    to_resource=host_dir,  # Placeholder for bind mount
    mount_path="/usr/share/nginx/html",
    source_path="./html",
    create_volume=False,
)
web.connect(bind_mount)

# Example 4: Container volume with explicit settings
db = AppleContainerResource(
    description="postgres database",
    name="postgres",
    image="postgres:15-alpine",
    ports=["5432:5432"],
)

# Use a BlankResource as a placeholder for the volume
db_data = BlankResource(name="db-data", description="postgres data volume")

db_volume = FileConnection(
    to_resource=db_data,  # Placeholder for volume
    volume_name="postgres-data",
    mount_path="/var/lib/postgresql/data",
    create_volume=True,
    volume_size="5G",  # Apple Container volume size
    read_only=False,
)
db.connect(db_volume)

print("FileConnection examples created successfully!")
print("\nExample 1: Shared volume (AI completion)")
print(f"  - Storage: {storage.name}")
print(f"  - App: {app.name}")
print(f"  - Connection: {connection.description}")

print("\nExample 2: Config file mount")
print(f"  - Config: {config.name} -> {config.directory}/{config.name}")
print(f"  - Nginx: {nginx.name}")
print(f"  - Mount: {config_connection.mount_path} (read-only)")

print("\nExample 3: Bind mount")
print(f"  - Web: {web.name}")
print(f"  - Mount: {bind_mount.source_path} -> {bind_mount.mount_path}")

print("\nExample 4: Container volume")
print(f"  - Database: {db.name}")
print(f"  - Volume: {db_volume.volume_name}")
print(f"  - Mount: {db_volume.mount_path}")
