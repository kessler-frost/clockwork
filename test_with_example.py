#!/usr/bin/env python3
"""
Test the enhanced validator with the actual example.cw file.
"""

from clockwork.intake.parser import Parser
from clockwork.intake.validator import EnhancedValidator
import json


def test_with_example_file():
    """Test validation with the example.cw file."""
    print("=== Testing with example.cw ===")
    
    # Parse the example file
    parser = Parser()
    try:
        parsed_data = parser.parse_file("example.cw")
        print("✓ Successfully parsed example.cw")
        
        # Convert to IR
        ir = parser.to_ir(parsed_data)
        print("✓ Successfully converted to IR")
        
        # Validate with enhanced validator
        validator = EnhancedValidator()
        result = validator.validate_ir(ir, "example.cw")
        
        print(f"\nValidation result: {'✓ VALID' if result.valid else '✗ INVALID'}")
        
        if result.issues:
            print("\nValidation issues:")
            for issue in result.issues:
                icon = "🔴" if issue.level == "error" else "🟡" if issue.level == "warning" else "🔵"
                print(f"  {icon} {issue.level.upper()}: {issue.message}")
                if issue.field_path:
                    print(f"    at: {issue.field_path}")
        else:
            print("✓ No validation issues found")
            
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()


def test_create_ir_manually():
    """Test validation with manually created IR that matches example.cw."""
    print("\n=== Testing with manually created IR ===")
    
    from clockwork.models import (
        IR, Variable, Resource, Output, ResourceType
    )
    
    # Create IR manually to match example.cw structure
    ir = IR(
        version="1.0",
        metadata={"source_file": "example.cw"},
        variables={
            "app_name": Variable(
                name="app_name",
                type="string",
                default="example-app",
                description="Application name"
            ),
            "port": Variable(
                name="port",
                type="number", 
                default=8080
            )
        },
        resources={
            "app": Resource(
                type=ResourceType.SERVICE,
                name="app",
                config={
                    "name": "${var.app_name}",
                    "image": "nginx:latest",
                    "ports": [{"external": "${var.port}", "internal": 80}],
                    "retries": 3,
                    "timeout": 30,
                    "health_check": {
                        "path": "/",
                        "interval": "30s"
                    }
                }
            )
        },
        outputs={
            "app_url": Output(
                name="app_url",
                value="http://localhost:${var.port}",
                description="Application URL"
            )
        }
    )
    
    # Validate
    validator = EnhancedValidator()
    result = validator.validate_ir(ir, "example.cw")
    
    print(f"Validation result: {'✓ VALID' if result.valid else '✗ INVALID'}")
    
    if result.issues:
        print("\nValidation issues:")
        for issue in result.issues:
            icon = "🔴" if issue.level == "error" else "🟡" if issue.level == "warning" else "🔵"
            print(f"  {icon} {issue.level.upper()}: {issue.message}")
            if issue.field_path:
                print(f"    at: {issue.field_path}")
    else:
        print("✓ No validation issues found")


if __name__ == "__main__":
    test_with_example_file()
    test_create_ir_manually()