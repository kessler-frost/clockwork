"""
Unit tests for PyInfraParser.

Tests the parsing of .cw files to pyinfra Python code including:
- Variable substitution
- Resource type mapping
- Health check generation
- Error handling
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from clockwork.parser import PyInfraParser, PyInfraParserError
from clockwork.models import IR, Resource, Variable, Output, ResourceType


class TestPyInfraParser:
    """Test PyInfraParser functionality."""

    def test_parser_initialization(self):
        """Test parser initialization with default parameters."""
        parser = PyInfraParser()
        assert parser.default_host == "localhost"
        assert "service" in parser._resource_mappings
        assert "repository" in parser._resource_mappings
        assert "file" in parser._resource_mappings

    def test_parser_custom_host(self):
        """Test parser initialization with custom default host."""
        parser = PyInfraParser(default_host="remote-host")
        assert parser.default_host == "remote-host"

    def test_parse_string_simple_service(self):
        """Test parsing a simple service resource from string."""
        cw_content = '''
        resource "service" "web" {
          name  = "nginx-server"
          image = "nginx:latest"
          ports = [{
            external = 8080
            internal = 80
          }]
        }
        '''

        parser = PyInfraParser()
        with patch.object(parser.hcl_parser, 'parse_string') as mock_parse:
            with patch.object(parser.hcl_parser, 'to_ir') as mock_to_ir:
                # Mock the IR
                mock_ir = IR(
                    resources={
                        "service.web": Resource(
                            type=ResourceType.SERVICE,
                            name="web",
                            config={
                                "name": "nginx-server",
                                "image": "nginx:latest",
                                "ports": [{"external": 8080, "internal": 80}]
                            }
                        )
                    }
                )
                mock_to_ir.return_value = mock_ir

                result = parser.parse_string(cw_content)

                # Check that pyinfra code is generated
                assert "from pyinfra import host" in result
                assert "from pyinfra.operations import docker" in result
                assert "nginx-server" in result
                assert "nginx:latest" in result
                assert "docker.container.running" in result

    def test_parse_string_with_variables(self):
        """Test parsing with variable substitution."""
        cw_content = '''
        variable "app_name" {
          type    = "string"
          default = "my-app"
        }

        variable "port" {
          type    = "number"
          default = 3000
        }

        resource "service" "web" {
          name = var.app_name
          ports = [{
            external = var.port
            internal = 80
          }]
        }
        '''

        parser = PyInfraParser()
        with patch.object(parser.hcl_parser, 'parse_string') as mock_parse:
            with patch.object(parser.hcl_parser, 'to_ir') as mock_to_ir:
                # Mock the IR with variables
                mock_ir = IR(
                    variables={
                        "app_name": Variable(name="app_name", type="string", default="my-app"),
                        "port": Variable(name="port", type="number", default=3000)
                    },
                    resources={
                        "service.web": Resource(
                            type=ResourceType.SERVICE,
                            name="web",
                            config={
                                "name": "var.app_name",
                                "ports": [{"external": "var.port", "internal": 80}]
                            }
                        )
                    }
                )
                mock_to_ir.return_value = mock_ir

                result = parser.parse_string(cw_content)

                # Check variable substitution
                assert "APP_NAME = \"my-app\"" in result
                assert "PORT = 3000" in result
                assert "'my-app'" in result or "'var.app_name'" in result

    def test_parse_file_operation(self):
        """Test parsing file resource."""
        parser = PyInfraParser()
        with patch.object(parser.hcl_parser, 'parse_string') as mock_parse:
            with patch.object(parser.hcl_parser, 'to_ir') as mock_to_ir:
                # Mock the IR with file resource
                mock_ir = IR(
                    resources={
                        "file.config": Resource(
                            type=ResourceType.FILE,
                            name="config",
                            config={
                                "path": "/etc/app/config.conf",
                                "content": "server_name = nginx",
                                "mode": "644"
                            }
                        )
                    }
                )
                mock_to_ir.return_value = mock_ir

                result = parser.parse_string("")

                # Check file operation generation
                assert "from pyinfra.operations import files" in result
                assert "files.file" in result
                assert "/etc/app/config.conf" in result
                assert "server_name = nginx" in result

    def test_parse_repository_operation(self):
        """Test parsing repository resource."""
        parser = PyInfraParser()
        with patch.object(parser.hcl_parser, 'parse_string') as mock_parse:
            with patch.object(parser.hcl_parser, 'to_ir') as mock_to_ir:
                # Mock the IR with repository resource
                mock_ir = IR(
                    resources={
                        "repository.app": Resource(
                            type=ResourceType.CUSTOM,  # repository maps to custom
                            name="app",
                            config={
                                "src": "https://github.com/user/repo.git",
                                "dest": "/opt/app",
                                "branch": "main"
                            }
                        )
                    }
                )
                mock_to_ir.return_value = mock_ir

                result = parser.parse_string("")

                # Check git operation generation
                assert "git.repo" in result or "server.shell" in result
                assert "https://github.com/user/repo.git" in result or "/opt/app" in result

    def test_parse_with_health_checks(self):
        """Test parsing resources with health checks."""
        parser = PyInfraParser()
        with patch.object(parser.hcl_parser, 'parse_string') as mock_parse:
            with patch.object(parser.hcl_parser, 'to_ir') as mock_to_ir:
                # Mock the IR with health check
                mock_ir = IR(
                    resources={
                        "service.web": Resource(
                            type=ResourceType.SERVICE,
                            name="web",
                            config={
                                "name": "nginx-server",
                                "image": "nginx:latest",
                                "ports": [{"external": 8080, "internal": 80}],
                                "health_check": {
                                    "path": "/health",
                                    "timeout": "10s",
                                    "retries": 3
                                }
                            }
                        )
                    }
                )
                mock_to_ir.return_value = mock_ir

                result = parser.parse_string("")

                # Check health check generation
                assert "Health check" in result
                assert "curl -f http://localhost:8080/health" in result
                assert "server.shell" in result

    def test_parse_with_outputs(self):
        """Test parsing with outputs."""
        parser = PyInfraParser()
        with patch.object(parser.hcl_parser, 'parse_string') as mock_parse:
            with patch.object(parser.hcl_parser, 'to_ir') as mock_to_ir:
                # Mock the IR with outputs
                mock_ir = IR(
                    outputs={
                        "app_url": Output(
                            name="app_url",
                            value="http://localhost:8080",
                            description="Application URL"
                        )
                    }
                )
                mock_to_ir.return_value = mock_ir

                result = parser.parse_string("")

                # Check output generation
                assert "# Outputs" in result
                assert "print(f\"app_url: http://localhost:8080\")" in result

    def test_parse_file_not_found(self):
        """Test error handling for non-existent file."""
        parser = PyInfraParser()

        with pytest.raises(FileNotFoundError):
            parser.parse_file("non_existent.cw")

    def test_parse_invalid_hcl(self):
        """Test error handling for invalid HCL syntax."""
        parser = PyInfraParser()

        with patch.object(parser.hcl_parser, 'parse_string') as mock_parse:
            mock_parse.side_effect = ValueError("Invalid HCL syntax")

            with pytest.raises(PyInfraParserError) as exc_info:
                parser.parse_string("invalid { hcl")

            assert "Failed to parse HCL" in str(exc_info.value)

    def test_parse_directory(self):
        """Test parsing a directory of .cw files."""
        parser = PyInfraParser()

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            with patch.object(parser.hcl_parser, 'parse_directory') as mock_parse_dir:
                # Mock the IR
                mock_ir = IR(
                    resources={
                        "service.web": Resource(
                            type=ResourceType.SERVICE,
                            name="web",
                            config={"name": "nginx", "image": "nginx:latest"}
                        )
                    }
                )
                mock_parse_dir.return_value = mock_ir

                result = parser.parse_directory(temp_path)

                # Check that pyinfra code is generated
                assert "from pyinfra import host" in result
                assert "nginx" in result

    def test_variable_substitution_complex(self):
        """Test complex variable substitution patterns."""
        parser = PyInfraParser()
        variables = {
            "app_name": "my-app",
            "port": 8080,
            "enabled": True,
            "tags": ["web", "production"]
        }

        # Test string substitution
        text = "Service ${var.app_name} on port var.port"
        result = parser._substitute_variables(text, variables)
        assert "my-app" in result
        assert "'8080'" in result or "8080" in result

        # Test dict substitution
        config = {
            "name": "var.app_name",
            "port": "var.port",
            "enabled": "var.enabled"
        }
        result = parser._substitute_variables(config, variables)
        assert result["name"] == "'my-app'"
        assert result["port"] == "8080"

        # Test list substitution
        ports = ["var.port", 443]
        result = parser._substitute_variables(ports, variables)
        assert result[0] == "8080"
        assert result[1] == 443

    def test_generate_inventory_localhost(self):
        """Test inventory generation for localhost."""
        parser = PyInfraParser()
        result = parser._generate_inventory(["localhost"])

        assert "INVENTORY = ['@local']" in result

    def test_generate_inventory_multiple_hosts(self):
        """Test inventory generation for multiple hosts."""
        parser = PyInfraParser()
        result = parser._generate_inventory(["host1", "host2", "host3"])

        assert "INVENTORY = ['host1', 'host2', 'host3']" in result

    def test_generate_imports_service_resource(self):
        """Test import generation for service resources."""
        parser = PyInfraParser()
        resources = {
            "web": Resource(type=ResourceType.SERVICE, name="web"),
            "db": Resource(type=ResourceType.FILE, name="db")
        }

        result = parser._generate_imports(resources)

        assert "from pyinfra.operations import docker" in result
        assert "from pyinfra.operations import files" in result
        assert "from pyinfra.operations import server" in result
        assert "from pyinfra import host" in result

    def test_resource_mapping_validation(self):
        """Test that resource mappings are properly configured."""
        parser = PyInfraParser()

        # Check service mapping
        service_mapping = parser._resource_mappings["service"]
        assert service_mapping["module"] == "docker.container"
        assert service_mapping["operation"] == "running"
        assert "name" in service_mapping["required_args"]
        assert "image" in service_mapping["required_args"]

        # Check file mapping
        file_mapping = parser._resource_mappings["file"]
        assert file_mapping["module"] == "files.file"
        assert file_mapping["operation"] == "file"
        assert "path" in file_mapping["required_args"]


class TestVariableResolution:
    """Test variable resolution functionality."""

    def test_resolve_variables_with_defaults(self):
        """Test resolving variables with default values."""
        parser = PyInfraParser()
        variables = {
            "app_name": Variable(name="app_name", type="string", default="test-app"),
            "port": Variable(name="port", type="number", default=8080),
            "enabled": Variable(name="enabled", type="boolean", default=True)
        }

        result = parser._resolve_variables(variables)

        assert result["app_name"] == "test-app"
        assert result["port"] == 8080
        assert result["enabled"] is True

    def test_resolve_variables_required(self):
        """Test resolving required variables without defaults."""
        parser = PyInfraParser()
        variables = {
            "api_key": Variable(name="api_key", type="string", required=True),
            "database_url": Variable(name="database_url", type="string", required=True)
        }

        result = parser._resolve_variables(variables)

        assert result["api_key"] == "<REQUIRED:api_key>"
        assert result["database_url"] == "<REQUIRED:database_url>"

    def test_resolve_variables_optional_without_default(self):
        """Test resolving optional variables without defaults."""
        parser = PyInfraParser()
        variables = {
            "debug": Variable(name="debug", type="boolean", required=False),
            "tags": Variable(name="tags", type="list", required=False),
            "count": Variable(name="count", type="number", required=False),
            "name": Variable(name="name", type="string", required=False)
        }

        result = parser._resolve_variables(variables)

        assert result["debug"] is False
        assert result["tags"] == []
        assert result["count"] == 0
        assert result["name"] == ""


if __name__ == "__main__":
    pytest.main([__file__])