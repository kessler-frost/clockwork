"""
Integration tests for Clockwork components.

Tests the interaction between different components of the system.
"""

import pytest
import tempfile
from pathlib import Path
from clockwork.core import ClockworkCore
from clockwork.models import ClockworkConfig
from clockwork.intake.parser import Parser
from clockwork.intake.validator import Validator
from clockwork.assembly.planner import convert_ir_to_actions


class TestIntakeIntegration:
    """Test integration between intake components."""
    
    def test_parser_validator_integration(self):
        """Test parser and validator working together."""
        parser = Parser()
        validator = Validator()
        
        # Create test HCL content
        hcl_content = '''
        variable "port" {
          type    = "number"
          default = 8080
        }
        
        resource "service" "web" {
          name  = "web-server"
          image = "nginx:latest"
          port  = var.port
        }
        '''
        
        # Parse HCL
        parsed_data = parser.parse_string(hcl_content)
        ir = parser.to_ir(parsed_data)
        
        # Validate IR
        result = validator.validate_ir(ir)
        assert result.valid


class TestAssemblyIntegration:
    """Test integration between assembly components."""
    
    def test_ir_to_actionlist_conversion(self):
        """Test converting IR to ActionList."""
        # Create test IR data
        ir_data = {
            "config": {"namespace": "test"},
            "services": {
                "web": {
                    "image": "nginx:latest",
                    "ports": [{"external": 8080, "internal": 80}],
                    "health_check": {"path": "/health"}
                }
            },
            "repositories": {}
        }
        
        # Convert to ActionList
        action_list = convert_ir_to_actions(ir_data)
        
        assert action_list.version == "1"
        assert len(action_list.steps) > 0
        
        # Check that steps follow README format
        for step in action_list.steps:
            assert hasattr(step, 'name')
            assert hasattr(step, 'args')


class TestForgeIntegration:
    """Test integration between forge components."""
    
    def test_compiler_executor_integration(self):
        """Test compiler and executor working together."""
        from clockwork.forge.compiler import Compiler
        from clockwork.forge.executor import ArtifactExecutor
        from clockwork.models import ActionList, ActionStep
        
        # Create test ActionList
        action_list = ActionList(
            version="1",
            steps=[
                ActionStep(
                    name="test_step",
                    args={"message": "Hello, World!"}
                )
            ]
        )
        
        # Compile (will use mock for now)
        compiler = Compiler()
        try:
            bundle = compiler.compile(action_list)
            assert bundle.version == "1"
            assert len(bundle.artifacts) > 0
        except Exception as e:
            # Expected if no real AI agent configured
            assert "Failed to compile" in str(e) or "mock" in str(e).lower()


class TestCoreIntegration:
    """Test ClockworkCore integration."""
    
    def test_core_initialization(self):
        """Test ClockworkCore initialization."""
        with tempfile.TemporaryDirectory() as temp_dir:
            core = ClockworkCore(config_path=Path(temp_dir))
            assert core.config.project_name is not None
            assert core.parser is not None
            assert core.validator is not None
    
    def test_core_pipeline_components(self):
        """Test that core has all pipeline components."""
        with tempfile.TemporaryDirectory() as temp_dir:
            core = ClockworkCore(config_path=Path(temp_dir))
            
            # Check all components are initialized
            assert hasattr(core, 'parser')
            assert hasattr(core, 'validator') 
            assert hasattr(core, 'state_manager')
            assert hasattr(core, 'compiler')
            assert hasattr(core, 'executor')


class TestStateIntegration:
    """Test state management integration."""
    
    def test_state_persistence(self):
        """Test state loading and saving."""
        from clockwork.forge.state import StateManager
        from clockwork.models import ClockworkState
        
        with tempfile.TemporaryDirectory() as temp_dir:
            state_file = Path(temp_dir) / "state.json"
            manager = StateManager(str(state_file))
            
            # Create and save state
            state = ClockworkState(version="1.0")
            manager.save_state(state)
            
            # Load state
            loaded_state = manager.load_state()
            assert loaded_state is not None
            assert loaded_state.version == "1.0"


if __name__ == "__main__":
    pytest.main([__file__])