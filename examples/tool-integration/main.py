"""
Tool Integration Example - PydanticAI Tools with Clockwork.

This example demonstrates the tool integration pattern in Clockwork.
For actual tool usage, uncomment the tools parameter and provide an API key.

Note: This example uses pre-written content to avoid AI completion timeouts.
To enable real web search, uncomment the tools=[duckduckgo_search_tool()] line.
"""

from clockwork.resources import FileResource
from clockwork.assertions import (
    FileExistsAssert,
    FileContentMatchesAssert,
)
# Uncomment to enable web search:
# from pydantic_ai.common_tools.duckduckgo import duckduckgo_search_tool

# Example showing how tools would be used (currently uses static content)
# To enable AI-powered web search, uncomment the tools parameter below
tech_guide = FileResource(
    name="tools_guide.md",
    description="Guide explaining how to use tools with Clockwork",
    directory="scratch",
    # tools=[duckduckgo_search_tool()],  # Uncomment to enable web search
    content="""# Tool Integration with Clockwork

## Overview

Clockwork supports PydanticAI common tools and MCP servers to extend AI capabilities
during resource completion. Tools enable AI to access real-time information beyond
its training data.

## Available Tools

### PydanticAI Common Tools

**DuckDuckGo Search** - Built-in web search (no API key required):
```python
from pydantic_ai.common_tools.duckduckgo import duckduckgo_search_tool

resource = FileResource(
    name="report.md",
    description="Research latest trends",
    tools=[duckduckgo_search_tool()],
)
```

**Tavily Search** - Alternative search (requires API key):
```python
from pydantic_ai.common_tools.tavily import tavily_search_tool

tools=[tavily_search_tool()]
```

### MCP Servers (Advanced)

**Filesystem Access**:
```python
from pydantic_ai.mcp import MCPServerStdio

filesystem_mcp = MCPServerStdio(
    'npx',
    args=['-y', '@modelcontextprotocol/server-filesystem', '/path']
)

toolsets=[filesystem_mcp]
```

## Usage Notes

- Tools add latency (multiple LLM round-trips)
- Local models (LM Studio, Ollama) may timeout with tools
- Cloud models (OpenRouter, OpenAI) recommended for tool usage
- Separate parameters: `tools=` for PydanticAI tools, `toolsets=` for MCP

Generated with Clockwork
""",
    mode="644",
    assertions=[
        FileExistsAssert(path="scratch/tools_guide.md"),
        FileContentMatchesAssert(
            path="scratch/tools_guide.md",
            pattern="Tool Integration"
        ),
    ]
)
