"""Base resource classes for Clockwork."""

from typing import Dict, Any, Optional, List, TYPE_CHECKING, Union
from pydantic import BaseModel, Field, field_validator, model_validator, PrivateAttr

if TYPE_CHECKING:
    from clockwork.assertions.base import BaseAssertion


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

    Attributes:
        name: Optional unique identifier (can be AI-completed if None)
        description: Optional human-readable description (used as context for AI)
        assertions: Optional list of type-safe assertion objects for validation
        tools: Optional list of PydanticAI tools (duckduckgo_search_tool(), MCPServerStdio, etc.)
               for AI-powered completion operations
        connections: List of connection context dicts (auto-converted from Resource objects)
        _connection_resources: Private list of actual Resource objects for dependency graphs
    """

    name: str | None = None
    description: str | None = None
    assertions: List["BaseAssertion"] | None = None
    connections: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Connection context dicts (Resource objects auto-converted via validator)"
    )
    _connection_resources: List["Resource"] = PrivateAttr(default_factory=list)

    # AI and integration capabilities
    tools: List[Any] | None = None  # PydanticAI tools (duckduckgo_search_tool(), MCPServerStdio, etc.)

    def __init__(self, **data):
        """Initialize Resource and capture connection Resource objects.

        This custom __init__ is necessary to preserve Resource objects before Pydantic
        processes them. Pydantic validation can cause Resource objects to lose their
        private attributes, so we extract them early.
        """
        # Extract Resource objects before Pydantic processes the connections field
        connection_resources = []
        if 'connections' in data and data['connections']:
            for item in data['connections']:
                if hasattr(item, 'get_connection_context'):
                    connection_resources.append(item)

        # Initialize Pydantic model (triggers validators)
        super().__init__(**data)

        # Store captured Resource objects in private attribute
        self._connection_resources = connection_resources

    @field_validator('connections', mode='before')
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
            if hasattr(item, 'get_connection_context'):
                # Convert Resource to dict
                result.append(item.get_connection_context())
            else:
                # Already a dict
                result.append(item)
        return result

    @model_validator(mode='after')
    def convert_connections_to_dicts(self) -> 'Resource':
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
            if hasattr(item, 'get_connection_context'):
                # Convert Resource to context dict
                connection_contexts.append(item.get_connection_context())
            elif isinstance(item, dict):
                # Already a context dict
                connection_contexts.append(item)
            else:
                import logging
                logging.warning(f"Unknown connection type: {type(item)}, skipping")

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

    def get_connection_context(self) -> Dict[str, Any]:
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
        raise NotImplementedError(f"{self.__class__.__name__} must implement to_pulumi()")
