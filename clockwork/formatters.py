"""
Formatters for Clockwork CLI output.

This module provides Rich-based formatting for displaying completed resources
with AI completion status markers.
"""

import json
from typing import Any

from rich.console import Console
from rich.tree import Tree


def format_resource_tree(
    resources: list[dict[str, Any]],
    console: Console,
    diff_only: bool = False,
) -> None:
    """
    Format and display resources as a Rich tree structure.

    Args:
        resources: List of formatted resource dicts from ClockworkCore.show()
        console: Rich Console instance for output
        diff_only: If True, only show AI-completed fields
    """
    if not resources:
        console.print("[dim]No resources to display.[/dim]")
        return

    for resource_data in resources:
        tree = _build_resource_tree(resource_data, diff_only)
        console.print(tree)
        console.print()  # Add spacing between resources


def _build_resource_tree(
    resource_data: dict[str, Any],
    diff_only: bool = False,
) -> Tree:
    """
    Build a Rich Tree for a single resource.

    Args:
        resource_data: Formatted resource dict
        diff_only: If True, only show AI-completed fields

    Returns:
        Rich Tree object
    """
    name = resource_data.get("name", "unnamed")
    resource_type = resource_data.get("type", "Resource")
    ai_fields = set(resource_data.get("ai_completed_fields", []))

    # Build tree root with resource name and type
    # Mark name as AI-completed if it was
    if "name" in ai_fields:
        tree = Tree(f"[bold]{name}[/bold] ({resource_type}) [cyan][AI][/cyan]")
    else:
        tree = Tree(f"[bold]{name}[/bold] ({resource_type})")

    # Add description if present
    description = resource_data.get("description")
    if description and not diff_only:
        tree.add(f'[dim]description:[/dim] "{description}"')

    # Add fields
    fields = resource_data.get("fields", {})
    for field_name, field_info in fields.items():
        value = field_info.get("value")
        is_ai = field_info.get("ai_completed", False)

        # Skip non-AI fields in diff mode
        if diff_only and not is_ai:
            continue

        # Skip None values and empty collections
        if value is None:
            continue
        if isinstance(value, list | dict) and not value:
            continue

        # Format the value
        formatted_value = _format_value(value)

        # Add AI marker if applicable
        if is_ai:
            tree.add(
                f"[dim]{field_name}:[/dim] {formatted_value} [cyan][AI][/cyan]"
            )
        else:
            tree.add(f"[dim]{field_name}:[/dim] {formatted_value}")

    # Add children (for composite resources)
    children = resource_data.get("children", [])
    if children:
        children_branch = tree.add("[dim]children:[/dim]")
        for child_data in children:
            child_tree = _build_resource_tree(child_data, diff_only)
            children_branch.add(child_tree)

    return tree


def _format_value(value: Any) -> str:
    """
    Format a field value for display.

    Args:
        value: The value to format

    Returns:
        Formatted string representation
    """
    if isinstance(value, str):
        # Truncate long strings
        if len(value) > 80:
            return f'"{value[:77]}..."'
        return f'"{value}"'
    elif isinstance(value, list):
        if not value:
            return "[]"
        # Format list items
        items = [_format_value(item) for item in value]
        return f"[{', '.join(items)}]"
    elif isinstance(value, dict):
        if not value:
            return "{}"
        # Format as compact JSON-like
        items = [f"{k}: {_format_value(v)}" for k, v in value.items()]
        return "{" + ", ".join(items) + "}"
    elif isinstance(value, bool):
        return str(value).lower()
    else:
        return str(value)


def format_resource_json(
    resources: list[dict[str, Any]],
    diff_only: bool = False,
) -> str:
    """
    Format resources as JSON string.

    Args:
        resources: List of formatted resource dicts
        diff_only: If True, only include AI-completed fields

    Returns:
        JSON string representation
    """
    if diff_only:
        # Filter to only show AI-completed fields
        filtered_resources = []
        for resource in resources:
            filtered = _filter_ai_fields(resource)
            if filtered:
                filtered_resources.append(filtered)
        return json.dumps(filtered_resources, indent=2, default=str)

    return json.dumps(resources, indent=2, default=str)


def _filter_ai_fields(resource_data: dict[str, Any]) -> dict[str, Any] | None:
    """
    Filter a resource to only include AI-completed fields.

    Args:
        resource_data: Formatted resource dict

    Returns:
        Filtered resource dict or None if no AI fields
    """
    ai_fields = set(resource_data.get("ai_completed_fields", []))

    if not ai_fields and not resource_data.get("children"):
        return None

    filtered = {
        "name": resource_data.get("name"),
        "type": resource_data.get("type"),
        "ai_completed_fields": list(ai_fields),
        "fields": {},
    }

    # Only include AI-completed fields
    fields = resource_data.get("fields", {})
    for field_name, field_info in fields.items():
        if field_info.get("ai_completed", False):
            filtered["fields"][field_name] = field_info

    # Process children recursively
    children = resource_data.get("children", [])
    if children:
        filtered["children"] = []
        for child in children:
            filtered_child = _filter_ai_fields(child)
            if filtered_child:
                filtered["children"].append(filtered_child)

    return filtered
