"""Base connection class for Clockwork."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import pulumi
from pydantic import BaseModel, Field, PrivateAttr

if TYPE_CHECKING:
    from clockwork.assertions.base import BaseAssertion

logger = logging.getLogger(__name__)


class Connection(BaseModel):
    """Base connection class - all connections inherit from this.

    Connections are first-class components that establish relationships between resources.
    Unlike simple dependencies, connections can:
    - Have their own setup resources (e.g., network bridges, config files)
    - Be AI-completed based on context from both endpoints
    - Run their own assertions to validate the connection

    Connection Flow:
    1. User creates connection with some fields set to None
    2. needs_completion() checks if any completable fields are None
    3. AI fills in missing fields using context from from_resource and to_resource
    4. to_pulumi() deploys any setup resources needed for the connection
    5. Assertions validate the connection is working

    Attributes:
        from_resource: Source resource (set by Resource.connect())
        to_resource: Target resource
        description: Optional description for AI completion context
        setup_resources: Resources created by this connection (e.g., config files, network bridges)
        assertions: Validation checks for the connection
        _pulumi_resources: Private list of deployed Pulumi resources
    """

    from_resource: Any = Field(
        default=None,
        description="Source resource (will be set by Resource.connect())",
    )
    to_resource: Any = Field(
        ..., description="Target resource this connection points to"
    )
    description: str | None = Field(
        default=None,
        description="Human-readable description for AI completion context",
    )
    setup_resources: list[Any] = Field(
        default_factory=list,
        description="Resources created by this connection (e.g., config files)",
    )
    assertions: list[BaseAssertion] | None = Field(
        default=None, description="Validation checks for the connection"
    )

    _pulumi_resources: list[pulumi.Resource] = PrivateAttr(default_factory=list)

    def needs_completion(self) -> bool:
        """Check if this connection needs AI completion for any fields.

        Override this method in subclasses to define which fields can be AI-completed.
        The default implementation checks if description is set but no setup resources exist.

        Returns:
            True if any completable fields are None, False otherwise

        Example:
            class DatabaseConnection(Connection):
                schema_file: str | None = None

                def needs_completion(self) -> bool:
                    return self.schema_file is None
        """
        # Base implementation: needs completion if has description but no setup resources
        return self.description is not None and len(self.setup_resources) == 0

    def get_connection_context(self) -> dict[str, Any]:
        """Get shareable context from this connection for AI completion.

        Returns context that can be used by AI when completing resources or other connections.

        Returns:
            Dict with shareable fields from this connection

        Example:
            class DatabaseConnection(Connection):
                database_name: str | None = None

                def get_connection_context(self) -> dict[str, Any]:
                    context = super().get_connection_context()
                    context.update({
                        "database_name": self.database_name,
                        "connection_type": "database"
                    })
                    return context
        """
        from_name = None
        to_name = None

        if self.from_resource is not None:
            from_name = getattr(self.from_resource, "name", None)

        if self.to_resource is not None:
            to_name = getattr(self.to_resource, "name", None)

        return {
            "type": self.__class__.__name__,
            "from_resource": from_name,
            "to_resource": to_name,
            "description": self.description,
        }

    def to_pulumi(self) -> list[pulumi.Resource] | None:
        """Create Pulumi resources for this connection's setup.

        This method is called after AI completion, so all required fields should
        be populated. It should create and return Pulumi resources needed to
        establish the connection (e.g., config files, network bridges).

        Override this in subclasses to deploy connection-specific infrastructure.
        The base implementation returns None (no setup resources).

        Returns:
            List of Pulumi Resource objects, or None if no setup needed

        Example:
            import pulumi_command as command

            def to_pulumi(self) -> list[pulumi.Resource] | None:
                # Create setup resources with dependency options
                opts = self._build_dependency_options()

                config_resource = command.local.Command(
                    f"{self.from_resource.name}-to-{self.to_resource.name}-setup",
                    create=f"echo 'Setting up connection...'",
                    opts=opts
                )

                # Store for later dependency tracking
                self._pulumi_resources = [config_resource]

                return self._pulumi_resources
        """
        return None

    def _build_dependency_options(self) -> pulumi.ResourceOptions | None:
        """Build Pulumi ResourceOptions from connection endpoints.

        Creates ResourceOptions with depends_on set to both from_resource and
        to_resource Pulumi resources. This ensures the connection's setup resources
        are deployed after both endpoints exist.

        Returns:
            pulumi.ResourceOptions with depends_on set if endpoints exist,
            None if no endpoint Pulumi resources available

        Example:
            # Internal use by to_pulumi():
            opts = self._build_dependency_options()
            setup = command.local.Command("setup", create="...", opts=opts)
        """
        depends_on = []

        # Add from_resource dependency
        if (
            self.from_resource is not None
            and hasattr(self.from_resource, "_pulumi_resource")
            and self.from_resource._pulumi_resource is not None
        ):
            depends_on.append(self.from_resource._pulumi_resource)

        # Add to_resource dependency
        if (
            self.to_resource is not None
            and hasattr(self.to_resource, "_pulumi_resource")
            and self.to_resource._pulumi_resource is not None
        ):
            depends_on.append(self.to_resource._pulumi_resource)

        if depends_on:
            return pulumi.ResourceOptions(depends_on=depends_on)

        return None
