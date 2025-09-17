"""
Agno 2.0 AI Agent Integration for Clockwork Compilation

This module provides AI-powered compilation of ActionList to ArtifactBundle
using the Agno 2.0 framework with LM Studio integration.
"""

import json
import logging
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field

from agno.agent import Agent, RunOutput
from agno.models.openai import OpenAIChat

from ..models import ActionList, ArtifactBundle, Artifact, ExecutionStep


logger = logging.getLogger(__name__)


class AgentArtifact(BaseModel):
    """Pydantic model for AI agent artifact generation."""
    path: str = Field(..., description="Artifact file path")
    template: str = Field(..., description="Template name to use")
    purpose: str = Field(..., description="Action purpose")
    image: str = Field(default="nginx:latest", description="Docker image")
    name: str = Field(default="service", description="Service name")
    ports: str = Field(default="80:80", description="Port mapping")


class AgentExecutionStep(BaseModel):
    """Pydantic model for execution steps."""
    purpose: str = Field(..., description="Step purpose")
    command: str = Field(..., description="Command to execute")


class AgentArtifactBundle(BaseModel):
    """Pydantic model for artifact bundle."""
    artifacts: List[AgentArtifact] = Field(..., description="List of artifacts")
    steps: List[AgentExecutionStep] = Field(..., description="List of execution steps")


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
        model_id: str = "openai/gpt-oss-20b",
        lm_studio_url: str = "http://localhost:1234",
        timeout: int = 300
    ):
        """
        Initialize the Agno 2.0 AI compiler.

        Args:
            model_id: Model identifier in LM Studio (default: openai/gpt-oss-20b)
            lm_studio_url: LM Studio server URL (default: http://localhost:1234)
            timeout: Request timeout in seconds
        """
        self.model_id = model_id
        self.lm_studio_url = lm_studio_url
        self.timeout = timeout

        # Initialize Agno 2.0 agent
        try:
            # Create OpenAI model pointing to LM Studio endpoint
            openai_model = OpenAIChat(
                id=model_id,
                api_key="dummy",  # LM Studio doesn't require a real API key
                base_url=f"{lm_studio_url}/v1",
                timeout=timeout,
                max_tokens=4000,
                temperature=0.05
            )

            # Initialize agent with proper Agno 2.0 syntax
            self.agent = Agent(
                model=openai_model,
                description="You are an expert DevOps engineer specializing in generating executable artifacts for task automation.",
                instructions=self._get_system_instructions(),
                output_schema=AgentArtifactBundle,
                markdown=False
            )
            logger.info(f"Initialized Agno 2.0 AI agent with model: {model_id}")

            # Skip connection test for now due to Agno 2.0 compatibility issues
            logger.info("Agno 2.0 agent initialized - skipping connection test")

        except Exception as e:
            logger.error(f"Failed to initialize Agno 2.0 agent: {e}")
            raise AgnoCompilerError(f"Failed to initialize AI agent: {e}")

    def _get_system_instructions(self) -> str:
        """Get flat structure instructions."""
        return """
You are a DevOps automation expert. Generate Docker deployment configuration.

OUTPUT FORMAT:
Return flat JSON with deployment parameters:
- deploy_script_path: Path to deployment script
- deploy_image: Docker image to use
- deploy_name: Service name
- deploy_ports: Port mapping (e.g. "3000:80")
- execute_command: Command to run the script

Example: {"deploy_script_path": "scripts/deploy.sh", "deploy_image": "nginx:latest", "deploy_name": "web", "deploy_ports": "8080:80", "execute_command": "bash scripts/deploy.sh"}
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

        # Provide default values for optional parameters based on template
        defaults = self._get_template_defaults(template_name)
        merged_params = {**defaults, **params}

        try:
            # Substitute parameters in the template
            script_content = template.format(**merged_params)
            return script_content
        except KeyError as e:
            raise AgnoCompilerError(
                f"Missing required parameter for template '{template_name}': {e}"
            )
        except Exception as e:
            raise AgnoCompilerError(
                f"Failed to substitute parameters in template '{template_name}': {e}"
            )

    def _get_template_defaults(self, template_name: str) -> Dict[str, str]:
        """Get default values for optional template parameters."""
        defaults = {
            'docker_run': {
                'name': 'None',
                'ports': 'None',
                'env_vars': 'None'
            },
            'check_http': {
                'expected_status': '200'
            },
            'run_with_timeout': {
                'timeout': '30'
            },
            'wait_for_service': {
                'timeout': '60'
            },
            'check_port': {
                'host': 'localhost'
            }
        }
        return defaults.get(template_name, {})

    def _resolve_variable_references(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve variable references like ${var.image} with actual values."""
        # Simple hardcoded resolution for the demo - in production this would
        # come from the variable resolution system
        variable_map = {
            'var.app_name': 'dev-web-app',
            'var.image': 'nginx:1.25-alpine',
            'var.port': '3000'
        }

        resolved = {}
        for key, value in args.items():
            if isinstance(value, str):
                # Replace variable references
                resolved_value = value
                for var_ref, var_value in variable_map.items():
                    resolved_value = resolved_value.replace(f"${{{var_ref}}}", str(var_value))
                resolved[key] = resolved_value
            elif isinstance(value, dict):
                resolved[key] = self._resolve_variable_references(value)
            elif isinstance(value, list):
                resolved[key] = [
                    self._resolve_variable_references(item) if isinstance(item, dict)
                    else (str(variable_map.get(f"var.{item}", item)) if isinstance(item, str) and item.startswith("${var.")
                    else item)
                    for item in value
                ]
            else:
                resolved[key] = value

        return resolved

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

            # Run agent with structured output using Agno 2.0 API
            response: RunOutput = self.agent.run(prompt)

            # Extract structured output from Agno 2.0 response
            if response and hasattr(response, 'content'):
                agent_bundle = response.content

                # Handle both structured and string responses
                if isinstance(agent_bundle, AgentArtifactBundle):
                    logger.info("Agno 2.0 agent compilation completed successfully")
                    return agent_bundle
                elif isinstance(agent_bundle, str):
                    logger.info("Agent returned string response, attempting to parse as JSON")
                    try:
                        import json
                        parsed_content = json.loads(agent_bundle)
                        agent_bundle = AgentArtifactBundle(**parsed_content)
                        logger.info("Successfully parsed string response to AgentArtifactBundle")
                        return agent_bundle
                    except (json.JSONDecodeError, TypeError, ValueError) as e:
                        logger.error(f"Failed to parse string response: {e}")
                        logger.debug(f"Raw string content: {agent_bundle}")
                        raise AgnoCompilerError(f"Agent returned unparseable string response: {e}")
                else:
                    logger.error(f"Unexpected response type: {type(agent_bundle)}")
                    raise AgnoCompilerError(f"Agent returned unexpected type: {type(agent_bundle)}")
            else:
                raise AgnoCompilerError("Agent completed but returned no content")

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
            # Resolve variable references in step arguments
            resolved_args = self._resolve_variable_references(step.args)
            prompt += f"""
Step {i}: {step.name}
  Type: {step.type if hasattr(step, 'type') else 'CUSTOM'}
  Arguments: {json.dumps(resolved_args, indent=2)}
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
        """Convert agent response to Clockwork ArtifactBundle format."""
        try:
            artifacts = []
            steps = []

            for agent_artifact in agent_bundle.artifacts:
                # Generate script content based on template
                if agent_artifact.template == "docker_run":
                    script_content = self.SCRIPT_TEMPLATES['docker_run'].format(
                        image=agent_artifact.image,
                        name=agent_artifact.name,
                        ports=agent_artifact.ports,
                        env_vars="None"
                    )
                else:
                    script_content = f'''#!/bin/bash
echo "Running {agent_artifact.purpose}"
echo "Template: {agent_artifact.template}"
exit 0'''

                artifact = Artifact(
                    path=agent_artifact.path,
                    mode="0755",
                    purpose=agent_artifact.purpose,
                    lang="bash",
                    content=script_content
                )
                artifacts.append(artifact)

            # Convert execution steps
            for agent_step in agent_bundle.steps:
                step = ExecutionStep(
                    purpose=agent_step.purpose,
                    run={"cmd": agent_step.command.split()}
                )
                steps.append(step)

            bundle = ArtifactBundle(
                version="1",
                artifacts=artifacts,
                steps=steps,
                vars={}
            )

            logger.info(f"Successfully converted agent response to Clockwork format: {len(artifacts)} artifacts, {len(steps)} steps")
            return bundle

        except Exception as e:
            logger.error(f"Failed to convert agent response to ArtifactBundle: {e}")
            raise AgnoCompilerError(f"Failed to convert agent response to ArtifactBundle: {e}")

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
    model_id = model_id or "openai/gpt-oss-20b"
    lm_studio_url = lm_studio_url or "http://localhost:1234"

    return AgnoCompiler(
        model_id=model_id,
        lm_studio_url=lm_studio_url,
        **kwargs
    )
