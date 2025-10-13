"""
Clockwork CLI - Intelligent Infrastructure Orchestration in Python.
"""

import logging
import shutil
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
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
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
        console.print("[bold red]✗ Error:[/bold red] No main.py found in current directory")
        console.print("[dim]Hint: cd into your project directory that contains main.py[/dim]")
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
        border_style=color
    )


def _initialize_core(api_key: str = None, model: str = None) -> ClockworkCore:
    """Initialize ClockworkCore with optional overrides.

    Args:
        api_key: Optional API key override
        model: Optional model override

    Returns:
        Configured ClockworkCore instance
    """
    return ClockworkCore(
        api_key=api_key,
        model=model
    )


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
        console.print(f"\n[bold red]✗ Assertion(s) failed[/bold red]")
        console.print(f"[dim]{error_msg}[/dim]")
    else:
        console.print(f"\n[bold red]✗ {command_type.capitalize()} failed:[/bold red] {e}")

    raise typer.Exit(code=1)


def _run_command(
    command_name: str,
    panel_title: str,
    panel_color: str,
    core_method: str,
    success_handler,
    api_key: str = None,
    model: str = None,
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
    """
    main_file = _get_main_file()
    console.print(_create_command_panel(panel_title, panel_color))

    try:
        core = _initialize_core(api_key, model)
        result = getattr(core, core_method)(main_file)
        success_handler(result)
    except Exception as e:
        _handle_command_error(e, command_name)


@app.command()
def apply(
    api_key: str = typer.Option(
        None,
        "--api-key",
        help="API key for AI service (overrides .env)"
    ),
    model: str = typer.Option(
        None,
        "--model",
        help="Model name (overrides .env)"
    ),
):
    """Apply infrastructure: complete resources + compile + deploy."""
    def _handle_success(result):
        console.print("\n[bold green]✓ Deployment successful![/bold green]")
        if result.get("stdout"):
            console.print("\n[dim]PyInfra output:[/dim]")
            console.print(result["stdout"])

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
        None,
        "--api-key",
        help="API key for AI service (overrides .env)"
    ),
    model: str = typer.Option(
        None,
        "--model",
        help="Model name (overrides .env)"
    ),
):
    """Complete resources and compile without deploying."""
    def _handle_success(result):
        console.print(f"\n[bold]Plan Summary:[/bold]")
        console.print(f"  Resources: {result['resources']}")
        console.print(f"  Completed resources: {result['completed_resources']}")
        console.print(f"  PyInfra directory: {result['pyinfra_dir']}")
        console.print("\n[dim]Run 'clockwork apply' to deploy these resources.[/dim]")

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
        None,
        "--api-key",
        help="API key for AI service (overrides .env)"
    ),
    model: str = typer.Option(
        None,
        "--model",
        help="Model name (overrides .env)"
    ),
    keep_files: bool = typer.Option(
        False,
        "--keep-files",
        help="Keep .clockwork directory after destroy"
    ),
):
    """Destroy infrastructure: remove all deployed resources."""
    def _handle_success(result):
        console.print("\n[bold green]✓ Resources destroyed successfully![/bold green]")
        if result.get("stdout"):
            console.print("\n[dim]PyInfra output:[/dim]")
            console.print(result["stdout"])

        # Clean up .clockwork directory unless --keep-files is set
        if not keep_files:
            settings = get_settings()
            # Get the .clockwork directory (parent of pyinfra output dir)
            main_file = Path.cwd() / "main.py"
            pyinfra_dir = main_file.parent / settings.pyinfra_output_dir
            clockwork_dir = pyinfra_dir.parent

            # Safety check: only remove if it's actually named .clockwork
            if clockwork_dir.exists() and clockwork_dir.name == ".clockwork":
                shutil.rmtree(str(clockwork_dir))
                console.print(f"\n[dim]✓ Removed {clockwork_dir}[/dim]")
        else:
            console.print(f"\n[dim]ℹ Kept .clockwork directory (--keep-files flag set)[/dim]")

    _run_command(
        command_name="destroy",
        panel_title="Clockwork Destroy",
        panel_color="red",
        core_method="destroy",
        success_handler=_handle_success,
        api_key=api_key,
        model=model,
    )


@app.command(name="assert")
def assert_cmd(
    api_key: str = typer.Option(
        None,
        "--api-key",
        help="API key for AI service (overrides .env)"
    ),
    model: str = typer.Option(
        None,
        "--model",
        help="Model name (overrides .env)"
    ),
):
    """Run assertions to validate deployed resources."""
    def _handle_success(result):
        console.print("\n[bold green]✓ All assertions passed![/bold green]")
        if result.get("stdout"):
            console.print("\n[dim]PyInfra output:[/dim]")
            console.print(result["stdout"])

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
