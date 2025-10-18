"""
Resource Completer - AI-powered resource completion using PydanticAI structured outputs.

This module uses schema-native completion where Pydantic Field descriptions define
the AI's task. No prompts needed - the schema IS the prompt!
"""

import logging
from typing import Any, List

from pydantic_ai import Agent, InlineDefsJsonSchemaTransformer, ModelRetry, RunContext
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.profiles.openai import OpenAIModelProfile

from .service.tools import ToolSelector
from .settings import get_settings

logger = logging.getLogger(__name__)


class ResourceCompleter:
    """Completes partial resources using AI via PydanticAI structured outputs."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        tool_selector: ToolSelector | None = None,
        enable_tool_selection: bool = True
    ):
        """
        Initialize the resource completer.

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
        self.tool_selector = tool_selector or (ToolSelector() if enable_tool_selection else None)

        logger.info(
            f"Initialized ResourceCompleter with model: {self.model} at {self.base_url} "
            f"(tool selection: {enable_tool_selection})"
        )

    async def complete(self, resources: List[Any]) -> List[Any]:
        """
        Complete partial resources using AI (async version).

        Args:
            resources: List of Resource objects (some may be partial)

        Returns:
            List of completed Resource objects with all fields filled
        """
        completed_resources = []

        for resource in resources:
            if resource.needs_completion():
                logger.info(f"Completing resource: {resource.name}")
                completed = await self._complete_resource(resource)
                completed_resources.append(completed)
                logger.info(f"Completed resource: {completed.name}")
            else:
                logger.info(f"Resource already complete: {resource.name}")
                completed_resources.append(resource)

        return completed_resources

    async def _complete_resource(self, resource: Any) -> Any:
        """
        Complete a single resource using PydanticAI Agent (async version).
        Uses schema-native completion - Field descriptions define the contract.

        Args:
            resource: Partial Resource object needing completion

        Returns:
            Completed Resource object with all fields filled
        """
        # Get tools: prioritize user-provided tools, then use ToolSelector
        tools = []
        if resource.tools is not None and len(resource.tools) > 0:
            tools = resource.tools
            logger.debug(f"Using {len(tools)} user-provided tools")
        elif self.enable_tool_selection and self.tool_selector:
            context = resource.description or ""
            tools = self.tool_selector.select_tools_for_resource(resource, context)
            logger.debug(f"ToolSelector chose {len(tools)} tools")

        # Create OpenAI-compatible model
        model = OpenAIChatModel(
            self.model,
            provider=OpenAIProvider(
                base_url=self.base_url,
                api_key=self.api_key
            ),
            profile=OpenAIModelProfile(
                json_schema_transformer=InlineDefsJsonSchemaTransformer,
                openai_supports_strict_tool_definition=False
            )
        )

        # Create PydanticAI Agent with minimal system prompt
        # Schema provides the detailed contract via Field descriptions
        settings = get_settings()
        agent = Agent(
            model,
            tools=tools,
            system_prompt="Complete the infrastructure resource by filling in all required fields based on the description. Use the schema field descriptions and examples as your guide.",
            output_type=resource.__class__,
            retries=settings.completion_max_retries,
        )

        # Add output validator to ensure required fields are completed
        @agent.output_validator
        async def validate_required_fields(ctx: RunContext, output: Any) -> Any:
            """Validate that all required fields defined by needs_completion() are filled."""
            if output.needs_completion():
                logger.warning(f"AI failed to complete required fields for {output.__class__.__name__}")
                raise ModelRetry(
                    f"The resource still has incomplete required fields. "
                    f"You MUST provide actual non-None values for ALL required fields. "
                    f"Review the resource definition and fill in any missing required fields. "
                    f"Do NOT leave required fields as None."
                )
            return output

        # Build user message including description and current state
        user_data = resource.model_dump(exclude={'tools', 'assertions', 'connections'})
        provided_fields = {k: v for k, v in user_data.items() if v is not None}

        # Create message showing what's provided and what needs completion
        if provided_fields:
            provided_str = "\n".join([f"- {k}: {v}" for k, v in provided_fields.items()])
            user_message = f"{resource.description}\n\nAlready provided:\n{provided_str}"
        else:
            user_message = resource.description

        # Run agent with description and current state
        result = await agent.run(user_message)

        # Merge user-provided values with AI suggestions
        final_resource = self._merge_resources(resource, result.output)

        return final_resource

    def _merge_resources(self, user_resource: Any, ai_resource: Any) -> Any:
        """
        Merge user-provided resource with AI-completed resource.

        User-provided values take precedence over AI suggestions.

        Args:
            user_resource: Original partial resource from user
            ai_resource: AI-completed resource with all fields

        Returns:
            Merged resource with user overrides applied
        """
        # Get all field values from user resource
        user_data = user_resource.model_dump(exclude_unset=False)
        ai_data = ai_resource.model_dump(exclude_unset=False)

        # Merge: user values override AI values
        # For each field, use user value if not None, otherwise use AI value
        merged_data = {}
        for field_name in user_data.keys():
            user_value = user_data[field_name]
            ai_value = ai_data.get(field_name)

            # Priority: user value > AI value
            # BUT: if user value is None and AI has a value, use AI's
            if user_value is not None:
                merged_data[field_name] = user_value
            elif ai_value is not None:
                merged_data[field_name] = ai_value
            else:
                merged_data[field_name] = None

        # Preserve connections from user resource (not part of AI completion)
        # Connections are already converted to dicts by the field validator
        if hasattr(user_resource, 'connections') and user_resource.connections:
            merged_data['connections'] = user_resource.connections

        # Preserve assertions from user resource (not part of AI completion)
        # Assertions should always come from the user, never generated by AI
        if hasattr(user_resource, 'assertions') and user_resource.assertions:
            merged_data['assertions'] = user_resource.assertions

        # Create new resource instance with merged data
        return user_resource.__class__(**merged_data)
