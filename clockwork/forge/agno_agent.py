"""
Agno AI Agent Integration for Clockwork Compilation

This module provides AI-powered compilation of ActionList to ArtifactBundle
using the Agno framework with LM Studio integration.
"""

import json
import logging
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field

from agno.agent import Agent, RunResponse
from agno.models.lmstudio import LMStudio

from ..models import ActionList, ArtifactBundle, Artifact, ExecutionStep


logger = logging.getLogger(__name__)


class AgentArtifact(BaseModel):
    """Pydantic model for AI agent artifact generation using templates."""
    path: str = Field(..., description="Relative path for the artifact file (e.g., 'scripts/01_fetch_repo.sh')")
    mode: str = Field(..., description="File permissions in octal format (e.g., '0755' for executable, '0644' for data)")
    purpose: str = Field(..., description="The purpose/name of the action this artifact serves")
    template: str = Field(..., description="Name of the script template to use (e.g., 'create_directory', 'write_file')")
    params: Dict[str, Any] = Field(..., description="Parameters to substitute in the template")
    # Keep content as optional for backwards compatibility, but prefer template + params
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
    AI-powered compiler using Agno framework with LM Studio integration.
    
    This class uses a local LM Studio instance to generate executable artifacts
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

        'run_with_timeout': '''#!/bin/bash
set -e
set -o pipefail

COMMAND="{command}"
TIMEOUT="{timeout}"
if [ -z "$COMMAND" ]; then
    echo "✗ Error: Command is required"
    exit 1
fi
if [ -z "$TIMEOUT" ]; then
    TIMEOUT="30"
fi

echo "Executing command with ${TIMEOUT}s timeout: $COMMAND"
timeout "$TIMEOUT" bash -c "$COMMAND"
EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo "✓ Command completed successfully: $COMMAND"
elif [ $EXIT_CODE -eq 124 ]; then
    echo "✗ Command timed out after ${TIMEOUT}s: $COMMAND"
    exit 1
else
    echo "✗ Command failed with exit code $EXIT_CODE: $COMMAND"
    exit $EXIT_CODE
fi
exit 0''',

        # Service Operations
        'check_port': '''#!/bin/bash
set -e
set -o pipefail

PORT="{port}"
HOST="{host}"
if [ -z "$PORT" ]; then
    echo "✗ Error: Port is required"
    exit 1
fi
if [ -z "$HOST" ]; then
    HOST="localhost"
fi

echo "Checking if port $PORT is open on $HOST"
if command -v nc >/dev/null 2>&1; then
    if nc -z "$HOST" "$PORT" 2>/dev/null; then
        echo "✓ Port $PORT is open on $HOST"
        exit 0
    else
        echo "✗ Port $PORT is not open on $HOST"
        exit 1
    fi
elif command -v curl >/dev/null 2>&1; then
    if curl -s --connect-timeout 5 "$HOST:$PORT" >/dev/null 2>&1; then
        echo "✓ Port $PORT is open on $HOST"
        exit 0
    else
        echo "✗ Port $PORT is not open on $HOST"
        exit 1
    fi
else
    echo "✗ Neither nc nor curl available for port check"
    exit 1
fi''',

        'wait_for_service': '''#!/bin/bash
set -e
set -o pipefail

SERVICE="{service}"
TIMEOUT_PARAM="{timeout}"
if [ -z "$SERVICE" ]; then
    echo "✗ Error: Service name is required"
    exit 1
fi
if [ -z "$TIMEOUT_PARAM" ] || [ "$TIMEOUT_PARAM" = "None" ]; then
    TIMEOUT=60
else
    TIMEOUT="$TIMEOUT_PARAM"
fi

echo "Waiting for service to be ready: $SERVICE (timeout: ${TIMEOUT}s)"
START_TIME=$(date +%s)

while true; do
    CURRENT_TIME=$(date +%s)
    ELAPSED=$((CURRENT_TIME - START_TIME))
    
    if [ $ELAPSED -ge $TIMEOUT ]; then
        echo "✗ Timeout waiting for service: $SERVICE"
        exit 1
    fi
    
    if pgrep -f "$SERVICE" >/dev/null 2>&1; then
        echo "✓ Service is running: $SERVICE"
        exit 0
    fi
    
    echo "  Waiting for service... (${ELAPSED}s/${TIMEOUT}s)"
    sleep 2
done''',

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
        Initialize the Agno AI compiler.
        
        Args:
            model_id: Model identifier in LM Studio (default: openai/gpt-oss-20b)
            lm_studio_url: LM Studio server URL (default: http://localhost:1234)
            timeout: Request timeout in seconds
        """
        self.model_id = model_id
        self.lm_studio_url = lm_studio_url
        self.timeout = timeout
        
        # Initialize Agno agent with structured output
        try:
            # Create LM Studio model with proper configuration
            lm_studio_model = LMStudio(
                id=model_id,
                base_url=lm_studio_url,
                # Add additional parameters that might help with LM Studio compatibility
                timeout=timeout,
                max_tokens=4000,
                temperature=0.05  # Lower temperature for more deterministic template selection
            )
            
            self.agent = Agent(
                model=lm_studio_model,
                response_model=AgentArtifactBundle,
                description="You are an expert DevOps engineer specializing in generating executable artifacts for task automation.",
                instructions=self._get_system_instructions(),
                markdown=False  # We want structured output, not markdown
            )
            logger.info(f"Initialized Agno AI agent with model: {model_id}")
            
            # Test connection to LM Studio - fail fast if not available
            logger.info("Validating LM Studio connection...")
            self._test_lm_studio_connection()
            logger.info("LM Studio validation successful - ready for AI compilation")
            
        except AgnoCompilerError:
            # Re-raise AgnoCompilerError with original message
            raise
        except Exception as e:
            logger.error(f"Failed to initialize Agno agent: {e}")
            raise AgnoCompilerError(f"Failed to initialize AI agent: {e}")
    
    def _get_system_instructions(self) -> str:
        """Get simplified system instructions for template-based artifact generation."""
        return f"""
You are an expert DevOps automation specialist. Your job is to convert task specifications into executable artifacts by selecting and parameterizing proven script templates.

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
- Commands: Use 'run_command' or 'run_with_timeout'
- Services: Use 'check_port', 'wait_for_service'
- Docker: Use 'docker_run'
- HTTP Checks: Use 'check_http'
- JSON Config: Use 'write_json_config'
- Generic Tasks: Use 'simple_task'

PARAMETER INFERENCE:
When parameters aren't explicitly provided, intelligently infer them:
- Ports: nginx=80, api=8080, database=5432/3306, redis=6379
- Paths: Use descriptive names under .clockwork/build/ or scripts/
- Timeouts: 30s for checks, 60s for service waits
- Hosts: Default to "localhost"

TEMPLATE CHAINING EXAMPLES:
1. Deploy web service:
   - create_directory (for config)
   - write_file (config file)
   - docker_run (start container)
   - check_port (verify running)

2. Verify deployment:
   - verify_exists (check files)
   - check_http (test endpoints)
   - check_port (verify services)

OUTPUT FORMAT:
You MUST respond with a JSON object containing:
- artifacts: Array of template selections with parameters
- steps: Execution order matching artifacts
- vars: Environment variables for the templates

EXAMPLE OUTPUT:
{{
  "version": "1",
  "artifacts": [
    {{
      "path": "scripts/01_setup_directory.sh",
      "mode": "0755",
      "purpose": "setup_directory",
      "template": "create_directory",
      "params": {{"path": "./demo-output"}}
    }},
    {{
      "path": "scripts/02_write_config.sh",
      "mode": "0755", 
      "purpose": "write_config",
      "template": "write_file",
      "params": {{"path": "./demo-output/config.json", "content": "{{\\"name\\": \\"demo\\"}}"}}
    }}
  ],
  "steps": [
    {{"purpose": "setup_directory", "run": {{"cmd": ["bash", "scripts/01_setup_directory.sh"]}}}},
    {{"purpose": "write_config", "run": {{"cmd": ["bash", "scripts/02_write_config.sh"]}}}}
  ],
  "vars": {{
    "DEMO_NAME": "clockwork-demo",
    "CONFIG_PATH": "./demo-output/config.json"
  }}
}}

REMEMBER:
- NEVER write bash code - only select templates and provide parameters
- All scripts will be generated from the proven templates
- Focus on correct template selection and parameter values
- Ensure proper dependency order in steps array"""

    def _get_template_descriptions(self) -> str:
        """Generate descriptions of available script templates."""
        return """
FILE OPERATIONS:
• create_directory: Creates a directory with proper error handling
  Parameters: path (required) - Directory path to create
  Example: {"template": "create_directory", "params": {"path": "./demo-output"}}

• write_file: Writes content to a file, creating parent directories if needed
  Parameters: path (required), content (required) - File path and content
  Example: {"template": "write_file", "params": {"path": "./config.json", "content": "{\\"name\\": \\"demo\\"}"}}

• verify_exists: Checks if a file or directory exists
  Parameters: path (required) - Path to verify
  Example: {"template": "verify_exists", "params": {"path": "./demo-output"}}

COMMAND OPERATIONS:
• run_command: Executes a shell command with error handling
  Parameters: command (required) - Command to execute
  Example: {"template": "run_command", "params": {"command": "echo Hello World"}}

• run_with_timeout: Executes a command with a timeout
  Parameters: command (required), timeout (optional, default: 30) - Command and timeout in seconds
  Example: {"template": "run_with_timeout", "params": {"command": "sleep 5", "timeout": "10"}}

SERVICE OPERATIONS:
• check_port: Checks if a port is open on a host
  Parameters: port (required), host (optional, default: localhost) - Port number and hostname
  Example: {"template": "check_port", "params": {"port": "8080", "host": "localhost"}}

• wait_for_service: Waits for a service to be running
  Parameters: service (required), timeout (optional, default: 60) - Service name and timeout
  Example: {"template": "wait_for_service", "params": {"service": "nginx", "timeout": "120"}}

DOCKER OPERATIONS:
• docker_run: Starts a Docker container
  Parameters: image (required), name (optional), ports (optional), env_vars (optional)
  Example: {"template": "docker_run", "params": {"image": "nginx:latest", "ports": "8080:80"}}

WEB/API OPERATIONS:
• check_http: Performs HTTP health check
  Parameters: url (required), expected_status (optional, default: 200)
  Example: {"template": "check_http", "params": {"url": "http://localhost:8080", "expected_status": "200"}}

CONFIGURATION:
• write_json_config: Writes a JSON configuration file with validation
  Parameters: path (required), config_json (required) - File path and JSON content
  Example: {"template": "write_json_config", "params": {"path": "./config.json", "config_json": "{\\"port\\": 8080}"}}

GENERIC:
• simple_task: Generic template for simple operations
  Parameters: task_name (required), description (optional), task_commands (required)
  Example: {"template": "simple_task", "params": {"task_name": "cleanup", "task_commands": "rm -f temp.txt"}}
"""

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
    
    def validate_template_params(self, template_name: str, params: Dict[str, Any]) -> List[str]:
        """
        Validate that all required parameters are provided for a template.
        
        Args:
            template_name: Name of the template
            params: Parameters to validate
            
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        if template_name not in self.SCRIPT_TEMPLATES:
            errors.append(f"Unknown template: '{template_name}'")
            return errors
        
        template = self.SCRIPT_TEMPLATES[template_name]
        
        # Extract parameter placeholders from template
        import re
        param_placeholders = re.findall(r'\{(\w+)\}', template)
        required_params = set(param_placeholders)
        
        # Check for missing required parameters
        provided_params = set(params.keys())
        missing_params = required_params - provided_params
        
        if missing_params:
            errors.append(
                f"Template '{template_name}' missing required parameters: {', '.join(missing_params)}"
            )
        
        return errors
    
    def list_available_templates(self) -> Dict[str, str]:
        """
        Get a list of all available templates with their descriptions.
        
        Returns:
            Dictionary mapping template names to descriptions
        """
        # Extract first line of each template as description
        descriptions = {}
        for name, template in self.SCRIPT_TEMPLATES.items():
            lines = template.strip().split('\n')
            # Find the first comment line after shebang
            description = f"Script template: {name}"
            for line in lines[1:]:  # Skip shebang
                if line.strip().startswith('#') and 'Error:' not in line:
                    description = line.strip('#').strip()
                    break
            descriptions[name] = description
        
        return descriptions

    def compile_to_artifacts(self, action_list: ActionList) -> ArtifactBundle:
        """
        Compile an ActionList into an ArtifactBundle using AI agent.
        
        Args:
            action_list: The ActionList to compile
            
        Returns:
            ArtifactBundle with generated executable artifacts
            
        Raises:
            AgnoCompilerError: If compilation fails
        """
        try:
            logger.info(f"Starting AI compilation of {len(action_list.steps)} action steps")
            
            # Use direct HTTP client instead of Agno due to LM Studio compatibility issues
            agent_bundle = self._call_lm_studio_directly(action_list)
            
            # Convert to Clockwork ArtifactBundle format
            clockwork_bundle = self._convert_to_clockwork_format(agent_bundle)
            
            logger.info(f"AI compilation completed: {len(clockwork_bundle.artifacts)} artifacts generated")
            return clockwork_bundle
            
        except Exception as e:
            logger.error(f"AI compilation failed: {e}")
            raise AgnoCompilerError(f"Failed to compile with AI agent: {e}")
    
    def _call_lm_studio_directly(self, action_list: ActionList) -> AgentArtifactBundle:
        """
        Call LM Studio directly using HTTP requests to avoid Agno compatibility issues.
        
        Args:
            action_list: The ActionList to compile
            
        Returns:
            AgentArtifactBundle with AI-generated artifacts
            
        Raises:
            AgnoCompilerError: If the call fails
        """
        try:
            import requests
            import json
            
            # Generate prompt
            prompt = self._generate_compilation_prompt(action_list)
            
            # Prepare request payload for LM Studio
            payload = {
                "model": self.model_id,
                "messages": [
                    {
                        "role": "system", 
                        "content": self._get_system_instructions()
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                "temperature": 0.05,  # Lower temperature for more deterministic template selection
                "max_tokens": 6000,
                "response_format": {"type": "text"}  # LM Studio requires 'text' or 'json_schema'
            }
            
            logger.debug("Sending request to LM Studio...")
            
            # Call LM Studio API
            response = requests.post(
                f"{self.lm_studio_url}/v1/chat/completions",
                json=payload,
                timeout=self.timeout,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code != 200:
                logger.error(f"LM Studio returned status {response.status_code}: {response.text}")
                raise AgnoCompilerError(f"LM Studio API error: {response.status_code} - {response.text}")
            
            # Parse response
            response_data = response.json()
            logger.debug(f"LM Studio response: {response_data}")
            
            # Extract content from OpenAI-compatible response
            if "choices" not in response_data or not response_data["choices"]:
                raise AgnoCompilerError("LM Studio response missing choices")
            
            content = response_data["choices"][0]["message"]["content"]
            logger.info(f"AI response content preview: {content[:200]}...")
            
            # Clean content to extract JSON (handle thinking tokens)
            cleaned_content = self._extract_json_from_response(content)
            
            # Parse JSON content
            try:
                content_dict = json.loads(cleaned_content)
                agent_bundle = AgentArtifactBundle(**content_dict)
                return agent_bundle
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse AI response as JSON: {e}")
                logger.error(f"Raw content: {content[:500]}...")
                logger.error(f"Cleaned content: {cleaned_content[:500]}...")
                raise AgnoCompilerError(f"AI returned invalid JSON: {e}")
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error calling LM Studio: {e}")
            raise AgnoCompilerError(f"Failed to connect to LM Studio: {e}")
        except Exception as e:
            logger.error(f"Unexpected error in LM Studio call: {e}")
            raise AgnoCompilerError(f"LM Studio call failed: {e}")
    
    def _extract_json_from_response(self, content: str) -> str:
        """
        Extract JSON from AI response, handling thinking tokens and extra text.
        
        Args:
            content: Raw AI response content
            
        Returns:
            Cleaned JSON string
        """
        import re
        
        # First remove thinking tokens completely
        content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL)
        
        # Clean up whitespace
        content = content.strip()
        
        # Find the FIRST occurrence of { and match it properly with balanced braces
        start_idx = content.find('{')
        if start_idx == -1:
            raise AgnoCompilerError("No JSON object found in AI response")
            
        # Find the matching closing brace by counting brace levels
        brace_count = 0
        end_idx = start_idx
        in_string = False
        escape_next = False
        
        for i, char in enumerate(content[start_idx:], start_idx):
            if escape_next:
                escape_next = False
                continue
                
            if char == '\\':
                escape_next = True
                continue
                
            if char == '"' and not escape_next:
                in_string = not in_string
                continue
                
            if not in_string:
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        end_idx = i + 1
                        break
        
        if brace_count != 0:
            raise AgnoCompilerError("Incomplete JSON object in AI response")
            
        json_content = content[start_idx:end_idx]
        
        # Clean up the JSON content
        json_content = json_content.strip()
        logger.debug(f"Extracted JSON ({len(json_content)} chars): {json_content[:200]}...")
        return json_content
    
    def _generate_compilation_prompt(self, action_list: ActionList) -> str:
        """Generate a simplified prompt for template-based artifact compilation."""
        
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
• run_with_timeout - Executes command with timeout
  Required: command, Optional: timeout (default 30s)

SERVICE OPERATIONS:
• check_port - Checks if a port is open
  Required: port, Optional: host (default localhost)
• wait_for_service - Waits for a service to start
  Required: service, Optional: timeout (default 60s)

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
- Run commands → use run_command or run_with_timeout  
- Deploy services → use docker_run, then check_port
- Verify deployments → use check_http, verify_exists, check_port
- Database setup → use docker_run + wait_for_service
- Configuration → use write_json_config or write_file

PARAMETER INFERENCE:
When step arguments don't provide all needed parameters, infer reasonable defaults:
- Ports: nginx=80, api=8080, database=5432, redis=6379
- Paths: Use descriptive names under scripts/ (e.g., scripts/01_setup_dir.sh)
- Timeouts: 30s for quick checks, 60s for service waits
- Hosts: Default to "localhost"

EXAMPLE OUTPUT (respond with ONLY this JSON format):
{{
  "version": "1",
  "artifacts": [
    {{
      "path": "scripts/01_create_output_dir.sh",
      "mode": "0755",
      "purpose": "create_output_directory", 
      "template": "create_directory",
      "params": {{"path": "./demo-output"}}
    }},
    {{
      "path": "scripts/02_write_config_file.sh",
      "mode": "0755",
      "purpose": "write_config_file",
      "template": "write_file", 
      "params": {{"path": "./demo-output/config.json", "content": "{{\\"name\\": \\"demo\\", \\"version\\": \\"1.0\\"}}"}}
    }},
    {{
      "path": "scripts/03_verify_setup.sh",
      "mode": "0755", 
      "purpose": "verify_setup",
      "template": "verify_exists",
      "params": {{"path": "./demo-output/config.json"}}
    }}
  ],
  "steps": [
    {{"purpose": "create_output_directory", "run": {{"cmd": ["bash", "scripts/01_create_output_dir.sh"]}}}},
    {{"purpose": "write_config_file", "run": {{"cmd": ["bash", "scripts/02_write_config_file.sh"]}}}},
    {{"purpose": "verify_setup", "run": {{"cmd": ["bash", "scripts/03_verify_setup.sh"]}}}}
  ],
  "vars": {{
    "DEMO_NAME": "clockwork-demo",
    "OUTPUT_DIR": "./demo-output",
    "CONFIG_FILE": "./demo-output/config.json"
  }}
}}

CRITICAL REQUIREMENTS:
- Respond with ONLY the JSON object above
- Use ONLY the templates listed (do not write bash code)
- Each artifact needs: path, mode, purpose, template, params
- Steps array must match artifact purposes
- Include relevant environment variables in vars
- Number artifacts in execution order (01_, 02_, etc.)
- All paths should be under scripts/ directory"""
        
        return prompt
    
    def _analyze_project_context(self) -> str:
        """Analyze the current project context to provide intelligent defaults."""
        import os
        context_info = []
        
        # Check for common project files in current directory
        project_indicators = {
            'package.json': 'Node.js project detected - will infer npm/yarn scripts, port 3000 default',
            'requirements.txt': 'Python project detected - will infer pip dependencies, port 8000 default',
            'Dockerfile': 'Containerized project detected - will infer Docker deployment patterns',
            'docker-compose.yml': 'Docker Compose project detected - will infer multi-service architecture',
            'pom.xml': 'Maven Java project detected - will infer Java build patterns, port 8080 default',
            'go.mod': 'Go project detected - will infer Go build patterns, port 8080 default',
            'Cargo.toml': 'Rust project detected - will infer Cargo build patterns',
            '.env': 'Environment configuration detected - will infer environment variables',
            'kubernetes/': 'Kubernetes deployment detected - will infer K8s manifests',
            'helm/': 'Helm charts detected - will infer Helm deployment patterns',
            'terraform/': 'Infrastructure as Code detected - will infer Terraform patterns'
        }
        
        try:
            for indicator, description in project_indicators.items():
                if os.path.exists(indicator):
                    context_info.append(f"  - {description}")
        except Exception:
            # If we can't read the filesystem, provide general context
            context_info.append("  - General cloud-native deployment patterns will be applied")
        
        if not context_info:
            context_info.append("  - No specific project type detected, will apply general best practices")
        
        return "\n".join(context_info)
    
    def _analyze_step_for_inference(self, step) -> str:
        """Analyze a single step to provide intelligent inference suggestions."""
        step_name = step.name.lower()
        step_args = getattr(step, 'args', {})
        inferences = []
        
        # Service deployment inferences
        if any(keyword in step_name for keyword in ['nginx', 'apache', 'web']):
            inferences.extend([
                "→ Web service detected: Will infer port 80/443, health check on '/', SSL/TLS setup",
                "→ Will add reverse proxy configuration and static file serving",
                "→ Security headers (HSTS, CSP) and caching strategy will be included"
            ])
        
        elif any(keyword in step_name for keyword in ['api', 'service', 'backend']):
            inferences.extend([
                "→ API service detected: Will infer port 8080, health check on '/health'",
                "→ Will add CORS configuration, rate limiting, and API documentation",
                "→ Request/response logging and authentication middleware will be included"
            ])
        
        elif any(keyword in step_name for keyword in ['database', 'mysql', 'postgres', 'mongo', 'redis']):
            db_type = 'MySQL' if 'mysql' in step_name else 'PostgreSQL' if 'postgres' in step_name else 'MongoDB' if 'mongo' in step_name else 'Redis' if 'redis' in step_name else 'Database'
            port_map = {'mysql': '3306', 'postgres': '5432', 'mongo': '27017', 'redis': '6379'}
            port = next((port_map[db] for db in port_map.keys() if db in step_name), '5432')
            inferences.extend([
                f"→ {db_type} database detected: Will infer port {port}, data persistence volumes",
                "→ Will add backup/restore procedures, connection pooling, performance tuning",
                "→ Security hardening (encryption, access controls) will be included"
            ])
        
        # Port inference from args
        if 'port' in step_args:
            port = step_args['port']
            inferences.append(f"→ Custom port {port} specified: Will configure service accordingly")
        
        # Image/container inferences
        if any(keyword in step_name for keyword in ['deploy', 'container', 'docker']):
            inferences.extend([
                "→ Container deployment detected: Will infer resource limits, non-root user",
                "→ Health checks (liveness, readiness) and rolling update strategy will be added",
                "→ Pod disruption budgets and monitoring setup will be included"
            ])
        
        # Build process inferences
        if any(keyword in step_name for keyword in ['build', 'compile']):
            inferences.extend([
                "→ Build process detected: Will infer multi-stage builds for efficiency",
                "→ Will add caching strategies and security scanning",
                "→ Artifact optimization and dependency management will be included"
            ])
        
        # Dependency inferences
        depends_on = getattr(step, 'depends_on', [])
        if depends_on:
            inferences.append(f"→ Dependencies detected: {', '.join(depends_on)} - will ensure proper startup order")
        
        # Default inference if nothing specific detected
        if not inferences:
            inferences.append("→ General automation task: Will apply security best practices and error handling")
        
        return "\n  ".join(inferences)
    
    def _get_service_inference_templates(self) -> Dict[str, Dict[str, Any]]:
        """Get comprehensive service inference templates for common deployment patterns."""
        return {
            "nginx": {
                "default_port": 80,
                "health_check_path": "/",
                "health_check_port": 80,
                "security_context": {"runAsNonRoot": True, "runAsUser": 101},
                "resource_limits": {"memory": "256Mi", "cpu": "250m"},
                "environment_vars": {
                    "NGINX_PORT": "80",
                    "NGINX_HOST": "0.0.0.0",
                    "NGINX_LOG_LEVEL": "warn"
                },
                "volumes": ["/etc/nginx/conf.d", "/var/log/nginx", "/usr/share/nginx/html"],
                "protocols": ["HTTP", "HTTPS"],
                "scaling": {"min_replicas": 2, "max_replicas": 10},
                "monitoring": {"metrics_path": "/nginx_status", "metrics_port": 8080}
            },
            "apache": {
                "default_port": 80,
                "health_check_path": "/",
                "health_check_port": 80,
                "security_context": {"runAsNonRoot": True, "runAsUser": 33},
                "resource_limits": {"memory": "512Mi", "cpu": "500m"},
                "environment_vars": {
                    "APACHE_PORT": "80",
                    "APACHE_LOG_LEVEL": "warn",
                    "APACHE_RUN_USER": "www-data"
                },
                "volumes": ["/etc/apache2", "/var/log/apache2", "/var/www/html"],
                "protocols": ["HTTP", "HTTPS"],
                "scaling": {"min_replicas": 2, "max_replicas": 8}
            },
            "mysql": {
                "default_port": 3306,
                "health_check_path": None,
                "health_check_command": ["mysqladmin", "ping", "-h", "localhost"],
                "security_context": {"runAsNonRoot": True, "runAsUser": 999},
                "resource_limits": {"memory": "1Gi", "cpu": "1000m"},
                "environment_vars": {
                    "MYSQL_PORT": "3306",
                    "MYSQL_ROOT_PASSWORD": "${MYSQL_ROOT_PASSWORD}",
                    "MYSQL_DATABASE": "${MYSQL_DATABASE}",
                    "MYSQL_USER": "${MYSQL_USER}",
                    "MYSQL_PASSWORD": "${MYSQL_PASSWORD}"
                },
                "volumes": ["/var/lib/mysql", "/etc/mysql/conf.d", "/var/log/mysql"],
                "protocols": ["TCP"],
                "persistence": {"storage_class": "fast-ssd", "size": "20Gi"},
                "backup": {"schedule": "0 2 * * *", "retention": "7d"}
            },
            "postgresql": {
                "default_port": 5432,
                "health_check_path": None,
                "health_check_command": ["pg_isready", "-U", "postgres"],
                "security_context": {"runAsNonRoot": True, "runAsUser": 999},
                "resource_limits": {"memory": "1Gi", "cpu": "1000m"},
                "environment_vars": {
                    "POSTGRES_PORT": "5432",
                    "POSTGRES_DB": "${POSTGRES_DB}",
                    "POSTGRES_USER": "${POSTGRES_USER}",
                    "POSTGRES_PASSWORD": "${POSTGRES_PASSWORD}",
                    "PGDATA": "/var/lib/postgresql/data/pgdata"
                },
                "volumes": ["/var/lib/postgresql/data", "/etc/postgresql", "/var/log/postgresql"],
                "protocols": ["TCP"],
                "persistence": {"storage_class": "fast-ssd", "size": "20Gi"},
                "backup": {"schedule": "0 3 * * *", "retention": "7d"}
            },
            "redis": {
                "default_port": 6379,
                "health_check_path": None,
                "health_check_command": ["redis-cli", "ping"],
                "security_context": {"runAsNonRoot": True, "runAsUser": 999},
                "resource_limits": {"memory": "512Mi", "cpu": "500m"},
                "environment_vars": {
                    "REDIS_PORT": "6379",
                    "REDIS_PASSWORD": "${REDIS_PASSWORD}",
                    "REDIS_MAXMEMORY": "256mb",
                    "REDIS_MAXMEMORY_POLICY": "allkeys-lru"
                },
                "volumes": ["/data", "/etc/redis"],
                "protocols": ["TCP"],
                "persistence": {"enabled": True, "size": "10Gi"}
            },
            "mongodb": {
                "default_port": 27017,
                "health_check_path": None,
                "health_check_command": ["mongo", "--eval", "db.adminCommand('ping')"],
                "security_context": {"runAsNonRoot": True, "runAsUser": 999},
                "resource_limits": {"memory": "1Gi", "cpu": "1000m"},
                "environment_vars": {
                    "MONGO_PORT": "27017",
                    "MONGO_INITDB_ROOT_USERNAME": "${MONGO_ROOT_USERNAME}",
                    "MONGO_INITDB_ROOT_PASSWORD": "${MONGO_ROOT_PASSWORD}",
                    "MONGO_INITDB_DATABASE": "${MONGO_DATABASE}"
                },
                "volumes": ["/data/db", "/etc/mongo"],
                "protocols": ["TCP"],
                "persistence": {"storage_class": "fast-ssd", "size": "50Gi"}
            },
            "node": {
                "default_port": 3000,
                "health_check_path": "/health",
                "health_check_port": 3000,
                "security_context": {"runAsNonRoot": True, "runAsUser": 1000},
                "resource_limits": {"memory": "512Mi", "cpu": "500m"},
                "environment_vars": {
                    "NODE_ENV": "production",
                    "PORT": "3000",
                    "NPM_CONFIG_LOGLEVEL": "warn"
                },
                "volumes": ["/app", "/app/node_modules"],
                "protocols": ["HTTP", "HTTPS"],
                "scaling": {"min_replicas": 2, "max_replicas": 20}
            },
            "python": {
                "default_port": 8000,
                "health_check_path": "/health",
                "health_check_port": 8000,
                "security_context": {"runAsNonRoot": True, "runAsUser": 1000},
                "resource_limits": {"memory": "512Mi", "cpu": "500m"},
                "environment_vars": {
                    "PYTHONUNBUFFERED": "1",
                    "PORT": "8000",
                    "WORKERS": "4"
                },
                "volumes": ["/app"],
                "protocols": ["HTTP", "HTTPS"],
                "scaling": {"min_replicas": 2, "max_replicas": 15}
            },
            "go": {
                "default_port": 8080,
                "health_check_path": "/health",
                "health_check_port": 8080,
                "security_context": {"runAsNonRoot": True, "runAsUser": 1000},
                "resource_limits": {"memory": "256Mi", "cpu": "250m"},
                "environment_vars": {
                    "PORT": "8080",
                    "GIN_MODE": "release"
                },
                "volumes": ["/app"],
                "protocols": ["HTTP", "HTTPS"],
                "scaling": {"min_replicas": 2, "max_replicas": 20}
            },
            "java": {
                "default_port": 8080,
                "health_check_path": "/actuator/health",
                "health_check_port": 8080,
                "security_context": {"runAsNonRoot": True, "runAsUser": 1000},
                "resource_limits": {"memory": "1Gi", "cpu": "1000m"},
                "environment_vars": {
                    "JAVA_OPTS": "-Xmx768m -XX:+UseG1GC",
                    "SERVER_PORT": "8080",
                    "SPRING_PROFILES_ACTIVE": "production"
                },
                "volumes": ["/app"],
                "protocols": ["HTTP", "HTTPS"],
                "scaling": {"min_replicas": 2, "max_replicas": 10}
            }
        }
    
    def _infer_service_configuration(self, service_name: str, step_args: Dict[str, Any]) -> Dict[str, Any]:
        """Infer comprehensive service configuration based on service type and provided arguments."""
        templates = self._get_service_inference_templates()
        
        # Detect service type from name
        service_type = None
        service_name_lower = service_name.lower()
        
        for template_name in templates.keys():
            if template_name in service_name_lower:
                service_type = template_name
                break
        
        # If no specific type detected, try to infer from context
        if not service_type:
            if any(keyword in service_name_lower for keyword in ['web', 'frontend', 'ui']):
                service_type = 'nginx'
            elif any(keyword in service_name_lower for keyword in ['api', 'backend', 'service']):
                service_type = 'python'  # Default API service
            elif 'db' in service_name_lower or 'database' in service_name_lower:
                service_type = 'postgresql'  # Default database
        
        if not service_type:
            service_type = 'python'  # Ultimate fallback
        
        template = templates[service_type]
        
        # Start with template defaults
        config = {
            'service_type': service_type,
            'port': template['default_port'],
            'health_check_path': template.get('health_check_path'),
            'health_check_command': template.get('health_check_command'),
            'security_context': template['security_context'].copy(),
            'resource_limits': template['resource_limits'].copy(),
            'environment_vars': template['environment_vars'].copy(),
            'volumes': template['volumes'].copy(),
            'protocols': template['protocols'].copy(),
            'scaling': template.get('scaling', {'min_replicas': 1, 'max_replicas': 5}).copy()
        }
        
        # Override with user-provided arguments
        if 'port' in step_args:
            config['port'] = step_args['port']
            # Update related environment variables
            if 'PORT' in config['environment_vars']:
                config['environment_vars']['PORT'] = str(step_args['port'])
        
        if 'replicas' in step_args:
            config['scaling']['min_replicas'] = step_args['replicas']
            config['scaling']['max_replicas'] = max(step_args['replicas'], step_args['replicas'] * 3)
        
        if 'memory' in step_args:
            config['resource_limits']['memory'] = step_args['memory']
        
        if 'cpu' in step_args:
            config['resource_limits']['cpu'] = step_args['cpu']
        
        # Add additional inferred configurations
        config['monitoring'] = {
            'metrics_enabled': True,
            'logs_enabled': True,
            'tracing_enabled': True,
            'health_check_interval': '30s',
            'health_check_timeout': '5s'
        }
        
        config['security'] = {
            'network_policies': True,
            'pod_security_standards': 'restricted',
            'secrets_encryption': True,
            'read_only_root_filesystem': True
        }
        
        return config
    
    def _convert_to_clockwork_format(self, agent_bundle: AgentArtifactBundle) -> ArtifactBundle:
        """Convert AI agent response to Clockwork ArtifactBundle format with template expansion."""
        try:
            artifacts = []
            template_expansion_errors = []
            
            for i, agent_artifact in enumerate(agent_bundle.artifacts):
                try:
                    # Expand template into actual script content
                    if hasattr(agent_artifact, 'template') and agent_artifact.template:
                        # Validate template parameters first
                        validation_errors = self.validate_template_params(
                            agent_artifact.template, 
                            agent_artifact.params or {}
                        )
                        if validation_errors:
                            error_msg = f"Template validation failed for artifact {i}: {'; '.join(validation_errors)}"
                            template_expansion_errors.append(error_msg)
                            logger.error(error_msg)
                            
                            # Fall back to a simple error script
                            script_content = f'''#!/bin/bash
echo "✗ Template expansion error: {error_msg}"
exit 1'''
                        else:
                            # Expand the template with parameters
                            script_content = self.get_template(
                                agent_artifact.template, 
                                **(agent_artifact.params or {})
                            )
                            logger.info(f"Expanded template '{agent_artifact.template}' for artifact: {agent_artifact.path}")
                    
                    elif agent_artifact.content:
                        # Use direct content if provided (fallback)
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
            
            # Convert execution steps (unchanged)
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
    
    def _test_lm_studio_connection(self) -> None:
        """Test connection to LM Studio server and fail fast if not available.
        
        Raises:
            AgnoCompilerError: If LM Studio is not running or no models are loaded
        """
        try:
            import requests
        except ImportError:
            raise AgnoCompilerError(
                "requests library is required for LM Studio connection. "
                "Please install it with: pip install requests"
            )
        
        # Test if LM Studio server is responding
        try:
            models_url = f"{self.lm_studio_url}/v1/models"
            logger.info(f"Testing LM Studio connection at {self.lm_studio_url}...")
            response = requests.get(models_url, timeout=10)
            
            if response.status_code != 200:
                raise AgnoCompilerError(
                    f"LM Studio not running on {self.lm_studio_url}. "
                    f"Server responded with status {response.status_code}. "
                    f"Please start LM Studio and ensure it's running on {self.lm_studio_url}."
                )
            
            # Check if any models are loaded
            try:
                models_data = response.json()
                loaded_models = models_data.get('data', [])
                
                if not loaded_models:
                    raise AgnoCompilerError(
                        f"No models loaded in LM Studio at {self.lm_studio_url}. "
                        f"Please load a model in LM Studio before using the AI compiler. "
                        f"Expected model: {self.model_id}"
                    )
                
                # Check if the specific model we need is available
                available_models = [model.get('id', '') for model in loaded_models]
                if self.model_id not in available_models:
                    logger.warning(
                        f"Expected model '{self.model_id}' not found in loaded models: {available_models}. "
                        f"Will attempt to use the first available model."
                    )
                
                logger.info(f"LM Studio connection successful. Found {len(loaded_models)} loaded models.")
                
            except (ValueError, json.JSONDecodeError) as e:
                raise AgnoCompilerError(
                    f"LM Studio returned invalid JSON response from {models_url}. "
                    f"Please check that LM Studio is properly configured and running."
                )
                
        except requests.exceptions.ConnectionError:
            raise AgnoCompilerError(
                f"Cannot connect to LM Studio at {self.lm_studio_url}. "
                f"Please ensure LM Studio is running and accessible at {self.lm_studio_url}. "
                f"You can start LM Studio and load a model, then try again."
            )
        except requests.exceptions.Timeout:
            raise AgnoCompilerError(
                f"Timeout connecting to LM Studio at {self.lm_studio_url}. "
                f"LM Studio may be starting up or overloaded. Please wait and try again."
            )
        except requests.exceptions.RequestException as e:
            raise AgnoCompilerError(
                f"Failed to connect to LM Studio at {self.lm_studio_url}: {e}. "
                f"Please check your LM Studio configuration and network connectivity."
            )
        
        # Test with a simple completion to ensure the model is actually responsive
        self._test_model_responsiveness()
    
    def _test_model_responsiveness(self) -> None:
        """Test that the loaded model can respond to requests.
        
        Raises:
            AgnoCompilerError: If the model is not responsive
        """
        try:
            import requests
            
            logger.info("Testing model responsiveness...")
            test_payload = {
                "model": self.model_id,
                "messages": [{"role": "user", "content": "Respond with 'OK' to confirm you are working."}],
                "max_tokens": 5,
                "temperature": 0.1
            }
            
            response = requests.post(
                f"{self.lm_studio_url}/v1/chat/completions",
                json=test_payload,
                timeout=30
            )
            
            if response.status_code != 200:
                error_detail = ""
                try:
                    error_data = response.json()
                    error_detail = f" Error details: {error_data.get('error', {}).get('message', response.text)}"
                except:
                    error_detail = f" Server response: {response.text}"
                
                raise AgnoCompilerError(
                    f"Model '{self.model_id}' is not responding properly. "
                    f"Status: {response.status_code}.{error_detail} "
                    f"Please check that the correct model is loaded in LM Studio."
                )
            
            # Verify we got a valid response
            try:
                response_data = response.json()
                if "choices" not in response_data or not response_data["choices"]:
                    raise AgnoCompilerError(
                        f"Model '{self.model_id}' returned invalid response format. "
                        f"Please check that the model is properly loaded and configured in LM Studio."
                    )
                
                logger.info("Model responsiveness test successful.")
                
            except (ValueError, json.JSONDecodeError):
                raise AgnoCompilerError(
                    f"Model '{self.model_id}' returned invalid JSON response. "
                    f"Please check that the model is properly configured in LM Studio."
                )
                
        except requests.exceptions.RequestException as e:
            raise AgnoCompilerError(
                f"Failed to test model responsiveness: {e}. "
                f"The model may not be properly loaded or LM Studio may be experiencing issues."
            )
    
    def test_connection(self) -> bool:
        """
        Test connection to LM Studio server.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Use our strict connection test method
            self._test_lm_studio_connection()
            return True
            
        except AgnoCompilerError as e:
            logger.warning(f"LM Studio connection test failed: {e}")
            return False
        except Exception as e:
            logger.warning(f"Unexpected error in connection test: {e}")
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get status information about the AI agent."""
        return {
            "model_id": self.model_id,
            "lm_studio_url": self.lm_studio_url,
            "timeout": self.timeout,
            "connection_ok": self.test_connection()
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