"""
Resource Completer - AI-powered resource completion using PydanticAI structured outputs.

This module uses schema-native completion where Pydantic Field descriptions define
the AI's task. No prompts needed - the schema IS the prompt!
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

from .settings import get_settings
from .tool_selector import ToolSelector

logger = logging.getLogger(__name__)


class ResourceCompleter:
    """Completes partial resources using AI via PydanticAI structured outputs."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        tool_selector: ToolSelector | None = None,
        enable_tool_selection: bool = True,
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
        self.tool_selector = tool_selector or (
            ToolSelector() if enable_tool_selection else None
        )

        logger.info(
            f"Initialized ResourceCompleter with model: {self.model} at {self.base_url} "
            f"(tool selection: {enable_tool_selection})"
        )

    async def complete(self, resources: list[Any]) -> list[Any]:
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

                # Detect composite resources and use two-phase completion
                if self._is_composite(resource):
                    logger.info(f"Detected composite resource: {resource.name}")
                    completed = await self._complete_composite(resource)
                else:
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
            tools = self.tool_selector.select_tools_for_resource(
                resource, context
            )
            logger.debug(f"ToolSelector chose {len(tools)} tools")

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
                logger.warning(
                    f"AI failed to complete required fields for {output.__class__.__name__}"
                )
                raise ModelRetry(
                    "The resource still has incomplete required fields. "
                    "You MUST provide actual non-None values for ALL required fields. "
                    "Review the resource definition and fill in any missing required fields. "
                    "Do NOT leave required fields as None."
                )
            return output

        # Build user message including description and current state
        user_data = resource.model_dump(
            exclude={"tools", "assertions", "connections"}
        )
        provided_fields = {k: v for k, v in user_data.items() if v is not None}

        # Create message showing what's provided and what needs completion
        if provided_fields:
            provided_str = "\n".join(
                [f"- {k}: {v}" for k, v in provided_fields.items()]
            )
            user_message = (
                f"{resource.description}\n\nAlready provided:\n{provided_str}"
            )
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
        for field_name in user_data:
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
        if hasattr(user_resource, "connections") and user_resource.connections:
            merged_data["connections"] = user_resource.connections

        # Preserve assertions from user resource (not part of AI completion)
        # Assertions should always come from the user, never generated by AI
        if hasattr(user_resource, "assertions") and user_resource.assertions:
            merged_data["assertions"] = user_resource.assertions

        # Create new resource instance with merged data
        return user_resource.__class__(**merged_data)

    def _is_composite(self, resource: Any) -> bool:
        """
        Detect if a resource is a composite resource with children.

        Checks for the _children attribute (dict of child resources).

        Args:
            resource: Resource object to check

        Returns:
            True if resource has children, False otherwise
        """
        # Check for _children attribute (new property-based API)
        if hasattr(resource, "_children"):
            children = getattr(resource, "_children", None)
            return children is not None and len(children) > 0

        # Fallback: check for public children attribute
        if hasattr(resource, "children"):
            children = getattr(resource, "children", None)
            return children is not None and len(children) > 0

        return False

    def _get_children(self, resource: Any) -> list[Any]:
        """
        Get child resources from a composite resource.

        Args:
            resource: Composite resource object

        Returns:
            List of child Resource objects (may be empty)
        """
        # Use _children list (internal list of child resources)
        if hasattr(resource, "_children"):
            children_list = getattr(resource, "_children", None)
            if children_list is not None:
                return children_list  # _children is already a list

        # Fallback to public children attribute (which returns ChildrenCollection)
        if hasattr(resource, "children"):
            children = getattr(resource, "children", None)
            if children is not None:
                return list(
                    children.values()
                )  # Convert ChildrenCollection to list

        return []

    def _set_children(self, resource: Any, children: list[Any]) -> None:
        """
        Set child resources on a composite resource.

        Args:
            resource: Composite resource object
            children: List of completed child Resource objects
        """
        # Use _children property (new property-based API)
        # Rebuild the dict by preserving the keys (names) and updating values
        if hasattr(resource, "_children"):
            # Clear existing children and rebuild
            resource._children.clear()
            for child in children:
                child_name = child.name or f"child_{id(child)}"
                resource._children[child_name] = child
            return

        # Fall back to direct attribute assignment for public children
        if hasattr(resource, "children"):
            resource.children = children
        else:
            logger.warning(
                f"Cannot set children on {resource.name}: no _children or children attribute"
            )

    async def _complete_composite(
        self, resource: Any, parent_context: str | None = None
    ) -> Any:
        """
        Complete a composite resource using two-phase completion.

        Phase 1: Complete the parent resource with all children visible as context
        Phase 2: Complete each child resource individually with parent context

        This enables the AI to:
        - Understand the full composite structure and purpose
        - Generate parent field values considering child relationships
        - Complete children with awareness of parent's description and purpose
        - Maintain internal consistency across the composite

        Args:
            resource: Composite resource object with children
            parent_context: Optional context from a parent composite (for nested composites)

        Returns:
            Completed composite resource with completed children
        """
        logger.info(
            f"Starting two-phase completion for composite resource: {resource.name}"
        )

        # Get children before completion
        children = self._get_children(resource)
        logger.info(
            f"Composite resource {resource.name} has {len(children)} children"
        )

        # PHASE 1: Complete the parent resource with children visible as context
        logger.info(f"Phase 1: Completing parent resource {resource.name}")

        # Build enhanced user message including parent context and children info
        user_data = resource.model_dump(
            exclude={"tools", "assertions", "connections", "children"}
        )
        provided_fields = {k: v for k, v in user_data.items() if v is not None}

        # Add children context to the message
        children_context = self._build_children_context(children)

        # Build parent message
        parent_message_parts = []
        if parent_context:
            parent_message_parts.append(f"Parent context: {parent_context}")

        parent_message_parts.append(
            resource.description or "Complete this composite resource"
        )

        if provided_fields:
            provided_str = "\n".join(
                [f"- {k}: {v}" for k, v in provided_fields.items()]
            )
            parent_message_parts.append(f"\nAlready provided:\n{provided_str}")

        if children_context:
            parent_message_parts.append(
                f"\nChildren in this composite:\n{children_context}"
            )

        parent_message = "\n\n".join(parent_message_parts)

        # Complete parent with standard single-resource completion
        # (temporarily remove children to avoid schema issues)
        resource_copy = resource.model_copy()
        if hasattr(resource_copy, "children"):
            resource_copy.children = []

        completed_parent = await self._complete_resource_with_message(
            resource_copy, parent_message
        )

        # PHASE 2: Complete each child resource with parent context
        logger.info(f"Phase 2: Completing {len(children)} children")

        completed_children = []
        parent_context_for_children = self._build_parent_context(
            completed_parent
        )

        for i, child in enumerate(children):
            logger.info(
                f"Completing child {i + 1}/{len(children)}: {child.name or 'unnamed'}"
            )

            # Check if child needs completion
            if not child.needs_completion():
                logger.info(
                    f"Child {child.name or 'unnamed'} already complete, skipping"
                )
                completed_children.append(child)
                continue

            # Recursive: if child is also composite, use two-phase completion
            if self._is_composite(child):
                logger.info(
                    f"Child {child.name or 'unnamed'} is composite, using recursive completion"
                )
                completed_child = await self._complete_composite(
                    child, parent_context_for_children
                )
            else:
                # Complete child with parent context
                completed_child = await self._complete_child_resource(
                    child, parent_context_for_children
                )

            completed_children.append(completed_child)

        # Set completed children on the parent
        self._set_children(completed_parent, completed_children)

        logger.info(
            f"Two-phase completion finished for composite resource: {completed_parent.name}"
        )
        return completed_parent

    def _build_children_context(self, children: list[Any]) -> str:
        """
        Build context string describing child resources.

        Args:
            children: List of child Resource objects

        Returns:
            Formatted string describing children
        """
        if not children:
            return ""

        context_parts = []
        for i, child in enumerate(children):
            child_data = child.model_dump(
                exclude={"tools", "assertions", "connections", "children"}
            )
            child_info = f"  {i + 1}. {child.__class__.__name__}"

            if child.name:
                child_info += f" (name: {child.name})"

            if child.description:
                child_info += f" - {child.description}"

            # Add key non-None fields
            key_fields = {
                k: v
                for k, v in child_data.items()
                if v is not None and k not in ["name", "description"]
            }
            if key_fields:
                fields_str = ", ".join(
                    [f"{k}={v}" for k, v in key_fields.items()]
                )
                child_info += f" [{fields_str}]"

            context_parts.append(child_info)

        return "\n".join(context_parts)

    def _build_parent_context(self, parent: Any) -> str:
        """
        Build context string from parent resource for child completion.

        Args:
            parent: Parent Resource object

        Returns:
            Formatted string with parent context
        """
        context_parts = [
            f"This resource is part of {parent.name or 'a composite resource'}"
        ]

        if parent.description:
            context_parts.append(f"Parent purpose: {parent.description}")

        # Add key parent fields that might be useful for children
        parent_data = parent.model_dump(
            exclude={"tools", "assertions", "connections", "children"}
        )
        key_fields = {
            k: v
            for k, v in parent_data.items()
            if v is not None and k not in ["name", "description"]
        }

        if key_fields:
            fields_str = ", ".join([f"{k}={v}" for k, v in key_fields.items()])
            context_parts.append(f"Parent configuration: {fields_str}")

        return ". ".join(context_parts)

    async def _complete_child_resource(
        self, resource: Any, parent_context: str
    ) -> Any:
        """
        Complete a child resource with parent context.

        Args:
            resource: Child resource to complete
            parent_context: Context string from parent resource

        Returns:
            Completed child resource
        """
        # Build message including parent context
        user_data = resource.model_dump(
            exclude={"tools", "assertions", "connections"}
        )
        provided_fields = {k: v for k, v in user_data.items() if v is not None}

        message_parts = [parent_context]
        message_parts.append(resource.description or "Complete this resource")

        if provided_fields:
            provided_str = "\n".join(
                [f"- {k}: {v}" for k, v in provided_fields.items()]
            )
            message_parts.append(f"\nAlready provided:\n{provided_str}")

        user_message = "\n\n".join(message_parts)

        return await self._complete_resource_with_message(
            resource, user_message
        )

    async def _complete_resource_with_message(
        self, resource: Any, user_message: str
    ) -> Any:
        """
        Complete a resource with a custom user message.

        This is a variant of _complete_resource() that accepts a pre-built message
        instead of constructing it from resource fields. Used for composite completion
        where we need to inject parent/children context.

        Args:
            resource: Partial Resource object needing completion
            user_message: Custom user message with context

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
            tools = self.tool_selector.select_tools_for_resource(
                resource, context
            )
            logger.debug(f"ToolSelector chose {len(tools)} tools")

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

        # Create PydanticAI Agent with minimal system prompt
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
                logger.warning(
                    f"AI failed to complete required fields for {output.__class__.__name__}"
                )
                raise ModelRetry(
                    "The resource still has incomplete required fields. "
                    "You MUST provide actual non-None values for ALL required fields. "
                    "Review the resource definition and fill in any missing required fields. "
                    "Do NOT leave required fields as None."
                )
            return output

        # Run agent with custom message
        result = await agent.run(user_message)

        # Merge user-provided values with AI suggestions
        final_resource = self._merge_resources(resource, result.output)

        return final_resource
