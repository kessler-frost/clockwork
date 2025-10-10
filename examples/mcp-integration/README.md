# MCP Integration Example

This example demonstrates how to use **MCP (Model Context Protocol) servers** with Clockwork for AI-powered artifact generation with access to external systems.

## What This Example Shows

1. **Filesystem Access** - AI can read and analyze local files/directories
2. **Multiple MCP Servers** - Combine multiple data sources
3. **Hybrid Approach** - Use both PydanticAI common tools AND MCP servers
4. **Various MCP Types** - stdio-based servers (HTTP not currently supported)

## Prerequisites

Install the filesystem MCP server (most common):

```bash
npm install -g @modelcontextprotocol/server-filesystem
```

Set your OpenRouter API key in `.env`:

```bash
CW_OPENROUTER_API_KEY=your-api-key-here
```

## Important: Update File Paths

Before running, update the file path in `main.py` to point to your actual project directory:

```python
filesystem_mcp = MCPServerStdio(
    'npx',
    args=['-y', '@modelcontextprotocol/server-filesystem', '/Users/sankalp/dev/clockwork']
    #                                                       ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    #                                                       Update this path!
)
```

## Running the Example

```bash
cd examples/mcp-integration
uv run clockwork apply
```

This will generate:
- `project_analysis.md` - Analysis of your project files using filesystem MCP

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

Resources with MCP servers in `toolsets=` can connect to external data sources:

```python
from pydantic_ai.mcp import MCPServerStdio

# Initialize the MCP server connection
filesystem_mcp = MCPServerStdio(
    'npx',
    args=['-y', '@modelcontextprotocol/server-filesystem', '/path/to/project']
)

project_analysis = FileResource(
    name="analysis.md",
    description="Analyze the project files",
    toolsets=[filesystem_mcp],  # MCP servers go in toolsets parameter
)
```

**Note:** PydanticAI common tools (like DuckDuckGo) go in `tools=`, while MCP servers go in `toolsets=`.

The AI will automatically use the MCP server to read files, query databases, etc.!

## Available MCP Servers

### Official MCP Servers (via npm)

```bash
# Filesystem access
npm install -g @modelcontextprotocol/server-filesystem

# PostgreSQL database
npm install -g @modelcontextprotocol/server-postgres

# SQLite database
npm install -g @modelcontextprotocol/server-sqlite

# GitHub integration
npm install -g @modelcontextprotocol/server-github

# Google Drive
npm install -g @modelcontextprotocol/server-gdrive
```

### Usage Examples

**Filesystem:**
```python
from pydantic_ai.mcp import MCPServerStdio

filesystem_mcp = MCPServerStdio(
    'npx',
    args=['-y', '@modelcontextprotocol/server-filesystem', '/path']
)
toolsets=[filesystem_mcp]
```

**PostgreSQL:**
```python
postgres_mcp = MCPServerStdio(
    'npx',
    args=['-y', '@modelcontextprotocol/server-postgres', 'postgresql://user:pass@host/db']
)
toolsets=[postgres_mcp]
```

**SQLite:**
```python
sqlite_mcp = MCPServerStdio(
    'npx',
    args=['-y', '@modelcontextprotocol/server-sqlite', '/path/to/db.sqlite']
)
toolsets=[sqlite_mcp]
```

**Custom Python/Docker MCP Servers:**
```python
# Python-based MCP server
python_mcp = MCPServerStdio('python', args=['/path/to/custom_server.py'])

# Docker-based MCP server
docker_mcp = MCPServerStdio('docker', args=['run', '-i', 'my-mcp-server'])
```

## Combining with PydanticAI Tools

You can combine MCP servers with PydanticAI common tools:

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
    tools=[duckduckgo_search_tool()],  # PydanticAI common tools go in 'tools'
    toolsets=[filesystem_mcp],         # MCP servers go in 'toolsets'
)
```

**Important:** Note the parameter separation:
- `tools=` - For PydanticAI common tools (e.g., `duckduckgo_search_tool()`)
- `toolsets=` - For MCP servers (e.g., `MCPServerStdio` instances)

## Troubleshooting

**MCP server not found:**
```bash
npm install -g @modelcontextprotocol/server-filesystem
```

**Permission denied:**
- Ensure the MCP server has read access to the specified directory
- Check file/directory permissions

**Connection timeout:**
- Verify the MCP server command is correct
- Check network connectivity for HTTP-based servers

## Key Insights

- **Local Data**: MCP servers give AI access to your local files, databases, etc.
- **External Systems**: Connect to APIs, cloud services, and more
- **Composable**: Combine multiple MCP servers and tools
- **Type Safety**: Clockwork validates MCP server configurations
