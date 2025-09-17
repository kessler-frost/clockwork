"""
Agno 2.0 AI Agent Integration for Clockwork Compilation

This module provides AI-powered compilation of ActionList to ArtifactBundle
using the Agno 2.0 framework with LM Studio integration.
"""

import json
import logging
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field

from agno.agent import Agent
from agno.models.lmstudio import LMStudio
from agno.workflow import Workflow, Step
from agno.tools.memory import MemoryTools
from agno.db.in_memory import InMemoryDb

from ..models import ActionList, ArtifactBundle, Artifact, ExecutionStep


logger = logging.getLogger(__name__)


class AgentArtifact(BaseModel):
    """Pydantic model for AI agent artifact generation using templates."""
    path: str = Field(..., description="Relative path for the artifact file (e.g., 'scripts/01_fetch_repo.sh')")
    mode: str = Field(..., description="File permissions in octal format (e.g., '0755' for executable, '0644' for data)")
    purpose: str = Field(..., description="The purpose/name of the action this artifact serves")
    template: str = Field(..., description="Name of the script template to use (e.g., 'create_directory', 'write_file')")
    params: Dict[str, Any] = Field(..., description="Parameters to substitute in the template")
    content: Optional[str] = Field(None, description="Direct script content (only used if template approach fails)")
    lang: str = Field(default="bash", description="Programming language (always bash for templates)")


class AgentExecutionStep(BaseModel):
    """Pydantic model for AI agent execution step generation."""
    purpose: str = Field(..., description="The purpose/name that matches an artifact's purpose")
    run: Dict[str, Any] = Field(..., description="Execution command configuration with 'cmd' array")


class AgentArtifactBundle(BaseModel):
    """Pydantic model for AI agent complete artifact bundle generation."""
    version: str = Field(default="1", description="Bundle format version")
    artifacts: List[AgentArtifact] = Field(..., description="List of executable artifacts to generate")
    steps: List[AgentExecutionStep] = Field(..., description="List of execution steps in order")
    vars: Dict[str, Any] = Field(default_factory=dict, description="Environment variables and configuration values")


class AgnoCompilerError(Exception):
    """Exception raised during Agno AI compilation."""
    pass


class AgnoCompiler:
    """
    AI-powered compiler using Agno 2.0 framework with LM Studio integration.

    This class uses Agno 2.0 agent to generate executable artifacts
    from declarative ActionList specifications using proven script templates.
    """

    # Pre-tested script templates that the AI combines and parameterizes
    SCRIPT_TEMPLATES = {
        # File Operations
        'create_directory': '''#!/bin/bash
set -e
set -o pipefail

DIR_PATH="{path}"
if [ -z "$DIR_PATH" ]; then
    echo "✗ Error: Directory path is required"
    exit 1
fi

echo "Creating directory: $DIR_PATH"
mkdir -p "$DIR_PATH"
echo "✓ Created directory: $DIR_PATH"
exit 0''',

        'write_file': '''#!/bin/bash
set -e
set -o pipefail

FILE_PATH="{path}"
if [ -z "$FILE_PATH" ]; then
    echo "✗ Error: File path is required"
    exit 1
fi

echo "Writing file: $FILE_PATH"
# Ensure parent directory exists
mkdir -p "$(dirname "$FILE_PATH")"

cat > "$FILE_PATH" << 'EOF'
{content}
EOF

if [ $? -eq 0 ]; then
    echo "✓ Successfully wrote file: $FILE_PATH"
    echo "  Size: $(wc -c < "$FILE_PATH") bytes"
else
    echo "✗ Failed to write file: $FILE_PATH"
    exit 1
fi
exit 0''',

        'verify_exists': '''#!/bin/bash
set -e
set -o pipefail

TARGET="{path}"
if [ -z "$TARGET" ]; then
    echo "✗ Error: Target path is required"
    exit 1
fi

echo "Verifying path exists: $TARGET"
if [ -e "$TARGET" ]; then
    if [ -f "$TARGET" ]; then
        echo "✓ File exists: $TARGET ($(wc -c < "$TARGET") bytes)"
    elif [ -d "$TARGET" ]; then
        echo "✓ Directory exists: $TARGET ($(ls -1 "$TARGET" | wc -l) items)"
    else
        echo "✓ Path exists: $TARGET"
    fi
    exit 0
else
    echo "✗ Path not found: $TARGET"
    exit 1
fi''',

        # Command Operations
        'run_command': '''#!/bin/bash
set -e
set -o pipefail

COMMAND="{command}"
if [ -z "$COMMAND" ]; then
    echo "✗ Error: Command is required"
    exit 1
fi

echo "Executing command: $COMMAND"
eval "$COMMAND"
EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo "✓ Command completed successfully: $COMMAND"
else
    echo "✗ Command failed with exit code $EXIT_CODE: $COMMAND"
    exit $EXIT_CODE
fi
exit 0''',

        # Docker Operations
        'docker_run': '''#!/bin/bash
set -e
set -o pipefail

IMAGE="{image}"
NAME="{name}"
PORTS="{ports}"
ENV_VARS="{env_vars}"

if [ -z "$IMAGE" ]; then
    echo "✗ Error: Docker image is required"
    exit 1
fi
if [ -z "$NAME" ] || [ "$NAME" = "None" ]; then
    NAME="$(echo "$IMAGE" | tr ':/' '_')"
fi

echo "Running Docker container: $IMAGE"
DOCKER_CMD="docker run -d --name $NAME"

if [ -n "$PORTS" ] && [ "$PORTS" != "None" ]; then
    DOCKER_CMD="$DOCKER_CMD -p $PORTS"
fi

if [ -n "$ENV_VARS" ] && [ "$ENV_VARS" != "None" ]; then
    DOCKER_CMD="$DOCKER_CMD $ENV_VARS"
fi

DOCKER_CMD="$DOCKER_CMD $IMAGE"

echo "Executing: $DOCKER_CMD"
eval "$DOCKER_CMD"
EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo "✓ Container started successfully: $NAME"
    echo "  Use 'docker logs $NAME' to view logs"
else
    echo "✗ Failed to start container: $NAME"
    exit $EXIT_CODE
fi
exit 0''',

        # Web/API Operations
        'check_http': '''#!/bin/bash
set -e
set -o pipefail

URL="{url}"
EXPECTED_STATUS="{expected_status}"
if [ -z "$URL" ]; then
    echo "✗ Error: URL is required"
    exit 1
fi
if [ -z "$EXPECTED_STATUS" ] || [ "$EXPECTED_STATUS" = "None" ]; then
    EXPECTED_STATUS="200"
fi

echo "Checking HTTP endpoint: $URL (expecting status $EXPECTED_STATUS)"
if command -v curl >/dev/null 2>&1; then
    ACTUAL_STATUS=$(curl -s -o /dev/null -w "%{{http_code}}" "$URL" 2>/dev/null || echo "000")

    if [ "$ACTUAL_STATUS" = "$EXPECTED_STATUS" ]; then
        echo "✓ HTTP check passed: $URL returned $ACTUAL_STATUS"
        exit 0
    else
        echo "✗ HTTP check failed: $URL returned $ACTUAL_STATUS (expected $EXPECTED_STATUS)"
        exit 1
    fi
else
    echo "✗ curl not available for HTTP check"
    exit 1
fi''',

        # JSON Configuration
        'write_json_config': '''#!/bin/bash
set -e
set -o pipefail

FILE_PATH="{path}"
CONFIG_DATA='{config_json}'

if [ -z "$FILE_PATH" ]; then
    echo "✗ Error: File path is required"
    exit 1
fi

echo "Writing JSON configuration: $FILE_PATH"
# Ensure parent directory exists
mkdir -p "$(dirname "$FILE_PATH")"

# Validate JSON before writing
if echo '$CONFIG_DATA' | python3 -m json.tool >/dev/null 2>&1; then
    echo '$CONFIG_DATA' | python3 -m json.tool > "$FILE_PATH"
    echo "✓ Successfully wrote JSON config: $FILE_PATH"
    echo "  Size: $(wc -c < "$FILE_PATH") bytes"
else
    echo "✗ Invalid JSON data"
    exit 1
fi
exit 0''',

        # Generic template for simple operations
        'simple_task': '''#!/bin/bash
set -e
set -o pipefail

echo "Executing task: {task_name}"
echo "Description: {description}"

{task_commands}

echo "✓ Task completed: {task_name}"
exit 0'''
    }

    def __init__(
        self,
        model_id: str = "qwen/qwen3-4b-2507",
        lm_studio_url: str = "http://localhost:1234",
        timeout: int = 300
    ):
        """
        Initialize the Agno 2.0 AI compiler.

        Args:
            model_id: Model identifier in LM Studio (default: qwen/qwen3-4b-2507)
            lm_studio_url: LM Studio server URL (default: http://localhost:1234)
            timeout: Request timeout in seconds
        """
        self.model_id = model_id
        self.lm_studio_url = lm_studio_url
        self.timeout = timeout

        # Initialize Agno 2.0 agent
        try:
            # Create LM Studio model
            lm_studio_model = LMStudio(
                id=model_id,
                base_url=lm_studio_url,
                timeout=timeout,
                max_tokens=4000,
                temperature=0.05
            )

            # Create in-memory database for MemoryTools
            memory_db = InMemoryDb()

            # Initialize agent with Agno 2.0 features only
            self.agent = Agent(
                model=lm_studio_model,
                output_schema=AgentArtifactBundle,
                description="You are an expert DevOps engineer specializing in generating executable artifacts for task automation.",
                instructions=self._get_system_instructions(),
                # Enable Agno 2.0 features
                enable_agentic_memory=True,
                add_memories_to_context=True,
                reasoning=True,  # Enable reasoning for better template selection
                exponential_backoff=True,  # Enable exponential backoff for retries
                retries=3,  # Retry up to 3 times on failure
                tools=[MemoryTools(db=memory_db)],  # Add memory management tools
                structured_outputs=True,  # Use structured outputs
                markdown=False
            )
            logger.info(f"Initialized Agno 2.0 AI agent with model: {model_id}")

            # Test connection - fail fast if not available
            logger.info("Validating LM Studio connection...")
            self._test_lm_studio_connection()
            logger.info("LM Studio validation successful - ready for AI compilation with Agno 2.0")

        except Exception as e:
            logger.error(f"Failed to initialize Agno 2.0 agent: {e}")
            raise AgnoCompilerError(f"Failed to initialize AI agent: {e}")

    def _get_system_instructions(self) -> str:
        """Get system instructions for template-based artifact generation."""
        return f"""
You are an expert DevOps automation specialist with advanced memory capabilities. Your job is to convert task specifications into executable artifacts by selecting and parameterizing proven script templates.

MEMORY CAPABILITIES:
- You can remember successful template patterns from previous compilations
- Store and retrieve compilation optimizations and best practices
- Learn from template usage patterns to improve future selections
- Remember common parameter combinations for different deployment scenarios

CRITICAL: You do NOT write bash scripts from scratch. You ONLY select from pre-tested script templates and provide parameters.

AVAILABLE SCRIPT TEMPLATES:
{self._get_template_descriptions()}

HOW TO USE TEMPLATES:
1. Analyze the task requirements
2. Select the appropriate template(s) from the list above
3. Provide the required parameters for each template
4. Chain templates together for complex operations
5. Ensure proper execution order using dependencies

TEMPLATE SELECTION GUIDELINES:
- File Operations: Use 'create_directory', 'write_file', 'verify_exists'
- Commands: Use 'run_command'
- Docker: Use 'docker_run'
- HTTP Checks: Use 'check_http'
- JSON Config: Use 'write_json_config'
- Generic Tasks: Use 'simple_task'

OUTPUT FORMAT:
You MUST respond with a structured AgentArtifactBundle containing:
- artifacts: Array of template selections with parameters
- steps: Execution order matching artifacts
- vars: Environment variables for the templates

REMEMBER:
- NEVER write bash code - only select templates and provide parameters
- All scripts will be generated from the proven templates
- Focus on correct template selection and parameter values
- Ensure proper dependency order in steps array
"""

    def _get_template_descriptions(self) -> str:
        """Generate descriptions of available script templates."""
        return """
FILE OPERATIONS:
• create_directory: Creates a directory with proper error handling
  Parameters: path (required) - Directory path to create

• write_file: Writes content to a file, creating parent directories if needed
  Parameters: path (required), content (required) - File path and content

• verify_exists: Checks if a file or directory exists
  Parameters: path (required) - Path to verify

COMMAND OPERATIONS:
• run_command: Executes a shell command with error handling
  Parameters: command (required) - Command to execute

DOCKER OPERATIONS:
• docker_run: Starts a Docker container
  Parameters: image (required), name (optional), ports (optional), env_vars (optional)

WEB/API OPERATIONS:
• check_http: Performs HTTP health check
  Parameters: url (required), expected_status (optional, default: 200)

CONFIGURATION:
• write_json_config: Writes a JSON configuration file with validation
  Parameters: path (required), config_json (required) - File path and JSON content

GENERIC:
• simple_task: Generic template for simple operations
  Parameters: task_name (required), description (optional), task_commands (required)
"""

    def _test_lm_studio_connection(self) -> None:
        """
        Test LM Studio connection via Agno 2.0 agent.

        Raises:
            AgnoCompilerError: If LM Studio is not accessible through Agno
        """
        try:
            logger.info(f"Testing LM Studio connection through Agno 2.0...")

            # Simple test using the agent
            test_response = self.agent.run("Respond with 'OK' to confirm you are working.")

            if test_response and hasattr(test_response, 'content'):
                logger.info("LM Studio connection successful through Agno 2.0")
            else:
                raise AgnoCompilerError("Agent test returned no response")

        except Exception as e:
            raise AgnoCompilerError(
                f"Failed to connect to LM Studio through Agno 2.0: {e}. "
                f"Please ensure LM Studio is running at {self.lm_studio_url} with model {self.model_id} loaded."
            )

    def get_template(self, template_name: str, **params) -> str:
        """
        Get a script template and substitute parameters.

        Args:
            template_name: Name of the template to use
            **params: Parameters to substitute in the template

        Returns:
            Script content with parameters substituted

        Raises:
            AgnoCompilerError: If template not found or parameter substitution fails
        """
        if template_name not in self.SCRIPT_TEMPLATES:
            available_templates = ', '.join(self.SCRIPT_TEMPLATES.keys())
            raise AgnoCompilerError(
                f"Unknown template: '{template_name}'. "
                f"Available templates: {available_templates}"
            )

        template = self.SCRIPT_TEMPLATES[template_name]

        try:
            # Substitute parameters in the template
            script_content = template.format(**params)
            return script_content
        except KeyError as e:
            raise AgnoCompilerError(
                f"Missing required parameter for template '{template_name}': {e}"
            )
        except Exception as e:
            raise AgnoCompilerError(
                f"Failed to substitute parameters in template '{template_name}': {e}"
            )

    def compile_to_artifacts(self, action_list: ActionList) -> ArtifactBundle:
        """
        Compile an ActionList into an ArtifactBundle using Agno 2.0 agent.

        Args:
            action_list: The ActionList to compile

        Returns:
            ArtifactBundle with generated executable artifacts

        Raises:
            AgnoCompilerError: If compilation fails
        """
        try:
            logger.info(f"Starting Agno 2.0 compilation of {len(action_list.steps)} action steps")

            # Use Agno 2.0 agent directly
            agent_bundle = self._compile_with_agent(action_list)

            # Convert to Clockwork ArtifactBundle format
            clockwork_bundle = self._convert_to_clockwork_format(agent_bundle)

            logger.info(f"Agno 2.0 compilation completed: {len(clockwork_bundle.artifacts)} artifacts generated")
            return clockwork_bundle

        except Exception as e:
            logger.error(f"Agno 2.0 compilation failed: {e}")
            raise AgnoCompilerError(f"Failed to compile with Agno 2.0 agent: {e}")

    def _compile_with_agent(self, action_list: ActionList) -> AgentArtifactBundle:
        """
        Compile using Agno 2.0 Agent with structured outputs.

        Args:
            action_list: The ActionList to compile

        Returns:
            AgentArtifactBundle with AI-generated artifacts

        Raises:
            AgnoCompilerError: If compilation fails
        """
        try:
            # Generate compilation prompt
            prompt = self._generate_compilation_prompt(action_list)

            logger.info("Executing Agno 2.0 agent compilation...")

            # Run agent with structured output
            response = self.agent.run(prompt)

            # Extract structured output
            if hasattr(response, 'content') and response.content:
                # Agno 2.0 should return structured output directly
                if isinstance(response.content, AgentArtifactBundle):
                    agent_bundle = response.content
                elif isinstance(response.content, dict):
                    agent_bundle = AgentArtifactBundle(**response.content)
                else:
                    # Parse JSON if needed
                    content_dict = json.loads(str(response.content))
                    agent_bundle = AgentArtifactBundle(**content_dict)

                logger.info("Agno 2.0 agent compilation completed successfully")
                return agent_bundle

            else:
                raise AgnoCompilerError("Agent completed but returned no structured output")

        except Exception as e:
            logger.error(f"Agno 2.0 agent compilation failed: {e}")
            raise AgnoCompilerError(f"Agent compilation failed: {e}")

    def _generate_compilation_prompt(self, action_list: ActionList) -> str:
        """Generate a compilation prompt for template-based artifact compilation."""

        prompt = f"""
Convert the following task automation sequence into executable artifacts by selecting script templates and providing parameters.

ACTION LIST SPECIFICATION:
Version: {action_list.version}
Total Steps: {len(action_list.steps)}

TASKS TO IMPLEMENT:
"""

        for i, step in enumerate(action_list.steps, 1):
            prompt += f"""
Step {i}: {step.name}
  Type: {step.type if hasattr(step, 'type') else 'CUSTOM'}
  Arguments: {json.dumps(step.args, indent=2)}
"""

        prompt += f"""

TEMPLATE SELECTION INSTRUCTIONS:
You MUST select from these available script templates (DO NOT write bash scripts):

FILE OPERATIONS:
• create_directory - Creates a directory
  Required: path
• write_file - Writes content to a file
  Required: path, content
• verify_exists - Checks if a file/directory exists
  Required: path

COMMAND OPERATIONS:
• run_command - Executes a shell command
  Required: command

DOCKER OPERATIONS:
• docker_run - Starts a Docker container
  Required: image, Optional: name, ports, env_vars

WEB OPERATIONS:
• check_http - HTTP health check
  Required: url, Optional: expected_status (default 200)

CONFIGURATION:
• write_json_config - Writes JSON configuration
  Required: path, config_json

TASK MAPPING GUIDE:
- Create/manage files → use create_directory, write_file, verify_exists
- Run commands → use run_command
- Deploy services → use docker_run, then check_http
- Verify deployments → use check_http, verify_exists
- Configuration → use write_json_config or write_file

PARAMETER INFERENCE:
When step arguments don't provide all needed parameters, infer reasonable defaults:
- Ports: nginx=80, api=8080, database=5432, redis=6379
- Paths: Use descriptive names under scripts/ (e.g., scripts/01_setup_dir.sh)
- Timeouts: 30s for quick checks, 60s for service waits
- Hosts: Default to "localhost"

CRITICAL REQUIREMENTS:
- Use ONLY the templates listed (do not write bash code)
- Each artifact needs: path, mode, purpose, template, params
- Steps array must match artifact purposes
- Include relevant environment variables in vars
- Number artifacts in execution order (01_, 02_, etc.)
- All paths should be under scripts/ directory
"""

        return prompt

    def _convert_to_clockwork_format(self, agent_bundle: AgentArtifactBundle) -> ArtifactBundle:
        """Convert AI agent response to Clockwork ArtifactBundle format with template expansion."""
        try:
            artifacts = []
            template_expansion_errors = []

            for i, agent_artifact in enumerate(agent_bundle.artifacts):
                try:
                    # Expand template into actual script content
                    if hasattr(agent_artifact, 'template') and agent_artifact.template:
                        # Expand the template with parameters
                        script_content = self.get_template(
                            agent_artifact.template,
                            **(agent_artifact.params or {})
                        )
                        logger.info(f"Expanded template '{agent_artifact.template}' for artifact: {agent_artifact.path}")

                    elif agent_artifact.content:
                        # Use direct content if provided
                        script_content = agent_artifact.content
                        logger.info(f"Using direct content for artifact: {agent_artifact.path}")

                    else:
                        # Neither template nor content provided
                        error_msg = f"Artifact {i} has neither template nor content"
                        template_expansion_errors.append(error_msg)
                        logger.error(error_msg)

                        script_content = f'''#!/bin/bash
echo "✗ No template or content provided for this artifact"
exit 1'''

                    # Create the artifact with expanded content
                    artifact = Artifact(
                        path=agent_artifact.path,
                        mode=agent_artifact.mode,
                        purpose=agent_artifact.purpose,
                        lang="bash",  # All templates are bash scripts
                        content=script_content
                    )
                    artifacts.append(artifact)

                except Exception as e:
                    error_msg = f"Failed to expand template for artifact {i}: {e}"
                    template_expansion_errors.append(error_msg)
                    logger.error(error_msg)

                    # Create an error artifact
                    error_script = f'''#!/bin/bash
echo "✗ Template expansion failed: {e}"
exit 1'''

                    artifact = Artifact(
                        path=agent_artifact.path or f"scripts/error_{i}.sh",
                        mode=agent_artifact.mode or "0755",
                        purpose=agent_artifact.purpose or f"error_{i}",
                        lang="bash",
                        content=error_script
                    )
                    artifacts.append(artifact)

            # Convert execution steps
            steps = []
            for agent_step in agent_bundle.steps:
                step = ExecutionStep(
                    purpose=agent_step.purpose,
                    run=agent_step.run
                )
                steps.append(step)

            # Add template expansion status to vars
            bundle_vars = agent_bundle.vars or {}
            if template_expansion_errors:
                bundle_vars["template_expansion_errors"] = template_expansion_errors
                bundle_vars["template_expansion_status"] = "partial_success"
                logger.warning(f"Template expansion completed with {len(template_expansion_errors)} errors")
            else:
                bundle_vars["template_expansion_status"] = "success"
                logger.info("All templates expanded successfully")

            # Create Clockwork ArtifactBundle
            bundle = ArtifactBundle(
                version=agent_bundle.version,
                artifacts=artifacts,
                steps=steps,
                vars=bundle_vars
            )

            return bundle

        except Exception as e:
            logger.error(f"Failed to convert AI response to ArtifactBundle: {e}")
            raise AgnoCompilerError(f"Failed to convert AI response to ArtifactBundle: {e}")

    def test_connection(self) -> bool:
        """
        Test connection through Agno 2.0 agent.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            self._test_lm_studio_connection()
            return True
        except AgnoCompilerError as e:
            logger.warning(f"Agno 2.0 connection test failed: {e}")
            return False
        except Exception as e:
            logger.warning(f"Unexpected error in connection test: {e}")
            return False

    def get_status(self) -> Dict[str, Any]:
        """Get status information about the Agno 2.0 AI agent."""
        return {
            "model_id": self.model_id,
            "lm_studio_url": self.lm_studio_url,
            "timeout": self.timeout,
            "connection_ok": self.test_connection(),
            "agno_version": "2.0",
            "features": ["memory", "reasoning", "structured_outputs", "exponential_backoff"]
        }


def create_agno_compiler(
    model_id: Optional[str] = None,
    lm_studio_url: Optional[str] = None,
    **kwargs
) -> AgnoCompiler:
    """
    Factory function to create an AgnoCompiler with optional configuration.

    Args:
        model_id: Model ID override
        lm_studio_url: LM Studio URL override
        **kwargs: Additional configuration options

    Returns:
        Configured AgnoCompiler instance
    """
    # Use defaults if not specified
    model_id = model_id or "qwen/qwen3-4b-2507"
    lm_studio_url = lm_studio_url or "http://localhost:1234"

    return AgnoCompiler(
        model_id=model_id,
        lm_studio_url=lm_studio_url,
        **kwargs
    )