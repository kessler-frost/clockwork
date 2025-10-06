"""
Artifact Generator - AI-powered content generation using Agno 2.0 + OpenRouter.
"""

import os
import logging
from typing import List, Dict, Any
from agno.agent import Agent
from openai import OpenAI

logger = logging.getLogger(__name__)


class ArtifactGenerator:
    """Generates artifacts (file contents, configs, etc.) using AI via OpenRouter."""

    def __init__(
        self,
        api_key: str = None,
        model: str = "openai/gpt-oss-20b:free",
        base_url: str = "https://openrouter.ai/api/v1"
    ):
        """
        Initialize the artifact generator.

        Args:
            api_key: OpenRouter API key (defaults to OPENROUTER_API_KEY env var)
            model: Model ID to use (default: openai/gpt-oss-20b:free)
            base_url: OpenRouter API base URL
        """
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            raise ValueError(
                "OpenRouter API key required. Set OPENROUTER_API_KEY environment variable "
                "or pass api_key parameter."
            )

        self.model = model
        self.base_url = base_url

        # Initialize OpenAI client pointing to OpenRouter
        self.client = OpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
        )

        logger.info(f"Initialized ArtifactGenerator with model: {self.model}")

    def generate(self, resources: List[Any]) -> Dict[str, str]:
        """
        Generate artifacts for resources that need them.

        Args:
            resources: List of Resource objects

        Returns:
            Dict mapping resource names to generated content
        """
        artifacts = {}

        for resource in resources:
            if resource.needs_artifact_generation():
                logger.info(f"Generating artifact for: {resource.name}")
                content = self._generate_for_resource(resource)
                artifacts[resource.name] = content
                logger.info(f"Generated {len(content)} chars for {resource.name}")

        return artifacts

    def _generate_for_resource(self, resource: Any) -> str:
        """
        Generate content for a single resource.

        Args:
            resource: Resource object needing content generation

        Returns:
            Generated content as string
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

            content = response.choices[0].message.content
            return content.strip()

        except Exception as e:
            logger.error(f"Failed to generate artifact for {resource.name}: {e}")
            raise

    def _build_prompt(self, resource: Any) -> str:
        """Build generation prompt based on resource."""

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
