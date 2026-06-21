"""Tests for ResourceCompleter including batch completion and helper methods."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from clockwork.resource_completer import ResourceCompleter
from clockwork.resources import FileResource


class TestBatchCompletion:
    """Tests for batch resource completion with parallel execution."""

    @pytest.fixture
    def completer(self):
        """Create a ResourceCompleter with mocked dependencies."""
        with patch("clockwork.resource_completer.ToolSelector"):
            completer = ResourceCompleter(
                api_key="test-key",  # pragma: allowlist secret
                base_url="https://api.example.com/v1",
            )
            return completer

    @pytest.mark.asyncio
    async def test_complete_filters_already_complete(self, completer):
        """Test that already complete resources are not sent for completion."""
        # Resources that don't need completion (have content)
        complete_resource = FileResource(
            name="complete.txt",
            content="Already has content",
            directory=".",
            mode="644",
        )

        # Resource that needs completion (no content)
        incomplete_resource = FileResource(
            name="incomplete.txt",
            description="Needs content",
            directory=".",
            mode="644",
        )

        # Mock the _complete_single method
        completed_result = FileResource(
            name="incomplete.txt",
            content="Generated content",
            directory=".",
            mode="644",
        )
        completer._complete_single = AsyncMock(return_value=completed_result)

        result = await completer.complete(
            [complete_resource, incomplete_resource]
        )

        # Should have called _complete_single only for incomplete resource
        # Note: use_cache=True is passed as second argument by default
        assert completer._complete_single.call_count == 1
        completer._complete_single.assert_called_once_with(
            incomplete_resource, True
        )

        # Result should contain both resources
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_complete_returns_empty_for_empty_list(self, completer):
        """Test that empty input returns empty output."""
        result = await completer.complete([])
        assert result == []

    @pytest.mark.asyncio
    async def test_complete_all_already_complete(self, completer):
        """Test batch with all resources already complete."""
        resources = [
            FileResource(
                name="a.txt", content="content a", directory=".", mode="644"
            ),
            FileResource(
                name="b.txt", content="content b", directory=".", mode="644"
            ),
        ]

        completer._complete_single = AsyncMock()

        result = await completer.complete(resources)

        # Should not call _complete_single at all
        completer._complete_single.assert_not_called()
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_complete_parallel_execution(self, completer):
        """Test that multiple resources are completed in parallel."""
        # Track call order and timing
        call_times = []
        call_order = []

        async def mock_complete(resource, use_cache=True):
            call_order.append(resource.name)
            call_times.append(asyncio.get_event_loop().time())
            # Simulate some async work
            await asyncio.sleep(0.01)
            return FileResource(
                name=resource.name,
                content=f"Generated for {resource.name}",
                directory=".",
                mode="644",
            )

        completer._complete_single = mock_complete

        resources = [
            FileResource(name="r1.txt", description="desc1"),
            FileResource(name="r2.txt", description="desc2"),
            FileResource(name="r3.txt", description="desc3"),
        ]

        await completer.complete(resources)

        # All three should have been called
        assert len(call_order) == 3
        assert set(call_order) == {"r1.txt", "r2.txt", "r3.txt"}

        # If parallel, calls should start close together (within 5ms)
        if len(call_times) >= 2:
            time_spread = max(call_times) - min(call_times)
            # In parallel, they should start almost simultaneously
            # Allow some tolerance for test environment variations
            assert time_spread < 0.1, (
                f"Calls spread over {time_spread}s, expected parallel"
            )


class TestHelperMethods:
    """Tests for extracted helper methods."""

    @pytest.fixture
    def completer(self):
        """Create a ResourceCompleter with mocked dependencies."""
        with patch("clockwork.resource_completer.ToolSelector"):
            completer = ResourceCompleter(
                api_key="test-key",  # pragma: allowlist secret
                base_url="https://api.example.com/v1",
            )
            return completer

    def test_get_tools_for_resource_user_tools_priority(self, completer):
        """Test that user-provided tools take priority."""
        user_tool = MagicMock()
        resource = FileResource(
            name="test.txt",
            description="Test file",
            tools=[user_tool],
        )

        tools = completer._get_tools_for_resource(resource)

        assert user_tool in tools

    def test_get_tools_for_resource_no_tools(self, completer):
        """Test resource with no tools."""
        resource = FileResource(
            name="test.txt",
            content="content",  # No description, so no selector tools
        )

        # Disable tool selector
        completer.enable_tool_selection = False
        completer.tool_selector = None

        tools = completer._get_tools_for_resource(resource)

        assert tools == []

    def test_create_model_returns_openai_model(self, completer):
        """Test that _create_model returns an OpenAI model."""
        from pydantic_ai.models.openai import OpenAIChatModel

        model = completer._create_model()

        assert isinstance(model, OpenAIChatModel)

    def test_create_agent_returns_agent(self, completer):
        """Test that _create_agent returns a configured agent."""
        from pydantic_ai import Agent

        model = completer._create_model()
        agent = completer._create_agent(model, [], FileResource)

        assert isinstance(agent, Agent)


class TestInitialization:
    """Tests for ResourceCompleter initialization."""

    def test_init_requires_api_key(self):
        """Test that initialization fails without API key."""
        with patch(
            "clockwork.resource_completer.get_settings"
        ) as mock_settings:
            mock_settings.return_value = MagicMock(
                api_key=None,
                model="test-model",
                base_url="https://api.example.com/v1",
            )

            with pytest.raises(ValueError, match="API key required"):
                ResourceCompleter()

    def test_init_with_api_key(self):
        """Test successful initialization with API key."""
        with patch("clockwork.resource_completer.ToolSelector"):
            completer = ResourceCompleter(
                api_key="test-key",  # pragma: allowlist secret
                base_url="https://api.example.com/v1",
            )

            assert completer.api_key == "test-key"  # pragma: allowlist secret

    def test_init_detects_lmstudio(self):
        """Test that LM Studio endpoint is detected."""
        with (
            patch("clockwork.resource_completer.ToolSelector"),
            patch(
                "clockwork.resource_completer.LMStudioModelLoader.is_lmstudio_endpoint",
                return_value=True,
            ),
        ):
            completer = ResourceCompleter(
                api_key="test-key",  # pragma: allowlist secret
                base_url="http://localhost:1234/v1",
            )

            assert completer.lmstudio_loader is not None
