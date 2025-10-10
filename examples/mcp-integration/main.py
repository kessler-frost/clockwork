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
    toolsets=[filesystem_mcp],
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

# Example 2: Combining multiple tools (DuckDuckGo + MCP)
from pydantic_ai.common_tools.duckduckgo import duckduckgo_search_tool

hybrid_analysis = FileResource(
    name="hybrid_analysis.md",
    description="Compare our Clockwork codebase architecture with industry best practices for Python infrastructure tools",
    size=ArtifactSize.LARGE,
    directory="scratch",
    tools=[duckduckgo_search_tool()],  # Web search
    toolsets=[filesystem_mcp],         # Local file access (MCP)
    assertions=[
        FileExistsAssert(path="scratch/hybrid_analysis.md"),
        FileSizeAssert(
            path="scratch/hybrid_analysis.md",
            min_bytes=1000,
            max_bytes=100000
        ),
    ]
)
