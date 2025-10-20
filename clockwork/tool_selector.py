"""Intelligent tool selection for ResourceCompleter.

This module provides the ToolSelector class which intelligently selects
PydanticAI tools and MCP servers based on resource type and completion context.
It enables AI-powered resource completion with access to external tools like
web search, filesystem access, and other integrations.
"""

import logging
import shutil
from typing import Any, ClassVar

logger = logging.getLogger(__name__)


class ToolSelector:
    """Intelligent tool selector for AI-powered resource completion.

    ToolSelector analyzes resources and their completion context to determine
    which tools (PydanticAI tools or MCP servers) should be available during
    AI completion. This enables the AI to access real-time information, interact
    with external systems, and make better completion decisions.

    Tool Types:
        - PydanticAI Common Tools: Universal tools (e.g., duckduckgo_search_tool)
        - MCP Servers: External services via Model Context Protocol

    Attributes:
        _tool_registry: Dict mapping tool names to tool instances
        _enable_mcp: Whether MCP server tools are enabled

    Example:
        >>> selector = ToolSelector()
        >>> tools = selector.select_tools_for_resource(
        ...     resource=FileResource(description="Latest AI news"),
        ...     context="Generate content about recent AI developments"
        ... )
        >>> # Returns: [duckduckgo_search_tool()]
    """

    # Tool registry - lazy loaded on first use
    _tool_registry: ClassVar[dict[str, Any | None]] = {
        "duckduckgo_search": None,  # Lazy load
        "filesystem_mcp": None,  # Lazy load
    }

    def __init__(self, enable_mcp: bool = False):
        """Initialize ToolSelector.

        Args:
            enable_mcp: Whether to enable MCP server tools. Default: False
                       Set to True to use filesystem, database, and other MCP servers
        """
        self._enable_mcp = enable_mcp
        logger.debug(f"ToolSelector initialized (MCP enabled: {enable_mcp})")

    def select_tools_for_resource(
        self, resource: Any, context: str = ""
    ) -> list[Any]:
        """Select appropriate tools for a resource based on type and context.

        Main entry point for tool selection. Combines resource-specific tools
        with context-aware tools to provide the AI with relevant capabilities.

        Args:
            resource: Resource object that needs completion
            context: Additional context string (e.g., error messages, user requirements)

        Returns:
            List of tool objects (PydanticAI tools or MCP servers) to pass to agent

        Example:
            >>> selector = ToolSelector()
            >>> file_resource = FileResource(description="Market analysis report")
            >>> tools = selector.select_tools_for_resource(
            ...     file_resource,
            ...     context="Include latest stock prices"
            ... )
            >>> # Returns: [duckduckgo_search_tool()] for web search
        """
        tools = []

        # 1. Get resource-specific tools
        resource_tools = self._get_resource_type_tools(resource)
        tools.extend(resource_tools)

        # 2. Get context-aware tools (based on keywords in context)
        context_tools = self._get_context_tools(context)
        tools.extend(context_tools)

        # 3. Remove duplicates (keep first occurrence)
        seen = set()
        unique_tools = []
        for tool in tools:
            tool_id = id(tool)
            if tool_id not in seen:
                seen.add(tool_id)
                unique_tools.append(tool)

        logger.debug(
            f"Selected {len(unique_tools)} tools for {resource.__class__.__name__}: "
            f"{[type(t).__name__ for t in unique_tools]}"
        )

        return unique_tools

    def _get_resource_type_tools(self, resource: Any) -> list[Any]:
        """Get tools specific to the resource type.

        Maps resource types to relevant tools:
        - FileResource: web search (for content generation)
        - DockerResource: web search (for image suggestions)
        - AppleContainerResource: web search (for image suggestions)
        - GitRepoResource: web search (for finding repos)
        - Default: web search (general purpose)

        Args:
            resource: Resource object to analyze

        Returns:
            List of tools appropriate for this resource type
        """
        resource_type = resource.__class__.__name__
        tools = []

        # FileResource benefits from web search
        if resource_type == "FileResource":
            # Always add web search for content generation
            search_tool = self._get_tool("duckduckgo_search")
            if search_tool:
                tools.append(search_tool)

            # Add filesystem MCP if enabled (useful for analyzing existing files)
            if self._enable_mcp:
                fs_mcp = self._get_tool("filesystem_mcp")
                if fs_mcp:
                    tools.append(fs_mcp)

        # Container resources benefit from web search for image suggestions
        elif (
            resource_type in ["DockerResource", "AppleContainerResource"]
            or resource_type == "GitRepoResource"
        ):
            search_tool = self._get_tool("duckduckgo_search")
            if search_tool:
                tools.append(search_tool)

        # Default: provide web search for general purpose completion
        else:
            search_tool = self._get_tool("duckduckgo_search")
            if search_tool:
                tools.append(search_tool)

        return tools

    def _get_context_tools(self, context: str) -> list[Any]:
        """Get tools based on context keywords.

        Analyzes the context string for keywords that suggest specific tool needs:
        - "failed", "error", "remediation": diagnostic tools (future)
        - "search", "research", "latest", "current": web search tools
        - "file", "content", "analyze": filesystem tools (if MCP enabled)

        Args:
            context: Context string to analyze for keywords

        Returns:
            List of tools relevant to the context
        """
        if not context:
            return []

        tools = []
        context_lower = context.lower()

        # Web search indicators
        search_keywords = [
            "search",
            "research",
            "latest",
            "current",
            "recent",
            "today",
        ]
        if any(keyword in context_lower for keyword in search_keywords):
            search_tool = self._get_tool("duckduckgo_search")
            if search_tool:
                tools.append(search_tool)

        # Filesystem indicators (only if MCP enabled)
        if self._enable_mcp:
            file_keywords = ["file", "content", "analyze", "read", "inspect"]
            if any(keyword in context_lower for keyword in file_keywords):
                fs_mcp = self._get_tool("filesystem_mcp")
                if fs_mcp:
                    tools.append(fs_mcp)

        return tools

    def _get_tool(self, tool_name: str) -> Any | None:
        """Get a tool from the registry, lazy loading if necessary.

        Implements lazy loading pattern - tools are only imported and initialized
        when first requested. This avoids import overhead for unused tools.

        Args:
            tool_name: Name of tool to retrieve (e.g., "duckduckgo_search")

        Returns:
            Tool instance, or None if tool is unavailable
        """
        # Check if tool is already loaded
        if (
            tool_name in self._tool_registry
            and self._tool_registry[tool_name] is not None
        ):
            return self._tool_registry[tool_name]

        # Lazy load the tool
        tool = None

        if tool_name == "duckduckgo_search":
            tool = self._load_duckduckgo_search_tool()
        elif tool_name == "filesystem_mcp":
            tool = self._load_filesystem_mcp()
        else:
            logger.warning(f"Unknown tool requested: {tool_name}")
            return None

        # Cache the loaded tool (even if None, to avoid repeated attempts)
        self._tool_registry[tool_name] = tool
        return tool

    def _load_duckduckgo_search_tool(self) -> Any | None:
        """Load DuckDuckGo search tool.

        Returns:
            DuckDuckGo search tool instance, or None if unavailable
        """
        try:
            from pydantic_ai.common_tools.duckduckgo import (
                duckduckgo_search_tool,
            )

            logger.debug("Loaded duckduckgo_search_tool")
            return duckduckgo_search_tool()
        except ImportError as e:
            logger.warning(f"Failed to load duckduckgo_search_tool: {e}")
            return None

    def _load_filesystem_mcp(self) -> Any | None:
        """Load filesystem MCP server.

        Requires:
        - npx (Node.js package runner) available in PATH
        - @modelcontextprotocol/server-filesystem npm package

        Returns:
            Filesystem MCP server instance, or None if unavailable
        """
        if not self._enable_mcp:
            return None

        # Check if npx is available
        if not shutil.which("npx"):
            logger.debug("npx not available, skipping filesystem MCP")
            return None

        try:
            # Note: This creates a filesystem MCP for the current working directory
            # In production, you'd want to make this configurable
            import os

            from pydantic_ai.mcp import MCPServerStdio

            cwd = os.getcwd()

            mcp = MCPServerStdio(
                "npx",
                args=["-y", "@modelcontextprotocol/server-filesystem", cwd],
            )
            logger.debug(f"Loaded filesystem MCP for directory: {cwd}")
            return mcp
        except ImportError as e:
            logger.warning(f"Failed to load filesystem MCP: {e}")
            return None

    def register_tool(self, name: str, tool: Any) -> None:
        """Register a custom tool in the tool registry.

        Allows users to register their own custom tools that can be selected
        by the ToolSelector. Useful for domain-specific tools or custom MCP servers.

        Args:
            name: Unique name for the tool
            tool: Tool instance (PydanticAI tool or MCP server)

        Example:
            >>> selector = ToolSelector()
            >>> custom_mcp = MCPServerStdio('docker', args=['run', '-i', 'my-tool'])
            >>> selector.register_tool("custom_docker_tool", custom_mcp)
        """
        self._tool_registry[name] = tool
        logger.debug(f"Registered custom tool: {name}")

    def get_available_tools(self) -> dict[str, Any]:
        """Get all available tools in the registry.

        Returns:
            Dict mapping tool names to tool instances (None if not loaded yet)

        Example:
            >>> selector = ToolSelector()
            >>> tools = selector.get_available_tools()
            >>> print(tools.keys())
            dict_keys(['duckduckgo_search', 'filesystem_mcp'])
        """
        return self._tool_registry.copy()
