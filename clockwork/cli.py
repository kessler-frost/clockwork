"""
Clockwork CLI - Command-line interface for PyInfra-based infrastructure automation.
"""

import typer
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
import logging

from .core import ClockworkCore

# Setup
app = typer.Typer(
    name="clockwork",
    help="Intelligent infrastructure automation with PyInfra",
    add_completion=False,
)
console = Console()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


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
        envvar="OPENROUTER_API_KEY",
        help="OpenRouter API key (or set OPENROUTER_API_KEY env var)"
    ),
    model: str = typer.Option(
        "openai/gpt-oss-20b:free",
        "--model",
        help="OpenRouter model to use"
    ),
):
    """Apply infrastructure: generate artifacts + compile + deploy."""

    console.print(Panel.fit(
        f"[bold blue]Clockwork Apply[/bold blue]\n"
        f"File: {main_file}\n"
        f"Model: {model}",
        border_style="blue"
    ))

    try:
        # Initialize core
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
        envvar="OPENROUTER_API_KEY",
        help="OpenRouter API key (or set OPENROUTER_API_KEY env var)"
    ),
    model: str = typer.Option(
        "openai/gpt-oss-20b:free",
        "--model",
        help="OpenRouter model to use"
    ),
):
    """Plan mode: show what would be deployed without executing."""

    console.print(Panel.fit(
        f"[bold cyan]Clockwork Plan (Dry Run)[/bold cyan]\n"
        f"File: {main_file}\n"
        f"Model: {model}",
        border_style="cyan"
    ))

    try:
        # Initialize core
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
