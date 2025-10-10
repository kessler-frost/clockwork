"""
MCP Integration Example - Model Context Protocol Server Integration.

This example demonstrates how to use MCPTools with Clockwork resources.
"""

from clockwork.resources import FileResource, ArtifactSize
from clockwork.assertions import (
    FileExistsAssert,
    FileSizeAssert,
    FileContentMatchesAssert,
)
from pydantic_ai.mcp import MCPServerStdio

# Example 1: Filesystem MCP - AI can read and analyze local files
# The MCPServerStdio object will be connected when the agent runs
filesystem_mcp = MCPServerStdio(
    'npx',
    args=['-y', '@modelcontextprotocol/server-filesystem', '/Users/sankalp/dev/clockwork']
)

project_analysis = FileResource(
    name="project_analysis.md",
    description="Analyze the Clockwork project structure, read the main files, and provide insights about the architecture and design patterns used",
    size=ArtifactSize.LARGE,
    directory="scratch",
    tools=[filesystem_mcp],
    assertions=[
        FileExistsAssert(path="scratch/project_analysis.md"),
        FileSizeAssert(
            path="scratch/project_analysis.md",
            min_bytes=1000,
            max_bytes=100000
        ),
        FileContentMatchesAssert(
            path="scratch/project_analysis.md",
            pattern="Clockwork"
        ),
    ]
)

# Example 2: HTTP-based MCP server
# http_mcp = MCPTools(
#     url="https://api.example.com/mcp",
#     transport="streamable-http"
# )
#
# api_report = FileResource(
#     name="api_report.md",
#     description="Generate report from API data",
#     tools=[http_mcp],
# )

# Example 3: Combining multiple tools (DuckDuckGo + MCP)
# from pydantic_ai.common_tools.duckduckgo import duckduckgo_search_tool
#
# hybrid_analysis = FileResource(
#     name="hybrid_analysis.md",
#     description="Compare our codebase with industry best practices",
#     tools=[
#         duckduckgo_search_tool(),  # Web search
#         filesystem_mcp,             # Local file access (MCP)
#     ],
# )
