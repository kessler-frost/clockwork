"""Base resource classes for Clockwork."""

from typing import Dict, Any, Optional, List, TYPE_CHECKING, Union
from pydantic import BaseModel, Field, field_validator, PrivateAttr
from pydantic_core import core_schema

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

    Attributes:
        name: Optional unique identifier (can be AI-completed if None)
        description: Optional human-readable description (used as context for AI)
        assertions: Optional list of type-safe assertion objects for validation
        tools: Optional list of PydanticAI tools (duckduckgo_search_tool(), MCPServerStdio, etc.)
               for AI-powered completion operations
        connections: Optional list of Resource objects this resource depends on
    """

    name: Optional[str] = None
    description: Optional[str] = None
    assertions: Optional[List["BaseAssertion"]] = None
    connections: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Connection context from connected resources (auto-converted from Resource objects)"
    )
    _connection_resources: List["Resource"] = PrivateAttr(default_factory=list)

    # AI and integration capabilities
    tools: Optional[List[Any]] = None  # PydanticAI tools (duckduckgo_search_tool(), MCPServerStdio, etc.)

    def __init__(self, **data):
        """Custom init to preserve original Resource objects before validation."""
        # Extract and store original Resource objects before Pydantic converts them
        connection_resources = []
        if 'connections' in data:
            original_connections = data['connections']
            if original_connections:
                for item in original_connections:
                    if hasattr(item, 'get_connection_context'):
                        connection_resources.append(item)

        # Call super().__init__ first to initialize the Pydantic model
        super().__init__(**data)

        # Now set the private attribute after initialization
        self._connection_resources = connection_resources

    @field_validator('connections', mode='wrap')
    @classmethod
    def convert_resources_to_context(cls, v: Any, handler, info) -> List[Dict[str, Any]]:
        """Convert Resource objects to connection context dictionaries.

        This allows users to pass Resource objects, but stores them as plain
        dictionaries to avoid circular references during serialization.

        The original Resource objects are preserved in __init__ via the
        _connection_resources private attribute before this validator runs.

        Args:
            v: List of Resource objects or connection context dicts
            handler: The default validator
            info: Validation context

        Returns:
            List of connection context dictionaries
        """
        if not v:
            return []

        result = []
        for item in v:
            if isinstance(item, dict):
                # Already a dict, use as-is
                result.append(item)
            elif hasattr(item, 'get_connection_context'):
                # It's a Resource, convert to context
                result.append(item.get_connection_context())
            else:
                # Unknown type, skip with warning
                import logging
                logging.warning(f"Unknown connection type: {type(item)}, skipping")

        return result

    def needs_completion(self) -> bool:
        """Check if this resource needs AI completion for any fields.

        Override this method in subclasses to define which fields can be AI-completed.
        The default implementation only checks if name is None.

        Returns:
            True if any completable fields are None, False otherwise

        Example:
            class MyResource(Resource):
                content: Optional[str] = None

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
                port: Optional[int] = None
                host: Optional[str] = None

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
