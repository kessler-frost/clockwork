#!/usr/bin/env python3
"""
Test complex validation scenarios for the enhanced validator.
"""

from clockwork.intake.validator import EnhancedValidator
from clockwork.models import (
    IR, Variable, Resource, Module, Provider, Output, 
    ResourceType, EnvFacts, ActionList, ActionStep, 
    ArtifactBundle, Artifact, ExecutionStep
)


def test_complex_ir_with_all_features():
    """Test validation with a complex IR that uses all features."""
    print("=== Testing Complex IR with All Features ===")
    
    # Create a complex IR
    ir = IR(
        version="1.0",
        metadata={"source_file": "complex.cw", "description": "Complex test configuration"},
        variables={
            "environment": Variable(
                name="environment",
                type="string",
                default="production",
                description="Deployment environment"
            ),
            "replica_count": Variable(
                name="replica_count", 
                type="number",
                default=3,
                description="Number of replicas"
            ),
            "database_password": Variable(
                name="database_password",
                type="string",
                required=True,
                description="Database password"
            )
        },
        providers=[
            Provider(
                name="kubernetes",
                source="hashicorp/kubernetes",
                version="2.0.0",
                config={
                    "host": "https://k8s.example.com",
                    "token": "${var.k8s_token}"
                }
            ),
            Provider(
                name="docker",
                source="registry.docker.io",
                config={}
            )
        ],
        resources={
            "database": Resource(
                type=ResourceType.SERVICE,
                name="database",
                config={
                    "image": "postgres:13",
                    "environment": {
                        "POSTGRES_PASSWORD": "${var.database_password}",
                        "POSTGRES_DB": "appdb"
                    },
                    "volumes": ["/data:/var/lib/postgresql/data"],
                    "ports": ["5432:5432"]
                },
                tags={"component": "database", "environment": "${var.environment}"}
            ),
            "application": Resource(
                type=ResourceType.SERVICE, 
                name="application",
                config={
                    "image": "myapp:latest",
                    "replicas": "${var.replica_count}",
                    "environment": {
                        "DATABASE_URL": "postgresql://user:${var.database_password}@${resource.service.database.ip}:5432/appdb"
                    },
                    "depends_on": ["database"]
                },
                depends_on=["database"],
                tags={"component": "app", "environment": "${var.environment}"}
            ),
            "load_balancer": Resource(
                type=ResourceType.NETWORK,
                name="load_balancer", 
                config={
                    "type": "application",
                    "ports": ["80:8080"],
                    "targets": ["${resource.service.application.ip}"]
                },
                depends_on=["application"],
                tags={"component": "networking"}
            )
        },
        modules={
            "monitoring": Module(
                name="monitoring",
                source="github.com/example/monitoring-module",
                version="1.0.0",
                inputs={
                    "environment": "${var.environment}",
                    "services": ["${resource.service.application.name}", "${resource.service.database.name}"]
                }
            )
        },
        outputs={
            "application_url": Output(
                name="application_url",
                value="http://${resource.network.load_balancer.ip}",
                description="Public application URL"
            ),
            "database_connection": Output(
                name="database_connection", 
                value="postgresql://user:***@${resource.service.database.ip}:5432/appdb",
                description="Database connection string",
                sensitive=True
            ),
            "monitoring_dashboard": Output(
                name="monitoring_dashboard",
                value="${module.monitoring.dashboard_url}",
                description="Monitoring dashboard URL"
            )
        }
    )
    
    # Test with enhanced validator
    validator = EnhancedValidator(security_checks=True)
    result = validator.validate_ir(ir, "complex.cw")
    
    print(f"Validation result: {'✓ VALID' if result.valid else '✗ INVALID'}")
    
    if result.issues:
        print(f"\nFound {len(result.issues)} validation issues:")
        for issue in result.issues:
            icon = "🔴" if issue.level == "error" else "🟡" if issue.level == "warning" else "🔵"
            print(f"  {icon} {issue.level.upper()}: {issue.message}")
            if issue.field_path:
                print(f"    at: {issue.field_path}")
    else:
        print("✓ No validation issues found")


def test_validation_with_errors():
    """Test validation with deliberate errors to verify error detection."""
    print("\n=== Testing Validation with Deliberate Errors ===")
    
    # Create IR with various errors
    ir = IR(
        version="1.0",
        metadata={"source_file": "errors.cw"},
        variables={
            "valid_var": Variable(name="valid_var", type="string", default="test")
        },
        providers=[],
        resources={
            "broken_service": Resource(
                type=ResourceType.SERVICE,
                name="broken_service", 
                config={
                    "image": "${var.undefined_variable}",  # Reference to undefined variable
                    "depends_on_undefined": "${resource.service.nonexistent.id}",  # Reference to undefined resource
                    "password": "hardcoded_secret_123",  # Hardcoded secret
                    "command": "rm -rf /tmp/*"  # Dangerous command
                },
                depends_on=["nonexistent_resource"]  # Dependency on non-existent resource
            ),
            "circular_a": Resource(
                type=ResourceType.SERVICE,
                name="circular_a",
                config={},
                depends_on=["circular_b"]
            ),
            "circular_b": Resource(
                type=ResourceType.SERVICE, 
                name="circular_b",
                config={},
                depends_on=["circular_a"]  # Creates circular dependency
            )
        },
        modules={
            "bad_module": Module(
                name="bad_module",
                source="github.com/example/module",
                inputs={
                    "undefined_input": "${var.undefined_var}",  # Reference to undefined variable
                    "bad_resource_ref": "${resource.service.missing.attr}"  # Reference to undefined resource
                }
            )
        },
        outputs={
            "bad_output": Output(
                name="bad_output",
                value="${module.undefined_module.output}",  # Reference to undefined module
                description="This output references undefined module"
            )
        }
    )
    
    # Test with enhanced validator
    validator = EnhancedValidator(security_checks=True)
    result = validator.validate_ir(ir, "errors.cw")
    
    print(f"Validation result: {'✗ INVALID' if not result.valid else '✓ VALID (unexpected!)'}")
    
    if result.issues:
        errors = [issue for issue in result.issues if issue.level == "error"]
        warnings = [issue for issue in result.issues if issue.level == "warning"]
        
        print(f"\nFound {len(errors)} errors and {len(warnings)} warnings:")
        
        for issue in result.issues:
            icon = "🔴" if issue.level == "error" else "🟡" if issue.level == "warning" else "🔵"
            print(f"  {icon} {issue.level.upper()}: {issue.message}")
            if issue.field_path:
                print(f"    at: {issue.field_path}")
    else:
        print("✗ No validation issues found (this is unexpected!)")


def test_performance_validation():
    """Test performance validation with high resource counts."""
    print("\n=== Testing Performance Validation ===")
    
    # Create IR with many resources to trigger performance warnings
    resources = {}
    for i in range(110):  # Exceeds max_resources limit of 100
        resources[f"service_{i}"] = Resource(
            type=ResourceType.SERVICE,
            name=f"service_{i}",
            config={
                "image": f"app:v{i}",
                "timeout": 7200 if i == 0 else 300,  # First service has very high timeout
                "retries": 15 if i == 1 else 3       # Second service has high retry count
            },
            depends_on=[f"service_{j}" for j in range(max(0, i-5), i)]  # Each depends on previous 5
        )
    
    ir = IR(
        version="1.0",
        metadata={"source_file": "performance_test.cw"},
        variables={},
        providers=[],
        resources=resources,
        modules={},
        outputs={}
    )
    
    validator = EnhancedValidator()
    result = validator.validate_ir(ir, "performance_test.cw")
    
    print(f"Validation result: {'✓ VALID' if result.valid else '✗ INVALID'}")
    
    performance_warnings = [issue for issue in result.issues if "resource count" in issue.message.lower() or 
                           "dependency count" in issue.message.lower() or 
                           "timeout" in issue.message.lower() or
                           "retry count" in issue.message.lower()]
    
    print(f"\nPerformance-related warnings: {len(performance_warnings)}")
    for warning in performance_warnings:
        print(f"  🟡 {warning.message}")


def test_component_validation():
    """Test validation of different component types."""
    print("\n=== Testing Component Validation ===")
    
    validator = EnhancedValidator()
    
    # Test EnvFacts
    print("\n--- Testing EnvFacts ---")
    env_facts = EnvFacts(
        os_type="linux",
        architecture="x86_64",
        available_runtimes=["python3", "node", "go"],
        docker_available=True,
        podman_available=False,
        kubernetes_available=True,
        working_directory="/home/user/project"
    )
    
    result = validator.validate_env_facts(env_facts)
    print(f"EnvFacts validation: {'✓ VALID' if result.valid else '✗ INVALID'}")
    
    # Test ActionList 
    print("\n--- Testing ActionList ---")
    action_list = ActionList(
        version="1",
        steps=[
            ActionStep(name="setup", args={"runtime": "python3"}),
            ActionStep(name="build", args={"target": "production"}),
            ActionStep(name="deploy", args={"environment": "staging"})
        ]
    )
    
    result = validator.validate_action_list(action_list)
    print(f"ActionList validation: {'✓ VALID' if result.valid else '✗ INVALID'}")
    
    # Test ArtifactBundle
    print("\n--- Testing ArtifactBundle ---")
    artifact_bundle = ArtifactBundle(
        version="1",
        artifacts=[
            Artifact(
                path="scripts/setup.py",
                mode="0755",
                purpose="setup",
                lang="python",
                content="#!/usr/bin/env python3\nprint('Setting up...')"
            ),
            Artifact(
                path="configs/app.yaml",
                mode="0644", 
                purpose="config",
                lang="yaml",
                content="app:\n  name: myapp\n  version: 1.0"
            )
        ],
        steps=[
            ExecutionStep(purpose="setup", run={"cmd": ["python3", "scripts/setup.py"]}),
            ExecutionStep(purpose="deploy", run={"cmd": ["kubectl", "apply", "-f", "configs/app.yaml"]})
        ],
        vars={"ENV": "production", "VERSION": "1.0.0"}
    )
    
    result = validator.validate_artifact_bundle(artifact_bundle)
    print(f"ArtifactBundle validation: {'✓ VALID' if result.valid else '✗ INVALID'}")


if __name__ == "__main__":
    test_complex_ir_with_all_features()
    test_validation_with_errors()
    test_performance_validation()
    test_component_validation()
    print("\n=== All complex validation tests completed ===")