"""
Artifact Generator - AI-powered content generation using PydanticAI + OpenRouter.
"""

import logging
from typing import Any, Dict, List, Optional

from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openrouter import OpenRouterProvider

from .settings import get_settings

logger = logging.getLogger(__name__)


class ContainerConfig(BaseModel):
    """Structured output model for complete container configuration."""
    name: str
    image: str
    ports: Optional[List[str]] = None
    volumes: Optional[List[str]] = None
    env_vars: Optional[Dict[str, str]] = None
    networks: Optional[List[str]] = None


class ArtifactGenerator:
    """Generates artifacts (file contents, configs, etc.) using AI via PydanticAI Agent."""

    # System prompt for AI generation
    SYSTEM_PROMPT = "You are a helpful assistant that generates high-quality content based on user requirements."

    # Size hints for artifact generation
    SIZE_HINTS = {
        "small": "Keep it concise, around 100-500 words.",
        "medium": "Provide moderate detail, around 500-2000 words.",
        "large": "Provide comprehensive coverage, 2000+ words."
    }

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None
    ):
        """
        Initialize the artifact generator.

        Args:
            api_key: OpenRouter API key (overrides settings/.env)
            model: Model ID to use (overrides settings/.env)
            base_url: OpenRouter API base URL (overrides settings/.env)
        """
        settings = get_settings()

        self.api_key = api_key or settings.openrouter_api_key
        if not self.api_key:
            raise ValueError(
                "OpenRouter API key required. Set CW_OPENROUTER_API_KEY in .env file "
                "or pass api_key parameter."
            )

        self.model = model or settings.openrouter_model
        self.base_url = base_url or settings.openrouter_base_url

        logger.info(f"Initialized ArtifactGenerator with model: {self.model}")

    async def generate(self, resources: List[Any]) -> Dict[str, Any]:
        """
        Generate artifacts for resources that need them (async version).

        Args:
            resources: List of Resource objects

        Returns:
            Dict mapping resource names to generated content (str or dict for containers)
        """
        artifacts = {}

        for resource in resources:
            if resource.needs_artifact_generation():
                logger.info(f"Generating artifact for: {resource.name}")
                content = await self._agenerate_for_resource(resource)
                artifacts[resource.name] = content

                # Log based on content type
                if isinstance(content, dict):
                    logger.info(f"Generated container config for {resource.name}: {content}")
                else:
                    logger.info(f"Generated {len(content)} chars for {resource.name}")

        return artifacts

    async def _agenerate_for_resource(self, resource: Any) -> Any:
        """
        Generate content for a single resource using PydanticAI Agent (async version).

        Args:
            resource: Resource object needing content generation

        Returns:
            Generated content - either a string or a dict (for container resources)
        """
        # Build prompt based on resource type
        prompt = self._build_prompt(resource)

        # Get tools from resource (handle None case)
        tools = resource.tools if resource.tools is not None else []
        logger.debug(f"Resource {resource.name} tools: {tools}, type: {type(tools)}")

        # Create OpenAI-compatible model pointing to OpenRouter
        model = OpenAIChatModel(
            self.model,
            provider=OpenRouterProvider(api_key=self.api_key)
        )

        # Create PydanticAI Agent
        # Note: We don't use output_type for container resources because
        # free OpenRouter models don't support structured outputs (tool use)
        agent = Agent(
            model,
            tools=tools,  # tools is already [] if resource.tools is None
            system_prompt=self.SYSTEM_PROMPT
        )

        # Get response from agent
        result = await agent.run(prompt)

        # Extract content from result
        content = result.output

        # Handle container resources specially - parse JSON from text response
        if self._is_container_resource(resource):
            return self._parse_container_response(content)

        return content

    def _parse_container_response(self, content: Any) -> Dict[str, Any]:
        """
        Parse AI response for container resources.

        Args:
            content: AI-generated content (either ContainerConfig instance or JSON string)

        Returns:
            Dict with complete container configuration (name, image, ports, volumes, env_vars, networks)
        """
        import json
        import re

        # With PydanticAI structured output, content is already a ContainerConfig instance
        if isinstance(content, ContainerConfig):
            parsed = content.model_dump()
            logger.info(f"Parsed container response: {parsed}")
            return parsed

        # Parse JSON from text response (for models without structured output support)
        if isinstance(content, str):
            # Try to extract JSON from the response
            # Look for JSON block (with or without markdown code fences)
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # Try to find raw JSON object
                json_match = re.search(r'\{.*?\}', content, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                else:
                    raise ValueError(f"No JSON found in response: {content}")

            try:
                parsed = json.loads(json_str)
                # Validate required fields
                if "name" not in parsed:
                    raise ValueError(f"Response JSON missing 'name' key: {parsed}")
                if "image" not in parsed:
                    raise ValueError(f"Response JSON missing 'image' key: {parsed}")
                logger.info(f"Parsed container response: {parsed}")
                return parsed
            except json.JSONDecodeError as e:
                raise ValueError(f"Failed to parse JSON from response: {json_str}. Error: {e}")

        # Fallback for unexpected format
        raise ValueError(f"Expected ContainerConfig instance or string, got: {type(content)}")

    def _build_prompt(self, resource: Any) -> str:
        """Build generation prompt based on resource."""

        # Check if this is a container resource
        if self._is_container_resource(resource):
            return self._build_container_prompt(resource)

        # Base prompt
        prompt = f"Generate content for: {resource.description}\n\n"

        # Add size guidance
        if resource.size is not None:
            prompt += self.SIZE_HINTS.get(resource.size.value, "")

        # Add format hints based on filename
        if resource.name:
            if resource.name.endswith('.md'):
                prompt += "\n\nFormat the output as Markdown."
            elif resource.name.endswith('.json'):
                prompt += "\n\nFormat the output as valid JSON."
            elif resource.name.endswith('.yaml') or resource.name.endswith('.yml'):
                prompt += "\n\nFormat the output as valid YAML."

        return prompt

    def _is_container_resource(self, resource: Any) -> bool:
        """Check if resource is a AppleContainerResource."""
        return resource.__class__.__name__ == 'AppleContainerResource'

    def _build_container_prompt(self, resource: Any) -> str:
        """Build specialized prompt for container resources with full completion."""
        # Collect what the user has already specified
        user_specified = []
        if resource.name is not None:
            user_specified.append(f"name: {resource.name}")
        if resource.image is not None:
            user_specified.append(f"image: {resource.image}")
        if resource.ports is not None:
            user_specified.append(f"ports: {resource.ports}")
        if resource.volumes is not None:
            user_specified.append(f"volumes: {resource.volumes}")
        if resource.env_vars is not None:
            user_specified.append(f"env_vars: {resource.env_vars}")
        if resource.networks is not None:
            user_specified.append(f"networks: {resource.networks}")

        user_spec_str = "\n".join(user_specified) if user_specified else "None"

        return f"""Based on this description: "{resource.description}"

User has already specified:
{user_spec_str}

Complete the missing container configuration fields. Provide intelligent defaults based on the description and best practices.

Respond in JSON format with ALL fields (even if some were already specified):
{{
  "name": "container-name",
  "image": "imagename:tag",
  "ports": ["80:80", "443:443"],
  "volumes": ["volume_name:/container/path"],
  "env_vars": {{"KEY": "value"}},
  "networks": ["network-name"]
}}

Guidelines:
- name: Short, descriptive service name (e.g., "nginx-server", "postgres-db", "redis-cache")
- image: Use official, well-maintained images with specific version tags (e.g., nginx:alpine, redis:7-alpine, postgres:16-alpine)
- ports: Standard ports for the service in "host:container" format
- volumes: Data persistence locations if needed (can be empty array if not needed)
- env_vars: Required environment variables (can be empty object if not needed)
- networks: Container networks to attach (can be empty array for simple cases)

If user already specified a field, KEEP their value. Only complete the missing fields."""

    def _get_max_tokens(self, resource: Any) -> int:
        """Get max tokens based on resource size."""
        if not hasattr(resource, 'size') or resource.size is None:
            return 1000

        size_tokens = {
            "small": 1000,
            "medium": 3000,
            "large": 6000,
        }
        return size_tokens.get(resource.size.value, 1000)
