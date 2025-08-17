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
    """Pydantic model for AI agent artifact generation."""
    path: str = Field(..., description="Relative path for the artifact file (e.g., 'scripts/01_fetch_repo.sh')")
    mode: str = Field(..., description="File permissions in octal format (e.g., '0755' for executable, '0644' for data)")
    purpose: str = Field(..., description="The purpose/name of the action this artifact serves")
    lang: str = Field(..., description="Programming language (bash, python, deno, go, etc.)")
    content: str = Field(..., description="Complete executable content of the artifact with proper headers and error handling")


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
    from declarative ActionList specifications.
    """
    
    def __init__(
        self,
        model_id: str = "qwen/qwen3-4b-2507",
        lm_studio_url: str = "http://localhost:1234",
        timeout: int = 300
    ):
        """
        Initialize the Agno AI compiler.
        
        Args:
            model_id: Model identifier in LM Studio (default: qwen/qwen3-4b-2507)
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
                temperature=0.1
            )
            
            self.agent = Agent(
                model=lm_studio_model,
                response_model=AgentArtifactBundle,
                description="You are an expert DevOps engineer specializing in generating executable artifacts for task automation.",
                instructions=self._get_system_instructions(),
                markdown=False  # We want structured output, not markdown
            )
            logger.info(f"Initialized Agno AI agent with model: {model_id}")
            
            # Test connection to LM Studio
            logger.info("Testing connection to LM Studio...")
            connection_ok = self._test_lm_studio_connection()
            if not connection_ok:
                logger.warning("LM Studio connection test failed - model may not be loaded")
            else:
                logger.info("LM Studio connection test successful")
            
        except Exception as e:
            logger.error(f"Failed to initialize Agno agent: {e}")
            raise AgnoCompilerError(f"Failed to initialize AI agent: {e}")
    
    def _get_system_instructions(self) -> str:
        """Get comprehensive system instructions for the AI agent."""
        return """
You are an expert DevOps engineer and automation specialist. Your job is to convert high-level declarative task specifications into production-ready executable artifacts.

CORE RESPONSIBILITIES:
1. Generate secure, production-ready scripts in appropriate languages
2. Ensure all artifacts follow security best practices
3. Include comprehensive error handling and logging
4. Respect execution order and dependencies
5. Use only allowlisted runtimes and secure file paths

SECURITY REQUIREMENTS:
- All artifact paths must be under .clockwork/build/ or scripts/
- Only use allowlisted runtimes: bash, python3, python, deno, go, node, npm, npx, java, mvn, gradle, dotnet, cargo, rustc, env
- Executable files should have 0755 permissions, data files 0644
- Never include hardcoded secrets or credentials
- Always validate inputs and handle errors gracefully

LANGUAGE SELECTION GUIDELINES:
- bash: System operations, file management, simple automation
- python3: Complex logic, API calls, data processing
- deno: Modern TypeScript/JavaScript with built-in security
- go: High-performance network operations, compiled binaries

SCRIPT STRUCTURE:
- Include proper shebang lines (#!/bin/bash, #!/usr/bin/env python3, etc.)
- Add descriptive comments explaining the purpose
- Include error handling with meaningful error messages
- Log important operations and results
- Use environment variables from the vars section
- Return meaningful exit codes (0 for success, non-zero for failure)

OUTPUT FORMAT:
Generate a complete ArtifactBundle with all required fields:
- version: Always "1"
- artifacts: Array of executable files with path, mode, purpose, lang, content
- steps: Array of execution commands matching artifact purposes
- vars: Environment variables and configuration values
"""

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
                "temperature": 0.1,
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
        """Generate a comprehensive prompt for AI artifact compilation."""
        prompt = f"""
Generate executable artifacts for the following task automation sequence:

ACTION LIST SPECIFICATION:
Version: {action_list.version}
Total Steps: {len(action_list.steps)}

STEPS TO IMPLEMENT:
"""
        
        for i, step in enumerate(action_list.steps, 1):
            prompt += f"""
Step {i}: {step.name}
  Arguments: {json.dumps(step.args, indent=2)}
"""
        
        prompt += f"""

IMPLEMENTATION REQUIREMENTS:
1. Create one artifact per step (or combine related steps if logical)
2. Use appropriate programming languages for each task type
3. Ensure all file paths are under .clockwork/build/ or scripts/
4. Include comprehensive error handling and logging
5. Use environment variables for configuration values
6. Follow security best practices (no hardcoded secrets, input validation)
7. Add proper file permissions (0755 for executables, 0644 for data)

ARTIFACT NAMING CONVENTION:
- Use descriptive names: scripts/01_fetch_repo.sh, scripts/02_build_image.py
- Number artifacts in execution order
- Include file extension matching the language

EXECUTION STEPS:
- Each step must have a 'purpose' matching an artifact's purpose
- Include the complete command to execute the artifact
- Example: {{"purpose": "fetch_repo", "run": {{"cmd": ["bash", "scripts/01_fetch_repo.sh"]}}}}

ENVIRONMENT VARIABLES:
Include relevant configuration in the vars section:
- Repository URLs, branch names, image tags
- Port numbers, service names
- Timeout values, retry counts

CRITICAL OUTPUT REQUIREMENT:
You MUST respond with ONLY a valid JSON object that exactly matches this structure:

{{
  "version": "1",
  "artifacts": [
    {{
      "path": "scripts/01_deploy_service.sh",
      "mode": "0755",
      "purpose": "ensure_service",
      "lang": "bash",
      "content": "#!/bin/bash\\nset -e\\necho 'Deploying service...'\\n# Add deployment commands here"
    }}
  ],
  "steps": [
    {{
      "purpose": "ensure_service",
      "run": {{"cmd": ["bash", "scripts/01_deploy_service.sh"]}}
    }}
  ],
  "vars": {{
    "SERVICE_NAME": "web",
    "PORT": "8080"
  }}
}}

IMPORTANT:
- Respond ONLY with valid JSON
- No explanatory text or comments
- Start with {{ and end with }}
- Follow the exact structure shown above
"""
        return prompt
    
    def _convert_to_clockwork_format(self, agent_bundle: AgentArtifactBundle) -> ArtifactBundle:
        """Convert AI agent response to Clockwork ArtifactBundle format."""
        try:
            # Convert artifacts
            artifacts = []
            for agent_artifact in agent_bundle.artifacts:
                artifact = Artifact(
                    path=agent_artifact.path,
                    mode=agent_artifact.mode,
                    purpose=agent_artifact.purpose,
                    lang=agent_artifact.lang,
                    content=agent_artifact.content
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
            
            # Create Clockwork ArtifactBundle
            bundle = ArtifactBundle(
                version=agent_bundle.version,
                artifacts=artifacts,
                steps=steps,
                vars=agent_bundle.vars or {}
            )
            
            return bundle
            
        except Exception as e:
            raise AgnoCompilerError(f"Failed to convert AI response to ArtifactBundle: {e}")
    
    def _test_lm_studio_connection(self) -> bool:
        """Test basic connection to LM Studio server."""
        try:
            import requests
            
            # Test if LM Studio server is responding
            health_url = f"{self.lm_studio_url}/health"
            try:
                response = requests.get(health_url, timeout=5)
                if response.status_code == 200:
                    logger.debug("LM Studio health check passed")
                    return True
            except requests.exceptions.RequestException:
                logger.debug("LM Studio health endpoint not available, trying models endpoint")
            
            # Try models endpoint to see if any models are loaded
            models_url = f"{self.lm_studio_url}/v1/models"
            try:
                response = requests.get(models_url, timeout=5)
                if response.status_code == 200:
                    models_data = response.json()
                    if models_data.get('data'):
                        logger.info(f"Found {len(models_data['data'])} loaded models in LM Studio")
                        return True
                    else:
                        logger.warning("No models loaded in LM Studio")
                        return False
            except requests.exceptions.RequestException:
                logger.debug("LM Studio models endpoint not available")
            
            # Fallback: try simple completion
            return self._test_simple_completion()
            
        except Exception as e:
            logger.debug(f"LM Studio connection test failed: {e}")
            return False
    
    def _test_simple_completion(self) -> bool:
        """Test with a simple completion request."""
        try:
            import requests
            
            test_payload = {
                "model": self.model_id,
                "messages": [{"role": "user", "content": "Test"}],
                "max_tokens": 10
            }
            
            response = requests.post(
                f"{self.lm_studio_url}/v1/chat/completions",
                json=test_payload,
                timeout=10
            )
            
            if response.status_code == 200:
                logger.debug("LM Studio completion test successful")
                return True
            else:
                logger.warning(f"LM Studio returned status {response.status_code}: {response.text}")
                return False
                
        except Exception as e:
            logger.debug(f"Simple completion test failed: {e}")
            return False
    
    def test_connection(self) -> bool:
        """
        Test connection to LM Studio server.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Simple test query to verify the agent is working
            test_response = self.agent.run("Respond with 'OK' to confirm connection.")
            return test_response is not None and test_response.content is not None
            
        except Exception as e:
            logger.warning(f"LM Studio connection test failed: {e}")
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
    model_id = model_id or "qwen/qwen3-4b-2507"
    lm_studio_url = lm_studio_url or "http://localhost:1234"
    
    return AgnoCompiler(
        model_id=model_id,
        lm_studio_url=lm_studio_url,
        **kwargs
    )