"""
Clockwork CLI - Command-line interface for PyInfra-based infrastructure automation.
"""

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
    help="Intelligent infrastructure automation with PyInfra",
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
        f"Model: {settings.openrouter_model}",
        border_style=color
    )


def _initialize_core(api_key: str = None, model: str = None) -> ClockworkCore:
    """Initialize ClockworkCore with optional overrides.

    Args:
        api_key: Optional OpenRouter API key override
        model: Optional model override

    Returns:
        Configured ClockworkCore instance
    """
    return ClockworkCore(
        openrouter_api_key=api_key,
        openrouter_model=model
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


@app.command()
def apply(
    api_key: str = typer.Option(
        None,
        "--api-key",
        help="OpenRouter API key (overrides .env)"
    ),
    model: str = typer.Option(
        None,
        "--model",
        help="OpenRouter model (overrides .env)"
    ),
):
    """Apply infrastructure: generate artifacts + compile + deploy."""
    main_file = _get_main_file()
    console.print(_create_command_panel("Clockwork Apply", "blue"))

    try:
        core = _initialize_core(api_key, model)
        result = core.apply(main_file)

        console.print("\n[bold green]✓ Deployment successful![/bold green]")
        if result.get("stdout"):
            console.print("\n[dim]PyInfra output:[/dim]")
            console.print(result["stdout"])

    except Exception as e:
        _handle_command_error(e, "deployment")


@app.command()
def generate(
    api_key: str = typer.Option(
        None,
        "--api-key",
        help="OpenRouter API key (overrides .env)"
    ),
    model: str = typer.Option(
        None,
        "--model",
        help="OpenRouter model (overrides .env)"
    ),
):
    """Generate artifacts and compile without deploying."""
    main_file = _get_main_file()
    console.print(_create_command_panel("Clockwork Generate", "cyan"))

    try:
        core = _initialize_core(api_key, model)
        result = core.plan(main_file)

        console.print(f"\n[bold]Generation Summary:[/bold]")
        console.print(f"  Resources: {result['resources']}")
        console.print(f"  Artifacts generated: {result['artifacts']}")
        console.print(f"  PyInfra directory: {result['pyinfra_dir']}")
        console.print("\n[dim]Run 'clockwork apply' to deploy these resources.[/dim]")

    except Exception as e:
        _handle_command_error(e, "generation")


@app.command()
def destroy(
    api_key: str = typer.Option(
        None,
        "--api-key",
        help="OpenRouter API key (overrides .env)"
    ),
    model: str = typer.Option(
        None,
        "--model",
        help="OpenRouter model (overrides .env)"
    ),
):
    """Destroy infrastructure: remove all deployed resources."""
    main_file = _get_main_file()
    console.print(_create_command_panel("Clockwork Destroy", "red"))

    try:
        core = _initialize_core(api_key, model)
        result = core.destroy(main_file)

        console.print("\n[bold green]✓ Resources destroyed successfully![/bold green]")
        if result.get("stdout"):
            console.print("\n[dim]PyInfra output:[/dim]")
            console.print(result["stdout"])

    except Exception as e:
        _handle_command_error(e, "destroy")


@app.command(name="assert")
def assert_cmd(
    api_key: str = typer.Option(
        None,
        "--api-key",
        help="OpenRouter API key (overrides .env)"
    ),
    model: str = typer.Option(
        None,
        "--model",
        help="OpenRouter model (overrides .env)"
    ),
):
    """Run assertions to validate deployed resources."""
    main_file = _get_main_file()
    console.print(_create_command_panel("Clockwork Assert", "blue"))

    try:
        core = _initialize_core(api_key, model)
        result = core.assert_resources(main_file)

        console.print("\n[bold green]✓ All assertions passed![/bold green]")
        if result.get("stdout"):
            console.print("\n[dim]PyInfra output:[/dim]")
            console.print(result["stdout"])

    except Exception as e:
        _handle_command_error(e, "assert")


@app.command()
def version():
    """Show Clockwork version."""
    from . import __version__
    console.print(f"Clockwork version: [bold]{__version__}[/bold]")


if __name__ == "__main__":
    app()
