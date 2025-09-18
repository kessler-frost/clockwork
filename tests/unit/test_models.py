"""
Unit tests for Clockwork models.

Tests the core Pydantic models and their validation logic for the pyinfra-based architecture.
"""

import pytest
from datetime import datetime
from clockwork.models import (
    IR, Variable, Provider, Resource, Module, Output,
    ClockworkState, ResourceState, ExecutionRecord,
    ClockworkConfig, ExecutionStatus, ResourceType
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
            type=ResourceType.SERVICE,
            name="web_server",
            config={"port": 8080},
            tags={"env": "prod"}
        )
        assert resource.type == ResourceType.SERVICE
        assert resource.name == "web_server"
        assert resource.config["port"] == 8080
    
    def test_ir_creation(self):
        """Test complete IR model creation."""
        ir = IR(
            version="1.0",
            variables={"port": Variable(name="port", type="number", default=8080)},
            resources={"web": Resource(type=ResourceType.SERVICE, name="web")},
            metadata={"source": "test"}
        )
        assert ir.version == "1.0"
        assert "port" in ir.variables
        assert "web" in ir.resources


class TestConfigurationModels:
    """Test configuration and settings models."""

    def test_clockwork_config_creation(self):
        """Test ClockworkConfig model creation."""
        config = ClockworkConfig(
            project_name="test-project",
            version="1.0",
            log_level="DEBUG",
            build_dir="/tmp/build",
            use_agno=True
        )
        assert config.project_name == "test-project"
        assert config.version == "1.0"
        assert config.log_level == "DEBUG"
        assert config.build_dir == "/tmp/build"
        assert config.use_agno is True

    def test_clockwork_config_defaults(self):
        """Test ClockworkConfig default values."""
        config = ClockworkConfig()
        # Note: project_name may be influenced by environment variables
        assert config.version == "1.0"
        assert config.log_level in ["INFO", "DEBUG"]  # May be set by test environment
        assert ".clockwork/build" in config.build_dir
        assert config.use_agno is True

    def test_clockwork_config_from_env(self):
        """Test ClockworkConfig loading from environment variables."""
        import os
        # Set test environment variables
        os.environ['CLOCKWORK_PROJECT_NAME'] = 'env-project'
        os.environ['CLOCKWORK_LOG_LEVEL'] = 'WARNING'

        try:
            config = ClockworkConfig()
            assert config.project_name == 'env-project'
            assert config.log_level == 'WARNING'
        finally:
            # Clean up
            os.environ.pop('CLOCKWORK_PROJECT_NAME', None)
            os.environ.pop('CLOCKWORK_LOG_LEVEL', None)


class TestStateModels:
    """Test state management models."""
    
    def test_resource_state_creation(self):
        """Test ResourceState model creation."""
        state = ResourceState(
            resource_id="web_service",
            type=ResourceType.SERVICE,
            status=ExecutionStatus.SUCCESS,
            config={"port": 8080}
        )
        assert state.resource_id == "web_service"
        assert state.type == ResourceType.SERVICE
        assert state.status == ExecutionStatus.SUCCESS
    
    def test_clockwork_state_creation(self):
        """Test ClockworkState model creation."""
        state = ClockworkState(
            version="1.0",
            current_resources={
                "web": ResourceState(
                    resource_id="web",
                    type=ResourceType.SERVICE,
                    status=ExecutionStatus.SUCCESS
                )
            }
        )
        assert state.version == "1.0"
        assert "web" in state.current_resources
        assert len(state.current_resources) == 1


class TestExecutionModels:
    """Test execution-related models."""

    def test_execution_record_creation(self):
        """Test ExecutionRecord model creation."""
        record = ExecutionRecord(
            run_id="run_20240101_120000",
            started_at=datetime.now(),
            completed_at=datetime.now(),
            status=ExecutionStatus.SUCCESS,
            action_list_checksum="abc123",
            artifact_bundle_checksum="def456",
            logs=["Step 1 completed", "Step 2 completed"]
        )
        assert record.run_id == "run_20240101_120000"
        assert record.status == ExecutionStatus.SUCCESS
        assert len(record.logs) == 2

    def test_execution_status_enum(self):
        """Test ExecutionStatus enum values."""
        assert ExecutionStatus.PENDING == "pending"
        assert ExecutionStatus.RUNNING == "running"
        assert ExecutionStatus.SUCCESS == "success"
        assert ExecutionStatus.FAILED == "failed"
        assert ExecutionStatus.SKIPPED == "skipped"

    def test_resource_type_enum(self):
        """Test ResourceType enum values."""
        assert ResourceType.SERVICE == "service"
        assert ResourceType.FILE == "file"
        assert ResourceType.DIRECTORY == "directory"
        assert ResourceType.NETWORK == "network"
        assert ResourceType.CUSTOM == "custom"


class TestModelIntegration:
    """Test model integration and relationships."""

    def test_state_with_execution_history(self):
        """Test ClockworkState with execution history."""
        execution_record = ExecutionRecord(
            run_id="test_run",
            started_at=datetime.now(),
            status=ExecutionStatus.SUCCESS,
            action_list_checksum="abc",
            artifact_bundle_checksum="def",
            logs=["Completed successfully"]
        )

        state = ClockworkState(
            version="1.0",
            execution_history=[execution_record]
        )

        assert len(state.execution_history) == 1
        assert state.execution_history[0].run_id == "test_run"
        assert state.execution_history[0].status == ExecutionStatus.SUCCESS

    def test_resource_state_with_timestamps(self):
        """Test ResourceState with timestamp handling."""
        now = datetime.now()
        resource_state = ResourceState(
            resource_id="test_resource",
            type=ResourceType.SERVICE,
            status=ExecutionStatus.SUCCESS,
            last_applied=now,
            last_verified=now,
            config={"test": "value"}
        )

        assert resource_state.last_applied == now
        assert resource_state.last_verified == now
        assert resource_state.config["test"] == "value"

    def test_ir_model_completeness(self):
        """Test complete IR model with all fields."""
        ir = IR(
            version="1.0",
            metadata={"generated_by": "test", "timestamp": "2024-01-01"},
            variables={
                "env": Variable(name="env", type="string", default="production")
            },
            providers=[
                Provider(name="docker", source="local")
            ],
            resources={
                "web": Resource(
                    type=ResourceType.SERVICE,
                    name="web",
                    config={"image": "nginx"},
                    depends_on=["db"],
                    tags={"tier": "frontend"}
                )
            },
            modules={
                "networking": Module(
                    name="networking",
                    source="./modules/network",
                    inputs={"vpc_cidr": "10.0.0.0/16"}
                )
            },
            outputs={
                "web_url": Output(
                    name="web_url",
                    value="http://localhost:8080",
                    description="Web application URL"
                )
            }
        )

        assert ir.version == "1.0"
        assert "env" in ir.variables
        assert len(ir.providers) == 1
        assert "web" in ir.resources
        assert "networking" in ir.modules
        assert "web_url" in ir.outputs
        assert ir.resources["web"].depends_on == ["db"]
        assert ir.resources["web"].tags["tier"] == "frontend"

    def test_model_serialization(self):
        """Test model serialization and deserialization."""
        resource_state = ResourceState(
            resource_id="test",
            type=ResourceType.FILE,
            status=ExecutionStatus.SUCCESS
        )

        # Test serialization
        data = resource_state.model_dump()
        assert data["resource_id"] == "test"
        assert data["type"] == "file"
        assert data["status"] == "success"

        # Test deserialization
        new_resource_state = ResourceState.model_validate(data)
        assert new_resource_state.resource_id == "test"
        assert new_resource_state.type == ResourceType.FILE
        assert new_resource_state.status == ExecutionStatus.SUCCESS

    def test_state_update_timestamp(self):
        """Test state timestamp update functionality."""
        state = ClockworkState(version="1.0")
        original_timestamp = state.updated_at

        # Update timestamp
        state.update_timestamp()

        # Timestamp should be updated
        assert state.updated_at > original_timestamp


if __name__ == "__main__":
    pytest.main([__file__])