"""
Unit tests for ClockworkCore.

Tests the core orchestration functionality including:
- Parse method
- Execute method
- Apply workflow
- State management
- Error handling
"""

import pytest
import tempfile
import subprocess
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call
from datetime import datetime

from clockwork.core import ClockworkCore
from clockwork.models import (
    ClockworkConfig, ClockworkState, ResourceState, ExecutionRecord,
    ExecutionStatus, ResourceType
)
from clockwork.errors import ClockworkError
from clockwork.parser import PyInfraParserError


class TestClockworkCoreInitialization:
    """Test ClockworkCore initialization."""

    def test_core_initialization_default(self):
        """Test core initialization with default parameters."""
        with tempfile.TemporaryDirectory() as temp_dir:
            core = ClockworkCore(config_path=Path(temp_dir))

            assert core.config_path == Path(temp_dir)
            assert core.config is not None
            assert core.parser is not None
            assert core.state_manager is not None

    def test_core_initialization_with_config(self):
        """Test core initialization with provided config."""
        config = ClockworkConfig(
            project_name="test-project",
            log_level="DEBUG"
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            core = ClockworkCore(config_path=Path(temp_dir), config=config)

            assert core.config.project_name == "test-project"
            assert core.config.log_level == "DEBUG"

    def test_core_state_manager_initialization(self):
        """Test state manager is properly initialized."""
        with tempfile.TemporaryDirectory() as temp_dir:
            core = ClockworkCore(config_path=Path(temp_dir))

            # Test state manager can load/save state
            state = ClockworkState(version="1.0")
            core.state_manager.save_state(state)

            loaded_state = core.state_manager.load_state()
            assert loaded_state is not None
            assert loaded_state.version == "1.0"


class TestClockworkCoreParse:
    """Test ClockworkCore parse method."""

    def test_parse_file_success(self):
        """Test successful parsing of a .cw file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            core = ClockworkCore(config_path=Path(temp_dir))

            # Create test .cw file
            cw_file = Path(temp_dir) / "test.cw"
            cw_file.write_text('''
            resource "service" "web" {
              name = "nginx"
              image = "nginx:latest"
            }
            ''')

            with patch.object(core.parser, 'parse_file') as mock_parse:
                mock_parse.return_value = "# Generated PyInfra code\nprint('test')"

                result = core.parse(cw_file)

                assert "Generated PyInfra code" in result
                mock_parse.assert_called_once_with(cw_file, ["localhost"])

    def test_parse_directory_success(self):
        """Test successful parsing of a directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            core = ClockworkCore(config_path=Path(temp_dir))

            with patch.object(core.parser, 'parse_directory') as mock_parse:
                mock_parse.return_value = "# Generated PyInfra code\nprint('test')"

                result = core.parse(Path(temp_dir))

                assert "Generated PyInfra code" in result
                mock_parse.assert_called_once_with(Path(temp_dir), ["localhost"])

    def test_parse_with_targets(self):
        """Test parsing with custom targets."""
        with tempfile.TemporaryDirectory() as temp_dir:
            core = ClockworkCore(config_path=Path(temp_dir))
            cw_file = Path(temp_dir) / "test.cw"
            cw_file.write_text("# test")

            targets = ["host1", "host2"]

            with patch.object(core.parser, 'parse_file') as mock_parse:
                mock_parse.return_value = "# Generated code"

                core.parse(cw_file, targets=targets)

                mock_parse.assert_called_once_with(cw_file, targets)

    def test_parse_with_variables(self):
        """Test parsing with variable overrides."""
        with tempfile.TemporaryDirectory() as temp_dir:
            core = ClockworkCore(config_path=Path(temp_dir))
            cw_file = Path(temp_dir) / "test.cw"
            cw_file.write_text("# test")

            variables = {"app_name": "test-app", "port": 8080}

            with patch.object(core.parser, 'parse_file') as mock_parse:
                mock_parse.return_value = "# Generated code"

                result = core.parse(cw_file, variables=variables)

                # Variables should be passed through (TODO: implement variable substitution)
                assert result == "# Generated code"

    def test_parse_pyinfra_parser_error(self):
        """Test error handling for PyInfra parser errors."""
        with tempfile.TemporaryDirectory() as temp_dir:
            core = ClockworkCore(config_path=Path(temp_dir))
            cw_file = Path(temp_dir) / "test.cw"
            cw_file.write_text("# test")

            with patch.object(core.parser, 'parse_file') as mock_parse:
                mock_parse.side_effect = PyInfraParserError("Parse failed")

                with pytest.raises(ClockworkError) as exc_info:
                    core.parse(cw_file)

                assert "Failed to parse .cw files" in str(exc_info.value)

    def test_parse_generic_error(self):
        """Test error handling for generic errors."""
        with tempfile.TemporaryDirectory() as temp_dir:
            core = ClockworkCore(config_path=Path(temp_dir))
            cw_file = Path(temp_dir) / "test.cw"
            cw_file.write_text("# test")

            with patch.object(core.parser, 'parse_file') as mock_parse:
                mock_parse.side_effect = RuntimeError("Unexpected error")

                with pytest.raises(ClockworkError) as exc_info:
                    core.parse(cw_file)

                assert "Failed to parse .cw files" in str(exc_info.value)


class TestClockworkCoreExecute:
    """Test ClockworkCore execute method."""

    def test_execute_success(self):
        """Test successful execution of pyinfra code."""
        with tempfile.TemporaryDirectory() as temp_dir:
            core = ClockworkCore(config_path=Path(temp_dir))

            python_code = "print('Hello, PyInfra!')"

            # Mock subprocess.run to simulate successful execution
            mock_result = Mock()
            mock_result.returncode = 0
            mock_result.stdout = "Hello, PyInfra!"
            mock_result.stderr = ""

            with patch('subprocess.run', return_value=mock_result) as mock_run:
                with patch.object(core, '_update_state_from_results') as mock_update:
                    results = core.execute(python_code)

                    assert len(results) == 1
                    assert results[0]["success"] is True
                    assert results[0]["exit_code"] == 0
                    assert results[0]["stdout"] == "Hello, PyInfra!"
                    assert results[0]["targets"] == ["localhost"]

                    # Check pyinfra command was called correctly
                    mock_run.assert_called_once()
                    args = mock_run.call_args[0][0]
                    assert args[0] == "pyinfra"
                    assert args[1] == "localhost"
                    assert args[3] == "--verbose"

    def test_execute_with_custom_targets(self):
        """Test execution with custom targets."""
        with tempfile.TemporaryDirectory() as temp_dir:
            core = ClockworkCore(config_path=Path(temp_dir))

            python_code = "print('test')"
            targets = ["host1", "host2"]

            mock_result = Mock()
            mock_result.returncode = 0
            mock_result.stdout = "success"
            mock_result.stderr = ""

            with patch('subprocess.run', return_value=mock_result) as mock_run:
                with patch.object(core, '_update_state_from_results'):
                    results = core.execute(python_code, targets=targets)

                    assert results[0]["targets"] == targets

                    # Check pyinfra was called with correct target string
                    args = mock_run.call_args[0][0]
                    assert args[1] == "host1,host2"

    def test_execute_failure(self):
        """Test execution failure handling."""
        with tempfile.TemporaryDirectory() as temp_dir:
            core = ClockworkCore(config_path=Path(temp_dir))

            python_code = "invalid_command()"

            # Mock subprocess.run to simulate failure
            mock_result = Mock()
            mock_result.returncode = 1
            mock_result.stdout = ""
            mock_result.stderr = "Error: command failed"

            with patch('subprocess.run', return_value=mock_result):
                with patch.object(core, '_update_state_from_results'):
                    results = core.execute(python_code)

                    assert len(results) == 1
                    assert results[0]["success"] is False
                    assert results[0]["exit_code"] == 1
                    assert results[0]["stderr"] == "Error: command failed"

    def test_execute_timeout(self):
        """Test execution timeout handling."""
        with tempfile.TemporaryDirectory() as temp_dir:
            core = ClockworkCore(config_path=Path(temp_dir))

            python_code = "time.sleep(1000)"

            with patch('subprocess.run') as mock_run:
                mock_run.side_effect = subprocess.TimeoutExpired("pyinfra", 5)

                with pytest.raises(ClockworkError) as exc_info:
                    core.execute(python_code, timeout_per_step=5)

                assert "timed out" in str(exc_info.value)

    def test_execute_process_error(self):
        """Test execution CalledProcessError handling."""
        with tempfile.TemporaryDirectory() as temp_dir:
            core = ClockworkCore(config_path=Path(temp_dir))

            python_code = "invalid_command()"

            with patch('subprocess.run') as mock_run:
                mock_run.side_effect = subprocess.CalledProcessError(1, "pyinfra")

                with pytest.raises(ClockworkError) as exc_info:
                    core.execute(python_code)

                assert "failed with exit code" in str(exc_info.value)


class TestClockworkCoreApply:
    """Test ClockworkCore apply method."""

    def test_apply_success(self):
        """Test successful apply workflow."""
        with tempfile.TemporaryDirectory() as temp_dir:
            core = ClockworkCore(config_path=Path(temp_dir))

            cw_file = Path(temp_dir) / "test.cw"
            cw_file.write_text("# test")

            with patch.object(core, 'parse') as mock_parse:
                with patch.object(core, 'execute') as mock_execute:
                    mock_parse.return_value = "# Generated code"
                    mock_execute.return_value = [{"success": True}]

                    results = core.apply(cw_file)

                    assert len(results) == 1
                    assert results[0]["success"] is True

                    mock_parse.assert_called_once_with(cw_file, None, ["localhost"])
                    mock_execute.assert_called_once_with("# Generated code", ["localhost"], 300)

    def test_apply_with_variables_and_targets(self):
        """Test apply with variables and targets."""
        with tempfile.TemporaryDirectory() as temp_dir:
            core = ClockworkCore(config_path=Path(temp_dir))

            cw_file = Path(temp_dir) / "test.cw"
            cw_file.write_text("# test")

            variables = {"app": "test"}
            targets = ["host1", "host2"]

            with patch.object(core, 'parse') as mock_parse:
                with patch.object(core, 'execute') as mock_execute:
                    mock_parse.return_value = "# Generated code"
                    mock_execute.return_value = [{"success": True}]

                    core.apply(cw_file, variables=variables, targets=targets, timeout_per_step=600)

                    mock_parse.assert_called_once_with(cw_file, variables, targets)
                    mock_execute.assert_called_once_with("# Generated code", targets, 600)


class TestClockworkCorePlan:
    """Test ClockworkCore plan method."""

    def test_plan_success(self):
        """Test successful plan generation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            core = ClockworkCore(config_path=Path(temp_dir))

            cw_file = Path(temp_dir) / "test.cw"
            cw_file.write_text("# test")

            with patch.object(core, 'parse') as mock_parse:
                mock_parse.return_value = "# Generated PyInfra code"

                result = core.plan(cw_file)

                assert result == "# Generated PyInfra code"
                mock_parse.assert_called_once_with(cw_file, None, ["localhost"])


class TestClockworkCoreStateManagement:
    """Test ClockworkCore state management."""

    def test_get_current_state_exists(self):
        """Test getting current state when it exists."""
        with tempfile.TemporaryDirectory() as temp_dir:
            core = ClockworkCore(config_path=Path(temp_dir))

            # Create and save a state
            state = ClockworkState(version="1.0")
            core.state_manager.save_state(state)

            current_state = core.get_current_state()
            assert current_state is not None
            assert current_state.version == "1.0"

    def test_get_current_state_not_exists(self):
        """Test getting current state when it doesn't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            core = ClockworkCore(config_path=Path(temp_dir))

            current_state = core.get_current_state()
            assert current_state is None

    def test_get_state_health_no_state(self):
        """Test getting state health when no state exists."""
        with tempfile.TemporaryDirectory() as temp_dir:
            core = ClockworkCore(config_path=Path(temp_dir))

            health = core.get_state_health()
            assert health["error"] == "No current state found"
            assert health["health_score"] == 0.0

    def test_get_state_health_empty_state(self):
        """Test getting state health for empty state."""
        with tempfile.TemporaryDirectory() as temp_dir:
            core = ClockworkCore(config_path=Path(temp_dir))

            state = ClockworkState(version="1.0")
            core.state_manager.save_state(state)

            health = core.get_state_health()
            assert health["health_score"] == 100.0
            assert health["total_resources"] == 0
            assert health["healthy_resources"] == 0

    def test_get_state_health_with_resources(self):
        """Test getting state health with resources."""
        with tempfile.TemporaryDirectory() as temp_dir:
            core = ClockworkCore(config_path=Path(temp_dir))

            # Create state with resources
            state = ClockworkState(
                version="1.0",
                current_resources={
                    "web": ResourceState(
                        resource_id="web",
                        type=ResourceType.SERVICE,
                        status=ExecutionStatus.SUCCESS
                    ),
                    "db": ResourceState(
                        resource_id="db",
                        type=ResourceType.SERVICE,
                        status=ExecutionStatus.FAILED
                    )
                }
            )
            core.state_manager.save_state(state)

            health = core.get_state_health()
            assert health["health_score"] == 50.0  # 1 success out of 2 total
            assert health["total_resources"] == 2
            assert health["healthy_resources"] == 1

    def test_update_state_from_results(self):
        """Test updating state from execution results."""
        with tempfile.TemporaryDirectory() as temp_dir:
            core = ClockworkCore(config_path=Path(temp_dir))

            python_code = "print('test')"
            results = [
                {"success": True, "stdout": "success", "stderr": ""},
                {"success": False, "stdout": "", "stderr": "error"}
            ]

            core._update_state_from_results(python_code, results)

            # Check state was updated
            state = core.get_current_state()
            assert state is not None
            assert len(state.current_resources) == 2
            assert len(state.execution_history) == 1

            # Check execution record
            execution = state.execution_history[0]
            assert execution.status == ExecutionStatus.FAILED  # Overall failed due to one failure
            assert len(execution.logs) == 2


class TestClockworkCoreUtilities:
    """Test ClockworkCore utility methods."""

    def test_cleanup(self):
        """Test cleanup method."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = ClockworkConfig(build_dir=str(Path(temp_dir) / "build"))
            core = ClockworkCore(config_path=Path(temp_dir), config=config)

            # Create build directory
            build_dir = Path(config.build_dir)
            build_dir.mkdir(parents=True, exist_ok=True)
            (build_dir / "test.txt").write_text("test")

            assert build_dir.exists()

            core.cleanup()

            assert not build_dir.exists()

    def test_context_manager(self):
        """Test using ClockworkCore as context manager."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = ClockworkConfig(build_dir=str(Path(temp_dir) / "build"))

            # Create build directory
            build_dir = Path(config.build_dir)
            build_dir.mkdir(parents=True, exist_ok=True)

            with ClockworkCore(config_path=Path(temp_dir), config=config) as core:
                assert core is not None
                assert build_dir.exists()

            # Build directory should be cleaned up
            assert not build_dir.exists()

    def test_verify_only(self):
        """Test verify_only method."""
        with tempfile.TemporaryDirectory() as temp_dir:
            core = ClockworkCore(config_path=Path(temp_dir))

            cw_file = Path(temp_dir) / "test.cw"
            cw_file.write_text("# test")

            with patch.object(core, 'parse') as mock_parse:
                with patch.object(core, 'execute') as mock_execute:
                    mock_parse.return_value = "# Generated code"
                    mock_execute.return_value = [{"success": True}]

                    results = core.verify_only(cw_file, targets=["localhost"], timeout=30)

                    assert len(results) == 1
                    assert results[0]["success"] is True

                    mock_execute.assert_called_once_with("# Generated code", ["localhost"], 30)


if __name__ == "__main__":
    pytest.main([__file__])