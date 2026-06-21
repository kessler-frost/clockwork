"""Tests for the clockwork show command."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from rich.console import Console
from typer.testing import CliRunner

from clockwork.cli import app
from clockwork.core import ClockworkCore
from clockwork.formatters import (
    _build_resource_tree,
    _filter_ai_fields,
    _format_value,
    format_resource_json,
    format_resource_tree,
)
from clockwork.resources import AppleContainerResource, BlankResource


@pytest.fixture
def sample_resource_data():
    """Sample resource data for testing formatters."""
    return {
        "name": "postgres",
        "type": "AppleContainerResource",
        "description": "PostgreSQL database",
        "ai_completed_fields": ["image", "ports"],
        "fields": {
            "image": {"value": "postgres:15-alpine", "ai_completed": True},
            "ports": {"value": ["5432:5432"], "ai_completed": True},
            "env_vars": {
                "value": {"POSTGRES_USER": "testuser"},
                "ai_completed": False,
            },
            "volumes": {"value": [], "ai_completed": False},
        },
        "children": [],
    }


@pytest.fixture
def sample_composite_data():
    """Sample composite resource data for testing."""
    return {
        "name": "webapp",
        "type": "BlankResource",
        "description": "Web application",
        "ai_completed_fields": [],
        "fields": {},
        "children": [
            {
                "name": "postgres",
                "type": "AppleContainerResource",
                "description": "Database",
                "ai_completed_fields": ["image", "ports"],
                "fields": {
                    "image": {
                        "value": "postgres:15-alpine",
                        "ai_completed": True,
                    },
                    "ports": {"value": ["5432:5432"], "ai_completed": True},
                },
                "children": [],
            },
            {
                "name": "redis",
                "type": "AppleContainerResource",
                "description": "Cache",
                "ai_completed_fields": ["image", "ports"],
                "fields": {
                    "image": {"value": "redis:7-alpine", "ai_completed": True},
                    "ports": {"value": ["6379:6379"], "ai_completed": True},
                },
                "children": [],
            },
        ],
    }


class TestFormatValue:
    """Tests for _format_value helper function."""

    def test_format_string(self):
        """Test formatting a string value."""
        assert _format_value("hello") == '"hello"'

    def test_format_long_string(self):
        """Test formatting a long string is truncated."""
        long_str = "a" * 100
        result = _format_value(long_str)
        assert result.endswith('..."')
        assert len(result) <= 85  # 80 chars + quotes + ellipsis

    def test_format_list(self):
        """Test formatting a list value."""
        assert _format_value(["a", "b"]) == '["a", "b"]'

    def test_format_empty_list(self):
        """Test formatting an empty list."""
        assert _format_value([]) == "[]"

    def test_format_dict(self):
        """Test formatting a dict value."""
        result = _format_value({"key": "value"})
        assert "key" in result
        assert "value" in result

    def test_format_empty_dict(self):
        """Test formatting an empty dict."""
        assert _format_value({}) == "{}"

    def test_format_bool(self):
        """Test formatting boolean values."""
        assert _format_value(True) == "true"
        assert _format_value(False) == "false"

    def test_format_number(self):
        """Test formatting numeric values."""
        assert _format_value(42) == "42"
        assert _format_value(3.14) == "3.14"


class TestBuildResourceTree:
    """Tests for _build_resource_tree function."""

    def test_basic_resource_tree(self, sample_resource_data):
        """Test building a tree for a basic resource."""
        tree = _build_resource_tree(sample_resource_data)

        # Tree should be created
        assert tree is not None
        # Tree label should contain resource name and type
        assert "postgres" in tree.label
        assert "AppleContainerResource" in tree.label

    def test_resource_with_ai_name(self):
        """Test resource with AI-completed name shows marker."""
        data = {
            "name": "ai-name",
            "type": "Resource",
            "ai_completed_fields": ["name"],
            "fields": {},
            "children": [],
        }
        tree = _build_resource_tree(data)

        # Tree label should include AI marker
        assert "[AI]" in tree.label

    def test_diff_only_mode(self, sample_resource_data):
        """Test diff_only mode only shows AI-completed fields."""
        tree = _build_resource_tree(sample_resource_data, diff_only=True)

        # Should have tree
        assert tree is not None

    def test_composite_resource_with_children(self, sample_composite_data):
        """Test building tree for composite resource."""
        tree = _build_resource_tree(sample_composite_data)

        # Should have children branch
        assert tree is not None
        # Should contain webapp name
        assert "webapp" in tree.label


class TestFilterAiFields:
    """Tests for _filter_ai_fields function."""

    def test_filter_resource_with_ai_fields(self, sample_resource_data):
        """Test filtering keeps only AI-completed fields."""
        result = _filter_ai_fields(sample_resource_data)

        assert result is not None
        assert result["name"] == "postgres"
        assert "image" in result["fields"]
        assert "ports" in result["fields"]
        # Non-AI fields should not be in filtered output
        assert "env_vars" not in result["fields"]
        assert "volumes" not in result["fields"]

    def test_filter_resource_without_ai_fields(self):
        """Test filtering returns None for resource without AI fields."""
        data = {
            "name": "manual",
            "type": "Resource",
            "ai_completed_fields": [],
            "fields": {
                "field1": {"value": "value1", "ai_completed": False},
            },
            "children": [],
        }
        result = _filter_ai_fields(data)

        # Should return None since no AI fields
        assert result is None

    def test_filter_composite_with_ai_children(self, sample_composite_data):
        """Test filtering composite resource keeps children with AI fields."""
        result = _filter_ai_fields(sample_composite_data)

        assert result is not None
        assert "children" in result
        assert len(result["children"]) == 2


class TestFormatResourceJson:
    """Tests for format_resource_json function."""

    def test_json_output(self, sample_resource_data):
        """Test JSON output is valid."""
        output = format_resource_json([sample_resource_data])

        # Should be valid JSON
        parsed = json.loads(output)
        assert isinstance(parsed, list)
        assert len(parsed) == 1
        assert parsed[0]["name"] == "postgres"

    def test_json_diff_only(self, sample_resource_data):
        """Test JSON output with diff_only flag."""
        output = format_resource_json([sample_resource_data], diff_only=True)

        parsed = json.loads(output)
        assert isinstance(parsed, list)
        # Should still have the resource (since it has AI fields)
        assert len(parsed) == 1


class TestFormatResourceTree:
    """Tests for format_resource_tree function."""

    def test_format_empty_resources(self):
        """Test formatting empty resource list."""
        console = Console(force_terminal=True, width=120)
        # Should not raise
        format_resource_tree([], console)

    def test_format_resources(self, sample_resource_data):
        """Test formatting resources."""
        console = Console(force_terminal=True, width=120)
        # Should not raise
        format_resource_tree([sample_resource_data], console)


class TestClockworkCoreShow:
    """Tests for ClockworkCore.show method."""

    @pytest.fixture
    def temp_main_file(self, temp_dir):
        """Create a temporary main.py file."""
        main_file = temp_dir / "main.py"
        main_file.write_text(
            """
from clockwork.resources import AppleContainerResource

db = AppleContainerResource(
    name="postgres",
    description="PostgreSQL database",
    image="postgres:15",
    ports=["5432:5432"],
)
"""
        )
        return main_file

    @pytest.mark.asyncio
    async def test_show_returns_resources(self, temp_main_file):
        """Test show method returns resource data."""
        with patch.object(
            ClockworkCore, "_complete_resources_safe"
        ) as mock_complete:
            # Create a mock completed resource
            completed_resource = AppleContainerResource(
                name="postgres",
                description="PostgreSQL database",
                image="postgres:15-alpine",
                ports=["5432:5432"],
            )
            completed_resource._ai_completed_fields = {"image"}
            mock_complete.return_value = [completed_resource]

            # Mock the API key requirement (test credentials)
            with patch("clockwork.core.get_settings") as mock_settings:
                mock_settings.return_value = MagicMock(
                    api_key="test-key",  # pragma: allowlist secret
                    model="test-model",
                    base_url="http://localhost",
                    cache_enabled=False,
                )

                core = ClockworkCore(
                    api_key="test-key"
                )  # pragma: allowlist secret
                result = await core.show(temp_main_file)

        assert "resources" in result
        assert "resource_count" in result
        assert "ai_completed_count" in result

    @pytest.mark.asyncio
    async def test_show_filters_by_name(self, temp_main_file):
        """Test show method filters by resource name."""
        with patch.object(
            ClockworkCore, "_complete_resources_safe"
        ) as mock_complete:
            # Create mock completed resources
            postgres = AppleContainerResource(
                name="postgres",
                description="PostgreSQL database",
                image="postgres:15-alpine",
                ports=["5432:5432"],
            )
            postgres._ai_completed_fields = {"image"}

            redis = AppleContainerResource(
                name="redis",
                description="Redis cache",
                image="redis:7-alpine",
                ports=["6379:6379"],
            )
            redis._ai_completed_fields = {"image"}

            mock_complete.return_value = [postgres, redis]

            with patch("clockwork.core.get_settings") as mock_settings:
                mock_settings.return_value = MagicMock(
                    api_key="test-key",  # pragma: allowlist secret
                    model="test-model",
                    base_url="http://localhost",
                    cache_enabled=False,
                )

                core = ClockworkCore(
                    api_key="test-key"
                )  # pragma: allowlist secret
                result = await core.show(
                    temp_main_file, resource_name="postgres"
                )

        # Should only return the postgres resource
        assert result["resource_count"] == 1
        assert result["resources"][0]["name"] == "postgres"


class TestFormatResourceForShow:
    """Tests for ClockworkCore._format_resource_for_show method."""

    def test_format_simple_resource(self):
        """Test formatting a simple resource."""
        with patch("clockwork.core.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                api_key="test-key",  # pragma: allowlist secret
                model="test-model",
                base_url="http://localhost",
                cache_enabled=False,
            )

            core = ClockworkCore(api_key="test-key")  # pragma: allowlist secret

            resource = AppleContainerResource(
                name="test",
                description="Test resource",
                image="nginx:alpine",
                ports=["80:80"],
            )
            resource._ai_completed_fields = {"image"}

            result = core._format_resource_for_show(resource)

        assert result["name"] == "test"
        assert result["type"] == "AppleContainerResource"
        assert "image" in result["ai_completed_fields"]
        assert result["fields"]["image"]["ai_completed"] is True

    def test_format_composite_resource(self):
        """Test formatting a composite resource with children."""
        with patch("clockwork.core.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                api_key="test-key",  # pragma: allowlist secret
                model="test-model",
                base_url="http://localhost",
                cache_enabled=False,
            )

            core = ClockworkCore(api_key="test-key")  # pragma: allowlist secret

            parent = BlankResource(name="parent", description="Parent")
            child = AppleContainerResource(
                name="child",
                description="Child",
                image="nginx:alpine",
                ports=["80:80"],
            )
            child._ai_completed_fields = {"image"}
            parent.add(child)

            result = core._format_resource_for_show(parent)

        assert result["name"] == "parent"
        assert len(result["children"]) == 1
        assert result["children"][0]["name"] == "child"


class TestShowCLI:
    """Tests for the show CLI command."""

    @pytest.fixture
    def runner(self):
        """Create a CLI test runner."""
        return CliRunner()

    def test_show_no_main_file(self, runner):
        """Test show command fails gracefully without main.py."""
        result = runner.invoke(app, ["show"])

        assert result.exit_code == 1
        assert "main.py" in result.output.lower()

    def test_show_with_json_flag(self, runner, temp_dir):
        """Test show command with --json flag."""
        main_file = temp_dir / "main.py"
        main_file.write_text(
            """
from clockwork.resources import AppleContainerResource

db = AppleContainerResource(
    name="postgres",
    image="postgres:15",
    ports=["5432:5432"],
)
"""
        )

        with patch("clockwork.cli._initialize_core") as mock_init:
            mock_core = MagicMock()
            mock_core.show = AsyncMock(
                return_value={
                    "resources": [
                        {
                            "name": "postgres",
                            "type": "AppleContainerResource",
                            "ai_completed_fields": [],
                            "fields": {},
                            "children": [],
                        }
                    ],
                    "resource_count": 1,
                    "ai_completed_count": 0,
                }
            )
            mock_init.return_value = mock_core

            with patch("clockwork.cli._get_main_file", return_value=main_file):
                result = runner.invoke(app, ["show", "--json"])

        # Should execute successfully and output JSON content
        assert result.exit_code == 0
        # The output should contain JSON array with resource name
        assert '"postgres"' in result.output or "postgres" in result.output

    def test_show_with_diff_flag(self, runner, temp_dir):
        """Test show command with --diff flag."""
        main_file = temp_dir / "main.py"
        main_file.write_text(
            """
from clockwork.resources import AppleContainerResource

db = AppleContainerResource(
    name="postgres",
    description="PostgreSQL database",
)
"""
        )

        with patch("clockwork.cli._initialize_core") as mock_init:
            mock_core = MagicMock()
            mock_core.show = AsyncMock(
                return_value={
                    "resources": [
                        {
                            "name": "postgres",
                            "type": "AppleContainerResource",
                            "ai_completed_fields": ["image", "ports"],
                            "fields": {
                                "image": {
                                    "value": "postgres:15-alpine",
                                    "ai_completed": True,
                                },
                                "ports": {
                                    "value": ["5432:5432"],
                                    "ai_completed": True,
                                },
                            },
                            "children": [],
                        }
                    ],
                    "resource_count": 1,
                    "ai_completed_count": 1,
                }
            )
            mock_init.return_value = mock_core

            with patch("clockwork.cli._get_main_file", return_value=main_file):
                result = runner.invoke(app, ["show", "--diff"])

        # Should execute without error
        # The diff mode should only show AI-completed fields
        assert result.exit_code == 0

    def test_show_specific_resource(self, runner, temp_dir):
        """Test show command with specific resource name."""
        main_file = temp_dir / "main.py"
        main_file.write_text(
            """
from clockwork.resources import AppleContainerResource

db = AppleContainerResource(name="postgres", image="postgres:15", ports=["5432:5432"])
cache = AppleContainerResource(name="redis", image="redis:7", ports=["6379:6379"])
"""
        )

        with patch("clockwork.cli._initialize_core") as mock_init:
            mock_core = MagicMock()
            mock_core.show = AsyncMock(
                return_value={
                    "resources": [
                        {
                            "name": "postgres",
                            "type": "AppleContainerResource",
                            "ai_completed_fields": [],
                            "fields": {},
                            "children": [],
                        }
                    ],
                    "resource_count": 1,
                    "ai_completed_count": 0,
                }
            )
            mock_init.return_value = mock_core

            with patch("clockwork.cli._get_main_file", return_value=main_file):
                result = runner.invoke(app, ["show", "postgres"])

        # Should execute and filter to only postgres
        assert result.exit_code == 0


class TestAiCompletedFieldsTracking:
    """Tests for AI-completed fields tracking in ResourceCompleter."""

    def test_merge_tracks_ai_fields(self):
        """Test that _merge_resources tracks AI-completed fields."""
        from clockwork.resource_completer import ResourceCompleter

        with patch(
            "clockwork.resource_completer.get_settings"
        ) as mock_settings:
            mock_settings.return_value = MagicMock(
                api_key="test-key",  # pragma: allowlist secret
                model="test-model",
                base_url="http://localhost",
                cache_enabled=False,
            )

            completer = ResourceCompleter(
                api_key="test-key"
            )  # pragma: allowlist secret

            # User resource with some fields None
            user_resource = AppleContainerResource(
                name="test",
                description="Test",
                image=None,
                ports=None,
            )

            # Completed resource with all fields
            completed_resource = AppleContainerResource(
                name="test",
                description="Test",
                image="nginx:alpine",
                ports=["80:80"],
            )

            merged = completer._merge_resources(
                user_resource, completed_resource
            )

        # Should have AI-completed fields tracked
        assert hasattr(merged, "_ai_completed_fields")
        assert "image" in merged._ai_completed_fields
        assert "ports" in merged._ai_completed_fields
        # name was provided by user, should not be in AI fields
        assert "name" not in merged._ai_completed_fields


class TestResourceBaseClass:
    """Tests for _ai_completed_fields attribute in Resource base class."""

    def test_resource_has_ai_completed_fields_attr(self):
        """Test that Resource has _ai_completed_fields attribute."""
        resource = AppleContainerResource(
            name="test",
            image="nginx",
            ports=["80:80"],
        )

        # Should have the attribute (empty by default)
        assert hasattr(resource, "_ai_completed_fields")
        assert isinstance(resource._ai_completed_fields, set)

    def test_ai_completed_fields_is_mutable(self):
        """Test that _ai_completed_fields can be modified."""
        resource = AppleContainerResource(
            name="test",
            image="nginx",
            ports=["80:80"],
        )

        resource._ai_completed_fields = {"image", "ports"}

        assert "image" in resource._ai_completed_fields
        assert "ports" in resource._ai_completed_fields
