"""Base resource classes for Clockwork."""

import logging
from collections.abc import Iterator, Mapping
from typing import TYPE_CHECKING, Any, Optional, Self

import pulumi
from pydantic import (
    BaseModel,
    Field,
    PrivateAttr,
    field_validator,
    model_validator,
)

if TYPE_CHECKING:
    from clockwork.assertions.base import BaseAssertion


class ChildrenCollection(Mapping):
    """Read-only dict-like collection for accessing children by name.

    Implements the Mapping protocol, providing dict-like access to child
    resources by their name attribute. This allows intuitive access patterns
    like webapp.children["postgres"] instead of webapp.get_children()[2].

    By extending collections.abc.Mapping, we get many methods for free:
    - keys() - iterate over child names
    - values() - iterate over child resources
    - items() - iterate over (name, resource) tuples
    - get(name, default) - safe access with default
    - __contains__ - check if child exists by name

    Args:
        children: List of Resource objects to wrap

    Example:
        >>> webapp = BlankResource(name="webapp")
        >>> webapp.add(
        ...     DockerResource(name="postgres", image="postgres:15"),
        ...     DockerResource(name="redis", image="redis:7")
        ... )
        >>>
        >>> # Dict-style access
        >>> webapp.children["postgres"].env_vars = {"POSTGRES_DB": "mydb"}
        >>>
        >>> # Safe access
        >>> redis = webapp.children.get("redis")
        >>> if redis:
        ...     redis.ports = ["6379:6379"]
        >>>
        >>> # Check existence
        >>> if "postgres" in webapp.children:
        ...     print("Has postgres!")
        >>>
        >>> # Iterate over names
        >>> for name in webapp.children:
        ...     print(f"Child: {name}")
        >>>
        >>> # Iterate over resources
        >>> for resource in webapp.children.values():
        ...     print(f"Resource: {resource.name}")
        >>>
        >>> # Iterate over both
        >>> for name, resource in webapp.children.items():
        ...     print(f"{name}: {resource.image}")
    """

    def __init__(self, children: list["Resource"]):
        """Initialize the collection with a list of child resources.

        Args:
            children: List of Resource objects
        """
        self._children = children

    def __getitem__(self, name: str) -> "Resource":
        """Access child by name: webapp.children["postgres"]

        Args:
            name: Name of the child resource to retrieve

        Returns:
            The child Resource with the given name

        Raises:
            KeyError: If no child with the given name exists
        """
        for child in self._children:
            if child.name == name:
                return child
        raise KeyError(f"No child resource named '{name}'")

    def __iter__(self) -> Iterator[str]:
        """Iterate over child names.

        Yields:
            Names of child resources
        """
        return (
            child.name for child in self._children if child.name is not None
        )

    def __len__(self) -> int:
        """Return number of children.

        Returns:
            Count of child resources
        """
        return len(self._children)

    def __repr__(self) -> str:
        """String representation of the collection.

        Returns:
            String showing children names
        """
        names = [child.name for child in self._children if child.name]
        return f"ChildrenCollection({names})"


class Resource(BaseModel):
    """Base resource class - all resources inherit from this.

    The new completion-based architecture allows resources to have optional fields
    that can be filled in by AI during the completion stage. Instead of generating
    separate "artifacts", the AI directly populates missing fields on the resource
    objects themselves.

    Completion Flow:
    1. User creates resource with some fields set to None (e.g., name=None, image=None)
    2. needs_completion() checks if any completable fields are None
    3. AI fills in the missing fields by creating a new completed resource instance
    4. to_pulumi() method converts completed resource to Pulumi resources

    Resource Connections:
    Resources can declare dependencies on other resources via the connections field.
    This enables:
    - AI-powered completion with context from connected resources
    - Automatic dependency ordering for deployment
    - Cross-resource configuration sharing

    Connection Storage Pattern:
    - Users pass Resource objects in the connections parameter
    - Pydantic stores connection context dicts in the connections field (serializable)
    - Original Resource objects are preserved in _connection_resources (for graph traversal)
    - This dual storage enables both AI completion and dependency resolution

    Composite Resources:
    Resources can have parent-child relationships to create hierarchical structures:
    - Use .add(*resources) to add child resources (chainable)
    - Children are deployed with their parent
    - Bidirectional parent-child relationship tracking
    - Access children via .children property (dict-like access by name)
    - Access parent via .parent property

    Attributes:
        name: Optional unique identifier (can be AI-completed if None)
        description: Optional human-readable description (used as context for AI)
        assertions: Optional list of type-safe assertion objects for validation
        tools: Optional list of PydanticAI tools (duckduckgo_search_tool(), MCPServerStdio, etc.)
               for AI-powered completion operations
        connections: List of connection context dicts (auto-converted from Resource objects)
        _connection_resources: Private list of actual Resource objects for dependency graphs
        _children: Private list of child resources (for composite resources)
        _parent: Private reference to parent resource (for hierarchy traversal)
    """

    name: str | None = None
    description: str | None = None
    assertions: list["BaseAssertion"] | None = None
    connections: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Connection context dicts (Resource objects auto-converted via validator)",
    )
    _connection_resources: list["Resource"] = PrivateAttr(default_factory=list)
    _children: list["Resource"] = PrivateAttr(default_factory=list)
    _parent: Optional["Resource"] = PrivateAttr(default=None)

    # AI and integration capabilities
    tools: list[Any] | None = (
        None  # PydanticAI tools (duckduckgo_search_tool(), MCPServerStdio, etc.)
    )

    def __init__(self, **data):
        """Initialize Resource and capture connection Resource objects.

        This custom __init__ is necessary to preserve Resource objects before Pydantic
        processes them. Pydantic validation can cause Resource objects to lose their
        private attributes, so we extract them early.
        """
        # Extract Resource objects before Pydantic processes the connections field
        connection_resources = []
        if data.get("connections"):
            for item in data["connections"]:
                if hasattr(item, "get_connection_context"):
                    connection_resources.append(item)

        # Initialize Pydantic model (triggers validators)
        super().__init__(**data)

        # Store captured Resource objects in private attribute
        self._connection_resources = connection_resources

    @field_validator("connections", mode="before")
    @classmethod
    def convert_resources_before_validation(cls, value):
        """Convert Resource objects to dicts before field validation.

        This runs before type validation, allowing users to pass Resource objects
        while the field type remains List[Dict] (avoiding circular schema references).

        Args:
            value: List that may contain Resource objects or dicts

        Returns:
            List of dicts only
        """
        if not value:
            return []

        result = []
        for item in value:
            if hasattr(item, "get_connection_context"):
                # Convert Resource to dict
                result.append(item.get_connection_context())
            else:
                # Already a dict
                result.append(item)
        return result

    @model_validator(mode="after")
    def convert_connections_to_dicts(self) -> "Resource":
        """Convert Resource objects in connections field to serializable dicts.

        This validator runs after __init__ and converts any remaining Resource objects
        in the connections field to context dictionaries. This ensures the connections
        field only contains serializable data.

        Note: The original Resource objects are already stored in _connection_resources
        by __init__, so this validator only handles the public connections field.

        Returns:
            Self with connections converted to context dicts
        """
        connection_contexts = []

        for item in self.connections:
            if hasattr(item, "get_connection_context"):
                # Convert Resource to context dict
                connection_contexts.append(item.get_connection_context())
            elif isinstance(item, dict):
                # Already a context dict
                connection_contexts.append(item)
            else:
                import logging

                logging.warning(
                    f"Unknown connection type: {type(item)}, skipping"
                )

        # Replace connections with context dicts only
        self.connections = connection_contexts

        return self

    def needs_completion(self) -> bool:
        """Check if this resource needs AI completion for any fields.

        Override this method in subclasses to define which fields can be AI-completed.
        The default implementation only checks if name is None.

        Returns:
            True if any completable fields are None, False otherwise

        Example:
            class MyResource(Resource):
                content: str | None = None

                def needs_completion(self) -> bool:
                    return self.name is None or self.content is None
        """
        return self.name is None

    def get_connection_context(self) -> dict[str, Any]:
        """Get shareable context from this resource for connected resources.

        This method returns a dictionary of fields that can be shared with other
        resources during AI completion. When a resource declares connections,
        the AI can access context from connected resources to make intelligent
        decisions about configuration.

        Subclasses should override this method to expose resource-specific fields.
        The default implementation provides basic information that's useful across
        all resource types.

        Returns:
            Dict with shareable fields from this resource

        Example:
            class DatabaseResource(Resource):
                port: int | None = None
                host: str | None = None

                def get_connection_context(self) -> Dict[str, Any]:
                    context = super().get_connection_context()
                    context.update({
                        "port": self.port,
                        "host": self.host,
                        "connection_string": f"{self.host}:{self.port}"
                    })
                    return context

            # Usage in connected resource:
            db = DatabaseResource(name="postgres", port=5432, host="localhost")
            app = AppResource(
                name="webapp",
                description="Connect to the database",
                connections=[db]  # AI can access db.get_connection_context()
            )
        """
        return {
            "name": self.name,
            "type": self.__class__.__name__,
            "description": self.description,
        }

    def add(self, *resources: "Resource") -> Self:
        """Add child resources to this resource (composite pattern).

        Creates parent-child relationships where children are deployed with their parent.
        This method is chainable for fluent API usage.

        Args:
            *resources: One or more Resource objects to add as children

        Returns:
            Self for method chaining

        Raises:
            TypeError: If any argument is not a Resource instance

        Example:
            # Single child
            parent = DockerResource(name="web-app", image="nginx")
            parent.add(FileResource(name="config", path="/etc/nginx/nginx.conf"))

            # Multiple children (chainable)
            parent = DockerResource(name="app", image="node:20")
            parent.add(
                FileResource(name="package.json", path="/app/package.json"),
                FileResource(name="server.js", path="/app/server.js")
            ).add(
                FileResource(name="config.yaml", path="/app/config.yaml")
            )

            # Hierarchical structure
            project = Resource(name="my-project")
            project.add(
                DockerResource(name="database", image="postgres:15"),
                DockerResource(name="cache", image="redis:7"),
                DockerResource(name="api", image="node:20")
            )
        """
        for resource in resources:
            if not isinstance(resource, Resource):
                raise TypeError(
                    f"Can only add Resource objects, got {type(resource).__name__}"
                )

            # Check for duplicates using object identity (not equality) to avoid
            # recursion issues with circular references
            if any(resource is child for child in self._children):
                logging.warning(
                    f"Resource '{resource.name}' is already a child of '{self.name}', skipping"
                )
                continue

            # Warn if re-parenting
            if resource._parent is not None and resource._parent is not self:
                logging.warning(
                    f"Resource '{resource.name}' is being re-parented from "
                    f"'{resource._parent.name}' to '{self.name}'"
                )

            # Set bidirectional relationship
            resource._parent = self
            self._children.append(resource)

        return self

    @property
    def children(self) -> ChildrenCollection:
        """Dict-like collection for accessing child resources by name.

        Returns:
            ChildrenCollection providing dict-like access to children

        Example:
            >>> parent = Resource(name="parent")
            >>> parent.add(
            ...     Resource(name="child1"),
            ...     Resource(name="child2")
            ... )
            >>>
            >>> # Access by name
            >>> parent.children["child1"].description = "Updated"
            >>>
            >>> # Iterate over names
            >>> for name in parent.children:
            ...     print(name)  # 'child1', 'child2'
            >>>
            >>> # Iterate over resources
            >>> for resource in parent.children.values():
            ...     print(resource.name)
            >>>
            >>> # Check existence
            >>> if "child1" in parent.children:
            ...     print("Found child1")
            >>>
            >>> # Safe access
            >>> child = parent.children.get("child3", None)
            >>>
            >>> # Count children
            >>> print(len(parent.children))  # 2
        """
        return ChildrenCollection(self._children)

    @property
    def parent(self) -> Optional["Resource"]:
        """The parent resource, if any.

        Returns:
            Parent Resource or None if this is a root resource

        Example:
            >>> parent = Resource(name="parent")
            >>> child = Resource(name="child")
            >>> parent.add(child)
            >>>
            >>> assert child.parent == parent
            >>> assert parent.parent is None
        """
        return self._parent

    def connect(self, *resources: "Resource") -> Self:
        """Add dependency connections to this resource (alternative to constructor param).

        This method provides a chainable alternative to passing connections in the constructor.
        Connected resources provide context for AI completion and establish deployment ordering.

        Args:
            *resources: One or more Resource objects to connect as dependencies

        Returns:
            Self for method chaining

        Raises:
            TypeError: If any argument is not a Resource instance

        Example:
            # Constructor style
            db = DockerResource(name="postgres", image="postgres:15")
            api = DockerResource(
                name="api",
                image="node:20",
                connections=[db]
            )

            # Chainable style (equivalent)
            db = DockerResource(name="postgres", image="postgres:15")
            api = DockerResource(name="api", image="node:20").connect(db)

            # Multiple connections
            db = DockerResource(name="postgres", image="postgres:15")
            cache = DockerResource(name="redis", image="redis:7")
            api = DockerResource(name="api", image="node:20").connect(db, cache)

            # Combined with .add()
            project = Resource(name="microservices")
            project.add(
                DockerResource(name="postgres", image="postgres:15"),
                DockerResource(name="redis", image="redis:7"),
                DockerResource(name="api", image="node:20").connect(db, cache)
            )
        """
        for resource in resources:
            if not isinstance(resource, Resource):
                raise TypeError(
                    f"Can only connect Resource objects, got {type(resource).__name__}"
                )

            # Check for duplicates in _connection_resources
            if resource in self._connection_resources:
                logging.warning(
                    f"Resource '{resource.name}' is already connected to '{self.name}', skipping"
                )
                continue

            # Add to private list (for graph traversal)
            self._connection_resources.append(resource)

            # Add context to public connections field (for AI and serialization)
            context = resource.get_connection_context()
            if context not in self.connections:
                self.connections.append(context)

        return self

    def get_all_descendants(self) -> list["Resource"]:
        """Get all descendant resources recursively (children, grandchildren, etc.).

        Uses depth-first traversal to collect all descendants in the hierarchy.

        Returns:
            List of all descendant resources in depth-first order

        Example:
            root = Resource(name="root")
            child1 = Resource(name="child1")
            child2 = Resource(name="child2")
            grandchild1 = Resource(name="grandchild1")
            grandchild2 = Resource(name="grandchild2")

            root.add(child1, child2)
            child1.add(grandchild1)
            child2.add(grandchild2)

            descendants = root.get_all_descendants()
            print([r.name for r in descendants])
            # ['child1', 'grandchild1', 'child2', 'grandchild2']
        """
        descendants = []
        for child in self._children:
            descendants.append(child)
            # Recursively add grandchildren
            descendants.extend(child.get_all_descendants())
        return descendants

    def _build_dependency_options(self) -> pulumi.ResourceOptions | None:
        """Build Pulumi ResourceOptions from connection dependencies.

        Iterates through connected resources and creates a ResourceOptions object
        with depends_on set to the Pulumi resources of connected resources. This
        ensures proper deployment ordering.

        Returns:
            pulumi.ResourceOptions with depends_on set if connections exist,
            None if no connections or no Pulumi resources available

        Example:
            db = DockerResource(name="postgres", image="postgres:15")
            # ... db.to_pulumi() creates db._pulumi_resource ...

            api = DockerResource(name="api", connections=[db])
            opts = api._build_dependency_options()
            # opts.depends_on contains db's Pulumi resource
        """
        if not self._connection_resources:
            return None

        depends_on = []
        for conn in self._connection_resources:
            if (
                hasattr(conn, "_pulumi_resource")
                and conn._pulumi_resource is not None
            ):
                depends_on.append(conn._pulumi_resource)

        if depends_on:
            return pulumi.ResourceOptions(depends_on=depends_on)

        return None

    def _compile_with_opts(
        self, opts: pulumi.ResourceOptions | None
    ) -> pulumi.Resource:
        """Internal method to compile resource with custom ResourceOptions.

        This method is used during recursive compilation of composite resources
        to pass parent information to children. It merges the provided options
        (typically containing parent reference) with dependency options from
        connections.

        Args:
            opts: ResourceOptions to use (typically contains parent reference)

        Returns:
            Pulumi Resource created by to_pulumi()

        Example:
            # Called internally by composite resources:
            parent_component = pulumi.ComponentResource(...)
            child_opts = pulumi.ResourceOptions(parent=parent_component)
            child._compile_with_opts(child_opts)
        """
        # Build dependency options from connections
        dep_opts = self._build_dependency_options()

        # Merge parent opts with dependency opts
        merged_opts = self._merge_resource_options(opts, dep_opts)

        # Store merged options temporarily for to_pulumi() to use
        # This is a bit of a hack but avoids changing all to_pulumi() signatures
        self._temp_compile_opts = merged_opts

        try:
            # Call to_pulumi() which should use _temp_compile_opts if available
            return self.to_pulumi()
        finally:
            # Clean up temporary options
            if hasattr(self, "_temp_compile_opts"):
                delattr(self, "_temp_compile_opts")

    def _merge_resource_options(
        self,
        parent_opts: pulumi.ResourceOptions | None,
        dep_opts: pulumi.ResourceOptions | None,
    ) -> pulumi.ResourceOptions | None:
        """Merge parent options and dependency options.

        Combines ResourceOptions from parent (for hierarchy) and dependencies
        (for ordering). Parent reference takes precedence, and depends_on lists
        are combined.

        Args:
            parent_opts: Options from parent (typically contains parent reference)
            dep_opts: Options from dependencies (typically contains depends_on)

        Returns:
            Merged ResourceOptions, or None if both inputs are None

        Example:
            parent_opts = pulumi.ResourceOptions(parent=component)
            dep_opts = pulumi.ResourceOptions(depends_on=[db, cache])
            merged = self._merge_resource_options(parent_opts, dep_opts)
            # merged has both parent=component and depends_on=[db, cache]
        """
        if parent_opts is None and dep_opts is None:
            return None

        if parent_opts is None:
            return dep_opts

        if dep_opts is None:
            return parent_opts

        # Both exist - merge them
        merged_depends_on = []

        # Collect depends_on from both
        if parent_opts.depends_on:
            if isinstance(parent_opts.depends_on, list):
                merged_depends_on.extend(parent_opts.depends_on)
            else:
                merged_depends_on.append(parent_opts.depends_on)

        if dep_opts.depends_on:
            if isinstance(dep_opts.depends_on, list):
                merged_depends_on.extend(dep_opts.depends_on)
            else:
                merged_depends_on.append(dep_opts.depends_on)

        # Create merged options with parent from parent_opts and combined depends_on
        return pulumi.ResourceOptions(
            parent=parent_opts.parent
            if hasattr(parent_opts, "parent")
            else None,
            depends_on=merged_depends_on if merged_depends_on else None,
        )

    def to_pulumi(self):
        """Create Pulumi resource(s) for this Clockwork resource.

        This method is called after AI completion, so all required fields should
        be populated. It should create and return one or more Pulumi resources
        using the Pulumi SDK.

        Returns:
            Pulumi Resource object(s)

        Example:
            import pulumi_docker as docker

            def to_pulumi(self):
                return docker.Container(
                    self.name,
                    image=self.image,
                    ports=[docker.ContainerPortArgs(internal=80, external=8080)]
                )
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement to_pulumi()"
        )
