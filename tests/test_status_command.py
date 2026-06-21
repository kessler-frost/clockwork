"""Tests for the status command and state checkers."""

import asyncio
import json
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from clockwork.state_checkers import (
    BlankStateChecker,
    ContainerStateChecker,
    FileStateChecker,
    GitRepoStateChecker,
    ResourceState,
    check_all_resources_state,
    check_resource_state,
    get_checker_for_resource,
)


@pytest.fixture(autouse=True)
def event_loop():
    """Create an event loop for each test."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop

    # Clean up pending tasks
    try:
        pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()
        if pending:
            loop.run_until_complete(
                asyncio.gather(*pending, return_exceptions=True)
            )
    except Exception:
        pass
    finally:
        loop.close()


class TestResourceState:
    """Tests for ResourceState dataclass."""

    def test_resource_state_creation(self):
        """Test basic ResourceState creation."""
        state = ResourceState(
            name="test",
            resource_type="TestResource",
            status="running",
            details={"port": "8080"},
        )

        assert state.name == "test"
        assert state.resource_type == "TestResource"
        assert state.status == "running"
        assert state.details == {"port": "8080"}
        assert state.error is None

    def test_resource_state_with_error(self):
        """Test ResourceState with error."""
        state = ResourceState(
            name="test",
            resource_type="TestResource",
            status="error",
            details={},
            error="Something went wrong",
        )

        assert state.status == "error"
        assert state.error == "Something went wrong"

    def test_resource_state_to_dict(self):
        """Test ResourceState.to_dict() method."""
        state = ResourceState(
            name="test",
            resource_type="TestResource",
            status="running",
            details={"port": "8080"},
        )

        result = state.to_dict()

        assert result == {
            "name": "test",
            "type": "TestResource",
            "status": "running",
            "details": {"port": "8080"},
        }

    def test_resource_state_to_dict_with_error(self):
        """Test ResourceState.to_dict() includes error when present."""
        state = ResourceState(
            name="test",
            resource_type="TestResource",
            status="error",
            details={},
            error="Connection failed",
        )

        result = state.to_dict()

        assert "error" in result
        assert result["error"] == "Connection failed"


class TestContainerStateChecker:
    """Tests for ContainerStateChecker."""

    def test_can_check_apple_container_resource(self):
        """Test that checker can handle AppleContainerResource."""
        checker = ContainerStateChecker()

        # Create mock resource
        mock_resource = MagicMock()
        mock_resource.__class__.__name__ = "AppleContainerResource"

        assert checker.can_check(mock_resource) is True

    def test_cannot_check_other_resources(self):
        """Test that checker rejects other resource types."""
        checker = ContainerStateChecker()

        mock_resource = MagicMock()
        mock_resource.__class__.__name__ = "FileResource"

        assert checker.can_check(mock_resource) is False

    @pytest.mark.asyncio
    async def test_check_container_running(self):
        """Test checking a running container."""
        checker = ContainerStateChecker()

        mock_resource = MagicMock()
        mock_resource.__class__.__name__ = "AppleContainerResource"
        mock_resource.name = "nginx"
        mock_resource.ports = ["8080:80"]

        # Mock container list output
        container_output = json.dumps(
            [
                {
                    "id": "abc123def456",  # pragma: allowlist secret
                    "status": "running",
                    "configuration": {
                        "image": "nginx:latest",
                        "labels": {"clockwork.name": "nginx"},
                    },
                }
            ]
        )

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout=container_output, stderr=""
            )

            state = await checker.check(mock_resource)

        assert state.status == "running"
        assert state.name == "nginx"
        assert "ports" in state.details

    @pytest.mark.asyncio
    async def test_check_container_missing(self):
        """Test checking a missing container."""
        checker = ContainerStateChecker()

        mock_resource = MagicMock()
        mock_resource.__class__.__name__ = "AppleContainerResource"
        mock_resource.name = "nonexistent"
        mock_resource.ports = []

        # Mock empty container list
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="[]", stderr=""
            )

            state = await checker.check(mock_resource)

        assert state.status == "missing"

    @pytest.mark.asyncio
    async def test_check_container_cli_not_found(self):
        """Test handling when container CLI is not found."""
        checker = ContainerStateChecker()

        mock_resource = MagicMock()
        mock_resource.__class__.__name__ = "AppleContainerResource"
        mock_resource.name = "test"

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("container not found")

            state = await checker.check(mock_resource)

        assert state.status == "error"
        assert "not found" in state.error

    @pytest.mark.asyncio
    async def test_check_container_timeout(self):
        """Test handling when container list times out."""
        checker = ContainerStateChecker()
        mock_resource = MagicMock()
        mock_resource.__class__.__name__ = "AppleContainerResource"
        mock_resource.name = "test"

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("container", 10)
            state = await checker.check(mock_resource)

        assert state.status == "error"
        assert "timed out" in state.error.lower()

    @pytest.mark.asyncio
    async def test_check_container_json_error(self):
        """Test handling when container list returns invalid JSON."""
        checker = ContainerStateChecker()
        mock_resource = MagicMock()
        mock_resource.__class__.__name__ = "AppleContainerResource"
        mock_resource.name = "test"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="not valid json {{{", stderr=""
            )
            state = await checker.check(mock_resource)

        assert state.status == "error"
        assert "parse" in state.error.lower() or "json" in state.error.lower()


class TestFileStateChecker:
    """Tests for FileStateChecker."""

    def test_can_check_file_resource(self):
        """Test that checker can handle FileResource."""
        checker = FileStateChecker()

        mock_resource = MagicMock()
        mock_resource.__class__.__name__ = "FileResource"

        assert checker.can_check(mock_resource) is True

    def test_cannot_check_other_resources(self):
        """Test that checker rejects other resource types."""
        checker = FileStateChecker()

        mock_resource = MagicMock()
        mock_resource.__class__.__name__ = "AppleContainerResource"

        assert checker.can_check(mock_resource) is False

    @pytest.mark.asyncio
    async def test_check_file_exists(self):
        """Test checking an existing file."""
        checker = FileStateChecker()

        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"test content")
            temp_path = f.name

        try:
            mock_resource = MagicMock()
            mock_resource.__class__.__name__ = "FileResource"
            mock_resource.name = "test.txt"
            mock_resource.path = temp_path
            mock_resource.directory = None

            state = await checker.check(mock_resource)

            assert state.status == "exists"
            assert state.details["path"] == temp_path
            assert "size" in state.details
            assert "modified" in state.details
            assert "mode" in state.details
        finally:
            Path(temp_path).unlink()

    @pytest.mark.asyncio
    async def test_check_file_missing(self):
        """Test checking a missing file."""
        checker = FileStateChecker()

        mock_resource = MagicMock()
        mock_resource.__class__.__name__ = "FileResource"
        mock_resource.name = "nonexistent.txt"
        mock_resource.path = "/nonexistent/path/to/file.txt"
        mock_resource.directory = None

        state = await checker.check(mock_resource)

        assert state.status == "missing"

    @pytest.mark.asyncio
    async def test_check_file_from_directory_and_name(self):
        """Test checking file with directory + name."""
        checker = FileStateChecker()

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a file
            file_path = Path(tmpdir) / "config.yaml"
            file_path.write_text("key: value")

            mock_resource = MagicMock()
            mock_resource.__class__.__name__ = "FileResource"
            mock_resource.name = "config.yaml"
            mock_resource.path = None
            mock_resource.directory = tmpdir

            state = await checker.check(mock_resource)

            assert state.status == "exists"

    def test_format_size(self):
        """Test file size formatting."""
        checker = FileStateChecker()

        assert checker._format_size(0) == "0B"
        assert checker._format_size(100) == "100B"
        assert checker._format_size(1024) == "1.0KB"
        assert checker._format_size(1024 * 1024) == "1.0MB"
        assert checker._format_size(1024 * 1024 * 1024) == "1.0GB"


class TestGitRepoStateChecker:
    """Tests for GitRepoStateChecker."""

    def test_can_check_git_repo_resource(self):
        """Test that checker can handle GitRepoResource."""
        checker = GitRepoStateChecker()

        mock_resource = MagicMock()
        mock_resource.__class__.__name__ = "GitRepoResource"

        assert checker.can_check(mock_resource) is True

    def test_cannot_check_other_resources(self):
        """Test that checker rejects other resource types."""
        checker = GitRepoStateChecker()

        mock_resource = MagicMock()
        mock_resource.__class__.__name__ = "FileResource"

        assert checker.can_check(mock_resource) is False

    @pytest.mark.asyncio
    async def test_check_repo_missing(self):
        """Test checking a missing repository."""
        checker = GitRepoStateChecker()

        mock_resource = MagicMock()
        mock_resource.__class__.__name__ = "GitRepoResource"
        mock_resource.name = "test-repo"
        mock_resource.dest = "/nonexistent/repo/path"

        state = await checker.check(mock_resource)

        assert state.status == "missing"

    @pytest.mark.asyncio
    async def test_check_repo_not_a_repo(self):
        """Test checking a directory that is not a git repo."""
        checker = GitRepoStateChecker()

        with tempfile.TemporaryDirectory() as tmpdir:
            mock_resource = MagicMock()
            mock_resource.__class__.__name__ = "GitRepoResource"
            mock_resource.name = "not-a-repo"
            mock_resource.dest = tmpdir

            state = await checker.check(mock_resource)

            assert state.status == "not_a_repo"

    @pytest.mark.asyncio
    async def test_check_repo_cloned(self):
        """Test checking a cloned repository."""
        checker = GitRepoStateChecker()

        with tempfile.TemporaryDirectory() as tmpdir:
            # Initialize a git repo with explicit main branch
            subprocess.run(
                ["git", "init", "-b", "main"],
                cwd=tmpdir,
                capture_output=True,
            )
            subprocess.run(
                ["git", "config", "user.email", "test@test.com"],
                cwd=tmpdir,
                capture_output=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Test"],
                cwd=tmpdir,
                capture_output=True,
            )

            # Create a file and commit
            (Path(tmpdir) / "test.txt").write_text("test")
            subprocess.run(["git", "add", "."], cwd=tmpdir, capture_output=True)
            result = subprocess.run(
                ["git", "commit", "-m", "Initial commit"],
                cwd=tmpdir,
                capture_output=True,
            )

            # Skip test if git commit failed (e.g., missing git config)
            if result.returncode != 0:
                pytest.skip("Git commit failed - skipping test")

            mock_resource = MagicMock()
            mock_resource.__class__.__name__ = "GitRepoResource"
            mock_resource.name = "test-repo"
            mock_resource.dest = tmpdir

            state = await checker.check(mock_resource)

            assert state.status == "cloned"
            assert "branch" in state.details
            assert "last_commit" in state.details
            assert "dirty" in state.details
            assert state.details["dirty"] is False

    @pytest.mark.asyncio
    async def test_check_git_repo_timeout(self):
        """Test handling when git command times out."""
        checker = GitRepoStateChecker()

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a .git directory to simulate a repo
            (Path(tmpdir) / ".git").mkdir()

            mock_resource = MagicMock()
            mock_resource.__class__.__name__ = "GitRepoResource"
            mock_resource.name = "test-repo"
            mock_resource.dest = tmpdir

            with patch("subprocess.run") as mock_run:
                mock_run.side_effect = subprocess.TimeoutExpired("git", 5)
                state = await checker.check(mock_resource)

        assert state.status == "error"
        assert "timed out" in state.error.lower()

    @pytest.mark.asyncio
    async def test_check_git_repo_not_found(self):
        """Test handling when git is not installed."""
        checker = GitRepoStateChecker()

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a .git directory to simulate a repo
            (Path(tmpdir) / ".git").mkdir()

            mock_resource = MagicMock()
            mock_resource.__class__.__name__ = "GitRepoResource"
            mock_resource.name = "test-repo"
            mock_resource.dest = tmpdir

            with patch("subprocess.run") as mock_run:
                mock_run.side_effect = FileNotFoundError("git not found")
                state = await checker.check(mock_resource)

        assert state.status == "error"
        assert "not found" in state.error.lower()


class TestBlankStateChecker:
    """Tests for BlankStateChecker."""

    def test_can_check_blank_resource(self):
        """Test that checker can handle BlankResource."""
        checker = BlankStateChecker()

        mock_resource = MagicMock()
        mock_resource.__class__.__name__ = "BlankResource"

        assert checker.can_check(mock_resource) is True

    @pytest.mark.asyncio
    async def test_check_blank_resource(self):
        """Test checking a BlankResource."""
        checker = BlankStateChecker()

        mock_resource = MagicMock()
        mock_resource.__class__.__name__ = "BlankResource"
        mock_resource.name = "app"
        mock_resource._children = [MagicMock(), MagicMock()]

        state = await checker.check(mock_resource)

        assert state.status == "composite"
        assert state.details["children"] == 2


class TestCheckerRegistry:
    """Tests for checker registry functions."""

    def test_get_checker_for_container(self):
        """Test getting checker for AppleContainerResource."""
        mock_resource = MagicMock()
        mock_resource.__class__.__name__ = "AppleContainerResource"

        checker = get_checker_for_resource(mock_resource)

        assert checker is not None
        assert isinstance(checker, ContainerStateChecker)

    def test_get_checker_for_file(self):
        """Test getting checker for FileResource."""
        mock_resource = MagicMock()
        mock_resource.__class__.__name__ = "FileResource"

        checker = get_checker_for_resource(mock_resource)

        assert checker is not None
        assert isinstance(checker, FileStateChecker)

    def test_get_checker_for_git(self):
        """Test getting checker for GitRepoResource."""
        mock_resource = MagicMock()
        mock_resource.__class__.__name__ = "GitRepoResource"

        checker = get_checker_for_resource(mock_resource)

        assert checker is not None
        assert isinstance(checker, GitRepoStateChecker)

    def test_get_checker_for_blank(self):
        """Test getting checker for BlankResource."""
        mock_resource = MagicMock()
        mock_resource.__class__.__name__ = "BlankResource"

        checker = get_checker_for_resource(mock_resource)

        assert checker is not None
        assert isinstance(checker, BlankStateChecker)

    def test_get_checker_for_unknown(self):
        """Test getting checker for unknown resource type."""
        mock_resource = MagicMock()
        mock_resource.__class__.__name__ = "UnknownResource"

        checker = get_checker_for_resource(mock_resource)

        assert checker is None


class TestCheckResourceState:
    """Tests for check_resource_state function."""

    @pytest.mark.asyncio
    async def test_check_resource_with_valid_checker(self):
        """Test checking resource with valid checker."""
        mock_resource = MagicMock()
        mock_resource.__class__.__name__ = "FileResource"
        mock_resource.name = "test.txt"
        mock_resource.path = "/nonexistent/path"
        mock_resource.directory = None

        state = await check_resource_state(mock_resource)

        assert state is not None
        assert state.name == "test.txt"
        assert state.status == "missing"

    @pytest.mark.asyncio
    async def test_check_resource_with_no_checker(self):
        """Test checking resource with no matching checker."""
        mock_resource = MagicMock()
        mock_resource.__class__.__name__ = "UnknownResource"
        mock_resource.name = "unknown"

        state = await check_resource_state(mock_resource)

        assert state.status == "unknown"
        assert state.error is not None
        assert "No state checker" in state.error


class TestCheckAllResourcesState:
    """Tests for check_all_resources_state function."""

    @pytest.mark.asyncio
    async def test_check_multiple_resources(self):
        """Test checking multiple resources."""
        # Create mock resources
        file_resource = MagicMock()
        file_resource.__class__.__name__ = "FileResource"
        file_resource.name = "config.yaml"
        file_resource.path = "/nonexistent/config.yaml"
        file_resource.directory = None

        blank_resource = MagicMock()
        blank_resource.__class__.__name__ = "BlankResource"
        blank_resource.name = "app"
        blank_resource._children = []

        resources = [file_resource, blank_resource]

        states = await check_all_resources_state(resources)

        assert len(states) == 2
        assert states[0].name == "config.yaml"
        assert states[1].name == "app"

    @pytest.mark.asyncio
    async def test_check_empty_resources(self):
        """Test checking empty resource list."""
        states = await check_all_resources_state([])

        assert states == []


class TestClockworkCoreStatus:
    """Tests for ClockworkCore.status() method."""

    @pytest.mark.asyncio
    async def test_status_loads_resources(self, temp_dir):
        """Test that status loads and checks resources."""
        # Create a simple main.py
        main_file = temp_dir / "main.py"
        main_file.write_text(
            """
from clockwork.resources import FileResource

config = FileResource(
    name="config.yaml",
    description="Config file",
    content="key: value",
    path="/tmp/config.yaml"
)
"""
        )

        from clockwork.core import ClockworkCore

        # Mock settings to provide API key
        mock_settings = MagicMock()
        mock_settings.api_key = "test-api-key"  # pragma: allowlist secret
        mock_settings.model = "test-model"
        mock_settings.base_url = "http://test"
        mock_settings.pulumi_config_passphrase = "test"
        mock_settings.log_level = "INFO"
        # Disable caching so no cache dir is created from a mock cache_dir.
        mock_settings.cache_enabled = False

        with (
            patch(
                "clockwork.resource_completer.get_settings",
                return_value=mock_settings,
            ),
            patch(
                "clockwork.connection_completer.get_settings",
                return_value=mock_settings,
            ),
            patch("clockwork.core.get_settings", return_value=mock_settings),
            patch(
                "clockwork.pulumi_compiler.get_settings",
                return_value=mock_settings,
            ),
        ):
            core = ClockworkCore()

            # Mock Pulumi state
            with patch.object(core, "_get_pulumi_state") as mock_pulumi:
                mock_pulumi.return_value = {
                    "available": False,
                    "error": "Stack not found",
                }

                result = await core.status(main_file)

        assert result["success"] is True
        assert "resources" in result
        assert len(result["resources"]) > 0

    @pytest.mark.asyncio
    async def test_status_handles_missing_pulumi_state(self, temp_dir):
        """Test status handles missing Pulumi state gracefully."""
        main_file = temp_dir / "main.py"
        main_file.write_text(
            """
from clockwork.resources import FileResource

config = FileResource(
    name="test.txt",
    content="test",
    path="/tmp/test.txt"
)
"""
        )

        from clockwork.core import ClockworkCore

        # Mock settings to provide API key
        mock_settings = MagicMock()
        mock_settings.api_key = "test-api-key"  # pragma: allowlist secret
        mock_settings.model = "test-model"
        mock_settings.base_url = "http://test"
        mock_settings.pulumi_config_passphrase = "test"
        mock_settings.log_level = "INFO"
        # Disable caching so no cache dir is created from a mock cache_dir.
        mock_settings.cache_enabled = False

        with (
            patch(
                "clockwork.resource_completer.get_settings",
                return_value=mock_settings,
            ),
            patch(
                "clockwork.connection_completer.get_settings",
                return_value=mock_settings,
            ),
            patch("clockwork.core.get_settings", return_value=mock_settings),
            patch(
                "clockwork.pulumi_compiler.get_settings",
                return_value=mock_settings,
            ),
        ):
            core = ClockworkCore()

            result = await core.status(main_file)

        # Should not fail even if Pulumi state is unavailable
        assert result["success"] is True
        assert result["pulumi_state"]["available"] is False
