"""
Compiler module for converting ActionList to ArtifactBundle using AI agents.

This module provides the interface for calling AI agents to transform 
declarative action lists into executable artifacts in various languages.
"""

import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pathlib import Path

logger = logging.getLogger(__name__)


class LanguageType(Enum):
    """Supported artifact languages."""
    PYTHON = "python"
    BASH = "bash"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    GO = "go"
    RUST = "rust"


class ActionType(Enum):
    """Types of actions that can be compiled."""
    FILE_OPERATION = "file_operation"
    NETWORK_REQUEST = "network_request"
    SYSTEM_COMMAND = "system_command"
    DATA_PROCESSING = "data_processing"
    API_CALL = "api_call"
    CUSTOM = "custom"


@dataclass
class Action:
    """Represents a single action to be performed."""
    action_type: ActionType
    description: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    timeout: Optional[int] = None
    retry_count: int = 0
    
    def validate(self) -> None:
        """Validate the action configuration."""
        if not self.description.strip():
            raise ValueError("Action description cannot be empty")
        
        if self.timeout is not None and self.timeout <= 0:
            raise ValueError("Timeout must be positive")
            
        if self.retry_count < 0:
            raise ValueError("Retry count must be non-negative")


@dataclass
class ActionList:
    """Collection of actions to be compiled into artifacts."""
    name: str
    description: str
    actions: List[Action]
    target_language: LanguageType
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def validate(self) -> None:
        """Validate the entire action list."""
        if not self.name.strip():
            raise ValueError("ActionList name cannot be empty")
            
        if not self.actions:
            raise ValueError("ActionList must contain at least one action")
            
        # Validate each action
        for i, action in enumerate(self.actions):
            try:
                action.validate()
            except ValueError as e:
                raise ValueError(f"Action {i}: {e}")
                
        # Validate dependencies
        action_names = {f"action_{i}" for i in range(len(self.actions))}
        for i, action in enumerate(self.actions):
            for dep in action.dependencies:
                if dep not in action_names:
                    raise ValueError(f"Action {i} has invalid dependency: {dep}")


@dataclass
class Artifact:
    """Represents a single executable artifact."""
    name: str
    language: LanguageType
    code: str
    entry_point: str
    dependencies: List[str] = field(default_factory=list)
    environment_vars: Dict[str, str] = field(default_factory=dict)
    
    def validate(self) -> None:
        """Validate the artifact."""
        if not self.name.strip():
            raise ValueError("Artifact name cannot be empty")
            
        if not self.code.strip():
            raise ValueError("Artifact code cannot be empty")
            
        if not self.entry_point.strip():
            raise ValueError("Artifact entry point cannot be empty")


@dataclass
class ArtifactBundle:
    """Bundle of artifacts generated from an ActionList."""
    name: str
    description: str
    artifacts: List[Artifact]
    execution_order: List[str]
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def validate(self) -> None:
        """Validate the artifact bundle."""
        if not self.name.strip():
            raise ValueError("ArtifactBundle name cannot be empty")
            
        if not self.artifacts:
            raise ValueError("ArtifactBundle must contain at least one artifact")
            
        # Validate each artifact
        artifact_names = {artifact.name for artifact in self.artifacts}
        for artifact in self.artifacts:
            artifact.validate()
            
        # Validate execution order
        for name in self.execution_order:
            if name not in artifact_names:
                raise ValueError(f"Execution order references unknown artifact: {name}")


class CompilerError(Exception):
    """Exception raised during compilation process."""
    pass


class Compiler:
    """
    Compiler interface for converting ActionList to ArtifactBundle using AI agents.
    
    This class provides the interface for calling AI agents to transform
    declarative action lists into executable artifacts.
    """
    
    def __init__(
        self, 
        agent_endpoint: Optional[str] = None,
        api_key: Optional[str] = None,
        model_name: str = "gpt-4",
        timeout: int = 300
    ):
        """
        Initialize the compiler.
        
        Args:
            agent_endpoint: URL of the AI agent endpoint
            api_key: API key for authentication
            model_name: Name of the AI model to use
            timeout: Request timeout in seconds
        """
        self.agent_endpoint = agent_endpoint or "https://api.openai.com/v1/chat/completions"
        self.api_key = api_key
        self.model_name = model_name
        self.timeout = timeout
        
        logger.info(f"Initialized compiler with model: {model_name}")
    
    def compile(self, action_list: ActionList) -> ArtifactBundle:
        """
        Compile an ActionList into an ArtifactBundle.
        
        Args:
            action_list: The list of actions to compile
            
        Returns:
            ArtifactBundle containing executable artifacts
            
        Raises:
            CompilerError: If compilation fails
        """
        try:
            # Validate input
            action_list.validate()
            logger.info(f"Compiling ActionList: {action_list.name}")
            
            # Generate prompt for AI agent
            prompt = self._generate_compilation_prompt(action_list)
            
            # Call AI agent
            response = self._call_agent(prompt)
            
            # Parse response into ArtifactBundle
            artifact_bundle = self._parse_agent_response(response, action_list)
            
            # Validate output
            artifact_bundle.validate()
            
            logger.info(f"Successfully compiled {len(artifact_bundle.artifacts)} artifacts")
            return artifact_bundle
            
        except Exception as e:
            logger.error(f"Compilation failed: {e}")
            raise CompilerError(f"Failed to compile ActionList: {e}")
    
    def _generate_compilation_prompt(self, action_list: ActionList) -> str:
        """Generate prompt for the AI agent."""
        prompt = f"""
You are an expert software engineer tasked with converting a declarative action list 
into executable code in {action_list.target_language.value}.

ActionList Details:
Name: {action_list.name}
Description: {action_list.description}
Target Language: {action_list.target_language.value}

Actions:
"""
        
        for i, action in enumerate(action_list.actions):
            prompt += f"""
Action {i}:
  Type: {action.action_type.value}
  Description: {action.description}
  Parameters: {json.dumps(action.parameters, indent=2)}
  Dependencies: {action.dependencies}
  Timeout: {action.timeout}
  Retry Count: {action.retry_count}
"""
        
        prompt += f"""

Requirements:
1. Generate clean, production-ready code in {action_list.target_language.value}
2. Include proper error handling and logging
3. Respect action dependencies and execution order
4. Include necessary imports and dependencies
5. Add appropriate comments and documentation
6. Ensure code is secure and follows best practices

Please respond with a JSON object containing:
{{
  "artifacts": [
    {{
      "name": "artifact_name",
      "language": "{action_list.target_language.value}",
      "code": "generated_code_here",
      "entry_point": "main_function_or_file",
      "dependencies": ["list", "of", "dependencies"],
      "environment_vars": {{"ENV_VAR": "value"}}
    }}
  ],
  "execution_order": ["artifact1", "artifact2"],
  "metadata": {{"compilation_info": "additional_details"}}
}}
"""
        return prompt
    
    def _call_agent(self, prompt: str) -> str:
        """
        Call the AI agent with the given prompt.
        
        Args:
            prompt: The prompt to send to the agent
            
        Returns:
            The agent's response
            
        Raises:
            CompilerError: If the agent call fails
        """
        # This is a placeholder implementation
        # In a real implementation, this would make an HTTP request to the AI agent
        logger.info("Calling AI agent for compilation")
        
        # Mock response for demonstration
        mock_response = {
            "artifacts": [
                {
                    "name": "main_artifact",
                    "language": "python",
                    "code": "# Generated Python code\nprint('Hello, World!')",
                    "entry_point": "main",
                    "dependencies": ["requests"],
                    "environment_vars": {}
                }
            ],
            "execution_order": ["main_artifact"],
            "metadata": {"compilation_timestamp": "2024-01-01T00:00:00Z"}
        }
        
        return json.dumps(mock_response)
    
    def _parse_agent_response(self, response: str, action_list: ActionList) -> ArtifactBundle:
        """
        Parse the agent's response into an ArtifactBundle.
        
        Args:
            response: JSON response from the agent
            action_list: Original action list for context
            
        Returns:
            Parsed ArtifactBundle
            
        Raises:
            CompilerError: If parsing fails
        """
        try:
            data = json.loads(response)
            
            # Parse artifacts
            artifacts = []
            for artifact_data in data.get("artifacts", []):
                artifact = Artifact(
                    name=artifact_data["name"],
                    language=LanguageType(artifact_data["language"]),
                    code=artifact_data["code"],
                    entry_point=artifact_data["entry_point"],
                    dependencies=artifact_data.get("dependencies", []),
                    environment_vars=artifact_data.get("environment_vars", {})
                )
                artifacts.append(artifact)
            
            # Create bundle
            bundle = ArtifactBundle(
                name=f"{action_list.name}_bundle",
                description=f"Compiled artifacts for {action_list.name}",
                artifacts=artifacts,
                execution_order=data.get("execution_order", []),
                metadata=data.get("metadata", {})
            )
            
            return bundle
            
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            raise CompilerError(f"Failed to parse agent response: {e}")
    
    def save_bundle(self, bundle: ArtifactBundle, output_dir: Path) -> None:
        """
        Save an ArtifactBundle to disk.
        
        Args:
            bundle: The bundle to save
            output_dir: Directory to save artifacts
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Save bundle metadata
        bundle_info = {
            "name": bundle.name,
            "description": bundle.description,
            "execution_order": bundle.execution_order,
            "metadata": bundle.metadata
        }
        
        with open(output_dir / "bundle.json", "w") as f:
            json.dump(bundle_info, f, indent=2)
        
        # Save each artifact
        for artifact in bundle.artifacts:
            file_ext = self._get_file_extension(artifact.language)
            artifact_file = output_dir / f"{artifact.name}{file_ext}"
            
            with open(artifact_file, "w") as f:
                f.write(artifact.code)
        
        logger.info(f"Saved bundle to {output_dir}")
    
    def _get_file_extension(self, language: LanguageType) -> str:
        """Get file extension for a given language."""
        extensions = {
            LanguageType.PYTHON: ".py",
            LanguageType.BASH: ".sh",
            LanguageType.JAVASCRIPT: ".js",
            LanguageType.TYPESCRIPT: ".ts",
            LanguageType.GO: ".go",
            LanguageType.RUST: ".rs"
        }
        return extensions.get(language, ".txt")