"""
Unit tests for Agno AI agent integration.

Tests the AI-powered compilation pipeline with LM Studio integration.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from clockwork.models import ActionList, ActionStep
from clockwork.forge.agno_agent import (
    AgnoCompiler, AgnoCompilerError, AgentArtifact, 
    AgentExecutionStep, AgentArtifactBundle, create_agno_compiler
)
from clockwork.forge.compiler import Compiler


class TestAgnoCompiler:
    """Test Agno AI compiler functionality."""
    
    def test_agno_compiler_initialization(self):
        """Test AgnoCompiler initialization with default parameters."""
        with patch('clockwork.forge.agno_agent.Agent') as mock_agent:
            compiler = AgnoCompiler()
            assert compiler.model_id == "qwen/qwen3-4b-2507"
            assert compiler.lm_studio_url == "http://localhost:1234"
            assert compiler.timeout == 300
            mock_agent.assert_called_once()
    
    def test_agno_compiler_custom_params(self):
        """Test AgnoCompiler with custom parameters."""
        with patch('clockwork.forge.agno_agent.Agent') as mock_agent:
            compiler = AgnoCompiler(
                model_id="custom/model",
                lm_studio_url="http://localhost:8080",
                timeout=600
            )
            assert compiler.model_id == "custom/model"
            assert compiler.lm_studio_url == "http://localhost:8080"
            assert compiler.timeout == 600
    
    def test_create_agno_compiler_factory(self):
        """Test the factory function for creating AgnoCompiler."""
        with patch('clockwork.forge.agno_agent.Agent'):
            compiler = create_agno_compiler(
                model_id="test/model",
                lm_studio_url="http://test:1234"
            )
            assert isinstance(compiler, AgnoCompiler)
            assert compiler.model_id == "test/model"
            assert compiler.lm_studio_url == "http://test:1234"
    
    @patch('requests.post')
    @patch('clockwork.forge.agno_agent.Agent')
    def test_compile_to_artifacts_success(self, mock_agent_class, mock_requests_post):
        """Test successful compilation of ActionList to ArtifactBundle."""
        # Mock HTTP response from LM Studio
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "content": """{
                        "version": "1",
                        "artifacts": [{
                            "path": "scripts/01_test.sh",
                            "mode": "0755", 
                            "purpose": "test_step",
                            "lang": "bash",
                            "content": "#!/bin/bash\\necho 'test'"
                        }],
                        "steps": [{
                            "purpose": "test_step",
                            "run": {"cmd": ["bash", "scripts/01_test.sh"]}
                        }],
                        "vars": {"TEST_VAR": "value"}
                    }"""
                }
            }]
        }
        mock_requests_post.return_value = mock_response
        
        # Create test ActionList
        action_list = ActionList(
            version="1",
            steps=[ActionStep(name="test_step", args={"key": "value"})]
        )
        
        # Compile and verify
        compiler = AgnoCompiler()
        result = compiler.compile_to_artifacts(action_list)
        
        assert result.version == "1"
        assert len(result.artifacts) == 1
        assert len(result.steps) == 1
        assert result.artifacts[0].path == "scripts/01_test.sh"
        assert result.steps[0].purpose == "test_step"
    
    @patch('requests.post')
    @patch('clockwork.forge.agno_agent.Agent')
    def test_compile_to_artifacts_failure(self, mock_agent_class, mock_requests_post):
        """Test compilation failure handling."""
        # Mock HTTP request failure
        mock_requests_post.side_effect = Exception("Network error")
        
        action_list = ActionList(
            version="1",
            steps=[ActionStep(name="test", args={})]
        )
        
        compiler = AgnoCompiler()
        
        with pytest.raises(AgnoCompilerError):
            compiler.compile_to_artifacts(action_list)
    
    @patch('clockwork.forge.agno_agent.Agent')
    def test_test_connection_success(self, mock_agent_class):
        """Test successful connection test."""
        mock_agent = Mock()
        mock_response = Mock()
        mock_response.content = "OK"
        mock_agent.run.return_value = mock_response
        mock_agent_class.return_value = mock_agent
        
        compiler = AgnoCompiler()
        assert compiler.test_connection() is True
    
    @patch('clockwork.forge.agno_agent.Agent')
    def test_test_connection_failure(self, mock_agent_class):
        """Test connection test failure."""
        mock_agent = Mock()
        mock_agent.run.side_effect = Exception("Connection failed")
        mock_agent_class.return_value = mock_agent
        
        compiler = AgnoCompiler()
        assert compiler.test_connection() is False
    
    @patch('clockwork.forge.agno_agent.Agent')
    def test_get_status(self, mock_agent_class):
        """Test status information retrieval."""
        mock_agent = Mock()
        mock_response = Mock()
        mock_response.content = "OK"
        mock_agent.run.return_value = mock_response
        mock_agent_class.return_value = mock_agent
        
        compiler = AgnoCompiler(
            model_id="test/model",
            lm_studio_url="http://test:1234",
            timeout=600
        )
        
        status = compiler.get_status()
        assert status["model_id"] == "test/model"
        assert status["lm_studio_url"] == "http://test:1234"
        assert status["timeout"] == 600
        assert status["connection_ok"] is True


class TestCompilerAgnoIntegration:
    """Test Compiler integration with Agno."""
    
    @patch('clockwork.forge.compiler.create_agno_compiler')
    def test_compiler_with_agno_enabled(self, mock_create_agno):
        """Test Compiler initialization with Agno enabled."""
        mock_agno_compiler = Mock()
        mock_create_agno.return_value = mock_agno_compiler
        
        compiler = Compiler(
            use_agno=True,
            lm_studio_url="http://test:1234",
            agno_model_id="test/model"
        )
        
        assert compiler.use_agno is True
        assert compiler.agno_compiler == mock_agno_compiler
        mock_create_agno.assert_called_once_with(
            model_id="test/model",
            lm_studio_url="http://test:1234",
            timeout=300
        )
    
    def test_compiler_with_agno_disabled(self):
        """Test Compiler initialization with Agno disabled."""
        compiler = Compiler(use_agno=False)
        
        assert compiler.use_agno is False
        assert compiler.agno_compiler is None
    
    @patch('clockwork.forge.compiler.create_agno_compiler')
    def test_compiler_agno_initialization_failure(self, mock_create_agno):
        """Test Compiler handles Agno initialization failure gracefully."""
        mock_create_agno.side_effect = Exception("Agno init failed")
        
        # Should not raise exception
        compiler = Compiler(use_agno=True)
        
        assert compiler.use_agno is True
        assert compiler.agno_compiler is None
    
    @patch('clockwork.forge.compiler.create_agno_compiler')
    def test_compile_with_agno_success(self, mock_create_agno):
        """Test compilation using Agno agent."""
        # Mock successful Agno compilation
        mock_agno_compiler = Mock()
        mock_bundle = Mock()
        mock_bundle.artifacts = []  # Add artifacts attribute for len() check
        mock_agno_compiler.compile_to_artifacts.return_value = mock_bundle
        mock_create_agno.return_value = mock_agno_compiler
        
        # Mock validation to avoid security checks in test
        with patch.object(Compiler, '_validate_artifact_bundle'):
            compiler = Compiler(use_agno=True)
            action_list = ActionList(version="1", steps=[])
            
            result = compiler.compile(action_list)
            
            assert result == mock_bundle
            mock_agno_compiler.compile_to_artifacts.assert_called_once_with(action_list)
    
    @patch('clockwork.forge.compiler.create_agno_compiler')
    def test_compile_agno_fallback(self, mock_create_agno):
        """Test compilation fallback when Agno fails."""
        # Mock Agno compiler that fails
        mock_agno_compiler = Mock()
        from clockwork.forge.agno_agent import AgnoCompilerError
        mock_agno_compiler.compile_to_artifacts.side_effect = AgnoCompilerError("Agno failed")
        mock_create_agno.return_value = mock_agno_compiler
        
        # Mock fallback compilation
        with patch.object(Compiler, '_fallback_compile') as mock_fallback:
            with patch.object(Compiler, '_validate_artifact_bundle'):
                mock_bundle = Mock()
                mock_bundle.artifacts = []  # Add artifacts attribute for len() check
                mock_fallback.return_value = mock_bundle
                
                compiler = Compiler(use_agno=True)
                action_list = ActionList(version="1", steps=[])
                
                result = compiler.compile(action_list)
                
                assert result == mock_bundle
                mock_fallback.assert_called_once_with(action_list)


if __name__ == "__main__":
    pytest.main([__file__])