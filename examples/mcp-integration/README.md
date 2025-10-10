# MCP Integration Example

This example demonstrates how to use **MCP (Model Context Protocol) servers** with Clockwork for AI-powered artifact generation with access to external systems.

## What This Example Shows

1. **Filesystem Access** - AI can read and analyze local files/directories
2. **Multiple MCP Servers** - Combine multiple data sources
3. **Hybrid Approach** - Use both Agno tools AND MCP servers
4. **Various MCP Types** - stdio, HTTP, Docker-based servers

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
mcp_servers=[
    "npx -y @modelcontextprotocol/server-filesystem /Users/sankalp/dev/clockwork"
    #                                                ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    #                                                Update this path!
]
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

Resources with MCPTools in `tools=` can connect to external data sources:

```python
from agno.tools.mcp import MCPTools

# Initialize the MCP server connection
filesystem_mcp = MCPTools(
    command="npx -y @modelcontextprotocol/server-filesystem /path/to/project"
)

project_analysis = FileResource(
    name="analysis.md",
    description="Analyze the project files",
    tools=[filesystem_mcp],  # Pass MCPTools object directly
)
```

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
from agno.tools.mcp import MCPTools

filesystem_mcp = MCPTools(command="npx -y @modelcontextprotocol/server-filesystem /path")
tools=[filesystem_mcp]
```

**PostgreSQL:**
```python
postgres_mcp = MCPTools(command="npx -y @modelcontextprotocol/server-postgres postgresql://user:pass@host/db")
tools=[postgres_mcp]
```

**SQLite:**
```python
sqlite_mcp = MCPTools(command="npx -y @modelcontextprotocol/server-sqlite /path/to/db.sqlite")
tools=[sqlite_mcp]
```

**HTTP Server:**
```python
http_mcp = MCPTools(url="https://api.example.com/mcp", transport="streamable-http")
tools=[http_mcp]
```

## Combining with Tools

You can combine MCP servers with Agno tools:

```python
from agno.tools.duckduckgo import DuckDuckGoTools
from agno.tools.mcp import MCPTools

filesystem_mcp = MCPTools(command="npx -y @modelcontextprotocol/server-filesystem /path")

resource = FileResource(
    name="hybrid.md",
    description="Compare our code with online best practices",
    tools=[
        DuckDuckGoTools(),  # Web search
        filesystem_mcp,     # File access
    ],
)
```

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
