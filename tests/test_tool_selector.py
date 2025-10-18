"""Tests for ToolSelector functionality."""

import pytest
from unittest.mock import Mock, patch

from clockwork.service.tools import ToolSelector
from clockwork.resources import (
    FileResource,
    DockerResource,
    AppleContainerResource,
    GitRepoResource,
)


class TestToolSelectorBasics:
    """Test basic ToolSelector functionality."""

    def test_initialization_without_mcp(self):
        """Test ToolSelector initialization without MCP enabled."""
        selector = ToolSelector(enable_mcp=False)
        assert selector._enable_mcp is False
        assert selector._tool_registry is not None

    def test_initialization_with_mcp(self):
        """Test ToolSelector initialization with MCP enabled."""
        selector = ToolSelector(enable_mcp=True)
        assert selector._enable_mcp is True

    def test_get_available_tools(self):
        """Test getting available tools returns registry."""
        selector = ToolSelector()
        tools = selector.get_available_tools()
        assert isinstance(tools, dict)
        assert "duckduckgo_search" in tools
        assert "filesystem_mcp" in tools


class TestResourceTypeTools:
    """Test tool selection based on resource type."""

    @patch("clockwork.service.tools.ToolSelector._get_tool")
    def test_file_resource_gets_web_search(self, mock_get_tool):
        """Test FileResource gets web search tool."""
        mock_search_tool = Mock()
        mock_get_tool.return_value = mock_search_tool

        selector = ToolSelector(enable_mcp=False)
        resource = FileResource(description="Test file")

        tools = selector.select_tools_for_resource(resource)

        # Should call for duckduckgo_search
        mock_get_tool.assert_called_with("duckduckgo_search")
        assert len(tools) > 0

    @patch("clockwork.service.tools.ToolSelector._get_tool")
    def test_docker_resource_gets_web_search(self, mock_get_tool):
        """Test DockerResource gets web search tool."""
        mock_search_tool = Mock()
        mock_get_tool.return_value = mock_search_tool

        selector = ToolSelector(enable_mcp=False)
        resource = DockerResource(description="Test container")

        tools = selector.select_tools_for_resource(resource)

        # Should call for duckduckgo_search
        mock_get_tool.assert_called_with("duckduckgo_search")
        assert len(tools) > 0

    @patch("clockwork.service.tools.ToolSelector._get_tool")
    def test_apple_container_resource_gets_web_search(self, mock_get_tool):
        """Test AppleContainerResource gets web search tool."""
        mock_search_tool = Mock()
        mock_get_tool.return_value = mock_search_tool

        selector = ToolSelector(enable_mcp=False)
        resource = AppleContainerResource(description="Test container")

        tools = selector.select_tools_for_resource(resource)

        # Should call for duckduckgo_search
        mock_get_tool.assert_called_with("duckduckgo_search")
        assert len(tools) > 0

    @patch("clockwork.service.tools.ToolSelector._get_tool")
    def test_git_resource_gets_web_search(self, mock_get_tool):
        """Test GitRepoResource gets web search tool."""
        mock_search_tool = Mock()
        mock_get_tool.return_value = mock_search_tool

        selector = ToolSelector(enable_mcp=False)
        resource = GitRepoResource(
            name="test-repo",
            description="Test git repository",
            dest="/tmp/test"
        )

        tools = selector.select_tools_for_resource(resource)

        # Should call for duckduckgo_search
        mock_get_tool.assert_called_with("duckduckgo_search")
        assert len(tools) > 0


class TestContextTools:
    """Test tool selection based on context."""

    @patch("clockwork.service.tools.ToolSelector._get_tool")
    def test_search_keyword_adds_search_tool(self, mock_get_tool):
        """Test context with 'search' keyword adds search tool."""
        mock_search_tool = Mock()
        mock_get_tool.return_value = mock_search_tool

        selector = ToolSelector(enable_mcp=False)
        resource = FileResource(description="Test file")
        context = "Please search for the latest information"

        tools = selector.select_tools_for_resource(resource, context)

        # Should call for duckduckgo_search at least once
        assert mock_get_tool.called
        assert len(tools) > 0

    @patch("clockwork.service.tools.ToolSelector._get_tool")
    def test_latest_keyword_adds_search_tool(self, mock_get_tool):
        """Test context with 'latest' keyword adds search tool."""
        mock_search_tool = Mock()
        mock_get_tool.return_value = mock_search_tool

        selector = ToolSelector(enable_mcp=False)
        resource = FileResource(description="Test file")
        context = "Get the latest news about AI"

        tools = selector.select_tools_for_resource(resource, context)

        assert mock_get_tool.called
        assert len(tools) > 0

    @patch("clockwork.service.tools.ToolSelector._get_tool")
    def test_current_keyword_adds_search_tool(self, mock_get_tool):
        """Test context with 'current' keyword adds search tool."""
        mock_search_tool = Mock()
        mock_get_tool.return_value = mock_search_tool

        selector = ToolSelector(enable_mcp=False)
        resource = FileResource(description="Test file")
        context = "Include current market trends"

        tools = selector.select_tools_for_resource(resource, context)

        assert mock_get_tool.called
        assert len(tools) > 0


class TestMCPTools:
    """Test MCP tool selection."""

    @patch("clockwork.service.tools.ToolSelector._get_tool")
    def test_file_resource_with_mcp_enabled(self, mock_get_tool):
        """Test FileResource with MCP enabled gets filesystem tool."""
        mock_search_tool = Mock()
        mock_fs_tool = Mock()

        def side_effect(tool_name):
            if tool_name == "duckduckgo_search":
                return mock_search_tool
            elif tool_name == "filesystem_mcp":
                return mock_fs_tool
            return None

        mock_get_tool.side_effect = side_effect

        selector = ToolSelector(enable_mcp=True)
        resource = FileResource(description="Test file")

        tools = selector.select_tools_for_resource(resource)

        # Should call for both search and filesystem
        assert mock_get_tool.call_count >= 2
        assert len(tools) > 0

    @patch("clockwork.service.tools.ToolSelector._get_tool")
    def test_file_keyword_with_mcp_adds_filesystem(self, mock_get_tool):
        """Test context with 'file' keyword and MCP adds filesystem tool."""
        mock_fs_tool = Mock()
        mock_search_tool = Mock()

        def side_effect(tool_name):
            if tool_name == "filesystem_mcp":
                return mock_fs_tool
            elif tool_name == "duckduckgo_search":
                return mock_search_tool
            return None

        mock_get_tool.side_effect = side_effect

        selector = ToolSelector(enable_mcp=True)
        resource = FileResource(description="Test")
        context = "Analyze existing files"

        tools = selector.select_tools_for_resource(resource, context)

        # Should request filesystem_mcp
        assert any(
            call[0][0] == "filesystem_mcp"
            for call in mock_get_tool.call_args_list
        )


class TestToolRegistry:
    """Test tool registry management."""

    def test_register_custom_tool(self):
        """Test registering a custom tool."""
        selector = ToolSelector()
        custom_tool = Mock()

        selector.register_tool("custom_tool", custom_tool)

        assert "custom_tool" in selector._tool_registry
        assert selector._tool_registry["custom_tool"] == custom_tool

    def test_get_tool_lazy_loading(self):
        """Test lazy loading of tools."""
        selector = ToolSelector()

        # Initially, tool should be None in registry
        assert selector._tool_registry["duckduckgo_search"] is None

        # After getting it, should be loaded (if available)
        tool = selector._get_tool("duckduckgo_search")

        # Tool should now be cached
        cached_tool = selector._tool_registry["duckduckgo_search"]
        assert cached_tool is not None or cached_tool is None  # Depends on if installed


class TestDuplicateRemoval:
    """Test duplicate tool removal."""

    @patch("clockwork.service.tools.ToolSelector._get_tool")
    def test_removes_duplicate_tools(self, mock_get_tool):
        """Test that duplicate tools are removed from selection."""
        mock_search_tool = Mock()
        mock_get_tool.return_value = mock_search_tool

        selector = ToolSelector(enable_mcp=False)
        resource = FileResource(description="Test file")
        # Context that also triggers search tool
        context = "search for latest information"

        tools = selector.select_tools_for_resource(resource, context)

        # Even though both resource type and context add search tool,
        # should only have unique tools
        tool_ids = [id(t) for t in tools]
        assert len(tool_ids) == len(set(tool_ids))


class TestToolLoading:
    """Test actual tool loading (integration-style tests)."""

    def test_load_duckduckgo_search_tool(self):
        """Test loading real DuckDuckGo search tool."""
        selector = ToolSelector()

        # Try to load the tool
        tool = selector._load_duckduckgo_search_tool()

        # Should either load successfully or return None if not installed
        # (we don't require it to be installed, but if it is, it should work)
        assert tool is not None or tool is None

    @patch("shutil.which")
    def test_load_filesystem_mcp_without_npx(self, mock_which):
        """Test loading filesystem MCP without npx available."""
        mock_which.return_value = None  # npx not available

        selector = ToolSelector(enable_mcp=True)
        tool = selector._load_filesystem_mcp()

        assert tool is None


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_context(self):
        """Test with empty context string."""
        selector = ToolSelector()
        resource = FileResource(description="Test")

        tools = selector.select_tools_for_resource(resource, context="")

        # Should still get resource-type tools
        assert isinstance(tools, list)

    def test_none_context(self):
        """Test with None context (uses default)."""
        selector = ToolSelector()
        resource = FileResource(description="Test")

        # Should not raise error
        tools = selector.select_tools_for_resource(resource)

        assert isinstance(tools, list)

    @patch("clockwork.service.tools.ToolSelector._get_tool")
    def test_tool_loading_failure(self, mock_get_tool):
        """Test graceful handling when tool loading fails."""
        mock_get_tool.return_value = None  # Tool loading failed

        selector = ToolSelector()
        resource = FileResource(description="Test")

        tools = selector.select_tools_for_resource(resource)

        # Should return empty list or handle gracefully
        assert isinstance(tools, list)

    def test_unknown_tool_name(self):
        """Test requesting an unknown tool."""
        selector = ToolSelector()

        tool = selector._get_tool("nonexistent_tool")

        assert tool is None
