"""Blank resource for pure composition - groups resources without additional functionality."""

from typing import Any

import pulumi
from pydantic import Field, PrivateAttr

from .base import Resource


class BlankResource(Resource):
    """Blank resource for pure composition - groups other resources together.

    BlankResource is a lightweight container for grouping related resources without
    adding any infrastructure-specific logic. It's designed for organizing resources
    into logical units while maintaining clean separation of concerns.

    Use Cases:
    - Group related resources (e.g., database + cache + API)
    - Create reusable resource compositions
    - Organize complex infrastructure into logical components
    - Build hierarchical resource structures

    The BlankResource delegates completion checks to its children and creates a
    Pulumi ComponentResource for proper dependency tracking and resource organization.

    Attributes:
        name: Unique identifier for this composition (required)
        description: Human-readable description of what this composition represents
        children: List of child resources to group together
        _children_resources: Private list of actual Resource objects for traversal

    Examples:
        # Simple grouping:
        >>> app = BlankResource(
        ...     name="web-app",
        ...     description="Complete web application stack"
        ... )
        >>> app.add(db, cache, api)

        # Hierarchical composition:
        >>> backend = BlankResource(name="backend").add(db, redis)
        >>> frontend = BlankResource(name="frontend").add(nginx, cdn)
        >>> full_stack = BlankResource(name="app").add(backend, frontend)

        # With AI completion:
        >>> services = BlankResource(
        ...     name="microservices",
        ...     description="Microservices architecture with database and cache"
        ... )
        >>> services.add(
        ...     DockerResource(description="PostgreSQL database"),
        ...     DockerResource(description="Redis cache"),
        ...     DockerResource(description="FastAPI backend")
        ... )
    """

    name: str = Field(..., description="Unique identifier for this composition")
    description: str | None = Field(
        None, description="What this composition represents"
    )
    # Note: children property is inherited from Resource base class
    # It provides dict-style access to child resources by name
    _children_resources: list["Resource"] = PrivateAttr(default_factory=list)
    _pulumi_resource: pulumi.Resource | None = None

    def __init__(self, **data):
        """Initialize BlankResource.

        Args:
            **data: Resource initialization data
        """
        # Initialize base Resource
        super().__init__(**data)

        # _children_resources will be populated via add() method
        self._children_resources = []

    def add(self, *resources: "Resource") -> "BlankResource":
        """Add child resources to this composition.

        This method enables fluent-style resource composition. Resources added
        become children of this BlankResource and are included in completion
        checks and context sharing.

        Args:
            *resources: One or more Resource objects to add as children

        Returns:
            Self (for method chaining)

        Examples:
            >>> app = BlankResource(name="app")
            >>> app.add(db, cache, api)
            >>> # Or chain: BlankResource(name="app").add(db).add(cache).add(api)
        """
        # Call parent add() method to handle parent-child relationships
        # This sets _children dict and _parent properly
        super().add(*resources)

        # Also store in BlankResource-specific list for backward compatibility
        for resource in resources:
            # Store the actual Resource object (avoid duplicates)
            # Use object identity to avoid recursion with circular references
            if not any(resource is child for child in self._children_resources):
                self._children_resources.append(resource)

        return self

    def needs_completion(self) -> bool:
        """Check if this resource or any children need AI completion.

        A BlankResource itself doesn't have fields that need completion (name is
        required). However, it should trigger completion if any of its children
        need completion, ensuring the entire composition is completed together.

        Returns:
            True if any child needs completion, False otherwise

        Example:
            >>> app = BlankResource(name="app")
            >>> app.add(DockerResource(description="web server"))  # needs completion
            >>> app.needs_completion()  # True
        """
        # Check if any child needs completion
        # Use _children list directly (not children property) since children without
        # names are filtered out of the property but still need completion checks
        return any(child.needs_completion() for child in self._children)

    def get_connection_context(self) -> dict[str, Any]:
        """Get connection context including information about children.

        When other resources connect to a BlankResource, they can access
        information about all the children in the composition. This enables
        AI to understand the full context of grouped resources.

        Returns:
            Dict with resource information and children contexts

        Example:
            >>> backend = BlankResource(name="backend")
            >>> backend.add(
            ...     DockerResource(name="postgres", image="postgres:15"),
            ...     DockerResource(name="redis", image="redis:7")
            ... )
            >>> backend.get_connection_context()
            {
                'name': 'backend',
                'type': 'BlankResource',
                'description': None,
                'children': [
                    {'name': 'postgres', 'type': 'DockerResource', ...},
                    {'name': 'redis', 'type': 'DockerResource', ...}
                ]
            }
        """
        context = {
            "name": self.name,
            "type": self.__class__.__name__,
            "description": self.description,
        }

        # Include children contexts if any exist
        # Use _children list to include all children, even those without names
        if len(self._children) > 0:
            children_contexts = [
                child.get_connection_context() for child in self._children
            ]
            context["children"] = children_contexts

        return context

    def to_pulumi(self) -> pulumi.Resource:
        """Convert to Pulumi ComponentResource for dependency tracking.

        Creates a Pulumi ComponentResource that acts as a logical grouping for
        the child resources. This ensures proper dependency tracking and allows
        Pulumi to understand the resource hierarchy.

        Children are compiled recursively with the parent option set, creating
        a proper Pulumi resource hierarchy.

        Returns:
            pulumi.Resource: Pulumi ComponentResource representing this composition

        Raises:
            ValueError: If name is not set (should never happen as name is required)

        Example:
            >>> app = BlankResource(name="web-app")
            >>> app.add(db, api)
            >>> component = app.to_pulumi()
        """
        if self.name is None:
            raise ValueError("BlankResource requires a name")

        # Build dependency options from connections
        dep_opts = self._build_dependency_options()

        # Check if we have temporary compile options (from _compile_with_opts)
        # This allows composites to be nested
        if hasattr(self, "_temp_compile_opts"):
            # Merge with dependency options
            opts = self._merge_resource_options(
                self._temp_compile_opts, dep_opts
            )
        else:
            opts = dep_opts

        # Create Pulumi ComponentResource
        # ComponentResource acts as a logical grouping without deploying actual infrastructure
        component = pulumi.ComponentResource(
            "clockwork:blank:BlankResource",
            self.name,
            {},  # Empty props dict for component
            opts,
        )

        # Store for dependency tracking
        self._pulumi_resource = component

        # Compile children recursively with parent option
        # Use _children list directly (not children property) to include all children
        # including those that may not have names yet
        import logging

        for child in self._children:
            logging.debug(
                f"Compiling child resource '{child.name}' under parent '{self.name}'"
            )

            # Create ResourceOptions with parent reference
            child_opts = pulumi.ResourceOptions(parent=component)

            # Use _compile_with_opts to merge parent opts with child's dependency opts
            child._compile_with_opts(child_opts)

        # Register outputs (empty for blank resource)
        component.register_outputs({})

        return component
