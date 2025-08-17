#!/usr/bin/env python3
"""
Test script for the enhanced validator functionality.
"""

import json
from clockwork.intake.validator import EnhancedValidator, Validator
from clockwork.models import IR, Variable, Resource, ResourceType, Provider, Output, EnvFacts, ActionList, ArtifactBundle


def test_basic_ir_validation():
    """Test basic IR validation with the enhanced validator."""
    print("=== Testing Basic IR Validation ===")
    
    validator = EnhancedValidator()
    
    # Test valid IR
    valid_ir_data = {
        "version": "1.0",
        "metadata": {"source_file": "test.cw"},
        "variables": {
            "app_name": {
                "name": "app_name",
                "type": "string",
                "default": "test-app",
                "description": "Application name"
            }
        },
        "providers": [
            {
                "name": "docker",
                "source": "registry.docker.io",
                "version": "latest"
            }
        ],
        "resources": {
            "web_service": {
                "type": "service",
                "name": "web_service",
                "config": {
                    "image": "nginx:latest",
                    "ports": ["80:8080"]
                }
            }
        },
        "modules": {},
        "outputs": {
            "service_url": {
                "name": "service_url",
                "value": "http://localhost:8080",
                "description": "Service URL"
            }
        }
    }
    
    result = validator.validate_ir(valid_ir_data, "test.cw")
    print(f"Valid IR validation result: {result.valid}")
    if not result.valid:
        for issue in result.issues:
            print(f"  {issue.level}: {issue.message}")
    
    # Test invalid IR with missing required fields
    invalid_ir_data = {
        "version": "1.0",
        "metadata": {},  # Missing source_file
        "variables": {},
        "providers": [],
        "resources": {},
        "modules": {},
        "outputs": {}
    }
    
    result = validator.validate_ir(invalid_ir_data, "test_invalid.cw")
    print(f"Invalid IR validation result: {result.valid}")
    for issue in result.issues:
        print(f"  {issue.level}: {issue.message}")


def test_hcl_reference_validation():
    """Test HCL reference validation."""
    print("\n=== Testing HCL Reference Validation ===")
    
    validator = EnhancedValidator()
    
    # Test with undefined variable reference
    ir_with_bad_ref = {
        "version": "1.0", 
        "metadata": {"source_file": "test.cw"},
        "variables": {
            "defined_var": {
                "name": "defined_var",
                "type": "string", 
                "default": "test"
            }
        },
        "providers": [],
        "resources": {
            "test_service": {
                "type": "service",
                "name": "test_service",
                "config": {
                    "image": "${var.undefined_var}",  # Reference to undefined variable
                    "name": "${var.defined_var}"       # Reference to defined variable
                }
            }
        },
        "modules": {},
        "outputs": {}
    }
    
    result = validator.validate_ir(ir_with_bad_ref, "test_ref.cw")
    print(f"Reference validation result: {result.valid}")
    for issue in result.issues:
        print(f"  {issue.level}: {issue.message} at {issue.field_path}")


def test_dependency_validation():
    """Test cross-resource dependency validation."""
    print("\n=== Testing Dependency Validation ===")
    
    validator = EnhancedValidator()
    
    # Test with circular dependency
    ir_with_circular_deps = {
        "version": "1.0",
        "metadata": {"source_file": "test.cw"},
        "variables": {},
        "providers": [],
        "resources": {
            "service_a": {
                "type": "service",
                "name": "service_a", 
                "config": {},
                "depends_on": ["service_b"]
            },
            "service_b": {
                "type": "service",
                "name": "service_b",
                "config": {},
                "depends_on": ["service_a"]  # Circular dependency
            }
        },
        "modules": {},
        "outputs": {}
    }
    
    result = validator.validate_ir(ir_with_circular_deps, "test_circular.cw")
    print(f"Circular dependency validation result: {result.valid}")
    for issue in result.issues:
        print(f"  {issue.level}: {issue.message}")


def test_security_validation():
    """Test security validation features."""
    print("\n=== Testing Security Validation ===")
    
    validator = EnhancedValidator(security_checks=True)
    
    # Test with potential security issues
    ir_with_security_issues = {
        "version": "1.0",
        "metadata": {"source_file": "test.cw"},
        "variables": {},
        "providers": [],
        "resources": {
            "insecure_service": {
                "type": "service",
                "name": "insecure_service",
                "config": {
                    "image": "nginx:latest",
                    "password": "hardcoded_secret123",  # Hardcoded secret
                    "privileged": True,                  # Privileged mode
                    "network_mode": "host"               # Host networking
                }
            }
        },
        "modules": {},
        "outputs": {}
    }
    
    result = validator.validate_ir(ir_with_security_issues, "test_security.cw")
    print(f"Security validation result: {result.valid}")
    for issue in result.issues:
        print(f"  {issue.level}: {issue.message}")


def test_env_facts_validation():
    """Test EnvFacts validation."""
    print("\n=== Testing EnvFacts Validation ===")
    
    validator = EnhancedValidator()
    
    # Test valid EnvFacts
    valid_env_facts = {
        "os_type": "linux",
        "architecture": "x86_64", 
        "available_runtimes": ["python3", "bash", "docker"],
        "docker_available": True,
        "podman_available": False,
        "kubernetes_available": False,
        "working_directory": "/home/user/project"
    }
    
    result = validator.validate_env_facts(valid_env_facts, "env_facts.json")
    print(f"Valid EnvFacts validation result: {result.valid}")
    for issue in result.issues:
        print(f"  {issue.level}: {issue.message}")
    
    # Test EnvFacts with warnings
    limited_env_facts = {
        "os_type": "linux",
        "architecture": "x86_64",
        "available_runtimes": [],  # No runtimes available
        "docker_available": False,
        "podman_available": False,  # No container runtime
        "kubernetes_available": False,
        "working_directory": "/home/user/project"
    }
    
    result = validator.validate_env_facts(limited_env_facts, "limited_env_facts.json")
    print(f"Limited EnvFacts validation result: {result.valid}")
    for issue in result.issues:
        print(f"  {issue.level}: {issue.message}")


def test_action_list_validation():
    """Test ActionList validation."""
    print("\n=== Testing ActionList Validation ===")
    
    validator = EnhancedValidator()
    
    # Test valid ActionList
    valid_action_list = {
        "version": "1",
        "steps": [
            {"name": "fetch_repo", "args": {"url": "https://github.com/example/repo.git"}},
            {"name": "build_image", "args": {"context": ".", "tag": "myapp:latest"}}
        ]
    }
    
    result = validator.validate_action_list(valid_action_list, "actions.json")
    print(f"Valid ActionList validation result: {result.valid}")
    for issue in result.issues:
        print(f"  {issue.level}: {issue.message}")
    
    # Test ActionList with missing name
    invalid_action_list = {
        "version": "1",
        "steps": [
            {"name": "", "args": {}},  # Missing name
            {"name": "valid_step", "args": {}}
        ]
    }
    
    result = validator.validate_action_list(invalid_action_list, "invalid_actions.json")
    print(f"Invalid ActionList validation result: {result.valid}")
    for issue in result.issues:
        print(f"  {issue.level}: {issue.message} at {issue.field_path}")


def test_artifact_bundle_validation():
    """Test ArtifactBundle validation."""
    print("\n=== Testing ArtifactBundle Validation ===")
    
    validator = EnhancedValidator(security_checks=True)
    
    # Test valid ArtifactBundle
    valid_bundle = {
        "version": "1",
        "artifacts": [
            {
                "path": "scripts/deploy.sh",
                "mode": "0755",
                "purpose": "deployment",
                "lang": "bash", 
                "content": "#!/bin/bash\necho 'Deploying application...'"
            }
        ],
        "steps": [
            {"purpose": "deployment", "run": {"cmd": ["bash", "scripts/deploy.sh"]}}
        ],
        "vars": {"APP_ENV": "production"}
    }
    
    result = validator.validate_artifact_bundle(valid_bundle, "bundle.json")
    print(f"Valid ArtifactBundle validation result: {result.valid}")
    for issue in result.issues:
        print(f"  {issue.level}: {issue.message}")
    
    # Test ArtifactBundle with security issues
    insecure_bundle = {
        "version": "1",
        "artifacts": [
            {
                "path": "scripts/dangerous.sh",
                "mode": "0755", 
                "purpose": "cleanup",
                "lang": "bash",
                "content": "#!/bin/bash\nrm -rf /"  # Dangerous command
            }
        ],
        "steps": [
            {"purpose": "cleanup", "run": {}}  # Missing cmd
        ],
        "vars": {}
    }
    
    result = validator.validate_artifact_bundle(insecure_bundle, "insecure_bundle.json")
    print(f"Insecure ArtifactBundle validation result: {result.valid}")
    for issue in result.issues:
        print(f"  {issue.level}: {issue.message} at {issue.field_path}")


def test_backward_compatibility():
    """Test backward compatibility with legacy Validator class."""
    print("\n=== Testing Backward Compatibility ===")
    
    legacy_validator = Validator()
    
    # Test with legacy format
    legacy_ir = {
        "metadata": {"source_file": "test.cw", "version": "1.0"},
        "variables": {"test_var": {"type": "string", "default": "test"}},
        "resources": [{"type": "service", "data": {"name": "test"}}],
        "outputs": {"result": "test"},
        "modules": []
    }
    
    result = legacy_validator.validate_ir(legacy_ir, "legacy_test.cw")
    print(f"Legacy validation result: {result.is_valid}")
    if not result.is_valid:
        for error in result.errors:
            print(f"  Error: {error.message}")
    for warning in result.warnings:
        print(f"  Warning: {warning}")


if __name__ == "__main__":
    test_basic_ir_validation()
    test_hcl_reference_validation()
    test_dependency_validation()
    test_security_validation()
    test_env_facts_validation()
    test_action_list_validation()
    test_artifact_bundle_validation()
    test_backward_compatibility()
    print("\n=== All validation tests completed ===")