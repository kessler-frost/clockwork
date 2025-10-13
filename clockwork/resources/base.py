"""Base resource classes for Clockwork."""

from typing import Dict, Any, Optional, List, TYPE_CHECKING, Union
from pydantic import BaseModel, Field, field_validator, PrivateAttr, model_validator
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
    4. PyInfra operations use self.* fields directly (no artifacts dict needed)

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

        Args:
            v: List of Resource objects or connection context dicts
            handler: The default validator
            info: Validation context

        Returns:
            List of connection context dictionaries
        """
        # Get the raw value before validation
        if not v:
            return []

        result = []
        connection_resources = []

        for item in v:
            if isinstance(item, dict):
                # Already a dict, use as-is
                result.append(item)
            elif hasattr(item, 'get_connection_context'):
                # It's a Resource, convert to context and store the resource
                result.append(item.get_connection_context())
                connection_resources.append(item)
            else:
                # Unknown type, skip with warning
                import logging
                logging.warning(f"Unknown connection type: {type(item)}, skipping")

        # Store the resource objects in the instance's _connection_resources
        # We can access the instance through info.context if it's a model_validator
        # But for field_validator, we need to store it temporarily and set it in model_validator
        if hasattr(info, 'context') and info.context and '_temp_connection_resources' in info.context:
            info.context['_temp_connection_resources'] = connection_resources

        return result

    @model_validator(mode='after')
    def store_connection_resources(self) -> 'Resource':
        """Store connection resources after validation.

        This runs after all fields are validated, allowing us to properly
        store the _connection_resources private attribute.
        """
        # The connections have already been converted to dicts by the field validator
        # We need to extract the original Resource objects from somewhere...
        # This approach won't work because we've lost the original objects by this point
        return self

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

    def to_pyinfra_operations(self) -> str:
        """Generate PyInfra operations code (template-based).

        This method is called after AI completion, so all required fields should
        be populated. Access fields directly via self.* instead of using an
        artifacts dict.

        Returns:
            String of PyInfra operation code

        Example:
            def to_pyinfra_operations(self) -> str:
                return f'''
files.file(
    name="Create {self.name}",
    path="/tmp/{self.name}",
    content="{self.content}"
)
'''
        """
        raise NotImplementedError(f"{self.__class__.__name__} must implement to_pyinfra_operations()")

    def to_pyinfra_destroy_operations(self) -> str:
        """Generate PyInfra operations code to destroy/remove this resource.

        Access resource fields directly via self.* to generate cleanup operations.

        Returns:
            String of PyInfra operation code to destroy the resource

        Example:
            def to_pyinfra_destroy_operations(self) -> str:
                return f'''
files.file(
    name="Remove {self.name}",
    path="/tmp/{self.name}",
    present=False
)
'''
        """
        raise NotImplementedError(f"{self.__class__.__name__} must implement to_pyinfra_destroy_operations()")

    def to_pyinfra_assert_operations(self) -> str:
        """Generate PyInfra operations code for assertions.

        Only processes BaseAssertion objects (type-safe assertions).
        Access resource fields directly via self.* when generating assertions.

        Returns:
            String of PyInfra assertion operation code
        """
        if not self.assertions:
            return ""

        # Import here to avoid circular imports
        from clockwork.assertions.base import BaseAssertion

        operations = []
        has_object_assertions = any(isinstance(a, BaseAssertion) for a in self.assertions)

        if not has_object_assertions:
            return ""

        operations.append(f"\n# Assertions for resource: {self.name}")

        for assertion in self.assertions:
            # Only handle BaseAssertion objects
            if isinstance(assertion, BaseAssertion):
                operations.append(assertion.to_pyinfra_operation(self))

        return "\n".join(operations)
