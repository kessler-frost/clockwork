"""
Connection Completer - AI-powered connection completion using PydanticAI structured outputs.

Similar to ResourceCompleter but for Connection objects.
"""

import logging
from typing import Any

from pydantic_ai import (
    Agent,
    InlineDefsJsonSchemaTransformer,
    ModelRetry,
    RunContext,
)
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.profiles.openai import OpenAIModelProfile
from pydantic_ai.providers.openai import OpenAIProvider

from .model_loader import LMStudioModelLoader
from .settings import get_settings
from .tool_selector import ToolSelector

logger = logging.getLogger(__name__)


class ConnectionCompleter:
    """Completes partial connections using AI via PydanticAI structured outputs."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        tool_selector: ToolSelector | None = None,
        enable_tool_selection: bool = True,
    ):
        """
        Initialize the connection completer.

        Args:
            api_key: API key for AI service (overrides settings/.env)
            model: Model name to use (overrides settings/.env)
            base_url: Base URL for API endpoint (overrides settings/.env)
            tool_selector: Optional ToolSelector instance for intelligent tool selection
            enable_tool_selection: Whether to enable automatic tool selection (default: True)
        """
        settings = get_settings()

        self.api_key = api_key or settings.api_key
        if not self.api_key:
            raise ValueError(
                "API key required. Set CW_API_KEY in .env file or pass api_key parameter."
            )

        self.model = model or settings.model
        self.base_url = base_url or settings.base_url

        # Tool selection setup
        self.enable_tool_selection = enable_tool_selection
        self.tool_selector = tool_selector or (
            ToolSelector() if enable_tool_selection else None
        )

        # LM Studio auto-loading setup
        self.lmstudio_loader: LMStudioModelLoader | None = None
        if LMStudioModelLoader.is_lmstudio_endpoint(self.base_url):
            self.lmstudio_loader = LMStudioModelLoader()
            logger.info(
                f"LM Studio endpoint detected, will auto-load model: {self.model}"
            )

        logger.info(
            f"Initialized ConnectionCompleter with model: {self.model} at {self.base_url} "
            f"(tool selection: {enable_tool_selection})"
        )

    async def _ensure_model_loaded(self) -> None:
        """
        Ensure the model is loaded in LM Studio if using LM Studio endpoint.

        This is a no-op for non-LM Studio endpoints.

        Raises:
            Exception: If model loading fails (connection, model not found, etc.)
        """
        if self.lmstudio_loader:
            await self.lmstudio_loader.load_model(self.model)

    async def complete(
        self, connections: list[Any], resources: list[Any]
    ) -> list[Any]:
        """
        Complete partial connections using AI (async version).

        Args:
            connections: List of Connection objects (some may be partial)
            resources: List of all Resource objects (for context)

        Returns:
            List of completed Connection objects with all fields filled
        """
        completed_connections = []

        for connection in connections:
            if connection.needs_completion():
                logger.info(
                    f"Completing connection: {connection.__class__.__name__} "
                    f"from {connection.from_resource.name} to {connection.to_resource.name}"
                )

                completed = await self._complete_connection(
                    connection, resources
                )

                completed_connections.append(completed)
                logger.info(
                    f"Completed connection: {completed.__class__.__name__}"
                )
            else:
                logger.info(
                    f"Connection already complete: {connection.__class__.__name__}"
                )
                completed_connections.append(connection)

        return completed_connections

    async def _complete_connection(
        self, connection: Any, resources: list[Any]
    ) -> Any:
        """
        Complete a single connection using PydanticAI Agent.

        Builds context from both from_resource and to_resource for AI completion.

        Args:
            connection: Partial Connection object needing completion
            resources: List of all Resource objects (for context)

        Returns:
            Completed Connection object with all fields filled
        """
        # Get tools from connection or use tool selector
        tools = []
        if hasattr(connection, "tools") and connection.tools is not None:
            tools = connection.tools
            logger.debug(f"Using {len(tools)} user-provided tools")
        elif self.enable_tool_selection and self.tool_selector:
            context = connection.description or ""
            # Use tool selector if available
            if hasattr(self.tool_selector, "select_tools_for_connection"):
                tools = self.tool_selector.select_tools_for_connection(
                    connection, context
                )
            logger.debug(f"ToolSelector chose {len(tools)} tools")

        # Ensure model is loaded (LM Studio auto-loading)
        await self._ensure_model_loaded()

        # Create OpenAI-compatible model
        model = OpenAIChatModel(
            self.model,
            provider=OpenAIProvider(
                base_url=self.base_url, api_key=self.api_key
            ),
            profile=OpenAIModelProfile(
                json_schema_transformer=InlineDefsJsonSchemaTransformer,
                openai_supports_strict_tool_definition=False,
            ),
        )

        # Create PydanticAI Agent
        settings = get_settings()
        agent = Agent(
            model,
            tools=tools,
            system_prompt="Complete the infrastructure connection by filling in all required fields based on the description and endpoint resources. Use the schema field descriptions and examples as your guide.",
            output_type=connection.__class__,
            retries=settings.completion_max_retries,
        )

        # Add output validator to ensure required fields are completed
        @agent.output_validator
        async def validate_required_fields(ctx: RunContext, output: Any) -> Any:
            """Validate that all required fields defined by needs_completion() are filled."""
            if output.needs_completion():
                logger.warning(
                    f"AI failed to complete required fields for {output.__class__.__name__}"
                )
                raise ModelRetry(
                    "The connection still has incomplete required fields. "
                    "You MUST provide actual non-None values for ALL required fields. "
                    "Review the connection definition and fill in any missing required fields. "
                    "Do NOT leave required fields as None."
                )
            return output

        # Build user message including connection description and endpoint context
        connection_data = connection.model_dump(exclude={"tools", "assertions"})
        provided_fields = {
            k: v for k, v in connection_data.items() if v is not None
        }

        # Build context from endpoints
        from_context = {}
        to_context = {}

        if connection.from_resource is not None:
            if hasattr(connection.from_resource, "get_connection_context"):
                from_context = connection.from_resource.get_connection_context()
            else:
                from_context = {
                    "name": getattr(connection.from_resource, "name", None),
                    "type": connection.from_resource.__class__.__name__,
                }

        if connection.to_resource is not None:
            if hasattr(connection.to_resource, "get_connection_context"):
                to_context = connection.to_resource.get_connection_context()
            else:
                to_context = {
                    "name": getattr(connection.to_resource, "name", None),
                    "type": connection.to_resource.__class__.__name__,
                }

        # Create message showing what's provided and what needs completion
        message_parts = []

        if connection.description:
            message_parts.append(connection.description)

        if from_context:
            from_str = "\n".join(
                [f"  - {k}: {v}" for k, v in from_context.items()]
            )
            message_parts.append(f"\nFrom resource:\n{from_str}")

        if to_context:
            to_str = "\n".join([f"  - {k}: {v}" for k, v in to_context.items()])
            message_parts.append(f"\nTo resource:\n{to_str}")

        if provided_fields:
            provided_str = "\n".join(
                [f"- {k}: {v}" for k, v in provided_fields.items()]
            )
            message_parts.append(f"\nAlready provided:\n{provided_str}")

        user_message = "\n\n".join(message_parts)

        # Run agent with description and context
        result = await agent.run(user_message)

        # Merge user-provided values with AI suggestions
        final_connection = self._merge_connections(connection, result.output)

        return final_connection

    def _merge_connections(
        self, user_connection: Any, ai_connection: Any
    ) -> Any:
        """
        Merge user-provided connection with AI-completed connection.

        User-provided values take precedence over AI suggestions.

        Args:
            user_connection: Original partial connection from user
            ai_connection: AI-completed connection with all fields

        Returns:
            Merged connection with user overrides applied
        """
        # Get all field values from user connection
        user_data = user_connection.model_dump(exclude_unset=False)
        ai_data = ai_connection.model_dump(exclude_unset=False)

        # Merge: user values override AI values
        merged_data = {}
        for field_name in user_data:
            user_value = user_data[field_name]
            ai_value = ai_data.get(field_name)

            # Priority: user value > AI value
            if user_value is not None:
                merged_data[field_name] = user_value
            elif ai_value is not None:
                merged_data[field_name] = ai_value
            else:
                merged_data[field_name] = None

        # Preserve assertions from user connection (not part of AI completion)
        if (
            hasattr(user_connection, "assertions")
            and user_connection.assertions
        ):
            merged_data["assertions"] = user_connection.assertions

        # Preserve endpoint resources (should not change)
        merged_data["from_resource"] = user_connection.from_resource
        merged_data["to_resource"] = user_connection.to_resource

        # Create new connection instance with merged data
        return user_connection.__class__(**merged_data)
