# Tool Integration Example

This example demonstrates how to use **PydanticAI tools** with Clockwork, showing both:

1. **Built-in tools** - DuckDuckGo web search (no setup required)
2. **Custom Python function tools** - Your own functions as tools

## What This Does

Creates two simple files demonstrating different tool types:

- `web_search_report.md` - Brief summary using web search
- `system_info_report.md` - Report using custom Python function tool

## Prerequisites

Configure your API key in `.env` (or use LM Studio locally):

```bash
CW_API_KEY=your-api-key-here
CW_MODEL=meta-llama/llama-4-scout:free
```

## Running the Example

```bash
cd examples/tool-integration
uv run clockwork apply
```

This takes about 1-2 minutes to complete.

## Validation

```bash
uv run clockwork assert
```

## Clean Up

```bash
uv run clockwork destroy
```

## Example 1: Built-in Tool (Web Search)

```python
from pydantic_ai.common_tools.duckduckgo import duckduckgo_search_tool

web_search_example = FileResource(
    name="web_search_report.md",
    description="Write a brief summary of the latest Python 3.13 features",
    tools=[duckduckgo_search_tool()],  # Built-in tool
)
```

## Example 2: Custom Python Function Tool

```python
from datetime import datetime

def get_system_info(query_type: str) -> str:
    """Get current system information.

    Args:
        query_type: Type of info to get ('time', 'date', or 'datetime')
    """
    now = datetime.now()
    if query_type == 'time':
        return now.strftime('%H:%M:%S')
    elif query_type == 'date':
        return now.strftime('%Y-%m-%d')
    elif query_type == 'datetime':
        return now.strftime('%Y-%m-%d %H:%M:%S')

custom_tool_example = FileResource(
    name="system_info_report.md",
    description="Create a system report with current date and time",
    tools=[get_system_info],  # Custom function as tool
)
```

PydanticAI automatically converts your Python function into a tool that the AI can call!

## Key Points

- **Built-in tools**: Use pre-made tools like DuckDuckGo search
- **Custom tools**: Any Python function can become a tool
- **Type hints required**: Functions must have type hints for parameters and return values
- **Docstrings help**: Good docstrings help the AI understand when to use your tool
