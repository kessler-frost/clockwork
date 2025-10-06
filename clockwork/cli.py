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


@app.command()
def apply(
    main_file: Path = typer.Argument(
        ...,
        help="Path to main.py file with resource definitions",
        exists=True,
        file_okay=True,
        dir_okay=False,
    ),
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

    # Get settings for display
    settings = get_settings()
    display_model = model or settings.openrouter_model

    console.print(Panel.fit(
        f"[bold blue]Clockwork Apply[/bold blue]\n"
        f"File: {main_file}\n"
        f"Model: {display_model}",
        border_style="blue"
    ))

    try:
        # Initialize core (uses settings if params not provided)
        core = ClockworkCore(
            openrouter_api_key=api_key,
            openrouter_model=model
        )

        # Execute pipeline
        result = core.apply(main_file)

        # Show results
        console.print("\n[bold green]✓ Deployment successful![/bold green]")
        if result.get("stdout"):
            console.print("\n[dim]PyInfra output:[/dim]")
            console.print(result["stdout"])

    except Exception as e:
        console.print(f"\n[bold red]✗ Deployment failed:[/bold red] {e}")
        raise typer.Exit(code=1)


@app.command()
def plan(
    main_file: Path = typer.Argument(
        ...,
        help="Path to main.py file with resource definitions",
        exists=True,
        file_okay=True,
        dir_okay=False,
    ),
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
    """Plan mode: show what would be deployed without executing."""

    # Get settings for display
    settings = get_settings()
    display_model = model or settings.openrouter_model

    console.print(Panel.fit(
        f"[bold cyan]Clockwork Plan (Dry Run)[/bold cyan]\n"
        f"File: {main_file}\n"
        f"Model: {display_model}",
        border_style="cyan"
    ))

    try:
        # Initialize core (uses settings if params not provided)
        core = ClockworkCore(
            openrouter_api_key=api_key,
            openrouter_model=model
        )

        # Run plan (dry run)
        result = core.plan(main_file)

        # Show plan
        console.print(f"\n[bold]Plan Summary:[/bold]")
        console.print(f"  Resources: {result['resources']}")
        console.print(f"  Artifacts to generate: {result['artifacts']}")
        console.print(f"  PyInfra directory: {result['pyinfra_dir']}")
        console.print("\n[dim]Run 'clockwork apply' to execute this plan.[/dim]")

    except Exception as e:
        console.print(f"\n[bold red]✗ Planning failed:[/bold red] {e}")
        raise typer.Exit(code=1)


@app.command()
def version():
    """Show Clockwork version."""
    from . import __version__
    console.print(f"Clockwork version: [bold]{__version__}[/bold]")


if __name__ == "__main__":
    app()
