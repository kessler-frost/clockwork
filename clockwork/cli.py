"""
Clockwork CLI - Intelligent Infrastructure Orchestration in Python.
"""

import asyncio
import logging
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel

from .core import ClockworkCore
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
    api_key: str | None = None, model: str | None = None
) -> ClockworkCore:
    """Initialize ClockworkCore with optional overrides.

    Args:
        api_key: Optional API key override
        model: Optional model override

    Returns:
        Configured ClockworkCore instance
    """
    return ClockworkCore(api_key=api_key, model=model)


def _handle_command_error(e: Exception, command_type: str) -> None:
    """Handle command errors with appropriate formatting.

    Args:
        e: Exception that occurred
        command_type: Type of command (for error message context)

    Raises:
        SystemExit: Always exits with code 1
    """
    # Special handling for assertion RuntimeError
    if command_type == "assert" and isinstance(e, RuntimeError):
        error_msg = str(e)
        console.print("\n[bold red]✗ Assertion(s) failed[/bold red]")
        console.print(f"[dim]{error_msg}[/dim]")
    else:
        console.print(
            f"\n[bold red]✗ {command_type.capitalize()} failed:[/bold red] {e}"
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
        **kwargs: Additional keyword arguments to pass to the core method
    """
    main_file = _get_main_file()
    console.print(_create_command_panel(panel_title, panel_color))

    try:
        core = _initialize_core(api_key, model)
        method = getattr(core, core_method)

        # Check if method is async and run accordingly
        if asyncio.iscoroutinefunction(method):
            result = asyncio.run(method(main_file, **kwargs))
        else:
            result = method(main_file, **kwargs)

        success_handler(result)
    except Exception as e:
        _handle_command_error(e, command_name)


@app.command()
def apply(
    api_key: str = typer.Option(
        None, "--api-key", help="API key for AI service (overrides .env)"
    ),
    model: str = typer.Option(
        None, "--model", help="Model name (overrides .env)"
    ),
):
    """Apply infrastructure: complete resources + compile + deploy."""

    def _handle_success(result):
        if result.get("success"):
            console.print("\n[bold green]✓ Deployment successful![/bold green]")

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

                if summary.get("duration"):
                    console.print(
                        f"[dim]Duration: {summary['duration']}s[/dim]"
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
    )


@app.command()
def plan(
    api_key: str = typer.Option(
        None, "--api-key", help="API key for AI service (overrides .env)"
    ),
    model: str = typer.Option(
        None, "--model", help="Model name (overrides .env)"
    ),
):
    """Preview Pulumi changes without deploying."""

    def _handle_success(result):
        console.print("\n[bold]Plan Summary:[/bold]")
        console.print(f"  Resources: {result['resources']}")
        console.print(f"  Completed resources: {result['completed_resources']}")

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
    )


@app.command()
def destroy(
    api_key: str = typer.Option(
        None, "--api-key", help="API key for AI service (overrides .env)"
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
        None, "--api-key", help="API key for AI service (overrides .env)"
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
def version():
    """Show Clockwork version."""
    from . import __version__

    console.print(f"Clockwork version: [bold]{__version__}[/bold]")


if __name__ == "__main__":
    app()
