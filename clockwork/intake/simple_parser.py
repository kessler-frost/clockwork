"""
Simple Syntax Parser for Clockwork Configuration Files

This module provides functionality to parse simplified .cw files with intent-based
declarations instead of verbose HCL configurations. It converts minimal syntax to
full IR that the existing system can understand.
"""

import hcl2
import logging
from pathlib import Path
from typing import Dict, Any, Union, List, Optional
from datetime import datetime
import re

# Import IR models
from ..models import IR, Variable, Resource, Module, Output, ResourceType

logger = logging.getLogger(__name__)


def parse_timeout(timeout_value: Any) -> int:
    """
    Parse timeout value to integer seconds.
    
    Args:
        timeout_value: Timeout value (int, str with unit, or str number)
        
    Returns:
        Integer timeout in seconds
    """
    if isinstance(timeout_value, int):
        return timeout_value
    elif isinstance(timeout_value, str):
        # Handle common time units
        timeout_str = timeout_value.lower().strip()
        if timeout_str.endswith('s'):
            return int(timeout_str[:-1])
        elif timeout_str.endswith('m'):
            return int(timeout_str[:-1]) * 60
        elif timeout_str.endswith('h'):
            return int(timeout_str[:-1]) * 3600
        else:
            # Assume it's already a number as string
            return int(timeout_str)
    else:
        return 300  # Default 5 minutes


class SimpleParseError(Exception):
    """Exception raised when simple syntax parsing fails."""
    
    def __init__(self, message: str, file_path: str = None, line_number: int = None):
        self.message = message
        self.file_path = file_path
        self.line_number = line_number
        
        error_msg = f"Simple parse error: {message}"
        if file_path:
            error_msg += f" in file '{file_path}'"
        if line_number:
            error_msg += f" at line {line_number}"
            
        super().__init__(error_msg)


class SimpleParser:
    """
    Parser for simplified Clockwork configuration files.
    
    Handles the parsing of minimal intent-based .cw files and converts them
    to full IR that the existing system can understand.
    """
    
    def __init__(self):
        """Initialize the simple parser."""
        self.auto_generated_vars = {}
        self.resource_counter = 0
    
    def is_simple_syntax(self, content: str) -> bool:
        """
        Detect if the content uses simplified syntax.
        
        Simple syntax is identified by:
        - Presence of simple directives (deploy, create_file, run_command, etc.)
        - Absence of explicit variable blocks
        - Simplified block structure
        
        Args:
            content: Raw file content to analyze
            
        Returns:
            True if content appears to use simple syntax
        """
        # Simple directives that indicate simplified syntax (top-level blocks only)
        simple_directives = [
            r'^[\s]*deployment\s+["\']',
            r'^[\s]*deploy\s+["\']',
            r'^[\s]*create_file\s+["\']',
            r'^[\s]*run_command\s+["\']',
            r'^[\s]*verify_http\s+["\']',
            r'^[\s]*wait_for\s+["\']',
            r'^[\s]*script\s+["\']'
        ]
        
        # Check for simple directive patterns (multiline mode for ^ anchor)
        has_simple_directives = any(re.search(pattern, content, re.IGNORECASE | re.MULTILINE) for pattern in simple_directives)
        
        # Traditional HCL patterns that indicate complex syntax
        traditional_patterns = [
            r'\bvariable\s+["\'][^"\']+["\']\s*{',
            r'\bresource\s+["\'][^"\']+["\']\s+["\'][^"\']+["\']\s*{',
            r'\bmodule\s+["\'][^"\']+["\']\s*{',
            r'\bprovider\s+["\'][^"\']+["\']\s*{',
            r'\btype\s*=\s*["\']',
            r'\bdefault\s*=\s*',
            r'\bdescription\s*=\s*["\']'
        ]
        
        has_traditional_patterns = any(re.search(pattern, content, re.IGNORECASE) for pattern in traditional_patterns)
        
        # If it has simple directives and no complex traditional patterns, it's likely simple syntax
        if has_simple_directives and not has_traditional_patterns:
            return True
            
        # If it has both, lean towards traditional (safer fallback)
        if has_simple_directives and has_traditional_patterns:
            return False
            
        # If it has traditional patterns, it's NOT simple syntax
        if has_traditional_patterns:
            return False
        
        # If it has simple directives, it IS simple syntax
        if has_simple_directives:
            return True
        
        # If it has neither, check for overall complexity
        # Count blocks and variable references
        block_count = len(re.findall(r'\w+\s*["\'][^"\']*["\']?\s*{', content))
        var_ref_count = len(re.findall(r'\bvar\.', content))
        
        # Simple files tend to have fewer blocks and variable references
        return block_count <= 3 and var_ref_count == 0
    
    def parse_string(self, content: str, file_path: str = None) -> Dict[str, Any]:
        """
        Parse simple syntax content from a string.
        
        Args:
            content: Simple syntax content as a string
            file_path: Optional file path for context
            
        Returns:
            Dictionary representation compatible with HCL parser output
            
        Raises:
            SimpleParseError: If the content cannot be parsed
        """
        try:
            # First try to parse as HCL to get the basic structure
            parsed_data = hcl2.loads(content)
            
            # Transform simple directives to full resource definitions
            return self._transform_simple_directives(parsed_data, file_path)
            
        except Exception as e:
            raise SimpleParseError(f"Failed to parse simple syntax: {str(e)}", file_path)
    
    def _transform_simple_directives(self, parsed_data: Dict[str, Any], file_path: str = None) -> Dict[str, Any]:
        """
        Transform simple directives into full resource definitions.
        
        Args:
            parsed_data: Parsed HCL data containing simple directives
            file_path: Optional file path for context
            
        Returns:
            Transformed data with full resource definitions
        """
        result = {
            "variable": {},
            "resource": {},
            "output": {}
        }
        
        # Keep track of created resources for dependency generation
        created_resources = []
        
        # Process each top-level block
        for block_type, blocks in parsed_data.items():
            if isinstance(blocks, dict):
                for block_name, block_config in blocks.items():
                    transformed = self._transform_directive(block_type, block_name, block_config, file_path)
                    if transformed:
                        self._merge_transformed_data(result, transformed, created_resources)
            elif isinstance(blocks, list):
                for block in blocks:
                    if isinstance(block, dict):
                        for block_name, block_config in block.items():
                            transformed = self._transform_directive(block_type, block_name, block_config, file_path)
                            if transformed:
                                self._merge_transformed_data(result, transformed, created_resources)
        
        # Generate dependencies based on resource order
        self._generate_dependencies(result, created_resources)
        
        return result
    
    def _transform_directive(self, directive_type: str, name: str, config: Dict[str, Any], file_path: str = None) -> Optional[Dict[str, Any]]:
        """
        Transform a single simple directive into full resource definitions.
        
        Args:
            directive_type: Type of directive (deploy, create_file, etc.)
            name: Name/identifier for the directive
            config: Configuration for the directive
            file_path: Optional file path for context
            
        Returns:
            Transformed data structure or None if not a recognized directive
        """
        directive_type = directive_type.lower()
        
        if directive_type in ["deploy", "deployment", "service"]:
            return self._transform_deploy_directive(name, config)
        elif directive_type in ["create_file", "file"]:
            return self._transform_file_directive(name, config)
        elif directive_type in ["run_command", "script", "command"]:
            return self._transform_command_directive(name, config)
        elif directive_type in ["verify_http", "verify"]:
            return self._transform_verify_directive(name, config)
        elif directive_type in ["wait_for", "wait"]:
            return self._transform_wait_directive(name, config)
        else:
            # Pass through unknown directives as generic resources
            return {
                "resource": {
                    directive_type: {
                        name: config
                    }
                }
            }
    
    def _transform_deploy_directive(self, service_name: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Transform deploy directive into service resource with smart defaults."""
        result = {
            "variable": {},
            "resource": {}
        }
        
        # Generate variables for common deployment parameters
        image_var = f"{service_name}_image"
        port_var = f"{service_name}_port"
        replicas_var = f"{service_name}_replicas"
        
        # Create variables with smart defaults
        if "image" not in config:
            result["variable"][image_var] = {
                "type": "string",
                "default": config.get("image", f"{service_name}:latest"),
                "description": f"Container image for {service_name} service"
            }
            self.auto_generated_vars[image_var] = f"var.{image_var}"
        
        if "port" in config:
            result["variable"][port_var] = {
                "type": "number", 
                "default": int(config["port"]) if isinstance(config["port"], (str, int)) else config["port"],
                "description": f"External port for {service_name} service"
            }
            self.auto_generated_vars[port_var] = f"var.{port_var}"
        
        # Build service resource configuration
        service_config = {
            "name": service_name,
            "image": config.get("image", f"var.{image_var}"),
            "ports": []
        }
        
        # Configure ports
        if "port" in config:
            service_config["ports"].append({
                "external": f"var.{port_var}",
                "internal": config.get("internal_port", 80)
            })
        
        # Add environment variables
        if "env" in config or "environment" in config:
            service_config["environment"] = config.get("env", config.get("environment", {}))
        else:
            # Add default environment
            service_config["environment"] = {
                "SERVICE_NAME": service_name
            }
        
        # Add health check if not specified
        if "health_check" not in config and "healthcheck" not in config:
            service_config["health_check"] = {
                "path": config.get("health_path", "/health"),
                "interval": "30s",
                "timeout": "5s",
                "retries": 3
            }
        else:
            service_config["health_check"] = config.get("health_check", config.get("healthcheck", {}))
        
        # Add replicas if specified
        if "replicas" in config:
            result["variable"][replicas_var] = {
                "type": "number",
                "default": config["replicas"], 
                "description": f"Number of replicas for {service_name} service"
            }
            service_config["replicas"] = f"var.{replicas_var}"
        
        # Add volumes if specified
        if "volumes" in config:
            service_config["volumes"] = config["volumes"]
        
        result["resource"]["service"] = {service_name: service_config}
        
        # Generate output for service URL
        if "port" in config:
            result["output"] = {
                f"{service_name}_url": {
                    "value": f"http://localhost:${{var.{port_var}}}",
                    "description": f"URL to access the {service_name} service"
                }
            }
        
        return result
    
    def _transform_file_directive(self, file_path: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Transform create_file directive into file resource."""
        result = {
            "resource": {}
        }
        
        # Generate unique resource name
        safe_name = re.sub(r'[^a-zA-Z0-9_]', '_', file_path.replace('/', '_').replace('.', '_'))
        resource_name = f"file_{safe_name}"
        
        file_config = {
            "path": file_path,
            "content": config.get("content", ""),
            "mode": config.get("mode", "0644")
        }
        
        # Handle different content types
        if "template" in config:
            file_config["template"] = config["template"]
            file_config["template_vars"] = config.get("vars", {})
        
        if "source" in config:
            file_config["source"] = config["source"]
        
        result["resource"]["file"] = {resource_name: file_config}
        
        return result
    
    def _transform_command_directive(self, command_name: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Transform run_command directive into script resource."""
        result = {
            "resource": {}
        }
        
        script_config = {
            "name": command_name,
            "interpreter": config.get("interpreter", "bash"),
            "timeout": parse_timeout(config.get("timeout", "300s"))
        }
        
        # Handle different script specification methods
        if "script" in config:
            script_config["content"] = config["script"]
        elif "command" in config:
            script_config["command"] = config["command"]
        elif "commands" in config:
            script_config["commands"] = config["commands"]
        
        # Add working directory if specified
        if "working_dir" in config or "cwd" in config:
            script_config["working_directory"] = config.get("working_dir", config.get("cwd"))
        
        # Add environment variables
        if "env" in config or "environment" in config:
            script_config["environment"] = config.get("env", config.get("environment", {}))
        
        result["resource"]["script"] = {command_name: script_config}
        
        return result
    
    def _transform_verify_directive(self, verify_name: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Transform verify_http directive into verification resource."""
        result = {
            "resource": {}
        }
        
        verify_config = {
            "name": verify_name
        }
        
        # Handle different verification types
        if "url" in config:
            verify_config["type"] = "http"
            verify_config["url"] = config["url"]
            verify_config["method"] = config.get("method", "GET")
            verify_config["expected_status"] = config.get("status", config.get("expected_status", 200))
        elif "service" in config:
            verify_config["type"] = "service"
            verify_config["service"] = config["service"]
            verify_config["port"] = config.get("port", 80)
        
        # Add timeout and retries  
        verify_config["timeout"] = parse_timeout(config.get("timeout", "30s"))
        verify_config["retries"] = config.get("retries", 3)
        verify_config["interval"] = parse_timeout(config.get("interval", "5s"))
        
        result["resource"]["verification"] = {verify_name: verify_config}
        
        return result
    
    def _transform_wait_directive(self, wait_name: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Transform wait_for directive into wait resource."""
        result = {
            "resource": {}
        }
        
        wait_config = {
            "name": wait_name,
            "timeout": parse_timeout(config.get("timeout", "300s"))
        }
        
        # Handle different wait conditions
        if "resource" in config:
            wait_config["wait_for_resource"] = config["resource"]
        elif "service" in config:
            wait_config["wait_for_service"] = config["service"]
        elif "url" in config:
            wait_config["wait_for_url"] = config["url"]
        elif "condition" in config:
            wait_config["condition"] = config["condition"]
        
        result["resource"]["wait"] = {wait_name: wait_config}
        
        return result
    
    def _merge_transformed_data(self, result: Dict[str, Any], transformed: Dict[str, Any], created_resources: List[str]):
        """Merge transformed directive data into the result."""
        for section, data in transformed.items():
            if section not in result:
                result[section] = {}
            
            if isinstance(data, dict):
                for sub_type, sub_data in data.items():
                    if sub_type not in result[section]:
                        result[section][sub_type] = {}
                    
                    if isinstance(sub_data, dict):
                        for resource_name, resource_config in sub_data.items():
                            result[section][sub_type][resource_name] = resource_config
                            
                            # Track created resources for dependency generation
                            if section == "resource":
                                created_resources.append(f"{sub_type}.{resource_name}")
    
    def _generate_dependencies(self, result: Dict[str, Any], created_resources: List[str]):
        """Generate smart dependencies between resources."""
        if "resource" not in result:
            return
        
        # Simple dependency rules:
        # 1. Services depend on files they might need
        # 2. Verifications depend on the services they verify
        # 3. Commands that setup databases run before services start
        # 4. Wait resources depend on what they're waiting for
        
        for resource_type, resources in result["resource"].items():
            for resource_name, resource_config in resources.items():
                depends_on = []
                
                if resource_type == "service":
                    # Services depend on setup scripts and files
                    for dep_resource in created_resources:
                        if dep_resource.startswith("script.setup") or dep_resource.startswith("script.init"):
                            depends_on.append(dep_resource)
                        elif dep_resource.startswith("file.") and ("config" in dep_resource or "env" in dep_resource):
                            depends_on.append(dep_resource)
                
                elif resource_type == "verification":
                    # Verifications depend on the services they verify
                    service_name = resource_config.get("service", resource_name)
                    service_resource = f"service.{service_name}"
                    if service_resource in created_resources:
                        depends_on.append(service_resource)
                
                elif resource_type == "script":
                    # Database migration scripts depend on database services
                    if "migrate" in resource_name or "database" in resource_name:
                        for dep_resource in created_resources:
                            if dep_resource.startswith("service.") and ("db" in dep_resource or "database" in dep_resource):
                                depends_on.append(dep_resource)
                
                if depends_on:
                    resource_config["depends_on"] = depends_on
    
    def to_ir(self, parsed_data: Dict[str, Any], file_path: str = None) -> IR:
        """
        Convert parsed simple syntax data to Clockwork Intermediate Representation (IR).
        
        Args:
            parsed_data: Parsed simple syntax data as dictionary
            file_path: Optional file path for context
            
        Returns:
            IR model instance with properly typed and validated data
            
        Raises:
            SimpleParseError: If conversion to IR fails
        """
        try:
            # Initialize collections for IR components
            variables = {}
            providers = []
            resources = {}
            modules = {}
            outputs = {}
            
            metadata = {
                "source_file": file_path,
                "parsed_at": datetime.now().isoformat(),
                "syntax_type": "simple",
                "auto_generated_vars": len(self.auto_generated_vars)
            }
            
            # Process variables
            if "variable" in parsed_data:
                for var_name, var_config in parsed_data["variable"].items():
                    variables[var_name] = Variable(
                        name=var_name,
                        type=var_config.get("type", "string"),
                        default=var_config.get("default"),
                        description=var_config.get("description"),
                        required=var_config.get("required", var_config.get("default") is None)
                    )
            
            # Process resources
            if "resource" in parsed_data:
                for resource_type_name, resource_instances in parsed_data["resource"].items():
                    # Map to known ResourceType
                    resource_type = ResourceType.SERVICE  # default
                    for rt in ResourceType:
                        if rt.value.lower() == resource_type_name.lower():
                            resource_type = rt
                            break
                    
                    # Handle special resource type mappings
                    if resource_type_name == "script":
                        resource_type = ResourceType.CUSTOM
                    elif resource_type_name == "verification":
                        resource_type = ResourceType.VERIFICATION
                    elif resource_type_name == "wait":
                        resource_type = ResourceType.CUSTOM
                    elif resource_type_name == "file":
                        resource_type = ResourceType.FILE
                    elif resource_type_name == "directory":
                        resource_type = ResourceType.DIRECTORY
                    elif resource_type_name == "check":
                        resource_type = ResourceType.CHECK
                    
                    # Process each instance
                    for resource_name, resource_config in resource_instances.items():
                        unique_key = f"{resource_type_name}.{resource_name}"
                        
                        resources[unique_key] = Resource(
                            type=resource_type,
                            name=resource_name,
                            config=resource_config,
                            depends_on=resource_config.get("depends_on", []),
                            tags={"generated_from": "simple_syntax", "resource_type": resource_type_name}
                        )
            
            # Process outputs
            if "output" in parsed_data:
                for output_name, output_config in parsed_data["output"].items():
                    outputs[output_name] = Output(
                        name=output_name,
                        value=output_config.get("value"),
                        description=output_config.get("description"),
                        sensitive=output_config.get("sensitive", False)
                    )
            
            # Create and return IR model instance
            return IR(
                version="1.0",
                metadata=metadata,
                variables=variables,
                providers=providers,
                resources=resources,
                modules=modules,
                outputs=outputs
            )
            
        except Exception as e:
            if isinstance(e, SimpleParseError):
                raise
            else:
                raise SimpleParseError(f"Failed to convert simple syntax to IR: {str(e)}", file_path)
    
    def parse_file(self, file_path: Union[str, Path]) -> Dict[str, Any]:
        """
        Parse a single simple syntax .cw file.
        
        Args:
            file_path: Path to the .cw file to parse
            
        Returns:
            Dictionary representation of the parsed content
            
        Raises:
            SimpleParseError: If the file cannot be parsed or read
            FileNotFoundError: If the file does not exist
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {file_path}")
            
        if file_path.suffix != '.cw':
            raise SimpleParseError(f"Expected .cw file, got {file_path.suffix}", str(file_path))
            
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()
                
            return self.parse_string(content, str(file_path))
            
        except Exception as e:
            if isinstance(e, (SimpleParseError, FileNotFoundError)):
                raise
            elif isinstance(e, UnicodeDecodeError):
                raise SimpleParseError(f"File encoding error: {str(e)}", str(file_path))
            else:
                raise SimpleParseError(f"Failed to parse simple syntax file: {str(e)}", str(file_path))
    
    def parse_file_to_ir(self, file_path: Union[str, Path]) -> IR:
        """
        Parse a single simple syntax .cw file directly to IR model.
        
        Args:
            file_path: Path to the .cw file to parse
            
        Returns:
            IR model instance
            
        Raises:
            SimpleParseError: If the file cannot be parsed
            FileNotFoundError: If the file does not exist
        """
        parsed_data = self.parse_file(file_path)
        return self.to_ir(parsed_data, str(file_path))