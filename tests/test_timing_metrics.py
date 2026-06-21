"""Tests for timing metrics in ClockworkCore and CLI display."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from clockwork.cli import _format_timings


class TestTimingDisplay:
    """Tests for CLI timing display helper."""

    def test_format_timings_all_fields(self):
        """Test formatting with all timing fields present."""
        result = {
            "timings": {
                "load": 0.234,
                "complete": 3.456,
                "deploy": 5.678,
                "total": 9.368,
            }
        }

        formatted = _format_timings(result)

        assert formatted is not None
        assert "Load: 0.2s" in formatted
        assert "Complete: 3.5s" in formatted
        assert "Deploy: 5.7s" in formatted
        assert "Total: 9.4s" in formatted
        assert " | " in formatted

    def test_format_timings_partial_fields(self):
        """Test formatting with only some timing fields."""
        result = {
            "timings": {
                "load": 0.1,
                "total": 0.1,
            }
        }

        formatted = _format_timings(result)

        assert formatted is not None
        assert "Load: 0.1s" in formatted
        assert "Total: 0.1s" in formatted
        assert "Complete" not in formatted
        assert "Deploy" not in formatted

    def test_format_timings_no_timings(self):
        """Test formatting with no timings key."""
        result = {"success": True}

        formatted = _format_timings(result)

        assert formatted is None

    def test_format_timings_empty_timings(self):
        """Test formatting with empty timings dict."""
        result = {"timings": {}}

        formatted = _format_timings(result)

        assert formatted is None

    def test_format_timings_rounds_correctly(self):
        """Test that timing values are rounded to 1 decimal place."""
        result = {
            "timings": {
                "load": 0.149,  # Should round to 0.1
                "complete": 0.151,  # Should round to 0.2
            }
        }

        formatted = _format_timings(result)

        assert "Load: 0.1s" in formatted
        assert "Complete: 0.2s" in formatted


class TestCoreTimingMetrics:
    """Tests for timing metrics in ClockworkCore."""

    @pytest.mark.asyncio
    async def test_apply_returns_timings(self, tmp_path):
        """Test that apply returns timing metrics in the result."""
        from clockwork.core import ClockworkCore

        # Create a simple main.py
        main_file = tmp_path / "main.py"
        main_file.write_text("""
from clockwork.resources import FileResource

test = FileResource(
    name="test.txt",
    content="content",
    directory=".",
    mode="644",
)
""")

        with patch("clockwork.core.ResourceCompleter") as mock_rc:
            mock_rc_instance = MagicMock()
            mock_rc_instance.complete = AsyncMock(return_value=[])
            mock_rc.return_value = mock_rc_instance

            with patch("clockwork.core.ConnectionCompleter") as mock_cc:
                mock_cc_instance = MagicMock()
                mock_cc_instance.complete = AsyncMock(return_value=[])
                mock_cc.return_value = mock_cc_instance

                with patch("clockwork.core.PulumiCompiler") as mock_compiler:
                    mock_compiler_instance = MagicMock()
                    mock_compiler_instance.apply = AsyncMock(
                        return_value={
                            "success": True,
                            "summary": {"result": "succeeded"},
                        }
                    )
                    mock_compiler.return_value = mock_compiler_instance

                    core = ClockworkCore(api_key="test-key")
                    result = await core.apply(main_file)

        # Verify timings are in result
        assert "timings" in result
        timings = result["timings"]

        # All timing keys should be present
        assert "load" in timings
        assert "complete" in timings
        assert "deploy" in timings
        assert "total" in timings

        # All values should be non-negative floats
        for key, value in timings.items():
            assert isinstance(value, float), f"{key} should be float"
            assert value >= 0, f"{key} should be non-negative"

        # Total should be >= sum of parts (approximately)
        parts_sum = timings["load"] + timings["complete"] + timings["deploy"]
        assert timings["total"] >= parts_sum * 0.99, (
            "Total should be >= sum of parts"
        )

    @pytest.mark.asyncio
    async def test_plan_returns_timings(self, tmp_path):
        """Test that plan returns timing metrics in the result."""
        from clockwork.core import ClockworkCore

        # Create a simple main.py
        main_file = tmp_path / "main.py"
        main_file.write_text("""
from clockwork.resources import FileResource

test = FileResource(
    name="test.txt",
    content="content",
    directory=".",
    mode="644",
)
""")

        with patch("clockwork.core.ResourceCompleter") as mock_rc:
            mock_rc_instance = MagicMock()
            mock_rc_instance.complete = AsyncMock(return_value=[])
            mock_rc.return_value = mock_rc_instance

            with patch("clockwork.core.ConnectionCompleter") as mock_cc:
                mock_cc_instance = MagicMock()
                mock_cc_instance.complete = AsyncMock(return_value=[])
                mock_cc.return_value = mock_cc_instance

                with patch("clockwork.core.PulumiCompiler") as mock_compiler:
                    mock_compiler_instance = MagicMock()
                    mock_compiler_instance.preview = AsyncMock(
                        return_value={"success": True}
                    )
                    mock_compiler.return_value = mock_compiler_instance

                    core = ClockworkCore(api_key="test-key")
                    result = await core.plan(main_file)

        # Verify timings are in result
        assert "timings" in result
        timings = result["timings"]

        # At least load and complete should be present
        assert "load" in timings
        assert "complete" in timings
        assert "deploy" in timings
        assert "total" in timings
