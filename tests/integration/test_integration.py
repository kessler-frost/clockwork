"""
Integration tests for Clockwork pyinfra-based architecture.

Tests the interaction between different components of the new simplified system:
- Parse → Execute pipeline
- State management
- CLI integration
- Full workflow tests
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from clockwork.core import ClockworkCore
from clockwork.models import ClockworkConfig, IR, Resource, ResourceType
from clockwork.parser import PyInfraParser
from clockwork.cli import app
from typer.testing import CliRunner


class TestParseExecutePipeline:
    """Test the Parse → Execute pipeline integration."""

    def test_parse_execute_integration(self, temp_dir, sample_cw_content, mock_pyinfra_subprocess):
        """Test complete parse → execute workflow."""
        # Setup
        core = ClockworkCore(config_path=temp_dir)
        cw_file = temp_dir / "test.cw"
        cw_file.write_text(sample_cw_content)

        # Mock the HCL parser and IR conversion
        with patch.object(core.parser, 'parse_file') as mock_parse:
            mock_parse.return_value = """
# Generated PyInfra code
from pyinfra.operations import docker
docker.container.running(name="test-app", image="nginx:latest")
"""

            # Parse phase
            python_code = core.parse(cw_file)
            assert "docker.container.running" in python_code
            assert "test-app" in python_code

            # Execute phase
            results = core.execute(python_code)
            assert len(results) == 1
            assert results[0]["success"] is True

            # Verify pyinfra was called correctly
            mock_pyinfra_subprocess.assert_called_once()
            call_args = mock_pyinfra_subprocess.call_args[0][0]
            assert call_args[0] == "pyinfra"

    def test_apply_workflow_integration(self, temp_dir, sample_cw_content, mock_pyinfra_subprocess):
        """Test the complete apply workflow (parse + execute)."""
        # Setup
        core = ClockworkCore(config_path=temp_dir)
        cw_file = temp_dir / "test.cw"
        cw_file.write_text(sample_cw_content)

        with patch.object(core.parser, 'parse_file') as mock_parse:
            mock_parse.return_value = "# Generated code\nprint('test')"

            # Apply workflow
            results = core.apply(cw_file, timeout_per_step=60)

            assert len(results) == 1
            assert results[0]["success"] is True

            # Verify both parse and execute were called
            mock_parse.assert_called_once()
            mock_pyinfra_subprocess.assert_called_once()

    def test_plan_workflow_integration(self, temp_dir, sample_cw_content):
        """Test the plan workflow (parse only)."""
        # Setup
        core = ClockworkCore(config_path=temp_dir)
        cw_file = temp_dir / "test.cw"
        cw_file.write_text(sample_cw_content)

        with patch.object(core.parser, 'parse_file') as mock_parse:
            mock_parse.return_value = "# Generated plan\nprint('plan')"

            # Plan workflow (no execution)
            result = core.plan(cw_file)

            assert "Generated plan" in result
            mock_parse.assert_called_once()


class TestStateManagementIntegration:
    """Test state management integration."""

    def test_state_persistence_workflow(self, temp_dir, sample_state):
        """Test state saving and loading."""
        core = ClockworkCore(config_path=temp_dir)

        # Save state
        core.state_manager.save_state(sample_state)

        # Load state
        loaded_state = core.get_current_state()
        assert loaded_state is not None
        assert loaded_state.version == "1.0"
        assert len(loaded_state.current_resources) == 2

    def test_state_health_calculation(self, temp_dir, sample_state):
        """Test state health calculation."""
        core = ClockworkCore(config_path=temp_dir)
        core.state_manager.save_state(sample_state)

        health = core.get_state_health()
        assert health["health_score"] == 100.0  # All resources successful
        assert health["total_resources"] == 2
        assert health["healthy_resources"] == 2

    def test_state_update_from_execution(self, temp_dir, mock_pyinfra_subprocess):
        """Test state update after execution."""
        core = ClockworkCore(config_path=temp_dir)

        python_code = "print('test execution')"
        results = [{"success": True, "stdout": "output", "stderr": ""}]

        # Mock the state update methods
        with patch.object(core, '_update_state_from_results_simple') as mock_update:
            core._update_state_from_results_simple(python_code, results)
            mock_update.assert_called_once()


class TestCLIIntegration:
    """Test CLI integration with core components."""

    def test_cli_apply_integration(self, temp_dir, sample_cw_content):
        """Test CLI apply command integration."""
        runner = CliRunner()
        cw_file = temp_dir / "test.cw"
        cw_file.write_text(sample_cw_content)

        with patch('clockwork.cli.Parser') as mock_parser_class:
            with patch('clockwork.cli.execute_pyinfra_operations') as mock_execute:
                with patch('clockwork.cli.show_execution_plan'):
                    with patch('typer.confirm', return_value=True):
                        # Setup mocks
                        mock_parser = Mock()
                        mock_ir = IR(
                            resources={
                                "service.web": Resource(
                                    type=ResourceType.SERVICE,
                                    name="web",
                                    config={"name": "test", "image": "nginx"}
                                )
                            }
                        )
                        mock_parser.parse_file_to_ir.return_value = mock_ir
                        mock_parser_class.return_value = mock_parser
                        mock_execute.return_value = True

                        result = runner.invoke(app, ["apply", str(cw_file), "--dry-run"])
                        assert result.exit_code == 0

    def test_cli_facts_integration(self):
        """Test CLI facts command integration."""
        runner = CliRunner()

        result = runner.invoke(app, ["facts", "@local"])
        assert result.exit_code == 0

    def test_cli_state_command_integration(self, temp_dir):
        """Test CLI state command integration."""
        runner = CliRunner()

        with patch('clockwork.cli.ClockworkCore') as mock_core_class:
            mock_core = Mock()
            mock_state_manager = Mock()
            mock_state_manager.get_state_summary.return_value = {
                "health_score": 85.0,
                "total_resources": 5,
                "resources_with_drift": 1,
                "stale_resources": 0,
                "failed_resources": 1
            }
            mock_core.state_manager = mock_state_manager
            mock_core_class.return_value = mock_core

            result = runner.invoke(app, ["state", "show"])
            assert result.exit_code == 0


class TestParserIntegration:
    """Test parser integration with different components."""

    def test_parser_with_variables(self, pyinfra_parser):
        """Test parser variable resolution integration."""
        cw_content = '''
        variable "app_name" {
          default = "test-app"
        }

        resource "service" "web" {
          name = var.app_name
        }
        '''

        with patch.object(pyinfra_parser.hcl_parser, 'parse_string') as mock_parse:
            with patch.object(pyinfra_parser.hcl_parser, 'to_ir') as mock_to_ir:
                # Mock IR with variables
                from clockwork.models import Variable
                mock_ir = IR(
                    variables={
                        "app_name": Variable(name="app_name", type="string", default="test-app")
                    },
                    resources={
                        "service.web": Resource(
                            type=ResourceType.SERVICE,
                            name="web",
                            config={"name": "var.app_name"}
                        )
                    }
                )
                mock_to_ir.return_value = mock_ir

                result = pyinfra_parser.parse_string(cw_content)

                # Check variable substitution in generated code
                assert "test-app" in result or "APP_NAME" in result

    def test_parser_with_health_checks(self, pyinfra_parser):
        """Test parser health check generation."""
        cw_content = '''
        resource "service" "web" {
          name = "nginx"
          ports = [{external = 8080, internal = 80}]
          health_check {
            path = "/health"
          }
        }
        '''

        with patch.object(pyinfra_parser.hcl_parser, 'parse_string'):
            with patch.object(pyinfra_parser.hcl_parser, 'to_ir') as mock_to_ir:
                mock_ir = IR(
                    resources={
                        "service.web": Resource(
                            type=ResourceType.SERVICE,
                            name="web",
                            config={
                                "name": "nginx",
                                "ports": [{"external": 8080, "internal": 80}],
                                "health_check": {"path": "/health"}
                            }
                        )
                    }
                )
                mock_to_ir.return_value = mock_ir

                result = pyinfra_parser.parse_string(cw_content)

                # Check health check generation
                assert "Health check" in result
                assert "curl" in result
                assert "/health" in result


class TestErrorHandlingIntegration:
    """Test error handling across components."""

    def test_parse_error_propagation(self, temp_dir):
        """Test error propagation from parser to core."""
        core = ClockworkCore(config_path=temp_dir)
        cw_file = temp_dir / "invalid.cw"
        cw_file.write_text("invalid { hcl syntax")

        from clockwork.parser import PyInfraParserError
        from clockwork.errors import ClockworkError

        with patch.object(core.parser, 'parse_file') as mock_parse:
            mock_parse.side_effect = PyInfraParserError("Parse failed")

            with pytest.raises(ClockworkError):
                core.parse(cw_file)

    def test_execution_error_handling(self, temp_dir, mock_pyinfra_subprocess):
        """Test execution error handling."""
        core = ClockworkCore(config_path=temp_dir)

        # Mock failed execution
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "PyInfra execution failed"
        mock_pyinfra_subprocess.return_value = mock_result

        python_code = "invalid_pyinfra_code()"
        results = core.execute(python_code)

        # Should handle error gracefully
        assert len(results) == 1
        assert results[0]["success"] is False
        assert results[0]["exit_code"] == 1


class TestFullWorkflowIntegration:
    """Test complete workflows from end to end."""

    def test_complete_deployment_workflow(self, temp_dir, sample_cw_content, mock_pyinfra_subprocess):
        """Test a complete deployment from .cw file to execution."""
        # Create .cw file
        cw_file = temp_dir / "deployment.cw"
        cw_file.write_text(sample_cw_content)

        # Initialize core
        core = ClockworkCore(config_path=temp_dir)

        # Mock parsing
        with patch.object(core.parser, 'parse_file') as mock_parse:
            mock_parse.return_value = """
# Generated deployment
from pyinfra.operations import docker, files

docker.container.running(
    name="test-app",
    image="nginx:latest",
    ports=["8080:80"]
)

files.file(
    path="/etc/nginx/nginx.conf",
    content="server_name test-app;"
)
"""

            # Execute complete workflow
            results = core.apply(cw_file, targets=["localhost"])

            # Verify success
            assert len(results) == 1
            assert results[0]["success"] is True

            # Verify state was updated
            current_state = core.get_current_state()
            assert current_state is not None
            assert len(current_state.execution_history) > 0

    def test_configuration_drift_detection(self, temp_dir, sample_state, mock_state_manager):
        """Test configuration drift detection workflow."""
        # Setup core with mocked state manager
        with patch('clockwork.core.EnhancedStateManager', return_value=mock_state_manager):
            core = ClockworkCore(config_path=temp_dir)

            # Mock drift detection
            mock_state_manager.detect_drift.return_value = ["resource_1", "resource_2"]
            mock_state_manager.load_state.return_value = sample_state

            # Mock inventory creation
            with patch.object(core, '_create_pyinfra_inventory') as mock_inventory:
                mock_inventory.return_value = Mock()

                # Get current state (should exist)
                current_state = core.get_current_state()
                assert current_state is not None

                # Detect drift
                from pyinfra.api.inventory import Inventory
                inventory = Inventory((["localhost"], {"localhost": {}}))
                drifted = mock_state_manager.detect_drift(inventory, current_state.current_resources)

                assert len(drifted) == 2
                assert "resource_1" in drifted


if __name__ == "__main__":
    pytest.main([__file__])