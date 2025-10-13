"""
Resource Completer - AI-powered resource completion using PydanticAI structured outputs.

This module replaces the artifact generation approach with a direct resource completion
paradigm. Instead of generating text artifacts, the AI directly completes missing fields
in Pydantic resource models.
"""

import logging
from typing import Any, Dict, List, Optional

from pydantic import BaseModel
from pydantic_ai import Agent, InlineDefsJsonSchemaTransformer
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.profiles.openai import OpenAIModelProfile

from .settings import get_settings

logger = logging.getLogger(__name__)


class ResourceCompleter:
    """Completes partial resources using AI via PydanticAI structured outputs."""

    # System prompt for AI completion
    SYSTEM_PROMPT = """You are a helpful assistant that completes partial infrastructure resource definitions.

IMPORTANT: You will see a list of missing fields, but you should ONLY complete fields that are actually REQUIRED.
Many fields are optional and should be left as None/empty unless there is a specific need for them.

Guidelines:
- REQUIRED fields: Must always be completed (e.g., name, image, content)
- OPTIONAL fields: Only complete if actually needed for the specific use case
- Leave optional fields as None/empty if not required (e.g., volumes, env_vars, networks, user, group)

Always prefer:
- Official, well-maintained images for containers
- Standard, commonly-used packages for brew resources
- Well-known official repositories for git resources
- Minimal configurations that include only what's necessary

Your completions should be production-ready, minimal, and follow best practices."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None
    ):
        """
        Initialize the resource completer.

        Args:
            api_key: API key for AI service (overrides settings/.env)
            model: Model name to use (overrides settings/.env)
            base_url: Base URL for API endpoint (overrides settings/.env)
        """
        settings = get_settings()

        self.api_key = api_key or settings.api_key
        if not self.api_key:
            raise ValueError(
                "API key required. Set CW_API_KEY in .env file or pass api_key parameter."
            )

        self.model = model or settings.model
        self.base_url = base_url or settings.base_url

        logger.info(f"Initialized ResourceCompleter with model: {self.model} at {self.base_url}")

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
                # Resource is already complete, use as-is
                logger.info(f"Resource already complete: {resource.name}")
                completed_resources.append(resource)

        return completed_resources

    async def _complete_resource(self, resource: Any) -> Any:
        """
        Complete a single resource using PydanticAI Agent (async version).

        Args:
            resource: Partial Resource object needing completion

        Returns:
            Completed Resource object with all fields filled
        """
        # Build completion prompt based on resource type
        prompt = self._build_completion_prompt(resource)

        # Get tools from resource (handle None case)
        tools = resource.tools if resource.tools is not None else []
        logger.debug(f"Resource {resource.name} tools: {tools}, type: {type(tools)}")

        # Create OpenAI-compatible model
        # Works with any OpenAI-compatible API (OpenRouter, LM Studio, Ollama, etc.)
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

        # Create PydanticAI Agent with structured output
        # Using default Tool Output mode for reliable structured data generation
        # Models that don't support tool calls should be replaced with compatible models
        agent = Agent(
            model,
            tools=tools,
            system_prompt=self.SYSTEM_PROMPT,
            output_type=resource.__class__,
        )

        # Get response from agent
        result = await agent.run(prompt)

        # Extract completed resource from result
        completed_resource = result.output

        # Merge user-provided values with AI suggestions
        # User values take precedence over AI suggestions
        final_resource = self._merge_resources(resource, completed_resource)

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

        # Create new resource instance with merged data
        return user_resource.__class__(**merged_data)

    def _build_completion_prompt(self, resource: Any) -> str:
        """Build completion prompt based on resource type and partial values.

        Args:
            resource: Partial resource object

        Returns:
            Prompt string for AI completion
        """
        resource_type = resource.__class__.__name__

        # Get resource data as dict
        data = resource.model_dump(exclude_unset=False)

        # Identify which fields are missing (None)
        missing_fields = [k for k, v in data.items() if v is None]
        provided_fields = {k: v for k, v in data.items() if v is not None}

        # Build prompt
        prompt = f"""You have a partial {resource_type} definition.

Provided fields:
{self._format_dict(provided_fields)}

Missing fields (but ONLY complete REQUIRED ones):
{', '.join(missing_fields)}

IMPORTANT: Only complete fields that are actually REQUIRED for this specific use case.
Leave optional fields as None unless explicitly needed.

"""

        # Add resource-specific completion instructions
        if resource_type == "FileResource":
            prompt += self._build_file_completion_instructions(resource)
        elif resource_type == "TemplateFileResource":
            prompt += self._build_template_file_completion_instructions(resource)
        elif resource_type == "AppleContainerResource":
            prompt += self._build_container_completion_instructions(resource)
        elif resource_type == "DockerResource":
            prompt += self._build_docker_completion_instructions(resource)
        elif resource_type == "BrewPackageResource":
            prompt += self._build_brew_completion_instructions(resource)
        elif resource_type == "GitRepoResource":
            prompt += self._build_git_completion_instructions(resource)
        elif resource_type == "DirectoryResource":
            prompt += self._build_directory_completion_instructions(resource)
        else:
            # Generic instructions
            prompt += f"""
Please complete ONLY the REQUIRED fields based on the description and resource type.
Leave optional fields as None unless explicitly needed.
"""

        return prompt

    def _build_file_completion_instructions(self, resource: Any) -> str:
        """Build completion instructions for FileResource."""
        return """
For FileResource, please complete:
- name: appropriate filename with extension (e.g., "README.md", "config.json")
- content: the actual file content based on the description
- directory: where to create the file (use None for current directory, or specify subdirectory like "scratch")
- mode: file permissions (default: "644" for regular files)

The content should be well-formatted and production-ready.
Return a complete FileResource object.
"""

    def _build_container_completion_instructions(self, resource: Any) -> str:
        """Build completion instructions for AppleContainerResource."""
        return """
For AppleContainerResource, complete these fields:

REQUIRED fields (must be completed):
- name: container service name (e.g., "nginx-web", "postgres-db", "redis-cache")
- image: Docker image with version tag (e.g., "nginx:alpine", "postgres:16-alpine", "redis:7-alpine")
  * Prefer official images with alpine variants for smaller size
  * Include version tags (not :latest) for reproducibility
- ports: standard port mappings (e.g., ["8080:80"] for web servers, ["5432:5432"] for postgres)

OPTIONAL fields (leave as None/empty unless actually needed):
- env_vars: environment variables - ONLY if required by the image (e.g., {"POSTGRES_PASSWORD": "secret"})
- volumes: data persistence - ONLY if data needs to persist (e.g., ["postgres_data:/var/lib/postgresql/data"])
- networks: container networks - leave as empty list unless specific networking is needed

Return a complete AppleContainerResource object with minimal necessary configuration.
"""

    def _build_docker_completion_instructions(self, resource: Any) -> str:
        """Build completion instructions for DockerResource."""
        return """
For DockerResource, complete these fields:

REQUIRED fields (must be completed):
- name: container service name (e.g., "nginx-web", "postgres-db", "redis-cache")
- image: Docker image with version tag (e.g., "nginx:alpine", "postgres:16-alpine", "redis:7-alpine")
  * Prefer official images with alpine variants for smaller size
  * Include version tags (not :latest) for reproducibility
- ports: standard port mappings (e.g., ["8080:80"] for web servers, ["5432:5432"] for postgres)

OPTIONAL fields (leave as None/empty unless actually needed):
- env_vars: environment variables - ONLY if required by the image (e.g., {"POSTGRES_PASSWORD": "secret"})
- volumes: data persistence - ONLY if data needs to persist (e.g., ["postgres_data:/var/lib/postgresql/data"])
- networks: container networks - leave as empty list unless specific networking is needed

Return a complete DockerResource object with minimal necessary configuration.
"""

    def _build_brew_completion_instructions(self, resource: Any) -> str:
        """Build completion instructions for BrewPackageResource."""
        return """
For BrewPackageResource, please complete:
- packages: list of Homebrew package names (e.g., ["jq", "htop", "wget"])
  * Use official package names from Homebrew
  * For CLI tools, use regular packages (cask=False)
  * For GUI applications, set cask=True
  * Common examples: jq, ripgrep, fzf, bat, git, python, node

Return a complete BrewPackageResource object with appropriate packages.
"""

    def _build_git_completion_instructions(self, resource: Any) -> str:
        """Build completion instructions for GitRepoResource."""
        return """
For GitRepoResource, please complete:
- repo_url: Git repository URL (e.g., "https://github.com/user/repo.git")
  * Prefer official repositories
  * Use HTTPS URLs (not SSH)
- branch: Git branch to checkout (default: "main", or "master" for older repos)

Return a complete GitRepoResource object with a valid repository URL.
"""

    def _build_directory_completion_instructions(self, resource: Any) -> str:
        """Build completion instructions for DirectoryResource."""
        return """
For DirectoryResource, please complete:
- mode: directory permissions (default: "755" for standard directories)
- user: owner username (optional, can be None)
- group: group name (optional, can be None)

Return a complete DirectoryResource object.
"""

    def _build_template_file_completion_instructions(self, resource: Any) -> str:
        """Build completion instructions for TemplateFileResource."""
        return """
For TemplateFileResource, complete these fields:

REQUIRED fields (must be completed):
- name: appropriate filename with extension (e.g., "config.conf", "settings.yaml")
- template_content: Jinja2 template string with variables in {{ variable_name }} format
- variables: Dictionary of variable names and their values for template rendering
- directory: where to create the file (use None for current directory, or specify subdirectory like "scratch")
- mode: file permissions (default: "644" for regular files)

OPTIONAL fields (leave as None unless actually needed):
- user: owner username - leave as None unless specific ownership required
- group: group name - leave as None unless specific group required
- path: full file path - leave as None (will be constructed from directory + name)

The template_content should use Jinja2 syntax with {{ variable_name }} for variable interpolation.
All variables referenced in the template should be provided in the variables dictionary.

Return a complete TemplateFileResource object with minimal necessary configuration.
"""

    def _format_dict(self, data: Dict[str, Any]) -> str:
        """Format dictionary for display in prompt."""
        if not data:
            return "(none)"

        lines = []
        for key, value in data.items():
            # Truncate long values
            value_str = str(value)
            if len(value_str) > 100:
                value_str = value_str[:100] + "..."
            lines.append(f"  - {key}: {value_str}")

        return "\n".join(lines)
