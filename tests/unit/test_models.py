"""
Unit tests for Clockwork models.

Tests the core Pydantic models and their validation logic.
"""

import pytest
from datetime import datetime
from clockwork.models import (
    IR, Variable, Provider, Resource, Module, Output,
    ActionList, ActionStep, ArtifactBundle, Artifact, ExecutionStep,
    ClockworkState, ResourceState, ExecutionRecord,
    ValidationResult, ValidationIssue, EnvFacts
)


class TestIRModels:
    """Test Intermediate Representation models."""
    
    def test_variable_creation(self):
        """Test Variable model creation and validation."""
        var = Variable(name="test_var", type="string", default="test_value")
        assert var.name == "test_var"
        assert var.type == "string"
        assert var.default == "test_value"
        assert var.required is True
    
    def test_resource_creation(self):
        """Test Resource model creation."""
        resource = Resource(
            type="service",
            name="web_server",
            config={"port": 8080},
            tags={"env": "prod"}
        )
        assert resource.type == "service"
        assert resource.name == "web_server"
        assert resource.config["port"] == 8080
    
    def test_ir_creation(self):
        """Test complete IR model creation."""
        ir = IR(
            version="1.0",
            variables={"port": Variable(name="port", type="number", default=8080)},
            resources={"web": Resource(type="service", name="web")},
            metadata={"source": "test"}
        )
        assert ir.version == "1.0"
        assert "port" in ir.variables
        assert "web" in ir.resources


class TestActionModels:
    """Test Action and ActionList models."""
    
    def test_action_step_creation(self):
        """Test ActionStep model creation."""
        step = ActionStep(
            name="fetch_repo",
            args={"url": "https://github.com/user/repo", "ref": "main"}
        )
        assert step.name == "fetch_repo"
        assert step.args["url"] == "https://github.com/user/repo"
    
    def test_action_list_creation(self):
        """Test ActionList model creation."""
        action_list = ActionList(
            version="1",
            steps=[
                ActionStep(name="fetch_repo", args={"url": "test"}),
                ActionStep(name="build_image", args={"tag": "latest"})
            ]
        )
        assert action_list.version == "1"
        assert len(action_list.steps) == 2
    
    def test_action_list_serialization(self):
        """Test ActionList JSON serialization."""
        action_list = ActionList(
            version="1",
            steps=[ActionStep(name="test", args={"key": "value"})]
        )
        json_str = action_list.to_json()
        assert '"version": "1"' in json_str
        assert '"name": "test"' in json_str


class TestArtifactModels:
    """Test Artifact and ArtifactBundle models."""
    
    def test_artifact_creation(self):
        """Test Artifact model creation."""
        artifact = Artifact(
            path="scripts/test.sh",
            mode="0755",
            purpose="test_script",
            lang="bash",
            content="#!/bin/bash\necho 'test'"
        )
        assert artifact.path == "scripts/test.sh"
        assert artifact.mode == "0755"
        assert artifact.lang == "bash"
    
    def test_artifact_bundle_creation(self):
        """Test ArtifactBundle model creation."""
        bundle = ArtifactBundle(
            version="1",
            artifacts=[
                Artifact(
                    path="test.sh", mode="0755", purpose="test",
                    lang="bash", content="echo test"
                )
            ],
            steps=[
                ExecutionStep(purpose="test", run={"cmd": ["bash", "test.sh"]})
            ],
            vars={"TEST_VAR": "value"}
        )
        assert bundle.version == "1"
        assert len(bundle.artifacts) == 1
        assert len(bundle.steps) == 1
        assert bundle.vars["TEST_VAR"] == "value"


class TestStateModels:
    """Test state management models."""
    
    def test_resource_state_creation(self):
        """Test ResourceState model creation."""
        state = ResourceState(
            resource_id="web_service",
            type="service",
            status="success",
            config={"port": 8080}
        )
        assert state.resource_id == "web_service"
        assert state.type == "service"
        assert state.status == "success"
    
    def test_clockwork_state_creation(self):
        """Test ClockworkState model creation."""
        state = ClockworkState(
            version="1.0",
            current_resources={
                "web": ResourceState(
                    resource_id="web", type="service", status="success"
                )
            }
        )
        assert state.version == "1.0"
        assert "web" in state.current_resources


class TestValidationModels:
    """Test validation result models."""
    
    def test_validation_issue_creation(self):
        """Test ValidationIssue model creation."""
        issue = ValidationIssue(
            level="error",
            message="Missing required field",
            field_path="resources.web.config.port"
        )
        assert issue.level == "error"
        assert issue.message == "Missing required field"
    
    def test_validation_result_creation(self):
        """Test ValidationResult model creation."""
        result = ValidationResult(
            valid=False,
            issues=[
                ValidationIssue(level="error", message="Error 1"),
                ValidationIssue(level="warning", message="Warning 1")
            ]
        )
        assert result.valid is False
        assert len(result.errors) == 1
        assert len(result.warnings) == 1


class TestEnvFactsModel:
    """Test EnvFacts model."""
    
    def test_env_facts_creation(self):
        """Test EnvFacts model creation."""
        facts = EnvFacts(
            os_type="Darwin",
            architecture="arm64",
            available_runtimes=["python3", "bash", "uv"],
            docker_available=True,
            podman_available=False,
            kubernetes_available=False,
            working_directory="/Users/test/project"
        )
        assert facts.os_type == "Darwin"
        assert facts.architecture == "arm64"
        assert "python3" in facts.available_runtimes
        assert facts.docker_available is True


if __name__ == "__main__":
    pytest.main([__file__])