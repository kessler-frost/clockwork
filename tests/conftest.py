"""
Pytest configuration and fixtures for Clockwork tests.
"""

import pytest
import tempfile
from pathlib import Path
from clockwork.core import ClockworkCore
from clockwork.models import ClockworkConfig


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
def clockwork_core(test_config):
    """Provide a ClockworkCore instance for testing."""
    return ClockworkCore(config=test_config)


@pytest.fixture
def sample_hcl_content():
    """Provide sample HCL content for testing."""
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
    }
    
    output "url" {
      value = "http://localhost:${var.port}"
    }
    '''


@pytest.fixture
def sample_ir_data():
    """Provide sample IR data for testing."""
    return {
        "config": {"namespace": "test"},
        "services": {
            "web": {
                "image": "nginx:latest",
                "ports": [{"external": 8080, "internal": 80}],
                "environment": {"APP_ENV": "test"},
                "health_check": {"path": "/health"}
            }
        },
        "repositories": {
            "app": {
                "url": "https://github.com/example/app",
                "branch": "main"
            }
        }
    }