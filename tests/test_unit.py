"""
Simple unit tests for core Clockwork functionality.
"""

import pytest
import tempfile
from pathlib import Path
from clockwork.models import IR, Variable, Resource, ActionList, ActionStep


def test_variable_model():
    """Test Variable model creation."""
    var = Variable(name="test", type="string", default="value")
    assert var.name == "test"
    assert var.default == "value"


def test_resource_model():
    """Test Resource model creation."""
    resource = Resource(
        type="service",
        name="web",
        config={"image": "nginx:latest"}
    )
    assert resource.type == "service"
    assert resource.name == "web"
    assert resource.config["image"] == "nginx:latest"


def test_action_list_model():
    """Test ActionList model creation."""
    action_list = ActionList(
        version="1",
        steps=[
            ActionStep(name="test", args={"key": "value"})
        ]
    )
    assert action_list.version == "1"
    assert len(action_list.steps) == 1
    assert action_list.steps[0].name == "test"


def test_action_list_serialization():
    """Test ActionList JSON serialization."""
    action_list = ActionList(
        version="1",
        steps=[ActionStep(name="test", args={})]
    )
    json_str = action_list.to_json()
    assert '"version": "1"' in json_str
    assert '"name": "test"' in json_str


def test_ir_creation():
    """Test IR model creation."""
    ir = IR(
        version="1.0",
        variables={"port": Variable(name="port", default=8080)},
        resources={"web": Resource(type="service", name="web")}
    )
    assert ir.version == "1.0"
    assert "port" in ir.variables
    assert "web" in ir.resources


if __name__ == "__main__":
    pytest.main([__file__])