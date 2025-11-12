"""Database connection with schema and migration support."""

import logging
from pathlib import Path
from typing import Any

import pulumi
from pulumi_command import local
from pydantic import Field

from .base import Connection

logger = logging.getLogger(__name__)


class DatabaseConnection(Connection):
    """Database connection with automatic configuration, schema execution, and migrations.

    This connection establishes a database connection between an application (from_resource)
    and a database (to_resource). It automatically generates connection strings, waits for
    database readiness, executes schema files, and runs migrations.

    Attributes:
        schema_file: Path to SQL schema file
        migrations_dir: Directory containing migration files
        connection_string_template: Template like "postgresql://{user}:{password}@{host}:{port}/{database}"
        env_var_name: Environment variable name for connection string (default: DATABASE_URL)
        username: Database username
        password: Database password
        database_name: Database name
        wait_for_ready: Wait for database to be healthy before proceeding
        timeout: Timeout in seconds for wait_for_ready

    Examples:
        # Basic usage with automatic connection string:
        >>> db = AppleContainerResource(
        ...     name="postgres",
        ...     image="postgres:15",
        ...     ports=["5432:5432"],
        ...     env_vars={"POSTGRES_PASSWORD": "secret"}  # pragma: allowlist secret
        ... )
        >>> api = AppleContainerResource(name="api", image="node:20")
        >>> connection = DatabaseConnection(
        ...     to_resource=db,
        ...     connection_string_template="postgresql://{user}:{password}@{host}:{port}/{database}",
        ...     username="postgres",
        ...     password="secret",  # pragma: allowlist secret
        ...     database_name="myapp"
        ... )
        >>> api.connect(connection)

        # With schema file:
        >>> connection = DatabaseConnection(
        ...     to_resource=db,
        ...     schema_file="schema.sql",
        ...     connection_string_template="postgresql://{user}:{password}@{host}:{port}/{database}",
        ...     username="postgres",
        ...     password="secret",  # pragma: allowlist secret
        ...     database_name="myapp"
        ... )

        # With migrations directory:
        >>> connection = DatabaseConnection(
        ...     to_resource=db,
        ...     schema_file="schema.sql",
        ...     migrations_dir="migrations/",
        ...     connection_string_template="postgresql://{user}:{password}@{host}:{port}/{database}",
        ...     username="postgres",
        ...     password="secret",  # pragma: allowlist secret
        ...     database_name="myapp"
        ... )
    """

    schema_file: str | None = Field(
        default=None,
        description="Path to SQL schema file to execute",
        examples=["schema.sql", "db/schema.sql"],
    )
    migrations_dir: str | None = Field(
        default=None,
        description="Directory containing migration files",
        examples=["migrations/", "db/migrations/"],
    )
    connection_string_template: str | None = Field(
        default=None,
        description="Connection string template with placeholders",
        examples=[
            "postgresql://{user}:{password}@{host}:{port}/{database}",
            "mysql://{user}:{password}@{host}:{port}/{database}",
        ],
    )
    env_var_name: str = Field(
        default="DATABASE_URL",
        description="Environment variable name for connection string",
    )
    username: str | None = Field(
        default=None,
        description="Database username",
    )
    password: str | None = Field(
        default=None,
        description="Database password",
    )
    database_name: str | None = Field(
        default=None,
        description="Database name",
    )
    wait_for_ready: bool = Field(
        default=True,
        description="Wait for database to be healthy before proceeding",
    )
    timeout: int = Field(
        default=30,
        description="Timeout in seconds for wait_for_ready",
    )

    def needs_completion(self) -> bool:
        """Check if this connection needs AI completion.

        Returns True if description is provided but connection_string_template
        or env_var_name are missing.

        Returns:
            True if needs AI completion, False otherwise
        """
        return (
            self.description is not None
            and self.connection_string_template is None
        ) or (self.description is not None and not self.env_var_name)

    def _extract_port(self, ports: list[str] | None) -> str | None:
        """Extract internal port from ports list.

        Args:
            ports: List of port mappings like ["5432:5432", "8080:80"]

        Returns:
            Internal port as string, or None if no ports
        """
        if not ports or len(ports) == 0:
            return None

        # Parse first port mapping: "external:internal" or "internal"
        first_port = ports[0]
        parts = first_port.split(":")

        if len(parts) == 2:
            # Format: "external:internal"
            return parts[1]
        if len(parts) == 1:
            # Format: "internal"
            return parts[0]

        return None

    def _extract_connection_info(self) -> dict[str, str]:
        """Extract connection info from to_resource.

        Returns:
            Dict with host and port keys

        Raises:
            ValueError: If to_resource type is not supported
        """
        from clockwork.resources.apple_container import AppleContainerResource

        if isinstance(self.to_resource, AppleContainerResource):
            # For containers, host is the container name
            host = self.to_resource.name
            # Extract port from ports list
            port = self._extract_port(self.to_resource.ports)

            return {"host": host, "port": port or "5432"}

        # Default to generic approach
        host = getattr(self.to_resource, "name", "localhost")
        port = "5432"  # Default PostgreSQL port

        return {"host": host, "port": port}

    def _build_connection_string(self) -> str:
        """Build database connection string from template.

        Returns:
            Connection string with placeholders filled in

        Raises:
            ValueError: If required fields are missing
        """
        if not self.connection_string_template:
            raise ValueError("connection_string_template is required")

        # Extract connection info from to_resource
        conn_info = self._extract_connection_info()

        # Build connection string
        connection_string = self.connection_string_template.format(
            user=self.username or "postgres",
            password=self.password or "postgres",
            host=conn_info["host"],
            port=conn_info["port"],
            database=self.database_name or "postgres",
        )

        return connection_string

    def to_pulumi(self) -> list[pulumi.Resource] | None:
        """Create Pulumi resources for database connection setup.

        This method:
        1. Extracts connection info from to_resource
        2. Builds connection string from template
        3. Creates wait-for-ready command if enabled
        4. Executes schema file if provided
        5. Runs migrations if directory provided
        6. Injects connection string into from_resource env_vars

        Returns:
            List of Pulumi Command resources created, or None if no setup needed
        """
        # Build connection string
        connection_string = self._build_connection_string()

        # Track created resources
        resources = []

        # Build dependency options
        dep_opts = self._build_dependency_options()

        # Create wait-for-ready command if enabled
        wait_cmd = None
        if self.wait_for_ready:
            conn_info = self._extract_connection_info()
            host = conn_info["host"]
            port = conn_info["port"]

            # Use pg_isready for PostgreSQL
            wait_cmd = local.Command(
                f"{self.from_resource.name}-wait-for-db",
                create=f"timeout {self.timeout} bash -c 'until pg_isready -h {host} -p {port}; do sleep 1; done'",
                opts=dep_opts,
            )
            resources.append(wait_cmd)

        # Execute schema file if provided
        if self.schema_file:
            schema_path = Path(self.schema_file)
            if schema_path.exists():
                schema_opts = (
                    pulumi.ResourceOptions(depends_on=[wait_cmd])
                    if wait_cmd
                    else dep_opts
                )

                schema_cmd = local.Command(
                    f"{self.from_resource.name}-schema",
                    create=f"psql '{connection_string}' -f {schema_path.absolute()}",
                    opts=schema_opts,
                )
                resources.append(schema_cmd)

        # Run migrations if directory provided
        if self.migrations_dir:
            migrations_path = Path(self.migrations_dir)
            if migrations_path.exists() and migrations_path.is_dir():
                # Get all .sql files in migrations directory, sorted
                migration_files = sorted(migrations_path.glob("*.sql"))

                # Create a command to run each migration
                for migration_file in migration_files:
                    migration_opts = (
                        pulumi.ResourceOptions(depends_on=[wait_cmd])
                        if wait_cmd
                        else dep_opts
                    )

                    migration_cmd = local.Command(
                        f"{self.from_resource.name}-migration-{migration_file.stem}",
                        create=f"psql '{connection_string}' -f {migration_file.absolute()}",
                        opts=migration_opts,
                    )
                    resources.append(migration_cmd)

        # Inject connection string into from_resource env_vars
        if not hasattr(self.from_resource, "env_vars"):
            self.from_resource.env_vars = {}
        self.from_resource.env_vars[self.env_var_name] = connection_string

        # Store resources for dependency tracking
        self._pulumi_resources = resources

        return resources if resources else None

    def get_connection_context(self) -> dict[str, Any]:
        """Get connection context for AI completion.

        Returns shareable fields that AI can use when completing resources.

        Returns:
            Dict with connection info including database name, username, etc.
        """
        context = super().get_connection_context()

        context.update(
            {
                "connection_type": "database",
                "database_name": self.database_name,
                "username": self.username,
                "env_var_name": self.env_var_name,
                "schema_file": self.schema_file,
                "migrations_dir": self.migrations_dir,
            }
        )

        return context
