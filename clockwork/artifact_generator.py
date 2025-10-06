"""
Artifact Generator - AI-powered content generation using Agno 2.0 + OpenRouter.
"""

import json
import logging
from typing import Any, Dict, List, Optional

from agno.agent import Agent
from openai import OpenAI

from .settings import get_settings

logger = logging.getLogger(__name__)


class ArtifactGenerator:
    """Generates artifacts (file contents, configs, etc.) using AI via OpenRouter."""

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
                "OpenRouter API key required. Set OPENROUTER_API_KEY in .env file "
                "or pass api_key parameter."
            )

        self.model = model or settings.openrouter_model
        self.base_url = base_url or settings.openrouter_base_url

        # Initialize OpenAI client pointing to OpenRouter
        self.client = OpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
        )

        logger.info(f"Initialized ArtifactGenerator with model: {self.model}")

    def generate(self, resources: List[Any]) -> Dict[str, Any]:
        """
        Generate artifacts for resources that need them.

        Args:
            resources: List of Resource objects

        Returns:
            Dict mapping resource names to generated content (str or dict for Docker)
        """
        artifacts = {}

        for resource in resources:
            if resource.needs_artifact_generation():
                logger.info(f"Generating artifact for: {resource.name}")
                content = self._generate_for_resource(resource)
                artifacts[resource.name] = content

                # Log based on content type
                if isinstance(content, dict):
                    logger.info(f"Generated Docker config for {resource.name}: {content}")
                else:
                    logger.info(f"Generated {len(content)} chars for {resource.name}")

        return artifacts

    def _generate_for_resource(self, resource: Any) -> Any:
        """
        Generate content for a single resource.

        Args:
            resource: Resource object needing content generation

        Returns:
            Generated content - either a string or a dict (for Docker resources)
        """
        # Build prompt based on resource type
        prompt = self._build_prompt(resource)

        # Call OpenRouter via OpenAI client
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that generates high-quality content based on user requirements."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=self._get_max_tokens(resource),
            )

            content = response.choices[0].message.content.strip()

            # Handle Docker resources specially
            if self._is_docker_resource(resource):
                return self._parse_docker_response(content, resource)

            return content

        except Exception as e:
            logger.error(f"Failed to generate artifact for {resource.name}: {e}")
            raise

    def _parse_docker_response(self, content: str, resource: Any) -> Dict[str, Any]:
        """
        Parse AI response for Docker resources.

        Handles both JSON format and simple string format, including markdown code blocks.

        Args:
            content: AI-generated content
            resource: Docker resource object

        Returns:
            Dict with at least {"image": "..."} key
        """
        # Strip markdown code blocks if present
        cleaned_content = content.strip()
        if cleaned_content.startswith('```'):
            # Remove opening code block marker (```json or ```)
            lines = cleaned_content.split('\n')
            if lines[0].startswith('```'):
                lines = lines[1:]
            # Remove closing code block marker
            if lines and lines[-1].strip() == '```':
                lines = lines[:-1]
            cleaned_content = '\n'.join(lines).strip()

        try:
            # Try to parse as JSON first
            parsed = json.loads(cleaned_content)

            # Ensure it's a dict
            if isinstance(parsed, dict):
                # Ensure 'image' key exists
                if 'image' in parsed:
                    logger.info(f"Parsed Docker response as JSON for {resource.name}: {parsed}")
                    return parsed
                else:
                    logger.warning(f"JSON response missing 'image' key for {resource.name}, using content as image")
                    return {"image": cleaned_content}
            else:
                # JSON parsed but not a dict (maybe just a string)
                logger.warning(f"JSON parsed but not a dict for {resource.name}, using as image")
                return {"image": str(parsed)}

        except json.JSONDecodeError:
            # Not valid JSON, treat as simple string (image name)
            logger.info(f"Treating Docker response as simple image string for {resource.name}: {cleaned_content}")
            return {"image": cleaned_content}
        except Exception as e:
            logger.error(f"Error parsing Docker response for {resource.name}: {e}")
            # Fallback to treating as image name
            return {"image": cleaned_content}

    def _build_prompt(self, resource: Any) -> str:
        """Build generation prompt based on resource."""

        # Check if this is a DockerServiceResource
        if self._is_docker_resource(resource):
            return self._build_docker_prompt(resource)

        # Base prompt
        prompt = f"Generate content for: {resource.description}\n\n"

        # Add size guidance
        if hasattr(resource, 'size') and resource.size is not None:
            size_hints = {
                "small": "Keep it concise, around 100-500 words.",
                "medium": "Provide moderate detail, around 500-2000 words.",
                "large": "Provide comprehensive coverage, 2000+ words."
            }
            prompt += size_hints.get(resource.size.value, "")

        # Add format hints based on filename
        if hasattr(resource, 'name'):
            if resource.name.endswith('.md'):
                prompt += "\n\nFormat the output as Markdown."
            elif resource.name.endswith('.json'):
                prompt += "\n\nFormat the output as valid JSON."
            elif resource.name.endswith('.yaml') or resource.name.endswith('.yml'):
                prompt += "\n\nFormat the output as valid YAML."

        return prompt

    def _is_docker_resource(self, resource: Any) -> bool:
        """Check if resource is a DockerServiceResource."""
        return resource.__class__.__name__ == 'DockerServiceResource'

    def _build_docker_prompt(self, resource: Any) -> str:
        """Build specialized prompt for Docker resources."""
        return f"""Based on this description: "{resource.description}"

Suggest an appropriate Docker image for this service.
Respond in JSON format:
{{
  "image": "docker/image:tag",
  "suggested_ports": ["80:80"],
  "suggested_env_vars": {{"KEY": "value"}}
}}

If only the image is known, respond with just: {{"image": "docker/image:tag"}}

Be specific and use official, well-maintained images when possible."""

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
