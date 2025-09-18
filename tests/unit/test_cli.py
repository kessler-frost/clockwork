"""
Unit tests for Clockwork CLI.

Tests all CLI commands including:
- apply command
- plan command
- watch command
- facts command
- Argument parsing
- Target handling
- Variable passing
"""

import pytest
import tempfile
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from typer.testing import CliRunner

from clockwork.cli import app, parse_variables, create_inventory_from_target, convert_ir_to_pyinfra_ops
from clockwork.models import IR, Resource, ResourceType


class TestCLICommands:
    """Test CLI command functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.runner = CliRunner()

    def test_version_callback(self):
        """Test version callback shows version and exits."""
        runner = CliRunner()
        result = runner.invoke(app, ["--version"])

        assert result.exit_code == 0
        assert "Clockwork" in result.output

    def test_apply_command_success(self):
        """Test successful apply command."""
        runner = CliRunner()

        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test .cw file
            cw_file = Path(temp_dir) / "test.cw"
            cw_file.write_text('''
            resource "service" "web" {
              name = "nginx"
              image = "nginx:latest"
            }
            ''')

            # Mock the parsing and execution
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
                                        config={"name": "nginx", "image": "nginx:latest"}
                                    )
                                }
                            )
                            mock_parser.parse_file_to_ir.return_value = mock_ir
                            mock_parser_class.return_value = mock_parser
                            mock_execute.return_value = True

                            # Run command
                            result = runner.invoke(app, ["apply", str(cw_file)])

                            assert result.exit_code == 0
                            assert "Apply completed successfully" in result.output

    def test_apply_command_dry_run(self):
        """Test apply command with dry run."""
        runner = CliRunner()

        with tempfile.TemporaryDirectory() as temp_dir:
            cw_file = Path(temp_dir) / "test.cw"
            cw_file.write_text("# test")

            with patch('clockwork.cli.Parser') as mock_parser_class:
                with patch('clockwork.cli.execute_pyinfra_operations') as mock_execute:
                    with patch('clockwork.cli.show_execution_plan'):
                        mock_parser = Mock()
                        mock_ir = IR(resources={})
                        mock_parser.parse_file_to_ir.return_value = mock_ir
                        mock_parser_class.return_value = mock_parser
                        mock_execute.return_value = True

                        result = runner.invoke(app, ["apply", str(cw_file), "--dry-run"])

                        assert result.exit_code == 0
                        assert "Plan completed" in result.output

    def test_apply_command_with_variables(self):
        """Test apply command with variables."""
        runner = CliRunner()

        with tempfile.TemporaryDirectory() as temp_dir:
            cw_file = Path(temp_dir) / "test.cw"
            cw_file.write_text("# test")

            with patch('clockwork.cli.Parser') as mock_parser_class:
                with patch('clockwork.cli.execute_pyinfra_operations') as mock_execute:
                    with patch('clockwork.cli.show_execution_plan'):
                        with patch('typer.confirm', return_value=True):
                            mock_parser = Mock()
                            mock_ir = IR(resources={})
                            mock_parser.parse_file_to_ir.return_value = mock_ir
                            mock_parser_class.return_value = mock_parser
                            mock_execute.return_value = True

                            result = runner.invoke(app, [
                                "apply", str(cw_file),
                                "--var", "app_name=test-app",
                                "--var", "port=8080"
                            ])

                            assert result.exit_code == 0
                            # Verify variables were parsed
                            mock_parser.parse_file_to_ir.assert_called_once()
                            call_args = mock_parser.parse_file_to_ir.call_args
                            variables = call_args[1]['variables'] if len(call_args) > 1 else {}
                            # Note: variables are passed to convert_ir_to_pyinfra_ops in the actual implementation

    def test_apply_command_with_target(self):
        """Test apply command with custom target."""
        runner = CliRunner()

        with tempfile.TemporaryDirectory() as temp_dir:
            cw_file = Path(temp_dir) / "test.cw"
            cw_file.write_text("# test")

            with patch('clockwork.cli.Parser') as mock_parser_class:
                with patch('clockwork.cli.execute_pyinfra_operations') as mock_execute:
                    with patch('clockwork.cli.show_execution_plan'):
                        with patch('typer.confirm', return_value=True):
                            mock_parser = Mock()
                            mock_ir = IR(resources={})
                            mock_parser.parse_file_to_ir.return_value = mock_ir
                            mock_parser_class.return_value = mock_parser
                            mock_execute.return_value = True

                            result = runner.invoke(app, [
                                "apply", str(cw_file),
                                "--target", "@ssh:user@host:2222"
                            ])

                            assert result.exit_code == 0

    def test_apply_command_cancel_execution(self):
        """Test apply command when user cancels execution."""
        runner = CliRunner()

        with tempfile.TemporaryDirectory() as temp_dir:
            cw_file = Path(temp_dir) / "test.cw"
            cw_file.write_text("# test")

            with patch('clockwork.cli.Parser') as mock_parser_class:
                with patch('clockwork.cli.show_execution_plan'):
                    with patch('typer.confirm', return_value=False):
                        mock_parser = Mock()
                        mock_ir = IR(
                            resources={
                                "service.web": Resource(
                                    type=ResourceType.SERVICE,
                                    name="web"
                                )
                            }
                        )
                        mock_parser.parse_file_to_ir.return_value = mock_ir
                        mock_parser_class.return_value = mock_parser

                        result = runner.invoke(app, ["apply", str(cw_file)])

                        assert result.exit_code == 0
                        assert "Execution cancelled" in result.output

    def test_plan_command(self):
        """Test plan command."""
        runner = CliRunner()

        with tempfile.TemporaryDirectory() as temp_dir:
            cw_file = Path(temp_dir) / "test.cw"
            cw_file.write_text("# test")

            # Plan command calls apply with dry_run=True
            with patch('clockwork.cli.apply') as mock_apply:
                result = runner.invoke(app, ["plan", str(cw_file)])

                # Plan should call apply with dry_run=True
                mock_apply.assert_called_once()

    def test_facts_command_local(self):
        """Test facts command for local target."""
        runner = CliRunner()

        result = runner.invoke(app, ["facts", "@local"])

        assert result.exit_code == 0
        # Should show local system facts
        assert "server.Os" in result.output or "Facts for @local" in result.output

    def test_facts_command_local_json(self):
        """Test facts command with JSON output."""
        runner = CliRunner()

        result = runner.invoke(app, ["facts", "@local", "--json"])

        assert result.exit_code == 0
        # Should contain JSON output
        try:
            json.loads(result.output)
        except json.JSONDecodeError:
            pytest.fail("Output should be valid JSON")

    def test_facts_command_specific_fact(self):
        """Test facts command for specific fact."""
        runner = CliRunner()

        result = runner.invoke(app, ["facts", "@local", "--fact", "server.Os"])

        assert result.exit_code == 0

    def test_facts_command_unknown_fact(self):
        """Test facts command for unknown fact."""
        runner = CliRunner()

        result = runner.invoke(app, ["facts", "@local", "--fact", "unknown.fact"])

        assert result.exit_code == 1
        assert "Unknown fact" in result.output

    def test_facts_command_remote_not_implemented(self):
        """Test facts command for remote targets (not implemented)."""
        runner = CliRunner()

        result = runner.invoke(app, ["facts", "@ssh:remote-host"])

        assert result.exit_code == 0
        assert "not yet implemented" in result.output

    def test_watch_command_file_not_found(self):
        """Test watch command with non-existent file."""
        runner = CliRunner()

        result = runner.invoke(app, ["watch", "non_existent.cw"])

        assert result.exit_code == 1
        assert "Configuration file not found" in result.output


class TestCLIHelperFunctions:
    """Test CLI helper functions."""

    def test_parse_variables_valid(self):
        """Test parsing valid variables."""
        var_list = ["app_name=my-app", "port=8080", "enabled=true"]

        result = parse_variables(var_list)

        assert result["app_name"] == "my-app"
        assert result["port"] == 8080
        assert result["enabled"] is True

    def test_parse_variables_json_values(self):
        """Test parsing variables with JSON values."""
        var_list = [
            'config={"host": "localhost", "port": 3000}',
            'tags=["web", "production"]',
            'count=42'
        ]

        result = parse_variables(var_list)

        assert result["config"] == {"host": "localhost", "port": 3000}
        assert result["tags"] == ["web", "production"]
        assert result["count"] == 42

    def test_parse_variables_invalid_format(self):
        """Test parsing variables with invalid format."""
        var_list = ["invalid_variable_format"]

        with pytest.raises(SystemExit):  # typer.Exit
            parse_variables(var_list)

    def test_create_inventory_local(self):
        """Test creating inventory for local target."""
        inventory = create_inventory_from_target("@local")

        assert inventory is not None
        # Check that inventory contains local host
        hosts, host_data = inventory
        assert "@local" in hosts
        assert "@local" in host_data

    def test_create_inventory_docker(self):
        """Test creating inventory for docker target."""
        inventory = create_inventory_from_target("@docker:my-container")

        assert inventory is not None
        hosts, host_data = inventory
        assert "my-container" in hosts
        assert host_data["my-container"]["pyinfra_connector"] == "docker"

    def test_create_inventory_ssh_simple(self):
        """Test creating inventory for simple SSH target."""
        inventory = create_inventory_from_target("@ssh:remote-host")

        assert inventory is not None
        hosts, host_data = inventory
        assert "remote-host" in hosts
        assert host_data["remote-host"]["ssh_port"] == 22

    def test_create_inventory_ssh_with_user_and_port(self):
        """Test creating inventory for SSH target with user and port."""
        inventory = create_inventory_from_target("@ssh:user@remote-host:2222")

        assert inventory is not None
        hosts, host_data = inventory
        assert "remote-host" in hosts
        assert host_data["remote-host"]["ssh_user"] == "user"
        assert host_data["remote-host"]["ssh_port"] == 2222

    def test_create_inventory_unsupported_target(self):
        """Test creating inventory for unsupported target."""
        with pytest.raises(ValueError) as exc_info:
            create_inventory_from_target("@unsupported:target")

        assert "Unsupported target format" in str(exc_info.value)

    def test_convert_ir_to_pyinfra_ops_service(self):
        """Test converting IR with service resource to PyInfra operations."""
        ir = IR(
            resources={
                "service.web": Resource(
                    type=ResourceType.SERVICE,
                    name="web",
                    config={
                        "name": "nginx-server",
                        "image": "nginx:latest",
                        "ports": [{"external": 8080, "internal": 80}],
                        "environment": {"ENV": "production"}
                    }
                )
            }
        )

        operations = convert_ir_to_pyinfra_ops(ir)

        assert len(operations) == 1
        op = operations[0]
        assert op["name"] == "Ensure Docker service nginx-server"
        assert op["operation"] == "docker.container"
        assert op["kwargs"]["image"] == "nginx:latest"
        assert op["kwargs"]["ports"] == [{"external": 8080, "internal": 80}]

    def test_convert_ir_to_pyinfra_ops_file(self):
        """Test converting IR with file resource to PyInfra operations."""
        ir = IR(
            resources={
                "file.config": Resource(
                    type=ResourceType.FILE,
                    name="config",
                    config={
                        "path": "/etc/app/config.conf",
                        "content": "server_name = nginx"
                    }
                )
            }
        )

        operations = convert_ir_to_pyinfra_ops(ir)

        assert len(operations) == 1
        op = operations[0]
        assert op["name"] == "Create file config"
        assert op["operation"] == "files.put"
        assert op["args"] == ["server_name = nginx", "/etc/app/config.conf"]

    def test_convert_ir_to_pyinfra_ops_directory(self):
        """Test converting IR with directory resource to PyInfra operations."""
        ir = IR(
            resources={
                "directory.logs": Resource(
                    type=ResourceType.DIRECTORY,
                    name="logs",
                    config={
                        "path": "/var/log/app"
                    }
                )
            }
        )

        operations = convert_ir_to_pyinfra_ops(ir)

        assert len(operations) == 1
        op = operations[0]
        assert op["name"] == "Create directory logs"
        assert op["operation"] == "files.directory"
        assert op["args"] == ["/var/log/app"]

    def test_convert_ir_to_pyinfra_ops_health_check_http(self):
        """Test converting IR with HTTP health check to PyInfra operations."""
        ir = IR(
            resources={
                "check.health": Resource(
                    type=ResourceType.CHECK,
                    name="health",
                    config={
                        "type": "http",
                        "url": "http://localhost:8080/health",
                        "expected_status": 200,
                        "timeout": 30,
                        "retries": 3
                    }
                )
            }
        )

        operations = convert_ir_to_pyinfra_ops(ir)

        assert len(operations) == 1
        op = operations[0]
        assert op["name"] == "HTTP health check health"
        assert op["operation"] == "clockwork.pyinfra_ops.health.http_health_check"
        assert op["kwargs"]["url"] == "http://localhost:8080/health"
        assert op["kwargs"]["expected_status"] == 200

    def test_convert_ir_to_pyinfra_ops_health_check_tcp(self):
        """Test converting IR with TCP health check to PyInfra operations."""
        ir = IR(
            resources={
                "check.tcp": Resource(
                    type=ResourceType.CHECK,
                    name="tcp",
                    config={
                        "type": "tcp",
                        "host_address": "localhost",
                        "port": 5432,
                        "timeout": 10
                    }
                )
            }
        )

        operations = convert_ir_to_pyinfra_ops(ir)

        assert len(operations) == 1
        op = operations[0]
        assert op["name"] == "TCP health check tcp"
        assert op["operation"] == "clockwork.pyinfra_ops.health.tcp_health_check"
        assert op["kwargs"]["host_address"] == "localhost"
        assert op["kwargs"]["port"] == 5432

    def test_convert_ir_to_pyinfra_ops_empty(self):
        """Test converting empty IR to PyInfra operations."""
        ir = IR(resources={})

        operations = convert_ir_to_pyinfra_ops(ir)

        assert len(operations) == 0


if __name__ == "__main__":
    pytest.main([__file__])