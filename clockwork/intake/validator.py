"""
Enhanced Validator for Clockwork Intermediate Representation

This module provides comprehensive validation functionality for parsed Clockwork IR
including:
- Schema validation using Pydantic models
- Cross-resource dependency validation
- HCL reference validation (variables, resources, modules)
- Security and performance validation
- Integration with resolver and parser from enhanced phases
"""

from typing import Dict, Any, List, Set, Optional, Union, Tuple
import re
from pathlib import Path
from pydantic import ValidationError as PydanticValidationError
from datetime import datetime
import networkx as nx  # For dependency graph analysis

# Import models from the enhanced models.py
from ..models import (
    IR, Variable, Provider, Resource, Module, Output, 
    ValidationResult, ValidationIssue, EnvFacts,
    ActionList, ActionStep, ArtifactBundle,
    ResourceType, ActionType
)


class ValidationError(Exception):
    """Exception raised when validation fails."""
    
    def __init__(self, message: str, field_path: str = None, file_path: str = None, line_number: int = None):
        self.message = message
        self.field_path = field_path
        self.file_path = file_path
        self.line_number = line_number
        
        error_msg = f"Validation error: {message}"
        if field_path:
            error_msg += f" at '{field_path}'"
        if file_path:
            error_msg += f" in file '{file_path}'"
        if line_number:
            error_msg += f" at line {line_number}"
            
        super().__init__(error_msg)


class LegacyValidationResult:
    """Legacy container for validation results - kept for compatibility."""
    
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
    
    def merge(self, other: 'LegacyValidationResult'):
        """Merge another validation result into this one."""
        if not other.is_valid:
            self.is_valid = False
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)
    
    def to_validation_result(self) -> ValidationResult:
        """Convert to new ValidationResult model."""
        issues = []
        
        # Convert errors
        for error in self.errors:
            issues.append(ValidationIssue(
                level="error",
                message=error.message,
                field_path=error.field_path,
                line_number=getattr(error, 'line_number', None)
            ))
        
        # Convert warnings
        for warning in self.warnings:
            issues.append(ValidationIssue(
                level="warning",
                message=warning
            ))
        
        return ValidationResult(
            valid=self.is_valid,
            issues=issues
        )


class EnhancedValidator:
    """
    Enhanced Validator for Clockwork Intermediate Representation.
    
    Provides comprehensive validation including:
    - Pydantic model validation
    - Cross-resource dependency validation
    - HCL reference validation
    - Security validation
    - Performance validation
    """
    
    def __init__(self, strict_mode: bool = True, security_checks: bool = True):
        """Initialize the enhanced validator.
        
        Args:
            strict_mode: Enable strict validation (treat warnings as errors)
            security_checks: Enable security validation checks
        """
        self.strict_mode = strict_mode
        self.security_checks = security_checks
        
        # HCL reference patterns
        self.var_reference_pattern = re.compile(r'\$\{var\.([a-zA-Z_][a-zA-Z0-9_]*)\}')
        self.resource_reference_pattern = re.compile(r'\$\{([a-zA-Z_][a-zA-Z0-9_]*)\.([a-zA-Z_][a-zA-Z0-9_]*)\.([a-zA-Z_][a-zA-Z0-9_]*)(?:\.([a-zA-Z_][a-zA-Z0-9_]*))?\}')
        self.module_reference_pattern = re.compile(r'\$\{module\.([a-zA-Z_][a-zA-Z0-9_]*)\.([a-zA-Z_][a-zA-Z0-9_]*)\}')
        self.provider_reference_pattern = re.compile(r'\$\{provider\.([a-zA-Z_][a-zA-Z0-9_]*)\.([a-zA-Z_][a-zA-Z0-9_]*)\}')
        
        # Security patterns to detect
        self.security_patterns = {
            'hardcoded_secrets': re.compile(r'(password|secret|key|token)\s*=\s*["\'][^"\']+', re.IGNORECASE),
            'dangerous_commands': re.compile(r'(rm\s+-rf|sudo|eval|exec)', re.IGNORECASE),
            'network_exposure': re.compile(r'0\.0\.0\.0'),
        }
        
        # Performance limits
        self.performance_limits = {
            'max_resources': 100,
            'max_dependencies': 50,
            'max_timeout': 3600,  # 1 hour
            'max_retries': 10
        }
    
    def validate_ir(self, ir: Union[Dict[str, Any], IR], file_path: str = None) -> ValidationResult:
        """
        Validate a complete IR structure using enhanced validation.
        
        Args:
            ir: The intermediate representation to validate (dict or IR model)
            file_path: Optional file path for context
            
        Returns:
            ValidationResult containing comprehensive validation results
        """
        result = LegacyValidationResult()
        
        try:
            # Convert dict to IR model if needed
            if isinstance(ir, dict):
                try:
                    ir_model = IR.model_validate(ir)
                except PydanticValidationError as e:
                    for error in e.errors():
                        result.add_error(ValidationError(
                            f"Pydantic validation error: {error['msg']}",
                            field_path='.'.join(str(loc) for loc in error['loc']),
                            file_path=file_path
                        ))
                    return result.to_validation_result()
            else:
                ir_model = ir
                
            # Comprehensive validation
            self._validate_pydantic_models(ir_model, result, file_path)
            self._validate_cross_resource_dependencies(ir_model, result, file_path)
            self._validate_hcl_references(ir_model, result, file_path)
            
            if self.security_checks:
                self._validate_security(ir_model, result, file_path)
            
            self._validate_performance(ir_model, result, file_path)
            
        except Exception as e:
            result.add_error(ValidationError(f"Unexpected validation error: {str(e)}", file_path=file_path))
            
        return result.to_validation_result()
    
    def _validate_pydantic_models(self, ir: IR, result: LegacyValidationResult, file_path: str = None):
        """Validate all Pydantic models within the IR."""
        try:
            # Validate individual variables
            for var_name, variable in ir.variables.items():
                try:
                    Variable.model_validate(variable.model_dump())
                except PydanticValidationError as e:
                    for error in e.errors():
                        result.add_error(ValidationError(
                            f"Variable '{var_name}' validation error: {error['msg']}",
                            field_path=f"variables.{var_name}.{'.'.join(str(loc) for loc in error['loc'])}",
                            file_path=file_path
                        ))
            
            # Validate providers
            for i, provider in enumerate(ir.providers):
                try:
                    Provider.model_validate(provider.model_dump())
                except PydanticValidationError as e:
                    for error in e.errors():
                        result.add_error(ValidationError(
                            f"Provider {i} validation error: {error['msg']}",
                            field_path=f"providers[{i}].{'.'.join(str(loc) for loc in error['loc'])}",
                            file_path=file_path
                        ))
            
            # Validate resources
            for resource_name, resource in ir.resources.items():
                try:
                    Resource.model_validate(resource.model_dump())
                except PydanticValidationError as e:
                    for error in e.errors():
                        result.add_error(ValidationError(
                            f"Resource '{resource_name}' validation error: {error['msg']}",
                            field_path=f"resources.{resource_name}.{'.'.join(str(loc) for loc in error['loc'])}",
                            file_path=file_path
                        ))
            
            # Validate modules
            for module_name, module in ir.modules.items():
                try:
                    Module.model_validate(module.model_dump())
                except PydanticValidationError as e:
                    for error in e.errors():
                        result.add_error(ValidationError(
                            f"Module '{module_name}' validation error: {error['msg']}",
                            field_path=f"modules.{module_name}.{'.'.join(str(loc) for loc in error['loc'])}",
                            file_path=file_path
                        ))
            
            # Validate outputs
            for output_name, output in ir.outputs.items():
                try:
                    Output.model_validate(output.model_dump())
                except PydanticValidationError as e:
                    for error in e.errors():
                        result.add_error(ValidationError(
                            f"Output '{output_name}' validation error: {error['msg']}",
                            field_path=f"outputs.{output_name}.{'.'.join(str(loc) for loc in error['loc'])}",
                            file_path=file_path
                        ))
                        
        except Exception as e:
            result.add_error(ValidationError(
                f"Pydantic model validation failed: {str(e)}",
                file_path=file_path
            ))
    
    def _validate_cross_resource_dependencies(self, ir: IR, result: LegacyValidationResult, file_path: str = None):
        """Validate cross-resource dependencies and detect circular dependencies."""
        try:
            # Build dependency graph
            dependency_graph = nx.DiGraph()
            
            # Add all resources as nodes
            for resource_name in ir.resources.keys():
                dependency_graph.add_node(resource_name)
            
            # Add dependencies as edges
            for resource_name, resource in ir.resources.items():
                for dep in resource.depends_on:
                    if dep not in ir.resources:
                        result.add_error(ValidationError(
                            f"Resource '{resource_name}' depends on non-existent resource '{dep}'",
                            field_path=f"resources.{resource_name}.depends_on",
                            file_path=file_path
                        ))
                    else:
                        dependency_graph.add_edge(dep, resource_name)
            
            # Check for circular dependencies
            try:
                cycles = list(nx.simple_cycles(dependency_graph))
                for cycle in cycles:
                    result.add_error(ValidationError(
                        f"Circular dependency detected: {' -> '.join(cycle)} -> {cycle[0]}",
                        field_path="resources",
                        file_path=file_path
                    ))
            except nx.NetworkXError:
                pass  # No cycles found
            
            # Validate provider references
            defined_providers = {provider.name for provider in ir.providers}
            for resource_name, resource in ir.resources.items():
                if hasattr(resource, 'provider') and resource.provider:
                    if resource.provider not in defined_providers:
                        result.add_error(ValidationError(
                            f"Resource '{resource_name}' references undefined provider '{resource.provider}'",
                            field_path=f"resources.{resource_name}.provider",
                            file_path=file_path
                        ))
            
            # Validate module input/output references
            for module_name, module in ir.modules.items():
                # Check if module inputs reference valid variables
                for input_name, input_value in module.inputs.items():
                    if isinstance(input_value, str):
                        self._validate_value_references(input_value, ir, result, 
                                                      f"modules.{module_name}.inputs.{input_name}", file_path)
                        
        except Exception as e:
            result.add_error(ValidationError(
                f"Cross-resource dependency validation failed: {str(e)}",
                file_path=file_path
            ))
    
    def _validate_hcl_references(self, ir: IR, result: LegacyValidationResult, file_path: str = None):
        """Validate HCL references throughout the IR."""
        try:
            # Collect all defined identifiers
            defined_vars = set(ir.variables.keys())
            defined_resources = set(ir.resources.keys())
            defined_modules = set(ir.modules.keys())
            defined_providers = {provider.name for provider in ir.providers}
            
            # Validate variable references in resources
            for resource_name, resource in ir.resources.items():
                self._validate_config_references(resource.config, defined_vars, defined_resources, 
                                                defined_modules, defined_providers, result, 
                                                f"resources.{resource_name}.config", file_path)
            
            # Validate references in outputs
            for output_name, output in ir.outputs.items():
                if isinstance(output.value, str):
                    self._validate_value_references(output.value, ir, result,
                                                  f"outputs.{output_name}.value", file_path)
            
            # Validate references in module inputs
            for module_name, module in ir.modules.items():
                for input_name, input_value in module.inputs.items():
                    if isinstance(input_value, str):
                        self._validate_value_references(input_value, ir, result,
                                                      f"modules.{module_name}.inputs.{input_name}", file_path)
                        
        except Exception as e:
            result.add_error(ValidationError(
                f"HCL reference validation failed: {str(e)}",
                file_path=file_path
            ))
    
    def _validate_config_references(self, config: Dict[str, Any], defined_vars: Set[str], 
                                  defined_resources: Set[str], defined_modules: Set[str],
                                  defined_providers: Set[str], result: LegacyValidationResult, 
                                  field_path: str, file_path: str = None):
        """Recursively validate references in configuration objects."""
        if isinstance(config, dict):
            for key, value in config.items():
                if isinstance(value, str):
                    self._validate_string_references(value, defined_vars, defined_resources,
                                                   defined_modules, defined_providers, result,
                                                   f"{field_path}.{key}", file_path)
                elif isinstance(value, (dict, list)):
                    self._validate_config_references(value, defined_vars, defined_resources,
                                                    defined_modules, defined_providers, result,
                                                    f"{field_path}.{key}", file_path)
        elif isinstance(config, list):
            for i, item in enumerate(config):
                if isinstance(item, str):
                    self._validate_string_references(item, defined_vars, defined_resources,
                                                   defined_modules, defined_providers, result,
                                                   f"{field_path}[{i}]", file_path)
                elif isinstance(item, (dict, list)):
                    self._validate_config_references(item, defined_vars, defined_resources,
                                                    defined_modules, defined_providers, result,
                                                    f"{field_path}[{i}]", file_path)
    
    def _validate_string_references(self, value: str, defined_vars: Set[str], 
                                  defined_resources: Set[str], defined_modules: Set[str],
                                  defined_providers: Set[str], result: LegacyValidationResult,
                                  field_path: str, file_path: str = None):
        """Validate HCL references in a string value."""
        # Check variable references
        var_matches = self.var_reference_pattern.findall(value)
        for var_name in var_matches:
            if var_name not in defined_vars:
                result.add_error(ValidationError(
                    f"Reference to undefined variable: var.{var_name}",
                    field_path=field_path,
                    file_path=file_path
                ))
        
        # Check resource references
        resource_matches = self.resource_reference_pattern.findall(value)
        for match in resource_matches:
            resource_type, resource_name = match[0], match[1]
            full_resource_name = f"{resource_type}.{resource_name}"
            if full_resource_name not in defined_resources and resource_name not in defined_resources:
                result.add_error(ValidationError(
                    f"Reference to undefined resource: {resource_type}.{resource_name}",
                    field_path=field_path,
                    file_path=file_path
                ))
        
        # Check module references
        module_matches = self.module_reference_pattern.findall(value)
        for module_name, output_name in module_matches:
            if module_name not in defined_modules:
                result.add_error(ValidationError(
                    f"Reference to undefined module: module.{module_name}",
                    field_path=field_path,
                    file_path=file_path
                ))
        
        # Check provider references
        provider_matches = self.provider_reference_pattern.findall(value)
        for provider_name, attr_name in provider_matches:
            if provider_name not in defined_providers:
                result.add_error(ValidationError(
                    f"Reference to undefined provider: provider.{provider_name}",
                    field_path=field_path,
                    file_path=file_path
                ))
    
    def _validate_value_references(self, value: str, ir: IR, result: LegacyValidationResult,
                                 field_path: str, file_path: str = None):
        """Validate references in a value string."""
        defined_vars = set(ir.variables.keys())
        defined_resources = set(ir.resources.keys())
        defined_modules = set(ir.modules.keys())
        defined_providers = {provider.name for provider in ir.providers}
        
        self._validate_string_references(value, defined_vars, defined_resources,
                                       defined_modules, defined_providers, result,
                                       field_path, file_path)
    
    def _validate_security(self, ir: IR, result: LegacyValidationResult, file_path: str = None):
        """Validate security aspects of the configuration."""
        try:
            # Check for hardcoded secrets in all string values
            self._check_security_in_config(ir.model_dump(), result, "ir", file_path)
            
            # Check for network exposure risks
            for resource_name, resource in ir.resources.items():
                if resource.type == ResourceType.SERVICE:
                    self._validate_service_security(resource, result, f"resources.{resource_name}", file_path)
            
            # Check provider configurations for security issues
            for i, provider in enumerate(ir.providers):
                self._validate_provider_security(provider, result, f"providers[{i}]", file_path)
                
        except Exception as e:
            result.add_error(ValidationError(
                f"Security validation failed: {str(e)}",
                file_path=file_path
            ))
    
    def _check_security_in_config(self, config: Any, result: LegacyValidationResult, 
                                field_path: str, file_path: str = None):
        """Recursively check configuration for security issues."""
        if isinstance(config, dict):
            for key, value in config.items():
                if isinstance(value, str):
                    self._check_security_patterns(value, result, f"{field_path}.{key}", file_path)
                else:
                    self._check_security_in_config(value, result, f"{field_path}.{key}", file_path)
        elif isinstance(config, list):
            for i, item in enumerate(config):
                self._check_security_in_config(item, result, f"{field_path}[{i}]", file_path)
        elif isinstance(config, str):
            self._check_security_patterns(config, result, field_path, file_path)
    
    def _check_security_patterns(self, value: str, result: LegacyValidationResult, 
                               field_path: str, file_path: str = None):
        """Check a string value against security patterns."""
        for pattern_name, pattern in self.security_patterns.items():
            if pattern.search(value):
                if pattern_name == 'hardcoded_secrets':
                    result.add_error(ValidationError(
                        "Potential hardcoded secret detected. Use variables or secure references instead.",
                        field_path=field_path,
                        file_path=file_path
                    ))
                elif pattern_name == 'dangerous_commands':
                    result.add_warning("Potentially dangerous command detected. Review for security implications.")
                elif pattern_name == 'network_exposure':
                    result.add_warning("Network exposure to 0.0.0.0 detected. Consider restricting access.")
    
    def _validate_service_security(self, resource: Resource, result: LegacyValidationResult,
                                 field_path: str, file_path: str = None):
        """Validate security aspects of service resources."""
        config = resource.config
        
        # Check for privileged mode
        if config.get('privileged', False):
            result.add_warning("Service running in privileged mode. Review security implications.")
        
        # Check for host network mode
        if config.get('network_mode') == 'host':
            result.add_warning("Service using host networking. Consider security implications.")
        
        # Check for volume mounts that could be dangerous
        volumes = config.get('volumes', [])
        for volume in volumes:
            if isinstance(volume, str) and ('/etc' in volume or '/var' in volume or '/sys' in volume):
                result.add_warning(f"Mounting sensitive system directory: {volume}")
    
    def _validate_provider_security(self, provider: Provider, result: LegacyValidationResult,
                                  field_path: str, file_path: str = None):
        """Validate security aspects of provider configurations."""
        # Check for insecure configurations
        if provider.config.get('skip_tls_verify', False):
            result.add_warning("Provider configured to skip TLS verification. Security risk.")
        
        if provider.config.get('insecure', False):
            result.add_warning("Provider configured in insecure mode.")
    
    def _validate_performance(self, ir: IR, result: LegacyValidationResult, file_path: str = None):
        """Validate performance aspects of the configuration."""
        try:
            # Check resource count limits
            resource_count = len(ir.resources)
            if resource_count > self.performance_limits['max_resources']:
                result.add_warning(f"High resource count ({resource_count}). Consider splitting into modules.")
            
            # Check dependency complexity
            total_deps = sum(len(resource.depends_on) for resource in ir.resources.values())
            if total_deps > self.performance_limits['max_dependencies']:
                result.add_warning(f"High dependency count ({total_deps}). Review architecture.")
            
            # Check for resource-specific performance issues
            for resource_name, resource in ir.resources.items():
                config = resource.config
                
                # Check timeout values
                timeout = config.get('timeout', 0)
                if timeout > self.performance_limits['max_timeout']:
                    result.add_warning(f"Resource '{resource_name}' has very high timeout: {timeout}s")
                
                # Check retry values
                retries = config.get('retries', 0)
                if retries > self.performance_limits['max_retries']:
                    result.add_warning(f"Resource '{resource_name}' has high retry count: {retries}")
                    
        except Exception as e:
            result.add_error(ValidationError(
                f"Performance validation failed: {str(e)}",
                file_path=file_path
            ))
    
    def validate_env_facts(self, env_facts: Union[Dict[str, Any], EnvFacts], file_path: str = None) -> ValidationResult:
        """Validate EnvFacts structure and content."""
        result = LegacyValidationResult()
        
        try:
            # Convert dict to EnvFacts model if needed
            if isinstance(env_facts, dict):
                try:
                    env_facts_model = EnvFacts.model_validate(env_facts)
                except PydanticValidationError as e:
                    for error in e.errors():
                        result.add_error(ValidationError(
                            f"EnvFacts validation error: {error['msg']}",
                            field_path='.'.join(str(loc) for loc in error['loc']),
                            file_path=file_path
                        ))
                    return result.to_validation_result()
            else:
                env_facts_model = env_facts
            
            # Validate runtime availability claims
            if not env_facts_model.available_runtimes:
                result.add_warning("No available runtimes detected. This may limit execution capabilities.")
            
            # Validate container runtime availability
            if not (env_facts_model.docker_available or env_facts_model.podman_available):
                result.add_warning("No container runtime available. Container-based resources may fail.")
            
            return result.to_validation_result()
            
        except Exception as e:
            result.add_error(ValidationError(f"EnvFacts validation failed: {str(e)}", file_path=file_path))
            return result.to_validation_result()
    
    def validate_action_list(self, action_list: Union[Dict[str, Any], ActionList], file_path: str = None) -> ValidationResult:
        """Validate ActionList structure and content."""
        result = LegacyValidationResult()
        
        try:
            # Convert dict to ActionList model if needed
            if isinstance(action_list, dict):
                try:
                    action_list_model = ActionList.model_validate(action_list)
                except PydanticValidationError as e:
                    for error in e.errors():
                        result.add_error(ValidationError(
                            f"ActionList validation error: {error['msg']}",
                            field_path='.'.join(str(loc) for loc in error['loc']),
                            file_path=file_path
                        ))
                    return result.to_validation_result()
            else:
                action_list_model = action_list
            
            # Validate action steps
            for i, step in enumerate(action_list_model.steps):
                if not step.name:
                    result.add_error(ValidationError(
                        f"Action step {i} missing name",
                        field_path=f"steps[{i}].name",
                        file_path=file_path
                    ))
            
            return result.to_validation_result()
            
        except Exception as e:
            result.add_error(ValidationError(f"ActionList validation failed: {str(e)}", file_path=file_path))
            return result.to_validation_result()
    
    def validate_artifact_bundle(self, artifact_bundle: Union[Dict[str, Any], ArtifactBundle], file_path: str = None) -> ValidationResult:
        """Validate ArtifactBundle structure and content."""
        result = LegacyValidationResult()
        
        try:
            # Convert dict to ArtifactBundle model if needed
            if isinstance(artifact_bundle, dict):
                try:
                    bundle_model = ArtifactBundle.model_validate(artifact_bundle)
                except PydanticValidationError as e:
                    for error in e.errors():
                        result.add_error(ValidationError(
                            f"ArtifactBundle validation error: {error['msg']}",
                            field_path='.'.join(str(loc) for loc in error['loc']),
                            file_path=file_path
                        ))
                    return result.to_validation_result()
            else:
                bundle_model = artifact_bundle
            
            # Validate artifacts
            for i, artifact in enumerate(bundle_model.artifacts):
                if not artifact.content:
                    result.add_error(ValidationError(
                        f"Artifact {i} has empty content",
                        field_path=f"artifacts[{i}].content",
                        file_path=file_path
                    ))
                
                # Check for potentially dangerous scripts
                if self.security_checks:
                    self._check_security_patterns(artifact.content, result, 
                                                 f"artifacts[{i}].content", file_path)
            
            # Validate execution steps
            for i, step in enumerate(bundle_model.steps):
                if 'cmd' not in step.run:
                    result.add_error(ValidationError(
                        f"Execution step {i} missing 'cmd' in run configuration",
                        field_path=f"steps[{i}].run",
                        file_path=file_path
                    ))
            
            return result.to_validation_result()
            
        except Exception as e:
            result.add_error(ValidationError(f"ArtifactBundle validation failed: {str(e)}", file_path=file_path))
            return result.to_validation_result()
    
    def _is_valid_identifier(self, name: str) -> bool:
        """Check if a string is a valid identifier."""
        if not isinstance(name, str):
            return False
        return re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', name) is not None


# Keep the original Validator class for backward compatibility
class Validator(EnhancedValidator):
    """Legacy Validator class for backward compatibility."""
    
    def __init__(self):
        super().__init__(strict_mode=False, security_checks=False)
        # Legacy required fields
        self.required_metadata_fields = {"source_file", "version"}
        self.required_ir_sections = {"metadata", "resources", "variables", "outputs", "modules"}
        self.valid_resource_types = {
            "task", "workflow", "schedule", "trigger", "connection", "dataset"
        }
    
    def validate_ir(self, ir: Dict[str, Any], file_path: str = None) -> LegacyValidationResult:
        """Legacy validate_ir method returning LegacyValidationResult."""
        enhanced_result = super().validate_ir(ir, file_path)
        
        # Convert back to legacy format
        legacy_result = LegacyValidationResult()
        legacy_result.is_valid = enhanced_result.valid
        
        for issue in enhanced_result.issues:
            if issue.level == "error":
                legacy_result.add_error(ValidationError(
                    issue.message,
                    field_path=issue.field_path,
                    file_path=file_path,
                    line_number=issue.line_number
                ))
            else:
                legacy_result.add_warning(issue.message)
        
        return legacy_result