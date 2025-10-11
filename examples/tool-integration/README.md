# Tool Integration Example

This example demonstrates intelligent infrastructure orchestration with **PydanticAI common tools**, enabling AI to access real-time information during resource completion.

## What This Example Shows

1. **Web Search** - AI can search the web for current information
2. **No Setup Required** - Uses built-in DuckDuckGo search (no external servers needed)
3. **Real-Time Data** - AI generates content based on latest information from the internet
4. **Simple Integration** - Just add `tools=[duckduckgo_search_tool()]` to resources

## Prerequisites

Set your API key in `.env`:

```bash
CW_API_KEY=your-api-key-here
```

No additional setup required - DuckDuckGo search works out of the box!

## Running the Example

```bash
cd examples/tool-integration
uv run clockwork apply
```

This will generate:
- `tech_trends_2025.md` - Latest AI/DevOps trends researched from the web
- `python_infra_best_practices.md` - Best practices researched from online sources

## Validation

Run assertions to validate the generated files:

```bash
uv run clockwork assert
```

## Clean Up

Remove the generated files:

```bash
uv run clockwork destroy
```

## How It Works

Resources with tools can access external data sources during AI completion:

```python
from pydantic_ai.common_tools.duckduckgo import duckduckgo_search_tool

tech_report = FileResource(
    name="tech_trends.md",
    description="Write about the latest AI infrastructure trends in 2025",
    tools=[duckduckgo_search_tool()],  # Enable web search
)
```

The AI will automatically search the web for relevant information before generating content!

## Available PydanticAI Common Tools

### Built-in Tools

**DuckDuckGo Search** (already included in Clockwork):
```python
from pydantic_ai.common_tools.duckduckgo import duckduckgo_search_tool

tools=[duckduckgo_search_tool()]
```

**Tavily Search** (requires API key):
```python
from pydantic_ai.common_tools.tavily import tavily_search_tool

tools=[tavily_search_tool()]
```

## Advanced: MCP Servers (Optional)

For more advanced use cases, you can also use MCP (Model Context Protocol) servers to access databases, filesystems, and custom services. See CLAUDE.md for MCP integration examples.

### Example MCP Servers

**Filesystem access:**
```python
from pydantic_ai.mcp import MCPServerStdio

filesystem_mcp = MCPServerStdio(
    'npx',
    args=['-y', '@modelcontextprotocol/server-filesystem', '/path/to/project']
)

resource = FileResource(
    name="analysis.md",
    description="Analyze the project files",
    toolsets=[filesystem_mcp],  # MCP servers go in 'toolsets'
)
```

**PostgreSQL database:**
```python
postgres_mcp = MCPServerStdio(
    'npx',
    args=['-y', '@modelcontextprotocol/server-postgres', 'postgresql://user:pass@host/db']
)

toolsets=[postgres_mcp]
```

**Note:** MCP servers require additional npm packages to be installed:
```bash
npm install -g @modelcontextprotocol/server-filesystem
npm install -g @modelcontextprotocol/server-postgres
```

## Combining Tools

You can combine PydanticAI tools with MCP servers:

```python
from pydantic_ai.common_tools.duckduckgo import duckduckgo_search_tool
from pydantic_ai.mcp import MCPServerStdio

filesystem_mcp = MCPServerStdio(
    'npx',
    args=['-y', '@modelcontextprotocol/server-filesystem', '/path']
)

resource = FileResource(
    name="hybrid.md",
    description="Compare our code with online best practices",
    tools=[duckduckgo_search_tool()],  # PydanticAI tools in 'tools'
    toolsets=[filesystem_mcp],         # MCP servers in 'toolsets'
)
```

**Important Parameter Separation:**
- `tools=` - For PydanticAI common tools (e.g., `duckduckgo_search_tool()`)
- `toolsets=` - For MCP servers (e.g., `MCPServerStdio` instances)

## Troubleshooting

**No search results:**
- Check your internet connection
- DuckDuckGo search is free and has no API key requirements

**Empty content generated:**
- Verify your API key is set correctly in `.env`
- Try with a more specific description
- Check that the AI model supports tool calling (most modern models do)

## Key Insights

- **Real-Time Information**: AI accesses current web data during content generation
- **Zero Setup**: DuckDuckGo search works without configuration
- **Composable**: Combine multiple tools for richer context
- **Type Safety**: Clockwork validates tool configurations
