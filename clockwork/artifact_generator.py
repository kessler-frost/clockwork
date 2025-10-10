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


class DockerConfig(BaseModel):
    """Structured output model for Docker image configuration."""
    image: str
    suggested_ports: Optional[List[str]] = None
    suggested_env_vars: Optional[Dict[str, str]] = None


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
            Dict mapping resource names to generated content (str or dict for Docker)
        """
        artifacts = {}

        for resource in resources:
            if resource.needs_artifact_generation():
                logger.info(f"Generating artifact for: {resource.name}")
                content = await self._agenerate_for_resource(resource)
                artifacts[resource.name] = content

                # Log based on content type
                if isinstance(content, dict):
                    logger.info(f"Generated Docker config for {resource.name}: {content}")
                else:
                    logger.info(f"Generated {len(content)} chars for {resource.name}")

        return artifacts

    async def _agenerate_for_resource(self, resource: Any) -> Any:
        """
        Generate content for a single resource using PydanticAI Agent (async version).

        Args:
            resource: Resource object needing content generation

        Returns:
            Generated content - either a string or a dict (for Docker resources)
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

        # Create PydanticAI Agent with structured output for Docker, plain for others
        if self._is_docker_resource(resource):
            agent = Agent(
                model,
                output_type=DockerConfig,
                system_prompt=self.SYSTEM_PROMPT
            )
        else:
            # Pass tools via the tools parameter for individual Tool objects
            # Note: PydanticAI requires a list (even empty []), not None
            agent = Agent(
                model,
                tools=tools,  # tools is already [] if resource.tools is None
                system_prompt=self.SYSTEM_PROMPT
            )

        # Get response from agent
        result = await agent.run(prompt)

        # Extract content from result
        content = result.output

        # Handle Docker resources specially
        if self._is_docker_resource(resource):
            return self._parse_docker_response(content, resource)

        return content

    def _parse_docker_response(self, content: Any, resource: Any) -> Dict[str, Any]:
        """
        Parse AI response for Docker resources.

        Args:
            content: AI-generated content (DockerConfig instance with structured output)
            resource: Docker resource object

        Returns:
            Dict with at least {"image": "..."} key
        """
        # With PydanticAI structured output, content is already a DockerConfig instance
        if isinstance(content, DockerConfig):
            parsed = content.model_dump()
            logger.info(f"Parsed Docker response for {resource.name}: {parsed}")
            return parsed

        # Fallback for unexpected format
        raise ValueError(f"Expected DockerConfig instance, got: {type(content)}")

    def _build_prompt(self, resource: Any) -> str:
        """Build generation prompt based on resource."""

        # Check if this is a DockerServiceResource
        if self._is_docker_resource(resource):
            return self._build_docker_prompt(resource)

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

    def _is_docker_resource(self, resource: Any) -> bool:
        """Check if resource is a AppleContainerResource (or legacy DockerServiceResource)."""
        return resource.__class__.__name__ in ('AppleContainerResource', 'DockerServiceResource')

    def _build_docker_prompt(self, resource: Any) -> str:
        """Build specialized prompt for container resources."""
        return f"""Based on this description: "{resource.description}"

Suggest an appropriate container image for this service.
Respond in JSON format:
{{
  "image": "imagename:tag",
  "suggested_ports": ["80:80"],
  "suggested_env_vars": {{"KEY": "value"}}
}}

If only the image is known, respond with just: {{"image": "imagename:tag"}}

Be specific and use official, well-maintained images when possible. Examples: nginx:alpine, redis:7-alpine, postgres:16-alpine"""

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
