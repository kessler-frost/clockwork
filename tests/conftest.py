"""
Pytest configuration and fixtures for Clockwork tests.
"""

import pytest
import tempfile
import json
from pathlib import Path
from unittest.mock import Mock, patch

from clockwork.core import ClockworkCore
from clockwork.models import (
    ClockworkConfig, ClockworkState, ResourceState, ExecutionRecord,
    ExecutionStatus, ResourceType, IR, Resource, Variable, Output
)
from clockwork.parser import PyInfraParser


@pytest.fixture
def temp_dir():
    """Provide a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def test_config(temp_dir):
    """Provide a test ClockworkConfig."""
    return ClockworkConfig(
        project_name="test-project",
        version="1.0",
        state_file=str(temp_dir / "state.json"),
        build_dir=str(temp_dir / "build"),
        log_level="DEBUG"
    )


@pytest.fixture
def clockwork_core(test_config, temp_dir):
    """Provide a ClockworkCore instance for testing."""
    return ClockworkCore(config_path=temp_dir, config=test_config)


@pytest.fixture
def pyinfra_parser():
    """Provide a PyInfraParser instance for testing."""
    return PyInfraParser(default_host="localhost")


@pytest.fixture
def mock_pyinfra_subprocess():
    """Mock subprocess.run for pyinfra execution."""
    with patch('subprocess.run') as mock_run:
        # Default successful execution
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "PyInfra execution successful"
        mock_result.stderr = ""
        mock_run.return_value = mock_result
        yield mock_run


@pytest.fixture
def sample_cw_content():
    """Provide sample .cw file content for testing."""
    return '''
    variable "app_name" {
      type    = "string"
      default = "test-app"
    }

    variable "port" {
      type    = "number"
      default = 8080
    }

    resource "service" "web" {
      name  = var.app_name
      image = "nginx:latest"
      ports = [{
        external = var.port
        internal = 80
      }]

      health_check {
        path    = "/health"
        timeout = "10s"
        retries = 3
      }
    }

    resource "file" "config" {
      path    = "/etc/nginx/nginx.conf"
      content = "server_name ${var.app_name};"
      mode    = "644"
    }

    output "app_url" {
      value       = "http://localhost:${var.port}"
      description = "Application URL"
    }
    '''


@pytest.fixture
def sample_ir():
    """Provide sample IR data for testing."""
    return IR(
        version="1.0",
        variables={
            "app_name": Variable(name="app_name", type="string", default="test-app"),
            "port": Variable(name="port", type="number", default=8080)
        },
        resources={
            "service.web": Resource(
                type=ResourceType.SERVICE,
                name="web",
                config={
                    "name": "test-app",
                    "image": "nginx:latest",
                    "ports": [{"external": 8080, "internal": 80}],
                    "health_check": {
                        "path": "/health",
                        "timeout": "10s",
                        "retries": 3
                    }
                }
            ),
            "file.config": Resource(
                type=ResourceType.FILE,
                name="config",
                config={
                    "path": "/etc/nginx/nginx.conf",
                    "content": "server_name test-app;",
                    "mode": "644"
                }
            )
        },
        outputs={
            "app_url": Output(
                name="app_url",
                value="http://localhost:8080",
                description="Application URL"
            )
        }
    )


@pytest.fixture
def sample_state():
    """Provide sample ClockworkState for testing."""
    return ClockworkState(
        version="1.0",
        current_resources={
            "web_service": ResourceState(
                resource_id="web_service",
                type=ResourceType.SERVICE,
                status=ExecutionStatus.SUCCESS,
                config={"name": "test-app", "image": "nginx:latest"}
            ),
            "nginx_config": ResourceState(
                resource_id="nginx_config",
                type=ResourceType.FILE,
                status=ExecutionStatus.SUCCESS,
                config={"path": "/etc/nginx/nginx.conf"}
            )
        },
        execution_history=[
            ExecutionRecord(
                run_id="run_20240101_120000",
                started_at="2024-01-01T12:00:00",
                completed_at="2024-01-01T12:01:00",
                status=ExecutionStatus.SUCCESS,
                action_list_checksum="abc123",
                artifact_bundle_checksum="def456",
                logs=["Execution completed successfully"]
            )
        ]
    )


@pytest.fixture
def sample_cw_file(temp_dir, sample_cw_content):
    """Create a sample .cw file for testing."""
    cw_file = temp_dir / "test.cw"
    cw_file.write_text(sample_cw_content)
    return cw_file


@pytest.fixture
def sample_docker_compose_content():
    """Provide sample docker-compose.yml content."""
    return '''
    version: '3.8'
    services:
      web:
        image: nginx:latest
        ports:
          - "8080:80"
        environment:
          - APP_ENV=test
      db:
        image: postgres:13
        environment:
          - POSTGRES_DB=testdb
          - POSTGRES_USER=user
          - POSTGRES_PASSWORD=pass
    '''


@pytest.fixture
def sample_kubernetes_manifest():
    """Provide sample Kubernetes manifest content."""
    return '''
    apiVersion: apps/v1
    kind: Deployment
    metadata:
      name: nginx-deployment
    spec:
      replicas: 3
      selector:
        matchLabels:
          app: nginx
      template:
        metadata:
          labels:
            app: nginx
        spec:
          containers:
          - name: nginx
            image: nginx:latest
            ports:
            - containerPort: 80
    '''


@pytest.fixture
def mock_hcl_parser():
    """Mock HCL parser for testing."""
    with patch('clockwork.parser.Parser') as mock_parser_class:
        mock_parser = Mock()
        mock_parser_class.return_value = mock_parser
        yield mock_parser


@pytest.fixture
def mock_state_manager():
    """Mock state manager for testing."""
    with patch('clockwork.core.EnhancedStateManager') as mock_sm_class:
        mock_sm = Mock()
        mock_sm_class.return_value = mock_sm

        # Default behavior
        mock_sm.load_state.return_value = None
        mock_sm.save_state.return_value = None
        mock_sm.collect_pre_execution_facts.return_value = {}
        mock_sm.collect_post_execution_facts.return_value = {}
        mock_sm.detect_drift.return_value = []
        mock_sm.get_state_summary.return_value = {
            "health_score": 100.0,
            "total_resources": 0,
            "resources_with_drift": 0,
            "stale_resources": 0,
            "failed_resources": 0
        }

        yield mock_sm


@pytest.fixture
def mock_pyinfra_inventory():
    """Mock PyInfra inventory for testing."""
    with patch('pyinfra.api.inventory.Inventory') as mock_inventory_class:
        mock_inventory = Mock()
        mock_inventory_class.return_value = mock_inventory
        yield mock_inventory


@pytest.fixture
def sample_pyinfra_code():
    """Provide sample generated PyInfra code."""
    return '''"""
PyInfra Deploy Script
Generated from Clockwork configuration

Source: test.cw
Generated: 2024-01-01T12:00:00
Parser: Clockwork PyInfra Parser v1.0

This script was automatically generated from Clockwork .cw files.
Run with: pyinfra TARGETS deploy.py
"""

# Configuration variables from .cw files
# Variables: ['app_name', 'port']

# PyInfra Inventory
# Using @local for localhost execution
INVENTORY = ['@local']

# PyInfra imports
from pyinfra import host
from pyinfra.operations import docker
from pyinfra.operations import files
from pyinfra.operations import server
import json
import os

# Variables from .cw configuration
APP_NAME = "test-app"
PORT = 8080

# Resource operations

# Resource: service.web
docker.container.running(
    name="test-app",
    image="nginx:latest",
    ports=["8080:80"]
)

# Resource: file.config
files.file(
    path="/etc/nginx/nginx.conf",
    content="server_name test-app;",
    mode="644"
)

# Health checks
# Health check for web
server.shell(
    command="curl -f http://localhost:8080/health || exit 1"
)

# Outputs
# Note: PyInfra doesn't have direct output support, using print statements

# Application URL
print(f"app_url: http://localhost:8080")
'''


# Additional test fixtures for specialized testing scenarios

@pytest.fixture(autouse=True)
def setup_test_environment():
    """Auto-used fixture to set up test environment."""
    import os
    # Set test environment variables
    os.environ['CLOCKWORK_TEST_MODE'] = 'true'
    os.environ['CLOCKWORK_LOG_LEVEL'] = 'DEBUG'
    yield
    # Clean up after tests
    os.environ.pop('CLOCKWORK_TEST_MODE', None)
    os.environ.pop('CLOCKWORK_LOG_LEVEL', None)


@pytest.fixture
def cleanup_temp_files():
    """Fixture to ensure temp files are cleaned up after tests."""
    temp_files = []
    yield temp_files
    # Clean up any temp files created during testing
    for temp_file in temp_files:
        try:
            if isinstance(temp_file, Path) and temp_file.exists():
                temp_file.unlink()
        except Exception:
            pass