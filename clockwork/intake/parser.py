"""
HCL Parser for Clockwork Configuration Files

This module provides functionality to parse Clockwork (.cw) files written in HCL
format and convert them into structured Python dictionaries and intermediate
representations (IR) for further processing.
"""

import hcl2
from pathlib import Path
from typing import Dict, Any, Union, List, Optional
import json
from datetime import datetime

# Import IR models
from ..models import IR, Variable, Provider, Resource, Module, Output, ResourceType


class ParseError(Exception):
    """Exception raised when parsing fails."""
    
    def __init__(self, message: str, file_path: str = None, line_number: int = None):
        self.message = message
        self.file_path = file_path
        self.line_number = line_number
        
        error_msg = f"Parse error: {message}"
        if file_path:
            error_msg += f" in file '{file_path}'"
        if line_number:
            error_msg += f" at line {line_number}"
            
        super().__init__(error_msg)


class Parser:
    """
    Parser for Clockwork configuration files.
    
    Handles the parsing of HCL (.cw) files into Python dictionaries
    and converts them to structured intermediate representations.
    """
    
    def __init__(self, resolve_references: bool = True):
        """Initialize the parser.
        
        Args:
            resolve_references: Whether to automatically resolve module/provider references
        """
        self.parsed_files = {}
        self.resolve_references = resolve_references
        self._resolver = None
    
    @property
    def resolver(self):
        """Get or create resolver instance."""
        if self._resolver is None and self.resolve_references:
            try:
                from .resolver import Resolver
                self._resolver = Resolver()
            except ImportError:
                # Resolver not available, disable resolution
                self.resolve_references = False
        return self._resolver
    
    def set_resolver(self, resolver):
        """Set custom resolver instance."""
        self._resolver = resolver
        if resolver is not None:
            self.resolve_references = True
        
    def parse_file(self, file_path: Union[str, Path]) -> Dict[str, Any]:
        """
        Parse a single Clockwork configuration file (.cw or .cwvars).
        
        Args:
            file_path: Path to the .cw or .cwvars file to parse
            
        Returns:
            Dictionary representation of the parsed HCL content
            
        Raises:
            ParseError: If the file cannot be parsed or read
            FileNotFoundError: If the file does not exist
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {file_path}")
            
        if file_path.suffix not in ['.cw', '.cwvars']:
            raise ParseError(f"Expected .cw or .cwvars file, got {file_path.suffix}", str(file_path))
            
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()
                
            # Parse HCL content using python-hcl2
            parsed_data = hcl2.loads(content)
            
            # Cache the parsed result
            self.parsed_files[str(file_path)] = parsed_data
            
            return parsed_data
            
        except Exception as e:
            # Check if it's an HCL parsing error (lark UnexpectedToken or similar)
            if hasattr(e, 'token') or 'UnexpectedToken' in str(type(e).__name__):
                raise ParseError(f"Invalid HCL syntax: {str(e)}", str(file_path))
            elif isinstance(e, UnicodeDecodeError):
                raise ParseError(f"File encoding error: {str(e)}", str(file_path))
            else:
                raise ParseError(f"Failed to parse HCL content: {str(e)}", str(file_path))
    
    def parse_string(self, hcl_content: str) -> Dict[str, Any]:
        """
        Parse HCL content from a string.
        
        Args:
            hcl_content: HCL content as a string
            
        Returns:
            Dictionary representation of the parsed HCL content
            
        Raises:
            ParseError: If the content cannot be parsed
        """
        try:
            return hcl2.loads(hcl_content)
        except Exception as e:
            # Check if it's an HCL parsing error (lark UnexpectedToken or similar)
            if hasattr(e, 'token') or 'UnexpectedToken' in str(type(e).__name__):
                raise ParseError(f"Invalid HCL syntax: {str(e)}")
            else:
                raise ParseError(f"Failed to parse HCL content: {str(e)}")
    
    def parse_directory(self, directory_path: Union[str, Path], include_cwvars: bool = True) -> IR:
        """
        Parse all .cw files in a directory and merge them into a single IR.
        
        Args:
            directory_path: Path to directory containing .cw files
            include_cwvars: Whether to include .cwvars files for variable overrides
            
        Returns:
            Merged IR model instance combining all .cw files in the directory
            
        Raises:
            ParseError: If any file cannot be parsed
            NotADirectoryError: If the path is not a directory
        """
        directory_path = Path(directory_path)
        
        if not directory_path.is_dir():
            raise NotADirectoryError(f"Path is not a directory: {directory_path}")
            
        cw_files = list(directory_path.glob("*.cw"))
        
        if not cw_files:
            # Return empty IR if no .cw files found
            return IR(
                version="1.0",
                metadata={
                    "source_directory": str(directory_path),
                    "parsed_at": datetime.now().isoformat(),
                    "files_parsed": []
                }
            )
            
        # Parse all .cw files and collect their IRs
        individual_irs = []
        parsed_file_paths = []
        
        for file_path in cw_files:
            try:
                parsed_content = self.parse_file(file_path)
                ir = self.to_ir(parsed_content, str(file_path))
                individual_irs.append(ir)
                parsed_file_paths.append(str(file_path))
            except ParseError as e:
                # Re-raise with additional context
                raise ParseError(f"Error in directory parsing: {e.message}", e.file_path, e.line_number)
        
        # Merge all IRs into a single IR
        merged_ir = self._merge_irs(individual_irs, str(directory_path), parsed_file_paths)
        
        # Apply .cwvars overrides if requested
        if include_cwvars:
            cwvars_files = self.find_cwvars_files(directory_path)
            if cwvars_files:
                variable_overrides = {}
                for cwvars_file in cwvars_files:
                    try:
                        vars_data = self.parse_cwvars_file(cwvars_file)
                        variable_overrides.update(vars_data)
                        merged_ir.metadata["cwvars_files"] = merged_ir.metadata.get("cwvars_files", [])
                        merged_ir.metadata["cwvars_files"].append(str(cwvars_file))
                    except ParseError as e:
                        # Re-raise with additional context
                        raise ParseError(f"Error parsing .cwvars file: {e.message}", e.file_path, e.line_number)
                
                if variable_overrides:
                    merged_ir.variables = self.merge_variables(merged_ir.variables, variable_overrides)
                    merged_ir.metadata["variable_overrides_applied"] = True
        
        # Resolve module and provider references if enabled
        if self.resolve_references and self.resolver:
            try:
                merged_ir = self.resolve_ir_references(merged_ir)
            except Exception as e:
                # Add resolution error to metadata but don't fail the parsing
                merged_ir.metadata.update({
                    "resolution_error": str(e),
                    "resolution_attempted": True,
                    "resolution_success": False
                })
                
        return merged_ir
    
    def to_ir(self, parsed_data: Dict[str, Any], file_path: str = None) -> IR:
        """
        Convert parsed HCL data to Clockwork Intermediate Representation (IR).
        
        Args:
            parsed_data: Parsed HCL data as dictionary
            file_path: Optional file path for context
            
        Returns:
            IR model instance with properly typed and validated data
            
        Raises:
            ParseError: If conversion to IR fails
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
                "parsed_at": datetime.now().isoformat()
            }
            
            # Extract different HCL block types
            for block_type, blocks in parsed_data.items():
                if isinstance(blocks, list):
                    for block in blocks:
                        self._process_block_to_models(block_type, block, variables, providers, resources, modules, outputs)
                elif isinstance(blocks, dict):
                    self._process_block_to_models(block_type, blocks, variables, providers, resources, modules, outputs)
            
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
            if isinstance(e, ParseError):
                raise
            else:
                raise ParseError(f"Failed to convert to IR: {str(e)}", file_path)
    
    def _process_block_to_models(self, block_type: str, block_data: Dict[str, Any], 
                                variables: Dict[str, Variable], providers: List[Provider],
                                resources: Dict[str, Resource], modules: Dict[str, Module], 
                                outputs: Dict[str, Output]):
        """
        Process a single HCL block and convert to appropriate Pydantic models.
        
        Args:
            block_type: Type of the HCL block (e.g., 'resource', 'variable')
            block_data: The block's data
            variables: Dictionary to store Variable models
            providers: List to store Provider models
            resources: Dictionary to store Resource models
            modules: Dictionary to store Module models
            outputs: Dictionary to store Output models
        """
        try:
            if block_type == "variable":
                for var_name, var_config in block_data.items():
                    variables[var_name] = Variable(
                        name=var_name,
                        type=var_config.get("type", "string"),
                        default=var_config.get("default"),
                        description=var_config.get("description"),
                        required=var_config.get("required", True)
                    )
            
            elif block_type == "provider":
                for provider_name, provider_config in block_data.items():
                    providers.append(Provider(
                        name=provider_name,
                        source=provider_config.get("source", ""),
                        version=provider_config.get("version"),
                        config=provider_config.get("config", {})
                    ))
            
            elif block_type == "resource":
                # Handle HCL resource structure: resource "type" "name" { ... }
                # Parsed as: {"type": {"name": {...}}}
                for resource_type_name, resource_instances in block_data.items():
                    # Try to map to known ResourceType
                    resource_type = ResourceType.SERVICE  # default
                    for rt in ResourceType:
                        if rt.value.lower() == resource_type_name.lower():
                            resource_type = rt
                            break
                    
                    # Process each instance of this resource type
                    for resource_name, resource_config in resource_instances.items():
                        # Use type_name format for unique identification
                        unique_key = f"{resource_type_name}.{resource_name}"
                        
                        resources[unique_key] = Resource(
                            type=resource_type,
                            name=resource_name,
                            config=resource_config.get("config", resource_config),
                            depends_on=resource_config.get("depends_on", []),
                            tags=resource_config.get("tags", {})
                        )
            
            elif block_type == "module":
                for module_name, module_config in block_data.items():
                    modules[module_name] = Module(
                        name=module_name,
                        source=module_config.get("source", ""),
                        version=module_config.get("version"),
                        inputs=module_config.get("inputs", {})
                    )
            
            elif block_type == "output":
                for output_name, output_config in block_data.items():
                    outputs[output_name] = Output(
                        name=output_name,
                        value=output_config.get("value"),
                        description=output_config.get("description"),
                        sensitive=output_config.get("sensitive", False)
                    )
            
            else:
                # Handle unknown block types as generic resources
                for item_name, item_config in block_data.items():
                    resources[f"{block_type}_{item_name}"] = Resource(
                        type=ResourceType.SERVICE,  # Default type
                        name=f"{block_type}_{item_name}",
                        config=item_config,
                        depends_on=[],
                        tags={"original_type": block_type}
                    )
                    
        except (ValueError, TypeError) as e:
            raise ParseError(f"Invalid data in {block_type} block: {str(e)}")
        except Exception as e:
            raise ParseError(f"Failed to process {block_type} block: {str(e)}")
    
    def get_parsed_files(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all previously parsed files.
        
        Returns:
            Dictionary mapping file paths to their parsed content
        """
        return self.parsed_files.copy()
    
    def parse_cwvars_file(self, file_path: Union[str, Path]) -> Dict[str, Any]:
        """
        Parse a .cwvars file containing variable overrides.
        
        Args:
            file_path: Path to the .cwvars file to parse
            
        Returns:
            Dictionary of variable values
            
        Raises:
            ParseError: If the file cannot be parsed or read
            FileNotFoundError: If the file does not exist
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"Variables file not found: {file_path}")
            
        if not file_path.suffix == '.cwvars':
            raise ParseError(f"Expected .cwvars file, got {file_path.suffix}", str(file_path))
            
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()
                
            # Parse HCL content using python-hcl2
            parsed_data = hcl2.loads(content)
            
            # Extract variables from the parsed data
            # .cwvars files typically contain direct variable assignments
            variables = {}
            
            # Handle direct variable assignments (key = value)
            for key, value in parsed_data.items():
                if not isinstance(value, (dict, list)) or key == "variable":
                    if key == "variable" and isinstance(value, dict):
                        # Handle variable blocks: variable "name" { default = "value" }
                        for var_name, var_config in value.items():
                            if isinstance(var_config, dict) and "default" in var_config:
                                variables[var_name] = var_config["default"]
                            else:
                                variables[var_name] = var_config
                    else:
                        variables[key] = value
            
            return variables
            
        except Exception as e:
            # Check if it's an HCL parsing error (lark UnexpectedToken or similar)
            if hasattr(e, 'token') or 'UnexpectedToken' in str(type(e).__name__):
                raise ParseError(f"Invalid HCL syntax in .cwvars file: {str(e)}", str(file_path))
            elif isinstance(e, UnicodeDecodeError):
                raise ParseError(f"File encoding error in .cwvars file: {str(e)}", str(file_path))
            else:
                raise ParseError(f"Failed to parse .cwvars content: {str(e)}", str(file_path))
    
    def merge_variables(self, base_variables: Dict[str, Variable], override_vars: Dict[str, Any]) -> Dict[str, Variable]:
        """
        Merge variable overrides from .cwvars files with base variables.
        
        Args:
            base_variables: Base variable definitions from .cw files
            override_vars: Variable overrides from .cwvars files
            
        Returns:
            Merged variables with overrides applied
        """
        merged = base_variables.copy()
        
        for var_name, override_value in override_vars.items():
            if var_name in merged:
                # Update existing variable with new default value
                existing_var = merged[var_name]
                merged[var_name] = Variable(
                    name=existing_var.name,
                    type=existing_var.type,
                    default=override_value,  # Override the default value
                    description=existing_var.description,
                    required=False  # If we have a value, it's no longer required
                )
            else:
                # Create new variable from override
                merged[var_name] = Variable(
                    name=var_name,
                    type="string",  # Default type, could be inferred from value
                    default=override_value,
                    description=f"Variable from .cwvars override",
                    required=False
                )
        
        return merged
    
    def parse_file_to_ir(self, file_path: Union[str, Path], variable_overrides: Optional[Dict[str, Any]] = None) -> IR:
        """
        Parse a single .cw file directly to IR model.
        
        Args:
            file_path: Path to the .cw file to parse
            variable_overrides: Optional variable overrides to apply
            
        Returns:
            IR model instance
            
        Raises:
            ParseError: If the file cannot be parsed
            FileNotFoundError: If the file does not exist
        """
        try:
            parsed_data = self.parse_file(file_path)
            ir = self.to_ir(parsed_data, str(file_path))
            
            # Apply variable overrides if provided
            if variable_overrides:
                ir.variables = self.merge_variables(ir.variables, variable_overrides)
                ir.metadata["variable_overrides_applied"] = True
            
            # Resolve module and provider references if enabled
            if self.resolve_references and self.resolver:
                try:
                    ir = self.resolve_ir_references(ir)
                except Exception as e:
                    # Add resolution error to metadata but don't fail the parsing
                    ir.metadata.update({
                        "resolution_error": str(e),
                        "resolution_attempted": True,
                        "resolution_success": False
                    })
            
            return ir
            
        except Exception as e:
            if isinstance(e, (ParseError, FileNotFoundError)):
                raise
            else:
                raise ParseError(f"Unexpected error parsing file: {str(e)}", str(file_path))
    
    def resolve_ir_references(self, ir: IR) -> IR:
        """
        Resolve module and provider references in an IR.
        
        Args:
            ir: IR instance to resolve references for
            
        Returns:
            IR with resolved references and updated metadata
            
        Raises:
            ParseError: If resolution fails
        """
        if not self.resolver:
            raise ParseError("No resolver available for reference resolution")
        
        try:
            from .resolver import resolve_references
            return resolve_references(ir, self.resolver)
        except Exception as e:
            raise ParseError(f"Failed to resolve references: {str(e)}")
    
    def clear_cache(self):
        """Clear the cache of parsed files."""
        self.parsed_files.clear()
    
    def find_cwvars_files(self, directory_path: Union[str, Path]) -> List[Path]:
        """
        Find all .cwvars files in a directory.
        
        Args:
            directory_path: Path to directory to search
            
        Returns:
            List of .cwvars file paths
        """
        directory_path = Path(directory_path)
        
        if not directory_path.is_dir():
            return []
            
        return list(directory_path.glob("*.cwvars"))
    
    def _merge_irs(self, irs: List[IR], source_directory: str, file_paths: List[str]) -> IR:
        """
        Merge multiple IR instances into a single unified IR.
        
        Args:
            irs: List of IR instances to merge
            source_directory: Source directory path for metadata
            file_paths: List of file paths that were parsed
            
        Returns:
            Merged IR instance
            
        Raises:
            ParseError: If merging fails due to conflicts
        """
        if not irs:
            raise ParseError("Cannot merge empty list of IRs")
        
        if len(irs) == 1:
            # If only one IR, just update metadata and return
            single_ir = irs[0]
            single_ir.metadata.update({
                "source_directory": source_directory,
                "files_parsed": file_paths,
                "merged_at": datetime.now().isoformat()
            })
            return single_ir
        
        # Initialize merged collections
        merged_variables = {}
        merged_providers = []
        merged_resources = {}
        merged_modules = {}
        merged_outputs = {}
        
        # Track conflicts for error reporting
        conflicts = []
        
        # Merge each IR
        for i, ir in enumerate(irs):
            file_path = file_paths[i] if i < len(file_paths) else f"IR_{i}"
            
            # Merge variables - check for conflicts
            for var_name, variable in ir.variables.items():
                if var_name in merged_variables:
                    existing_var = merged_variables[var_name]
                    # Check if variables are compatible (same type and description)
                    if (existing_var.type != variable.type or 
                        existing_var.description != variable.description):
                        conflicts.append(
                            f"Variable '{var_name}' conflicts between files: "
                            f"type='{existing_var.type}' vs '{variable.type}', "
                            f"description='{existing_var.description}' vs '{variable.description}'"
                        )
                    # Use the one with a default value if available
                    if variable.default is not None:
                        merged_variables[var_name] = variable
                else:
                    merged_variables[var_name] = variable
            
            # Merge providers - append unique ones
            for provider in ir.providers:
                # Check if provider with same name already exists
                existing_provider = next(
                    (p for p in merged_providers if p.name == provider.name), 
                    None
                )
                if existing_provider:
                    # Check for conflicts
                    if (existing_provider.source != provider.source or 
                        existing_provider.version != provider.version):
                        conflicts.append(
                            f"Provider '{provider.name}' conflicts between files: "
                            f"source='{existing_provider.source}' vs '{provider.source}', "
                            f"version='{existing_provider.version}' vs '{provider.version}'"
                        )
                else:
                    merged_providers.append(provider)
            
            # Merge resources - check for name conflicts
            for resource_name, resource in ir.resources.items():
                if resource_name in merged_resources:
                    conflicts.append(
                        f"Resource '{resource_name}' is defined in multiple files"
                    )
                else:
                    merged_resources[resource_name] = resource
            
            # Merge modules - check for name conflicts
            for module_name, module in ir.modules.items():
                if module_name in merged_modules:
                    conflicts.append(
                        f"Module '{module_name}' is defined in multiple files"
                    )
                else:
                    merged_modules[module_name] = module
            
            # Merge outputs - check for name conflicts
            for output_name, output in ir.outputs.items():
                if output_name in merged_outputs:
                    conflicts.append(
                        f"Output '{output_name}' is defined in multiple files"
                    )
                else:
                    merged_outputs[output_name] = output
        
        # Report conflicts if strict mode (could be made configurable)
        if conflicts:
            conflict_msg = "Merge conflicts detected:\n" + "\n".join(f"  - {c}" for c in conflicts)
            raise ParseError(f"Failed to merge IRs: {conflict_msg}")
        
        # Create merged metadata
        merged_metadata = {
            "source_directory": source_directory,
            "files_parsed": file_paths,
            "files_count": len(file_paths),
            "merged_at": datetime.now().isoformat(),
            "merge_conflicts": len(conflicts)
        }
        
        # Create and return merged IR
        return IR(
            version="1.0",
            metadata=merged_metadata,
            variables=merged_variables,
            providers=merged_providers,
            resources=merged_resources,
            modules=merged_modules,
            outputs=merged_outputs
        )