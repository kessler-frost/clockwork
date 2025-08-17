"""
Validator for Clockwork Intermediate Representation

This module provides functionality to validate parsed Clockwork IR
for required fields, references, schema compliance, and other
integrity checks.
"""

from typing import Dict, Any, List, Set, Optional, Union
import re
from pathlib import Path


class ValidationError(Exception):
    """Exception raised when validation fails."""
    
    def __init__(self, message: str, field_path: str = None, file_path: str = None):
        self.message = message
        self.field_path = field_path
        self.file_path = file_path
        
        error_msg = f"Validation error: {message}"
        if field_path:
            error_msg += f" at '{field_path}'"
        if file_path:
            error_msg += f" in file '{file_path}'"
            
        super().__init__(error_msg)


class ValidationResult:
    """Container for validation results."""
    
    def __init__(self):
        self.is_valid = True
        self.errors: List[ValidationError] = []
        self.warnings: List[str] = []
    
    def add_error(self, error: ValidationError):
        """Add a validation error."""
        self.errors.append(error)
        self.is_valid = False
    
    def add_warning(self, warning: str):
        """Add a validation warning."""
        self.warnings.append(warning)
    
    def merge(self, other: 'ValidationResult'):
        """Merge another validation result into this one."""
        if not other.is_valid:
            self.is_valid = False
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)


class Validator:
    """
    Validator for Clockwork Intermediate Representation.
    
    Validates parsed IR for schema compliance, required fields,
    reference integrity, and other business rules.
    """
    
    def __init__(self):
        """Initialize the validator."""
        self.required_metadata_fields = {"source_file", "version"}
        self.required_ir_sections = {"metadata", "resources", "variables", "outputs", "modules"}
        self.valid_resource_types = {
            "task", "workflow", "schedule", "trigger", "connection", "dataset"
        }
        
    def validate_ir(self, ir: Dict[str, Any], file_path: str = None) -> ValidationResult:
        """
        Validate a complete IR structure.
        
        Args:
            ir: The intermediate representation to validate
            file_path: Optional file path for context
            
        Returns:
            ValidationResult containing errors and warnings
        """
        result = ValidationResult()
        
        try:
            # Validate top-level structure
            structure_result = self._validate_structure(ir, file_path)
            result.merge(structure_result)
            
            # Validate metadata section
            if "metadata" in ir:
                metadata_result = self._validate_metadata(ir["metadata"], file_path)
                result.merge(metadata_result)
            
            # Validate resources
            if "resources" in ir:
                resources_result = self._validate_resources(ir["resources"], file_path)
                result.merge(resources_result)
            
            # Validate variables
            if "variables" in ir:
                variables_result = self._validate_variables(ir["variables"], file_path)
                result.merge(variables_result)
            
            # Validate outputs
            if "outputs" in ir:
                outputs_result = self._validate_outputs(ir["outputs"], file_path)
                result.merge(outputs_result)
            
            # Validate modules
            if "modules" in ir:
                modules_result = self._validate_modules(ir["modules"], file_path)
                result.merge(modules_result)
            
            # Validate cross-references
            references_result = self._validate_references(ir, file_path)
            result.merge(references_result)
            
        except Exception as e:
            result.add_error(ValidationError(f"Unexpected validation error: {str(e)}", file_path=file_path))
            
        return result
    
    def _validate_structure(self, ir: Dict[str, Any], file_path: str = None) -> ValidationResult:
        """Validate the top-level IR structure."""
        result = ValidationResult()
        
        if not isinstance(ir, dict):
            result.add_error(ValidationError("IR must be a dictionary", file_path=file_path))
            return result
        
        # Check for required sections
        missing_sections = self.required_ir_sections - set(ir.keys())
        if missing_sections:
            result.add_error(ValidationError(
                f"Missing required IR sections: {', '.join(missing_sections)}", 
                file_path=file_path
            ))
        
        # Check for unexpected sections
        extra_sections = set(ir.keys()) - self.required_ir_sections
        if extra_sections:
            result.add_warning(f"Unknown IR sections: {', '.join(extra_sections)}")
        
        return result
    
    def _validate_metadata(self, metadata: Dict[str, Any], file_path: str = None) -> ValidationResult:
        """Validate the metadata section."""
        result = ValidationResult()
        
        if not isinstance(metadata, dict):
            result.add_error(ValidationError("Metadata must be a dictionary", "metadata", file_path))
            return result
        
        # Check required fields
        missing_fields = self.required_metadata_fields - set(metadata.keys())
        if missing_fields:
            result.add_error(ValidationError(
                f"Missing required metadata fields: {', '.join(missing_fields)}",
                "metadata",
                file_path
            ))
        
        # Validate version format
        if "version" in metadata:
            version = metadata["version"]
            if not isinstance(version, str) or not re.match(r'^\d+\.\d+$', version):
                result.add_error(ValidationError(
                    "Version must be in format 'X.Y' (e.g., '1.0')",
                    "metadata.version",
                    file_path
                ))
        
        return result
    
    def _validate_resources(self, resources: List[Dict[str, Any]], file_path: str = None) -> ValidationResult:
        """Validate the resources section."""
        result = ValidationResult()
        
        if not isinstance(resources, list):
            result.add_error(ValidationError("Resources must be a list", "resources", file_path))
            return result
        
        for i, resource in enumerate(resources):
            resource_result = self._validate_single_resource(resource, f"resources[{i}]", file_path)
            result.merge(resource_result)
        
        return result
    
    def _validate_single_resource(self, resource: Dict[str, Any], field_path: str, file_path: str = None) -> ValidationResult:
        """Validate a single resource."""
        result = ValidationResult()
        
        if not isinstance(resource, dict):
            result.add_error(ValidationError("Resource must be a dictionary", field_path, file_path))
            return result
        
        # Check required fields
        if "type" not in resource:
            result.add_error(ValidationError("Resource missing 'type' field", field_path, file_path))
        elif resource["type"] not in self.valid_resource_types:
            result.add_warning(f"Unknown resource type: {resource['type']}")
        
        if "data" not in resource:
            result.add_error(ValidationError("Resource missing 'data' field", field_path, file_path))
        elif not isinstance(resource["data"], dict):
            result.add_error(ValidationError("Resource 'data' must be a dictionary", f"{field_path}.data", file_path))
        
        return result
    
    def _validate_variables(self, variables: Dict[str, Any], file_path: str = None) -> ValidationResult:
        """Validate the variables section."""
        result = ValidationResult()
        
        if not isinstance(variables, dict):
            result.add_error(ValidationError("Variables must be a dictionary", "variables", file_path))
            return result
        
        # Validate variable names
        for var_name in variables.keys():
            if not self._is_valid_identifier(var_name):
                result.add_error(ValidationError(
                    f"Invalid variable name: '{var_name}'. Must be a valid identifier.",
                    f"variables.{var_name}",
                    file_path
                ))
        
        return result
    
    def _validate_outputs(self, outputs: Dict[str, Any], file_path: str = None) -> ValidationResult:
        """Validate the outputs section."""
        result = ValidationResult()
        
        if not isinstance(outputs, dict):
            result.add_error(ValidationError("Outputs must be a dictionary", "outputs", file_path))
            return result
        
        # Validate output names
        for output_name in outputs.keys():
            if not self._is_valid_identifier(output_name):
                result.add_error(ValidationError(
                    f"Invalid output name: '{output_name}'. Must be a valid identifier.",
                    f"outputs.{output_name}",
                    file_path
                ))
        
        return result
    
    def _validate_modules(self, modules: List[Dict[str, Any]], file_path: str = None) -> ValidationResult:
        """Validate the modules section."""
        result = ValidationResult()
        
        if not isinstance(modules, list):
            result.add_error(ValidationError("Modules must be a list", "modules", file_path))
            return result
        
        for i, module in enumerate(modules):
            module_result = self._validate_single_module(module, f"modules[{i}]", file_path)
            result.merge(module_result)
        
        return result
    
    def _validate_single_module(self, module: Dict[str, Any], field_path: str, file_path: str = None) -> ValidationResult:
        """Validate a single module."""
        result = ValidationResult()
        
        if not isinstance(module, dict):
            result.add_error(ValidationError("Module must be a dictionary", field_path, file_path))
            return result
        
        # Check required fields
        if "type" not in module:
            result.add_error(ValidationError("Module missing 'type' field", field_path, file_path))
        
        if "data" not in module:
            result.add_error(ValidationError("Module missing 'data' field", field_path, file_path))
        elif not isinstance(module["data"], dict):
            result.add_error(ValidationError("Module 'data' must be a dictionary", f"{field_path}.data", file_path))
        
        return result
    
    def _validate_references(self, ir: Dict[str, Any], file_path: str = None) -> ValidationResult:
        """Validate cross-references within the IR."""
        result = ValidationResult()
        
        # Collect all defined identifiers
        defined_vars = set(ir.get("variables", {}).keys())
        defined_outputs = set(ir.get("outputs", {}).keys())
        
        # TODO: Add more sophisticated reference validation
        # This could include checking that referenced variables exist,
        # that there are no circular dependencies, etc.
        
        return result
    
    def _is_valid_identifier(self, name: str) -> bool:
        """Check if a string is a valid identifier."""
        if not isinstance(name, str):
            return False
        return re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', name) is not None
    
    def validate_file_references(self, ir: Dict[str, Any], base_path: Union[str, Path] = None) -> ValidationResult:
        """
        Validate that file references in the IR point to existing files.
        
        Args:
            ir: The intermediate representation to validate
            base_path: Base path for resolving relative file references
            
        Returns:
            ValidationResult containing any file reference errors
        """
        result = ValidationResult()
        
        if base_path:
            base_path = Path(base_path)
        
        # TODO: Implement file reference validation
        # This would check that any file paths referenced in the IR
        # actually exist on the filesystem
        
        return result
    
    def validate_schema_version(self, ir: Dict[str, Any], expected_version: str = "1.0") -> ValidationResult:
        """
        Validate that the IR schema version matches expectations.
        
        Args:
            ir: The intermediate representation to validate
            expected_version: Expected schema version
            
        Returns:
            ValidationResult containing version compatibility errors
        """
        result = ValidationResult()
        
        metadata = ir.get("metadata", {})
        actual_version = metadata.get("version")
        
        if actual_version != expected_version:
            result.add_error(ValidationError(
                f"Schema version mismatch. Expected '{expected_version}', got '{actual_version}'",
                "metadata.version"
            ))
        
        return result