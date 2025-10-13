"""
Tool Integration Example - PydanticAI Tools with Clockwork.

This example demonstrates two types of tools:
1. Built-in tools (DuckDuckGo web search)
2. Custom Python function tools

Tools enable AI to access external data and perform custom operations
during resource completion.
"""

from datetime import datetime
from clockwork.resources import FileResource
from clockwork.assertions import (
    FileExistsAssert,
    FileContentMatchesAssert,
)
from pydantic_ai.common_tools.duckduckgo import duckduckgo_search_tool


# Custom tool: Get current system information
def get_system_info(query_type: str) -> str:
    """Get current system information.

    Args:
        query_type: Type of info to get ('time', 'date', or 'datetime')

    Returns:
        Requested system information as a string
    """
    now = datetime.now()
    if query_type == 'time':
        return now.strftime('%H:%M:%S')
    elif query_type == 'date':
        return now.strftime('%Y-%m-%d')
    elif query_type == 'datetime':
        return now.strftime('%Y-%m-%d %H:%M:%S')
    else:
        return f"Unknown query type: {query_type}"


# Example 1: Built-in tool - Web search with DuckDuckGo
web_search_example = FileResource(
    name="web_search_report.md",
    description="Write a brief summary of the latest Python 3.13 features released in 2024",
    directory="scratch",
    tools=[duckduckgo_search_tool()],  # Built-in web search tool
    assertions=[
        FileExistsAssert(path="scratch/web_search_report.md"),
        FileContentMatchesAssert(
            path="scratch/web_search_report.md",
            pattern="Python"
        ),
    ]
)

# Example 2: Custom Python function tool
custom_tool_example = FileResource(
    name="system_info_report.md",
    description="Create a system report that includes the current date and time, with a brief greeting message",
    directory="scratch",
    tools=[get_system_info],  # Custom Python function as tool
    assertions=[
        FileExistsAssert(path="scratch/system_info_report.md"),
        FileContentMatchesAssert(
            path="scratch/system_info_report.md",
            pattern=r"\d{4}-\d{2}-\d{2}"  # Date pattern
        ),
    ]
)
