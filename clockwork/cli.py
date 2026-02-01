"""
Clockwork CLI - Intelligent Infrastructure Orchestration in Python.
"""

import asyncio
import json
import logging
import traceback
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from . import __version__
from .completion import CompletionCache
from .core import ClockworkCore
from .exceptions import CompletionError, format_completion_error
from .formatters import format_resource_json, format_resource_tree
from .settings import get_settings

# Setup
app = typer.Typer(
    name="clockwork",
    help="Intelligent Infrastructure Orchestration in Python",
    add_completion=False,
)
console = Console()


def configure_logging():
    """Configure logging based on settings."""
    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


# Configure logging on module import
configure_logging()


# Helper functions to reduce duplication across commands
def _get_main_file() -> Path:
    """Check for main.py in current directory and return Path.

    Returns:
        Path to main.py

    Raises:
        SystemExit: If main.py is not found
    """
    main_file = Path.cwd() / "main.py"
    if not main_file.exists():
        console.print(
            "[bold red]✗ Error:[/bold red] No main.py found in current directory"
        )
        console.print(
            "[dim]Hint: cd into your project directory that contains main.py[/dim]"
        )
        raise typer.Exit(code=1)
    return main_file


def _create_command_panel(title: str, color: str) -> Panel:
    """Create a Rich Panel for command display.

    Args:
        title: Command title (e.g., "Clockwork Apply")
        color: Border color (e.g., "blue", "cyan", "red")

    Returns:
        Formatted Rich Panel
    """
    settings = get_settings()
    return Panel.fit(
        f"[bold {color}]{title}[/bold {color}]\n"
        f"Directory: {Path.cwd().name}\n"
        f"Model: {settings.model}",
        border_style=color,
    )


def _initialize_core(
    api_key: str | None = None,
    model: str | None = None,
    debug: bool = False,
) -> ClockworkCore:
    """Initialize ClockworkCore with optional overrides.

    Args:
        api_key: Optional API key override
        model: Optional model override
        debug: Whether to enable debug mode for completion errors

    Returns:
        Configured ClockworkCore instance
    """
    return ClockworkCore(api_key=api_key, model=model, debug=debug)


def _format_timings(result: dict) -> str | None:
    """Format timing information from result dict.

    Args:
        result: Result dict that may contain 'timings' key

    Returns:
        Formatted timing string or None if no timings
    """
    if not result.get("timings"):
        return None

    timings = result["timings"]
    timing_parts = []
    if "load" in timings:
        timing_parts.append(f"Load: {timings['load']:.1f}s")
    if "complete" in timings:
        timing_parts.append(f"Complete: {timings['complete']:.1f}s")
    if "deploy" in timings:
        timing_parts.append(f"Deploy: {timings['deploy']:.1f}s")
    if "total" in timings:
        timing_parts.append(f"Total: {timings['total']:.1f}s")

    return " | ".join(timing_parts) if timing_parts else None


def _handle_command_error(
    e: Exception, command_type: str, debug: bool = False
) -> None:
    """Handle command errors with appropriate formatting.

    Args:
        e: Exception that occurred
        command_type: Type of command (for error message context)
        debug: Whether to show debug info for completion errors

    Raises:
        SystemExit: Always exits with code 1
    """
    # Special handling for CompletionError
    if isinstance(e, CompletionError):
        error_output = format_completion_error(e, show_debug=debug)
        console.print()
        console.print(
            Panel(
                error_output,
                title="[bold red]Completion Failed[/bold red]",
                border_style="red",
            )
        )
    # Special handling for assertion RuntimeError
    elif command_type == "assert" and isinstance(e, RuntimeError):
        error_msg = str(e)
        console.print("\n[bold red]Assertion(s) failed[/bold red]")
        console.print(f"[dim]{error_msg}[/dim]")
    elif not isinstance(e, CompletionError | typer.Exit):
        console.print(
            f"\n[bold red]{command_type.capitalize()} failed:[/bold red] {e}"
        )
        if debug:
            console.print("\n[dim]Stack trace:[/dim]")
            console.print(f"[dim]{traceback.format_exc()}[/dim]")
    else:
        console.print(
            f"\n[bold red]{command_type.capitalize()} failed:[/bold red] {e}"
        )

    raise typer.Exit(code=1)


def _run_command(
    command_name: str,
    panel_title: str,
    panel_color: str,
    core_method: str,
    success_handler,
    api_key: str | None = None,
    model: str | None = None,
    debug: bool = False,
    **kwargs,
):
    """Execute a Clockwork command with common setup and error handling.

    Args:
        command_name: Command name for error messages (e.g., "apply", "plan")
        panel_title: Title for the command panel (e.g., "Clockwork Apply")
        panel_color: Border color for the panel (e.g., "blue", "cyan")
        core_method: Name of the ClockworkCore method to call (e.g., "apply")
        success_handler: Callable that takes result dict and prints success output
        api_key: Optional API key override
        model: Optional model override
        debug: Whether to enable debug mode for completion errors
        **kwargs: Additional keyword arguments to pass to the core method
    """
    main_file = _get_main_file()
    console.print(_create_command_panel(panel_title, panel_color))

    try:
        core = _initialize_core(api_key, model, debug=debug)
        method = getattr(core, core_method)

        # Check if method is async and run accordingly
        if asyncio.iscoroutinefunction(method):
            result = asyncio.run(method(main_file, **kwargs))
        else:
            result = method(main_file, **kwargs)

        success_handler(result)
    except Exception as e:
        _handle_command_error(e, command_name, debug=debug)


@app.command()
def apply(
    api_key: str = typer.Option(
        None,
        "--api-key",
        help="API key for completion service (overrides .env)",
    ),
    model: str = typer.Option(
        None, "--model", help="Model name (overrides .env)"
    ),
    no_cache: bool = typer.Option(
        False,
        "--no-cache",
        help="Disable completion cache (always run AI completion)",
    ),
    debug: bool = typer.Option(
        False,
        "--debug",
        help="Show full API request/response on completion errors",
    ),
):
    """Apply infrastructure: complete resources + compile + deploy."""

    def _handle_success(result):
        if result.get("success"):
            console.print("\n[bold green]✓ Deployment successful![/bold green]")

            # Show timing summary
            timing_str = _format_timings(result)
            if timing_str:
                console.print(f"[dim]  {timing_str}[/dim]")

            # Show Pulumi summary
            if result.get("summary"):
                summary = result["summary"]
                console.print(
                    f"\n[dim]Result: {summary.get('result', 'unknown')}[/dim]"
                )

                changes = summary.get("resource_changes", {})
                if changes:
                    console.print(
                        f"[dim]Resources: +{changes.get('create', 0)} ~{changes.get('update', 0)} -{changes.get('delete', 0)}[/dim]"
                    )

            # Show outputs if any
            if result.get("outputs"):
                console.print("\n[dim]Outputs:[/dim]")
                for key, value in result["outputs"].items():
                    console.print(f"  {key}: {value}")
        else:
            console.print(
                f"\n[bold red]✗ Deployment failed:[/bold red] {result.get('error', 'Unknown error')}"
            )

    _run_command(
        command_name="deployment",
        panel_title="Clockwork Apply",
        panel_color="blue",
        core_method="apply",
        success_handler=_handle_success,
        api_key=api_key,
        model=model,
        debug=debug,
        use_cache=not no_cache,
    )


@app.command()
def plan(
    api_key: str = typer.Option(
        None,
        "--api-key",
        help="API key for completion service (overrides .env)",
    ),
    model: str = typer.Option(
        None, "--model", help="Model name (overrides .env)"
    ),
    no_cache: bool = typer.Option(
        False,
        "--no-cache",
        help="Disable completion cache (always run AI completion)",
    ),
    debug: bool = typer.Option(
        False,
        "--debug",
        help="Show full API request/response on completion errors",
    ),
):
    """Preview Pulumi changes without deploying."""

    def _handle_success(result):
        console.print("\n[bold]Plan Summary:[/bold]")
        console.print(f"  Resources: {result['resources']}")
        console.print(f"  Completed resources: {result['completed_resources']}")

        # Show timing summary
        timing_str = _format_timings(result)
        if timing_str:
            console.print(f"[dim]  {timing_str}[/dim]")

        # Show preview details
        preview = result.get("preview", {})
        if preview.get("success"):
            summary = preview.get("summary", {})
            change_summary = summary.get("change_summary", {})

            console.print("\n[bold]Planned Changes (preview only):[/bold]")
            console.print(f"  Would create: {change_summary.get('create', 0)}")
            console.print(f"  Would update: {change_summary.get('update', 0)}")
            console.print(f"  Would delete: {change_summary.get('delete', 0)}")
            console.print(f"  Total steps: {summary.get('steps', 0)}")
        elif preview.get("error"):
            console.print(
                f"\n[yellow]⚠ Preview error:[/yellow] {preview['error']}"
            )

        console.print(
            "\n[dim]Run 'clockwork apply' to deploy these resources.[/dim]"
        )

    _run_command(
        command_name="plan",
        panel_title="Clockwork Plan",
        panel_color="cyan",
        core_method="plan",
        success_handler=_handle_success,
        api_key=api_key,
        model=model,
        debug=debug,
        use_cache=not no_cache,
    )


@app.command()
def show(
    resource_name: str = typer.Argument(
        None,
        help="Name of specific resource to show (optional)",
    ),
    api_key: str = typer.Option(
        None,
        "--api-key",
        help="API key for completion service (overrides .env)",
    ),
    model: str = typer.Option(
        None, "--model", help="Model name (overrides .env)"
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output in JSON format",
    ),
    diff: bool = typer.Option(
        False,
        "--diff",
        help="Only show AI-completed fields",
    ),
    no_cache: bool = typer.Option(
        False,
        "--no-cache",
        help="Disable completion cache (always run AI completion)",
    ),
    debug: bool = typer.Option(
        False,
        "--debug",
        help="Show full API request/response on completion errors",
    ),
):
    """Show completed resources BEFORE deployment.

    Displays what AI decided for each resource field, marking AI-completed
    fields with [AI]. Use --diff to only see AI-completed fields, or --json
    for machine-readable output.
    """
    main_file = _get_main_file()
    console.print(_create_command_panel("Clockwork Show", "magenta"))

    try:
        core = _initialize_core(api_key, model, debug=debug)
        result = asyncio.run(
            core.show(
                main_file, resource_name=resource_name, use_cache=not no_cache
            )
        )

        resources = result.get("resources", [])

        if not resources:
            if resource_name:
                console.print(
                    f"\n[yellow]No resource found with name '{resource_name}'[/yellow]"
                )
            else:
                console.print("\n[yellow]No resources found.[/yellow]")
            return

        # Output format
        if json_output:
            output = format_resource_json(resources, diff_only=diff)
            console.print(output)
        else:
            console.print()  # Add spacing
            format_resource_tree(resources, console, diff_only=diff)

            # Summary
            console.print(
                f"[dim]Total resources: {result.get('resource_count', 0)} | "
                f"AI-completed: {result.get('ai_completed_count', 0)}[/dim]"
            )
            console.print(
                "\n[dim]Run 'clockwork apply' to deploy these resources.[/dim]"
            )

    except Exception as e:
        _handle_command_error(e, "show", debug=debug)


@app.command()
def destroy(
    api_key: str = typer.Option(
        None,
        "--api-key",
        help="API key for completion service (overrides .env)",
    ),
    model: str = typer.Option(
        None, "--model", help="Model name (overrides .env)"
    ),
    keep_files: bool = typer.Option(
        False,
        "--keep-files",
        help="Keep working directories (do not delete files created by resources)",
    ),
):
    """Destroy infrastructure: remove all deployed resources."""

    def _handle_success(result):
        if result.get("success"):
            console.print(
                "\n[bold green]✓ Resources destroyed successfully![/bold green]"
            )

            # Show Pulumi summary
            if result.get("summary"):
                summary = result["summary"]
                console.print(
                    f"\n[dim]Result: {summary.get('result', 'unknown')}[/dim]"
                )

                if summary.get("duration"):
                    console.print(
                        f"[dim]Duration: {summary['duration']}s[/dim]"
                    )

            # Show info about kept files if applicable
            if keep_files and result.get("working_directories_kept"):
                console.print("\n[dim]Working directories kept:[/dim]")
                for directory in result["working_directories_kept"]:
                    console.print(f"  [dim]• {directory}[/dim]")
        else:
            console.print(
                f"\n[bold red]✗ Destroy failed:[/bold red] {result.get('error', 'Unknown error')}"
            )

    _run_command(
        command_name="destroy",
        panel_title="Clockwork Destroy",
        panel_color="red",
        core_method="destroy",
        success_handler=_handle_success,
        api_key=api_key,
        model=model,
        keep_files=keep_files,
    )


@app.command(name="assert")
def assert_cmd(
    api_key: str = typer.Option(
        None,
        "--api-key",
        help="API key for completion service (overrides .env)",
    ),
    model: str = typer.Option(
        None, "--model", help="Model name (overrides .env)"
    ),
):
    """Run assertions to validate deployed resources."""

    def _handle_success(result):
        if result.get("success"):
            console.print("\n[bold green]✓ All assertions passed![/bold green]")
        else:
            console.print("\n[bold red]✗ Some assertions failed[/bold red]")

        # Show assertion summary
        console.print("\n[bold]Assertion Summary:[/bold]")
        console.print(f"  Total: {result.get('total', 0)}")
        console.print(f"  Passed: {result.get('passed', 0)}")
        console.print(f"  Failed: {result.get('failed', 0)}")

        # Show failed assertions if any
        if result.get("failed", 0) > 0:
            details = result.get("details", {})
            failed = details.get("failed", [])
            if failed:
                console.print("\n[bold red]Failed Assertions:[/bold red]")
                for failure in failed:
                    console.print(
                        f"  • {failure['resource']}: {failure['assertion']}"
                    )
                    if failure.get("error"):
                        console.print(
                            f"    [dim]Error: {failure['error']}[/dim]"
                        )

    _run_command(
        command_name="assert",
        panel_title="Clockwork Assert",
        panel_color="blue",
        core_method="assert_resources",
        success_handler=_handle_success,
        api_key=api_key,
        model=model,
    )


@app.command()
def status(
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output in JSON format",
    ),
):
    """Show status of deployed resources.

    Inspects currently deployed resources and shows their actual system state.
    Shows container status (running/stopped), file existence, git repo status, etc.
    """
    main_file = _get_main_file()

    # Create a simpler panel for status (no model needed)
    status_panel = Panel.fit(
        "[bold green]Clockwork Status[/bold green]\n"
        f"Directory: {Path.cwd().name}",
        border_style="green",
    )
    console.print(status_panel)

    try:
        core = _initialize_core()
        result = asyncio.run(core.status(main_file))

        if json_output:
            # Output as JSON
            console.print(json.dumps(result, indent=2, default=str))
            return

        # Display Pulumi state info
        pulumi_state = result.get("pulumi_state", {})
        if pulumi_state.get("available"):
            console.print(
                f"\n[dim]Pulumi stack: {pulumi_state.get('stack_name', 'dev')} | "
                f"Resources: {pulumi_state.get('resource_count', 'unknown')}[/dim]"
            )
            if pulumi_state.get("last_update"):
                console.print(
                    f"[dim]Last update: {pulumi_state.get('last_update')}[/dim]"
                )
        else:
            console.print(
                f"\n[yellow]Pulumi state: {pulumi_state.get('error', 'Not available')}[/yellow]"
            )

        # Create status table
        resources = result.get("resources", [])

        if not resources:
            console.print("\n[yellow]No resources found.[/yellow]")
            return

        table = Table(show_header=True, header_style="bold")
        table.add_column("Name", style="cyan")
        table.add_column("Type", style="dim")
        table.add_column("Status", style="bold")
        table.add_column("Details", style="dim")

        for resource in resources:
            name = resource.get("name", "unknown")
            resource_type = resource.get("type", "unknown")
            status_value = resource.get("status", "unknown")
            details = resource.get("details", {})

            # Format status with color
            status_styled = _format_status(status_value)

            # Format details
            details_str = _format_details(details)

            table.add_row(name, resource_type, status_styled, details_str)

        console.print()
        console.print(table)

        # Show summary
        running = sum(
            1
            for r in resources
            if r.get("status") in ("running", "exists", "cloned")
        )
        total = len(resources)
        console.print(f"\n[dim]Resources: {running}/{total} healthy[/dim]")

        # Show errors if any
        errors = [r for r in resources if r.get("error")]
        if errors:
            console.print("\n[bold red]Errors:[/bold red]")
            for r in errors:
                console.print(f"  {r.get('name')}: {r.get('error')}")

    except Exception as e:
        _handle_command_error(e, "status")


def _format_status(status: str) -> str:
    """Format status with appropriate color.

    Args:
        status: Status string

    Returns:
        Styled status string
    """
    status_colors = {
        "running": "[green]running[/green]",
        "stopped": "[yellow]stopped[/yellow]",
        "exists": "[green]exists[/green]",
        "missing": "[red]missing[/red]",
        "cloned": "[green]cloned[/green]",
        "not_a_repo": "[yellow]not_a_repo[/yellow]",
        "composite": "[blue]composite[/blue]",
        "error": "[red]error[/red]",
        "unknown": "[dim]unknown[/dim]",
    }
    return status_colors.get(status, f"[dim]{status}[/dim]")


def _format_details(details: dict) -> str:
    """Format details dictionary as a string.

    Args:
        details: Details dictionary

    Returns:
        Formatted string
    """
    if not details:
        return ""

    parts = []
    # Priority order for displaying details
    priority_keys = ["ports", "path", "branch", "image", "size", "children"]

    for key in priority_keys:
        if key in details:
            value = details[key]
            if isinstance(value, bool):
                if value:
                    parts.append(key)
            else:
                parts.append(f"{key}: {value}")

    return ", ".join(parts) if parts else ""


@app.command()
def version():
    """Show Clockwork version."""
    console.print(f"Clockwork version: [bold]{__version__}[/bold]")


# Cache subcommand group
cache_app = typer.Typer(
    name="cache",
    help="Manage completion cache",
    add_completion=False,
)
app.add_typer(cache_app, name="cache")


@cache_app.command(name="clear")
def cache_clear():
    """Clear all cached completions."""
    settings = get_settings()

    if not settings.cache_enabled:
        console.print("[yellow]Cache is disabled in settings.[/yellow]")
        raise typer.Exit(code=0)

    cache = CompletionCache(
        cache_dir=settings.cache_dir,
        ttl_days=settings.cache_ttl_days,
    )

    count = cache.clear()

    console.print(
        f"[bold green]Cache cleared.[/bold green] Removed {count} entries."
    )


@cache_app.command(name="stats")
def cache_stats():
    """Show cache statistics."""
    settings = get_settings()

    if not settings.cache_enabled:
        console.print("[yellow]Cache is disabled in settings.[/yellow]")
        raise typer.Exit(code=0)

    cache = CompletionCache(
        cache_dir=settings.cache_dir,
        ttl_days=settings.cache_ttl_days,
    )

    stats = cache.stats()

    # Create a nice table for stats
    table = Table(show_header=False, box=None)
    table.add_column("Key", style="cyan")
    table.add_column("Value", style="bold")

    table.add_row("Cache Directory", stats["cache_dir"])
    table.add_row("Database Size", _format_bytes(stats["db_size_bytes"]))
    table.add_row("Total Entries", str(stats["total_entries"]))
    table.add_row("Valid Entries", str(stats["valid_entries"]))
    table.add_row("Expired Entries", str(stats["expired_entries"]))
    table.add_row("TTL", f"{settings.cache_ttl_days} days")

    console.print("\n[bold]Completion Cache Statistics[/bold]\n")
    console.print(table)

    # Show resource type breakdown if any
    if stats["resource_types"]:
        console.print("\n[bold]Entries by Resource Type:[/bold]")
        for resource_type, count in stats["resource_types"].items():
            console.print(f"  {resource_type}: {count}")


def _format_bytes(size_bytes: int) -> str:
    """Format bytes as human-readable string.

    Args:
        size_bytes: Size in bytes

    Returns:
        Human-readable size string
    """
    if size_bytes == 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB"]
    i = 0
    while size_bytes >= 1024 and i < len(units) - 1:
        size_bytes /= 1024
        i += 1
    return f"{size_bytes:.1f} {units[i]}"


if __name__ == "__main__":
    app()
