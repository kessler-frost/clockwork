"""Dependency connection - simplest connection type."""

import logging

import pulumi

from .base import Connection

logger = logging.getLogger(__name__)


class DependencyConnection(Connection):
    """Simple dependency connection that establishes ordering without setup.

    This is the default connection type auto-created when user does: api.connect(db)

    DependencyConnection just establishes deployment ordering - the to_resource
    will be deployed before the from_resource. No setup resources are created.

    Attributes:
        from_resource: Source resource (depends on to_resource)
        to_resource: Target resource (dependency)

    Example:
        # Automatic creation
        db = AppleContainerResource(name="postgres", image="postgres:15")
        api = AppleContainerResource(name="api", image="node:20").connect(db)
        # Creates: DependencyConnection(from_resource=api, to_resource=db)

        # Manual creation
        db = AppleContainerResource(name="postgres", image="postgres:15")
        api = AppleContainerResource(name="api", image="node:20")
        connection = DependencyConnection(
            from_resource=api,
            to_resource=db
        )
        api.connect(connection)
    """

    def needs_completion(self) -> bool:
        """DependencyConnection never needs AI completion.

        Returns:
            Always False - this connection type is always complete
        """
        return False

    def to_pulumi(self) -> list[pulumi.Resource] | None:
        """DependencyConnection creates no setup resources.

        The dependency is handled automatically by Pulumi's depends_on mechanism
        in the Resource._build_dependency_options() method.

        Returns:
            Always None - no setup resources needed
        """
        return None
