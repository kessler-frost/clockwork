"""
Clockwork to PyInfra Parser

This module provides functionality to parse Clockwork (.cw) files and convert them
directly into executable PyInfra Python code. It supports:

1. Parsing .cw HCL-like syntax using existing HCL parsing infrastructure
2. Mapping Clockwork resources to PyInfra operations:
   - resource "service" → docker.container operations
   - resource "repository" → git.repo operations
   - resource "file" → files.file operations
   - health_check blocks → server.shell operations for verification
3. Variable substitution and string interpolation
4. PyInfra inventory generation from targets
5. Comprehensive error handling and validation

Usage:
    parser = PyInfraParser()
    python_code = parser.parse_file("main.cw")

    # Or parse a string directly
    python_code = parser.parse_string(cw_content)
"""

import re
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, Tuple
from datetime import datetime

# Import HCL parsing and Clockwork models
import hcl2
from .models import IR, Resource, Variable, Output, ResourceType

logger = logging.getLogger(__name__)


class PyInfraParserError(Exception):
    """Exception raised when PyInfra parsing fails."""

    def __init__(self, message: str, file_path: str = None, line_number: int = None):
        self.message = message
        self.file_path = file_path
        self.line_number = line_number

        error_msg = f"PyInfra parser error: {message}"
        if file_path:
            error_msg += f" in file '{file_path}'"
        if line_number:
            error_msg += f" at line {line_number}"

        super().__init__(error_msg)


class PyInfraParser:
    """
    Parser that converts Clockwork .cw files to executable PyInfra Python code.

    This parser reuses the existing HCL parsing infrastructure and generates
    PyInfra deploy scripts with proper operation mappings and inventory.
    """

    def __init__(self, default_host: str = "localhost"):
        """
        Initialize the PyInfra parser.

        Args:
            default_host: Default host for PyInfra inventory when no targets specified
        """
        # No separate HCL parser instance needed, using hcl2 directly
        self.default_host = default_host
        self._resource_mappings = self._init_resource_mappings()

    def _parse_hcl_to_ir(self, content: str, source_path: str = None) -> IR:
        """Parse HCL content and convert to IR."""
        try:
            # Parse HCL content
            parsed = hcl2.loads(content)

            # Convert to IR
            ir = IR()

            # Process variables - hcl2 returns lists
            if 'variable' in parsed:
                for var_block in parsed['variable']:
                    for var_name, var_config in var_block.items():
                        variable = Variable(
                            name=var_name,
                            type=var_config.get('type', 'string'),
                            default=var_config.get('default'),
                            description=var_config.get('description', ''),
                            required=var_config.get('required', False)
                        )
                        ir.variables[var_name] = variable

            # Process resources
            if 'resource' in parsed:
                # hcl2 returns a list of resource blocks
                for resource_block in parsed['resource']:
                    for resource_type, resource_instances in resource_block.items():
                        for resource_name, resource_config in resource_instances.items():
                            resource_id = f"{resource_type}.{resource_name}"

                            # Map resource type
                            type_mapping = {
                                'service': ResourceType.SERVICE,
                                'file': ResourceType.FILE,
                                'repository': ResourceType.CUSTOM,
                                'directory': ResourceType.DIRECTORY
                            }

                            resource = Resource(
                                type=type_mapping.get(resource_type, ResourceType.CUSTOM),
                                name=resource_name,
                                config=resource_config
                            )
                            ir.resources[resource_id] = resource

            # Process outputs
            if 'output' in parsed:
                # hcl2 returns a list of output blocks (similar to resources)
                if isinstance(parsed['output'], list):
                    for output_block in parsed['output']:
                        for output_name, output_config in output_block.items():
                            output = Output(
                                name=output_name,
                                value=output_config.get('value', ''),
                                description=output_config.get('description', '')
                            )
                            ir.outputs[output_name] = output
                else:
                    # Fallback for when output is a dictionary (older hcl2 versions)
                    for output_name, output_configs in parsed['output'].items():
                        for output_config in output_configs:
                            output = Output(
                                name=output_name,
                                value=output_config.get('value', ''),
                                description=output_config.get('description', '')
                            )
                            ir.outputs[output_name] = output

            return ir

        except Exception as e:
            raise PyInfraParserError(
                f"Failed to parse HCL content: {e}",
                file_path=source_path
            )

    def _init_resource_mappings(self) -> Dict[str, Dict[str, Any]]:
        """
        Initialize mappings from Clockwork resource types to PyInfra operations.

        Returns:
            Dictionary mapping resource types to their PyInfra operation details
        """
        return {
            "service": {
                "module": "docker.container",
                "operation": "running",
                "required_args": ["name", "image"],
                "optional_args": ["ports", "environment", "volumes", "restart_policy"]
            },
            "repository": {
                "module": "git.repo",
                "operation": "repo",
                "required_args": ["dest"],
                "optional_args": ["src", "branch", "update"]
            },
            "file": {
                "module": "files.file",
                "operation": "file",
                "required_args": ["path"],
                "optional_args": ["content", "mode", "user", "group", "backup"]
            },
            "directory": {
                "module": "files.directory",
                "operation": "directory",
                "required_args": ["path"],
                "optional_args": ["mode", "user", "group", "recursive"]
            },
            "verification": {
                "module": "server.shell",
                "operation": "command",
                "required_args": ["command"],
                "optional_args": ["chdir", "env", "success_codes"]
            }
        }

    def parse_file(self, file_path: Union[str, Path], targets: Optional[List[str]] = None) -> str:
        """
        Parse a .cw file and generate executable PyInfra Python code.

        Args:
            file_path: Path to the .cw file to parse
            targets: Optional list of target hosts for PyInfra inventory

        Returns:
            Generated PyInfra Python code as a string

        Raises:
            PyInfraParserError: If parsing fails
            FileNotFoundError: If the file does not exist
        """
        file_path = Path(file_path)

        try:
            # Read and parse .cw file
            with open(file_path, 'r') as f:
                content = f.read()
            ir = self._parse_hcl_to_ir(content, str(file_path))

            # Generate PyInfra code
            return self._generate_pyinfra_code(ir, targets or [self.default_host], str(file_path))

        except PyInfraParserError:
            raise
        except Exception as e:
            raise PyInfraParserError(f"Unexpected error: {str(e)}", str(file_path))

    def parse_string(self, cw_content: str, targets: Optional[List[str]] = None) -> str:
        """
        Parse .cw content from a string and generate PyInfra Python code.

        Args:
            cw_content: .cw file content as a string
            targets: Optional list of target hosts for PyInfra inventory

        Returns:
            Generated PyInfra Python code as a string

        Raises:
            PyInfraParserError: If parsing fails
        """
        try:
            # Parse HCL content directly
            ir = self._parse_hcl_to_ir(cw_content)

            # Generate PyInfra code
            return self._generate_pyinfra_code(ir, targets or [self.default_host])

        except PyInfraParserError:
            raise
        except Exception as e:
            raise PyInfraParserError(f"Unexpected error: {str(e)}")

    def parse_directory(self, directory_path: Union[str, Path],
                       targets: Optional[List[str]] = None) -> str:
        """
        Parse all .cw files in a directory and generate consolidated PyInfra code.

        Args:
            directory_path: Path to directory containing .cw files
            targets: Optional list of target hosts for PyInfra inventory

        Returns:
            Generated PyInfra Python code as a string

        Raises:
            PyInfraParserError: If parsing fails
        """
        directory_path = Path(directory_path)

        try:
            # Parse all .cw files in directory
            ir = IR()
            for cw_file in directory_path.glob("*.cw"):
                with open(cw_file, 'r') as f:
                    content = f.read()
                file_ir = self._parse_hcl_to_ir(content, str(cw_file))

                # Merge IRs
                ir.variables.update(file_ir.variables)
                ir.resources.update(file_ir.resources)
                ir.outputs.update(file_ir.outputs)

            # Generate PyInfra code
            return self._generate_pyinfra_code(ir, targets or [self.default_host], str(directory_path))

        except PyInfraParserError:
            raise
        except Exception as e:
            raise PyInfraParserError(f"Unexpected error: {str(e)}", str(directory_path))

    def parse_string_for_destroy(self, cw_content: str, targets: Optional[List[str]] = None) -> str:
        """
        Parse .cw content and generate PyInfra destroy operations.

        Args:
            cw_content: .cw file content as a string
            targets: Optional list of target hosts for PyInfra inventory

        Returns:
            Generated PyInfra Python code for destroying resources

        Raises:
            PyInfraParserError: If parsing fails
        """
        try:
            # Parse HCL content to intermediate representation
            ir = self._parse_hcl_to_ir(cw_content)

            # Resolve variables first
            resolved_variables = self._resolve_variables(ir.variables)

            # Generate PyInfra destroy code
            return self._generate_pyinfra_destroy_code(ir.resources, resolved_variables)

        except PyInfraParserError:
            raise
        except Exception as e:
            raise PyInfraParserError(f"Unexpected error: {str(e)}")

    def parse_file_for_destroy(self, file_path: Union[str, Path], targets: Optional[List[str]] = None) -> str:
        """
        Parse a .cw configuration file and generate PyInfra destroy operations.

        Args:
            file_path: Path to the .cw configuration file
            targets: Optional list of target hosts for PyInfra inventory

        Returns:
            Generated PyInfra Python code for destroying resources

        Raises:
            PyInfraParserError: If parsing fails
        """
        file_path = Path(file_path)

        if not file_path.exists():
            raise PyInfraParserError(f"Configuration file not found: {file_path}")

        if not file_path.suffix == '.cw':
            raise PyInfraParserError(f"Expected .cw file, got: {file_path.suffix}")

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            return self.parse_string_for_destroy(content, targets)

        except PyInfraParserError:
            raise
        except Exception as e:
            raise PyInfraParserError(f"Failed to parse file: {e}", str(file_path))

    def _generate_pyinfra_code(self, ir: IR, targets: List[str], source_path: str = None) -> str:
        """
        Generate executable PyInfra Python code from the parsed IR.

        Args:
            ir: Intermediate representation of the parsed .cw file(s)
            targets: List of target hosts for PyInfra inventory
            source_path: Optional source file/directory path for metadata

        Returns:
            Generated PyInfra Python code as a string
        """
        # Resolve variables first
        resolved_vars = self._resolve_variables(ir.variables)

        # Generate the PyInfra code sections
        header = self._generate_header(source_path, resolved_vars)
        inventory = self._generate_inventory(targets)
        imports = self._generate_imports(ir.resources)
        variables = self._generate_variables_section(resolved_vars)
        operations = self._generate_operations(ir.resources, resolved_vars)
        health_checks = self._generate_health_checks(ir.resources, resolved_vars)
        outputs = self._generate_outputs(ir.outputs, resolved_vars)

        # Combine all sections
        code_sections = [header, inventory, imports, variables, operations, health_checks, outputs]
        return "\n\n".join(section for section in code_sections if section.strip())

    def _resolve_variables(self, variables: Dict[str, Variable]) -> Dict[str, Any]:
        """
        Resolve variables to their default values or mark as required.

        Args:
            variables: Dictionary of Variable objects

        Returns:
            Dictionary of resolved variable values
        """
        resolved = {}

        for var_name, var_obj in variables.items():
            if var_obj.default is not None:
                resolved[var_name] = var_obj.default
            elif not var_obj.required:
                # Use a sensible default based on type
                if var_obj.type == "number":
                    resolved[var_name] = 0
                elif var_obj.type == "boolean":
                    resolved[var_name] = False
                elif var_obj.type == "list":
                    resolved[var_name] = []
                else:
                    resolved[var_name] = ""
            else:
                # Mark as required for substitution
                resolved[var_name] = f"<REQUIRED:{var_name}>"

        return resolved

    def _substitute_variables(self, text: Any, variables: Dict[str, Any]) -> Any:
        """
        Substitute variables in text using ${var.name} and var.name syntax.

        Args:
            text: Text to substitute (can be string, dict, list, etc.)
            variables: Dictionary of variable values

        Returns:
            Text with variables substituted
        """
        if isinstance(text, str):
            # Handle ${var.name} syntax
            def replace_var_ref(match):
                var_name = match.group(1)
                if var_name in variables:
                    return str(variables[var_name])
                logger.warning(f"Variable '{var_name}' not found, leaving unchanged")
                return match.group(0)

            text = re.sub(r'\$\{var\.([^}]+)\}', replace_var_ref, text)

            # Handle direct var.name references (as Python expressions)
            for var_name, var_value in variables.items():
                var_pattern = f"var.{var_name}"
                if var_pattern in text:
                    if isinstance(var_value, str):
                        text = text.replace(var_pattern, f"'{var_value}'")
                    else:
                        text = text.replace(var_pattern, str(var_value))

            return text

        elif isinstance(text, dict):
            return {k: self._substitute_variables(v, variables) for k, v in text.items()}
        elif isinstance(text, list):
            return [self._substitute_variables(item, variables) for item in text]
        else:
            return text

    def _generate_header(self, source_path: str = None, variables: Dict[str, Any] = None) -> str:
        """Generate the file header with metadata and docstring."""
        timestamp = datetime.now().isoformat()

        header = f'''"""
PyInfra Deploy Script
Generated from Clockwork configuration

Source: {source_path or 'Unknown'}
Generated: {timestamp}
Parser: Clockwork PyInfra Parser v1.0

This script was automatically generated from Clockwork .cw files.
Run with: pyinfra TARGETS deploy.py
"""'''

        if variables:
            header += f"\n\n# Configuration variables from .cw files"
            header += f"\n# Variables: {list(variables.keys())}"

        return header

    def _generate_inventory(self, targets: List[str]) -> str:
        """Generate PyInfra inventory section."""
        if len(targets) == 1 and targets[0] == "localhost":
            return """# PyInfra Inventory
# Using @local for localhost execution
INVENTORY = ['@local']"""
        else:
            targets_list = [f"'{target}'" for target in targets]
            return f"""# PyInfra Inventory
# Target hosts for deployment
INVENTORY = [{', '.join(targets_list)}]"""

    def _generate_imports(self, resources: Dict[str, Resource]) -> str:
        """Generate necessary PyInfra module imports based on resources."""
        imports = set(['from pyinfra import host'])
        modules = set()

        for resource in resources.values():
            resource_type = resource.type.value if hasattr(resource.type, 'value') else str(resource.type)

            if resource_type in self._resource_mappings:
                module = self._resource_mappings[resource_type]["module"]
                module_name = module.split('.')[0]  # Get base module name
                modules.add(module_name)
            else:
                # Default to server operations for unknown types
                modules.add("server")

        # Always add server for health checks
        modules.add("server")

        # Generate import statements
        for module in sorted(modules):
            imports.add(f"from pyinfra.operations import {module}")

        # Add common imports
        imports.add("import json")
        imports.add("import os")

        # Check if any file resources have content (need StringIO)
        for resource in resources.values():
            if resource.type == ResourceType.FILE and 'content' in resource.config:
                imports.add("from io import StringIO")
                break

        return "# PyInfra imports\n" + "\n".join(sorted(imports))

    def _generate_variables_section(self, variables: Dict[str, Any]) -> str:
        """Generate the variables section with resolved values."""
        if not variables:
            return "# No variables defined"

        lines = ["# Variables from .cw configuration"]

        for var_name, var_value in variables.items():
            if isinstance(var_value, str):
                # Check if it's a required variable marker
                if var_value.startswith("<REQUIRED:"):
                    lines.append(f'{var_name.upper()} = os.getenv("{var_name.upper()}", "{var_value}")')
                else:
                    lines.append(f'{var_name.upper()} = "{var_value}"')
            elif isinstance(var_value, (int, float, bool)):
                lines.append(f'{var_name.upper()} = {var_value}')
            elif isinstance(var_value, (list, dict)):
                lines.append(f'{var_name.upper()} = {json.dumps(var_value)}')
            else:
                lines.append(f'{var_name.upper()} = "{str(var_value)}"')

        return "\n".join(lines)

    def _generate_operations(self, resources: Dict[str, Resource], variables: Dict[str, Any]) -> str:
        """Generate PyInfra operations from resources."""
        if not resources:
            return "# No resources defined"

        lines = ["# Resource operations"]
        lines.append("")

        for resource_key, resource in resources.items():
            try:
                operation_code = self._generate_single_operation(resource, variables)
                if operation_code:
                    lines.append(f"# Resource: {resource_key}")
                    lines.append(operation_code)
                    lines.append("")
            except Exception as e:
                logger.error(f"Failed to generate operation for resource {resource_key}: {e}")
                lines.append(f"# ERROR: Failed to generate operation for {resource_key}: {e}")
                lines.append("")

        return "\n".join(lines)

    def _generate_single_operation(self, resource: Resource, variables: Dict[str, Any]) -> str:
        """Generate a single PyInfra operation from a resource."""
        resource_type = resource.type.value if hasattr(resource.type, 'value') else str(resource.type)

        # Substitute variables in the resource config
        config = self._substitute_variables(resource.config, variables)

        if resource_type == "service":
            return self._generate_service_operation(resource, config)
        elif resource_type == "repository":
            return self._generate_repository_operation(resource, config)
        elif resource_type == "file":
            return self._generate_file_operation(resource, config)
        elif resource_type == "directory":
            return self._generate_directory_operation(resource, config)
        else:
            # Generic operation using server.shell
            return self._generate_generic_operation(resource, config)

    def _generate_service_operation(self, resource: Resource, config: Dict[str, Any]) -> str:
        """Generate PyInfra docker.container operation for service resources."""
        name = config.get('name', resource.name)
        image = config.get('image', 'nginx:latest')

        lines = [f"# Service: {name}"]

        # Build the operation call
        args = [f'container="{name}"', f'image="{image}"']

        # Handle ports
        if 'ports' in config and config['ports']:
            ports_list = []
            for port_config in config['ports']:
                if isinstance(port_config, dict):
                    external = port_config.get('external', 80)
                    internal = port_config.get('internal', 80)
                    ports_list.append(f'"{external}:{internal}"')
                else:
                    ports_list.append(f'"{port_config}"')
            if ports_list:
                args.append(f'ports=[{", ".join(ports_list)}]')

        # Handle environment variables (temporarily disabled due to pyinfra parsing issue)
        # if 'environment' in config and config['environment']:
        #     env_dict = config['environment']
        #     env_items = [f'"{k}={v}"' for k, v in env_dict.items()]
        #     args.append(f'env_vars=[{", ".join(env_items)}]')

        # Handle volumes
        if 'volumes' in config and config['volumes']:
            volumes = config['volumes']
            if isinstance(volumes, list):
                volumes_list = [f'"{v}"' for v in volumes]
                args.append(f'volumes=[{", ".join(volumes_list)}]')

        # Handle restart policy
        if 'restart_policy' in config:
            args.append(f'restart_policy="{config["restart_policy"]}"')

        operation = f"docker.container(\n    {',\n    '.join(args)}\n)"

        return operation

    def _generate_repository_operation(self, resource: Resource, config: Dict[str, Any]) -> str:
        """Generate PyInfra git.repo operation for repository resources."""
        dest = config.get('dest', f'/opt/{resource.name}')
        src = config.get('src', config.get('url', ''))

        lines = [f"# Repository: {resource.name}"]

        args = [f'dest="{dest}"']
        if src:
            args.append(f'src="{src}"')

        if 'branch' in config:
            args.append(f'branch="{config["branch"]}"')

        if 'update' in config:
            args.append(f'update={config["update"]}')

        operation = f"git.repo(\n    {',\n    '.join(args)}\n)"

        return operation

    def _generate_file_operation(self, resource: Resource, config: Dict[str, Any]) -> str:
        """Generate PyInfra files.put operation for file resources with content."""
        path = config.get('path', f'/tmp/{resource.name}')

        if 'content' in config:
            # Use files.put with StringIO for content
            content = config['content'].replace('"', '\\"').replace('\n', '\\n')
            args = [f'src=StringIO("{content}")', f'dest="{path}"']
        else:
            # Use files.file for touch operation
            args = [f'path="{path}"', 'touch=True']

        if 'mode' in config:
            args.append(f'mode="{config["mode"]}"')

        if 'user' in config:
            args.append(f'user="{config["user"]}"')

        if 'group' in config:
            args.append(f'group="{config["group"]}"')

        if 'content' in config:
            operation = f"files.put(\n    {',\n    '.join(args)}\n)"
        else:
            operation = f"files.file(\n    {',\n    '.join(args)}\n)"

        return operation

    def _generate_directory_operation(self, resource: Resource, config: Dict[str, Any]) -> str:
        """Generate PyInfra files.directory operation for directory resources."""
        path = config.get('path', f'/opt/{resource.name}')

        args = [f'path="{path}"']

        if 'mode' in config:
            args.append(f'mode="{config["mode"]}"')

        if 'user' in config:
            args.append(f'user="{config["user"]}"')

        if 'group' in config:
            args.append(f'group="{config["group"]}"')

        if 'recursive' in config:
            args.append(f'recursive={config["recursive"]}')

        operation = f"files.directory(\n    {',\n    '.join(args)}\n)"

        return operation

    def _generate_generic_operation(self, resource: Resource, config: Dict[str, Any]) -> str:
        """Generate generic PyInfra server.shell operation for unknown resource types."""
        command = config.get('command', f'echo "Processing {resource.name}"')

        args = [f'commands="{command}"']

        if 'chdir' in config:
            args.append(f'chdir="{config["chdir"]}"')

        operation = f"server.shell(\n    {',\n    '.join(args)}\n)"

        return operation

    def _generate_health_checks(self, resources: Dict[str, Resource], variables: Dict[str, Any]) -> str:
        """Generate health check operations from resource health_check blocks."""
        health_checks = []

        for resource_key, resource in resources.items():
            config = self._substitute_variables(resource.config, variables)

            if 'health_check' in config:
                health_check_config = config['health_check']

                # Handle both single health check and list of health checks
                if isinstance(health_check_config, list):
                    health_checks_list = health_check_config
                else:
                    health_checks_list = [health_check_config]

                for hc in health_checks_list:
                    if isinstance(hc, dict):
                        check_code = self._generate_single_health_check(resource, hc, variables)
                        if check_code:
                            health_checks.append(check_code)

        if not health_checks:
            return "# No health checks defined"

        lines = ["# Health checks"]
        lines.extend(health_checks)

        return "\n\n".join(lines)

    def _generate_single_health_check(self, resource: Resource, health_check: Dict[str, Any], variables: Dict[str, Any]) -> str:
        """Generate a single health check operation."""
        path = health_check.get('path', '/')
        timeout = health_check.get('timeout', '5s')
        retries = health_check.get('retries', 3)

        # Convert health check to shell command
        if resource.type.value == "service":
            # Get the substituted config for accurate port info
            substituted_config = self._substitute_variables(resource.config, variables)
            service_name = substituted_config.get('name', resource.name)
            port = 8080  # default external port

            # Extract port from service config
            if 'ports' in substituted_config and substituted_config['ports']:
                port_config = substituted_config['ports'][0]
                if isinstance(port_config, dict):
                    port = port_config.get('external', port)
                else:
                    port = port_config

            # Generate HTTP health check command with retry logic
            command = f'sleep 5; for i in {{1..{retries}}}; do curl -f http://localhost:{port}{path} && exit 0 || sleep 2; done; exit 1'
        else:
            # Generic health check
            command = f'echo "Health check for {resource.name}: OK"'

        lines = [f"# Health check for {resource.name}"]
        args = [f'commands="{command}"']

        operation = f"server.shell(\n    {',\n    '.join(args)}\n)"

        return "\n".join([lines[0], operation])

    def _generate_outputs(self, outputs: Dict[str, Output], variables: Dict[str, Any]) -> str:
        """Generate output statements from output blocks."""
        if not outputs:
            return "# No outputs defined"

        lines = ["# Outputs"]
        lines.append("# Note: PyInfra doesn't have direct output support, using print statements")
        lines.append("")

        for output_name, output in outputs.items():
            value = self._substitute_variables(output.value, variables)
            description = output.description or f"Output: {output_name}"

            lines.append(f'# {description}')
            lines.append(f'print(f"{output_name}: {value}")')
            lines.append("")

        return "\n".join(lines)

    def _generate_pyinfra_destroy_code(self, resources: Dict[str, Resource], variables: Dict[str, Any]) -> str:
        """
        Generate PyInfra operations for destroying resources (reverse operations).

        Args:
            resources: Dictionary of resources to destroy
            variables: Dictionary of variable values

        Returns:
            Generated PyInfra Python code for destruction
        """
        operations = []

        # Process resources in reverse order for proper cleanup
        for resource_key, resource in reversed(list(resources.items())):
            operation_code = self._generate_single_destroy_operation(resource, variables)
            operations.append(operation_code)

        if not operations:
            return "# No resources to destroy"

        lines = [
            "# Generated PyInfra destroy operations from .cw file",
            "# This code removes/destroys infrastructure components",
            "",
            "from pyinfra.operations import docker, files, git, server",
            "",
        ]

        lines.extend(operations)

        return "\n\n".join(lines)

    def _generate_single_destroy_operation(self, resource: Resource, variables: Dict[str, Any]) -> str:
        """
        Generate a single destroy operation for a resource.

        Args:
            resource: Resource to destroy
            variables: Dictionary of variable values

        Returns:
            PyInfra operation code for destroying the resource
        """
        config = self._substitute_variables(resource.config, variables)

        if resource.type.value == "service":
            return self._generate_service_destroy_operation(resource, config)
        elif resource.type.value == "repository":
            return self._generate_repository_destroy_operation(resource, config)
        elif resource.type.value == "file":
            return self._generate_file_destroy_operation(resource, config)
        elif resource.type.value == "directory":
            return self._generate_directory_destroy_operation(resource, config)
        else:
            return self._generate_generic_destroy_operation(resource, config)

    def _generate_service_destroy_operation(self, resource: Resource, config: Dict[str, Any]) -> str:
        """Generate PyInfra destroy operation for service resources (remove Docker container)."""
        service_name = config.get('name', resource.name)

        args = [
            f'container="{service_name}"',
            'present=False'  # This removes the container
        ]

        operation = f"docker.container(\n    {',\n    '.join(args)}\n)"

        lines = [f"# Destroy service: {resource.name}", operation]
        return "\n".join(lines)

    def _generate_repository_destroy_operation(self, resource: Resource, config: Dict[str, Any]) -> str:
        """Generate PyInfra destroy operation for repository resources (remove directory)."""
        dest = config.get('dest', f'/opt/{resource.name}')

        args = [
            f'path="{dest}"',
            'present=False'  # This removes the directory
        ]

        operation = f"files.directory(\n    {',\n    '.join(args)}\n)"

        lines = [f"# Destroy repository: {resource.name}", operation]
        return "\n".join(lines)

    def _generate_file_destroy_operation(self, resource: Resource, config: Dict[str, Any]) -> str:
        """Generate PyInfra destroy operation for file resources."""
        path = config.get('path', f'/tmp/{resource.name}')

        args = [
            f'path="{path}"',
            'present=False'  # This removes the file
        ]

        operation = f"files.file(\n    {',\n    '.join(args)}\n)"

        lines = [f"# Destroy file: {resource.name}", operation]
        return "\n".join(lines)

    def _generate_directory_destroy_operation(self, resource: Resource, config: Dict[str, Any]) -> str:
        """Generate PyInfra destroy operation for directory resources."""
        path = config.get('path', f'/tmp/{resource.name}')

        args = [
            f'path="{path}"',
            'present=False'  # This removes the directory
        ]

        operation = f"files.directory(\n    {',\n    '.join(args)}\n)"

        lines = [f"# Destroy directory: {resource.name}", operation]
        return "\n".join(lines)

    def _generate_generic_destroy_operation(self, resource: Resource, config: Dict[str, Any]) -> str:
        """Generate generic PyInfra destroy operation for unknown resource types."""
        command = config.get('destroy_command', f'echo "Destroying {resource.name}"')

        args = [f'commands="{command}"']

        if 'chdir' in config:
            args.append(f'chdir="{config["chdir"]}"')

        operation = f"server.shell(\n    {',\n    '.join(args)}\n)"

        lines = [f"# Destroy resource: {resource.name}", operation]
        return "\n".join(lines)


def parse_cw_to_pyinfra(file_path: Union[str, Path],
                       targets: Optional[List[str]] = None,
                       output_file: Optional[Union[str, Path]] = None) -> str:
    """
    Convenience function to parse a .cw file and generate PyInfra code.

    Args:
        file_path: Path to the .cw file to parse
        targets: Optional list of target hosts for PyInfra inventory
        output_file: Optional path to write the generated code to

    Returns:
        Generated PyInfra Python code as a string

    Raises:
        PyInfraParserError: If parsing fails
    """
    parser = PyInfraParser()
    python_code = parser.parse_file(file_path, targets)

    if output_file:
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(python_code)
        logger.info(f"Generated PyInfra code written to {output_path}")

    return python_code


# Export main classes and functions
__all__ = [
    'PyInfraParser',
    'PyInfraParserError',
    'parse_cw_to_pyinfra'
]