"""Edge-case hardening tests for clockwork.

Targets gaps that lacked explicit coverage:
1. Dependency cycle detection on direct ``.connect()`` graphs (non-composite).
2. Malformed / invalid resource loading (syntax error, import-time raise,
   unknown resource type, missing required fields) -> clear errors, no crash.
3. ``clockwork show`` / ``status`` CLI edge cases (no main.py, malformed
   main.py, empty result).
4. Completion timeout / model-load-failure handling leaves state untouched.
"""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from clockwork.cli import app
from clockwork.core import ClockworkCore
from clockwork.exceptions import CompletionTimeoutError
from clockwork.resource_completer import ResourceCompleter
from clockwork.resources import (
    AppleContainerResource,
    FileResource,
)


# =============================================================================
# 1. Dependency cycle detection on direct .connect() graphs
# =============================================================================
class TestDirectConnectCycleDetection:
    """Cycle detection on plain resource-to-resource connections."""

    def test_two_resource_cycle(self):
        """A -> B -> A is caught with a clear message."""
        a = AppleContainerResource(name="a", image="nginx:1.25")
        b = AppleContainerResource(name="b", image="redis:7")
        a.connect(b)
        b.connect(a)

        core = ClockworkCore(api_key="test", model="test")
        with pytest.raises(ValueError, match="Dependency cycle detected"):
            core._resolve_dependency_order([a, b])

    def test_three_resource_cycle(self):
        """A -> B -> C -> A is caught."""
        a = AppleContainerResource(name="a", image="nginx:1.25")
        b = AppleContainerResource(name="b", image="redis:7")
        c = AppleContainerResource(name="c", image="postgres:15")
        a.connect(b)
        b.connect(c)
        c.connect(a)

        core = ClockworkCore(api_key="test", model="test")
        with pytest.raises(ValueError, match="Dependency cycle detected"):
            core._resolve_dependency_order([a, b, c])

    def test_self_loop_cycle(self):
        """A resource that connects to itself is caught as a cycle."""
        a = AppleContainerResource(name="a", image="nginx:1.25")
        a.connect(a)

        core = ClockworkCore(api_key="test", model="test")
        with pytest.raises(ValueError, match="Dependency cycle detected"):
            core._resolve_dependency_order([a])

    def test_cycle_message_names_resources(self):
        """The error message lists the resources on the cycle path."""
        a = AppleContainerResource(name="alpha", image="nginx:1.25")
        b = AppleContainerResource(name="beta", image="redis:7")
        a.connect(b)
        b.connect(a)

        core = ClockworkCore(api_key="test", model="test")
        with pytest.raises(ValueError) as exc_info:
            core._resolve_dependency_order([a, b])

        message = str(exc_info.value)
        assert "alpha" in message
        assert "beta" in message
        assert "→" in message

    def test_linear_chain_has_no_cycle(self):
        """A -> B -> C (no back edge) resolves and deploys deps first."""
        a = AppleContainerResource(name="a", image="nginx:1.25")
        b = AppleContainerResource(name="b", image="redis:7")
        c = AppleContainerResource(name="c", image="postgres:15")
        a.connect(b)
        b.connect(c)

        core = ClockworkCore(api_key="test", model="test")
        ordered = core._resolve_dependency_order([a, b, c])

        # Use id() positions: resources have circular private refs, so == /
        # list.index() would recurse (the codebase itself keys on id()).
        order = [id(r) for r in ordered]
        assert len(order) == 3
        # Dependencies deploy before dependents: c before b before a.
        assert order.index(id(c)) < order.index(id(b)) < order.index(id(a))

    def test_diamond_dependency_is_not_a_cycle(self):
        """A -> B, A -> C, B -> D, C -> D (diamond) is acyclic."""
        a = AppleContainerResource(name="a", image="nginx:1.25")
        b = AppleContainerResource(name="b", image="redis:7")
        c = AppleContainerResource(name="c", image="memcached:1")
        d = AppleContainerResource(name="d", image="postgres:15")
        a.connect(b)
        a.connect(c)
        b.connect(d)
        c.connect(d)

        core = ClockworkCore(api_key="test", model="test")
        ordered = core._resolve_dependency_order([a, b, c, d])

        order = [id(r) for r in ordered]
        assert len(order) == 4
        # d is a dependency of both b and c, so it deploys first; a deploys last.
        assert order.index(id(d)) < order.index(id(b))
        assert order.index(id(d)) < order.index(id(c))
        assert order.index(id(a)) == 3


# =============================================================================
# 2. Malformed / invalid resource loading
# =============================================================================
class TestMalformedResourceLoading:
    """Loading bad main.py files must raise clear errors, not crash."""

    def _core(self):
        return ClockworkCore(
            api_key="test",  # pragma: allowlist secret
            model="test",
        )

    def test_syntax_error_in_main_raises_syntax_error(self, tmp_path):
        main_file = tmp_path / "main.py"
        main_file.write_text("this is not valid python ===\n")

        with pytest.raises(SyntaxError):
            self._core()._load_resources(main_file)

    def test_import_time_exception_propagates(self, tmp_path):
        """An exception raised while executing main.py surfaces cleanly."""
        main_file = tmp_path / "main.py"
        main_file.write_text("raise RuntimeError('boom at import time')\n")

        with pytest.raises(RuntimeError, match="boom at import time"):
            self._core()._load_resources(main_file)

    def test_unknown_resource_type_import_fails(self, tmp_path):
        """Referencing a non-existent resource class is an ImportError."""
        main_file = tmp_path / "main.py"
        main_file.write_text(
            "from clockwork.resources import NotARealResource\n"
            "x = NotARealResource(name='x')\n"
        )

        with pytest.raises(ImportError):
            self._core()._load_resources(main_file)

    def test_missing_required_field_raises_clear_error_on_compile(self):
        """A fully-specified FileResource still missing a name fails its own
        path resolution with a clear ValueError (not an opaque crash)."""
        f = FileResource(content="hello world")  # no name, no path

        with pytest.raises(ValueError, match="name must be set"):
            f.to_pulumi()

    def test_empty_main_raises_no_resources(self, tmp_path):
        main_file = tmp_path / "main.py"
        main_file.write_text("x = 1\ny = 2\n")

        with pytest.raises(ValueError, match="No resources found"):
            self._core()._load_resources(main_file)

    def test_missing_file_raises_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            self._core()._load_resources(Path("/nonexistent/does/not/main.py"))


# =============================================================================
# 3. clockwork show / status CLI edge cases
# =============================================================================
class TestShowStatusCliEdgeCases:
    """CLI-level edge cases for show and status."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    def test_status_no_main_file(self, runner, tmp_path, monkeypatch):
        """status without main.py exits 1 and mentions main.py."""
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["status"])

        assert result.exit_code == 1
        assert "main.py" in result.output.lower()

    def test_show_malformed_main_reports_cleanly(self, runner, tmp_path):
        """A main.py that raises at import is reported, not a raw traceback."""
        main_file = tmp_path / "main.py"
        main_file.write_text("raise RuntimeError('explode')\n")

        # Pass --api-key so init succeeds and the load error is what surfaces.
        with patch("clockwork.cli._get_main_file", return_value=main_file):
            result = runner.invoke(app, ["show", "--api-key", "test-key"])

        assert result.exit_code == 1
        assert "show failed" in result.output.lower()
        assert "explode" in result.output

    def test_status_malformed_main_reports_cleanly(self, runner, tmp_path):
        # status has no --api-key flag; supply a settings object with a key so
        # init succeeds and the load error from main.py is what surfaces.
        settings = MagicMock()
        settings.api_key = "test-key"  # pragma: allowlist secret
        settings.model = "test-model"
        settings.base_url = "https://example.test/v1"
        settings.pulumi_config_passphrase = "test"
        settings.log_level = "INFO"
        # Keep caching off so no cache dir is created from a mock cache_dir.
        settings.cache_enabled = False
        settings.enable_tool_selection = False

        main_file = tmp_path / "main.py"
        main_file.write_text("raise RuntimeError('explode-status')\n")

        with (
            patch("clockwork.cli._get_main_file", return_value=main_file),
            patch("clockwork.core.get_settings", return_value=settings),
            patch(
                "clockwork.resource_completer.get_settings",
                return_value=settings,
            ),
            patch(
                "clockwork.connection_completer.get_settings",
                return_value=settings,
            ),
            patch(
                "clockwork.pulumi_compiler.get_settings",
                return_value=settings,
            ),
        ):
            result = runner.invoke(app, ["status"])

        assert result.exit_code == 1
        assert "status failed" in result.output.lower()
        assert "explode-status" in result.output

    def test_show_empty_result_message(self, runner, tmp_path):
        """show with zero resources prints a friendly empty message."""
        main_file = tmp_path / "main.py"
        main_file.write_text("# nothing here\n")

        with (
            patch("clockwork.cli._get_main_file", return_value=main_file),
            patch("clockwork.cli._initialize_core") as mock_init,
        ):
            mock_core = MagicMock()
            mock_core.show = AsyncMock(
                return_value={
                    "resources": [],
                    "resource_count": 0,
                    "ai_completed_count": 0,
                }
            )
            mock_init.return_value = mock_core
            result = runner.invoke(app, ["show"])

        assert result.exit_code == 0
        assert "no resources found" in result.output.lower()

    def test_show_named_resource_not_found(self, runner, tmp_path):
        """show <name> for an absent resource reports it clearly."""
        main_file = tmp_path / "main.py"
        main_file.write_text("# nothing here\n")

        with (
            patch("clockwork.cli._get_main_file", return_value=main_file),
            patch("clockwork.cli._initialize_core") as mock_init,
        ):
            mock_core = MagicMock()
            mock_core.show = AsyncMock(
                return_value={
                    "resources": [],
                    "resource_count": 0,
                    "ai_completed_count": 0,
                }
            )
            mock_init.return_value = mock_core
            result = runner.invoke(app, ["show", "ghost"])

        assert result.exit_code == 0
        assert "ghost" in result.output

    def test_status_empty_result_message(self, runner, tmp_path):
        main_file = tmp_path / "main.py"
        main_file.write_text("# nothing here\n")

        with (
            patch("clockwork.cli._get_main_file", return_value=main_file),
            patch("clockwork.cli._initialize_core") as mock_init,
        ):
            mock_core = MagicMock()
            mock_core.status = AsyncMock(
                return_value={
                    "success": True,
                    "resources": [],
                    "pulumi_state": {
                        "available": False,
                        "error": "Stack not found",
                    },
                }
            )
            mock_init.return_value = mock_core
            result = runner.invoke(app, ["status"])

        assert result.exit_code == 0
        assert "no resources found" in result.output.lower()


# =============================================================================
# 4. Completion timeout / model-load-failure keeps state clean
# =============================================================================
class TestCompletionFailureStateCleanliness:
    """Failures during completion must not mutate the input resources."""

    def _completer(self):
        mock_settings = MagicMock()
        mock_settings.api_key = "test-key"  # pragma: allowlist secret
        mock_settings.model = "test-model"
        mock_settings.base_url = "https://example.test/v1"
        mock_settings.completion_timeout = 1
        mock_settings.completion_max_retries = 1
        mock_settings.cache_enabled = False
        mock_settings.enable_tool_selection = False
        with patch(
            "clockwork.resource_completer.get_settings",
            return_value=mock_settings,
        ):
            return ResourceCompleter(
                api_key="test-key",  # pragma: allowlist secret
                model="test-model",
                base_url="https://example.test/v1",
                enable_tool_selection=False,
            )

    @pytest.mark.asyncio
    async def test_timeout_raises_and_leaves_resource_untouched(self):
        """A timed-out completion raises CompletionTimeoutError; the input
        resource keeps its original (incomplete) field values."""
        completer = self._completer()
        resource = AppleContainerResource(description="a web server")
        # Snapshot the unfilled fields before completion.
        assert resource.image is None
        before = resource.model_dump()

        async def _never_returns(*_args, **_kwargs):
            await asyncio.sleep(10)

        with (
            patch.object(completer, "_ensure_model_loaded", AsyncMock()),
            patch("clockwork.resource_completer.Agent") as mock_agent_cls,
        ):
            mock_agent = MagicMock()
            mock_agent.run = _never_returns
            mock_agent_cls.return_value = mock_agent
            completer.timeout = 0.05

            with pytest.raises(CompletionTimeoutError):
                await completer._run_completion(resource, "complete me")

        # The original resource must be unchanged after the failure.
        assert resource.image is None
        assert resource.model_dump() == before

    @pytest.mark.asyncio
    async def test_model_load_failure_wraps_error_cleanly(self):
        """If model loading fails, completion raises a CompletionError-derived
        error and the input resource is untouched."""
        from clockwork.exceptions import CompletionError

        completer = self._completer()
        resource = AppleContainerResource(description="a web server")
        before = resource.model_dump()

        async def _fail_load(*_args, **_kwargs):
            raise ConnectionError("Cannot connect to LM Studio")

        with (
            patch.object(
                completer, "_ensure_model_loaded", side_effect=_fail_load
            ),
            pytest.raises(CompletionError),
        ):
            await completer._run_completion(resource, "complete me")

        assert resource.image is None
        assert resource.model_dump() == before

    @pytest.mark.asyncio
    async def test_batch_completion_failure_does_not_partially_mutate(self):
        """When one resource in a batch fails, complete() raises and the
        already-complete resources are not deployed/mutated in place."""
        completer = self._completer()

        complete_resource = FileResource(
            name="ok.txt", content="hello", path="/tmp/ok.txt"
        )
        partial_resource = AppleContainerResource(description="needs ai")
        partial_before = partial_resource.model_dump()

        async def _boom(*_args, **_kwargs):
            raise CompletionTimeoutError(
                "timed out", resource_name="needs ai", timeout_seconds=1
            )

        with (
            patch.object(completer, "_complete_single", side_effect=_boom),
            pytest.raises(CompletionTimeoutError),
        ):
            await completer.complete(
                [complete_resource, partial_resource], use_cache=False
            )

        # Inputs are unchanged after the failed batch.
        assert partial_resource.model_dump() == partial_before
        assert complete_resource.content == "hello"
