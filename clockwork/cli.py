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

    # Check for main.py in current directory
    main_file = Path.cwd() / "main.py"
    if not main_file.exists():
        console.print("[bold red]✗ Error:[/bold red] No main.py found in current directory")
        console.print("[dim]Hint: cd into your project directory that contains main.py[/dim]")
        raise typer.Exit(code=1)

    # Get settings for display
    settings = get_settings()
    display_model = model or settings.openrouter_model

    console.print(Panel.fit(
        f"[bold blue]Clockwork Apply[/bold blue]\n"
        f"Directory: {Path.cwd().name}\n"
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

    # Check for main.py in current directory
    main_file = Path.cwd() / "main.py"
    if not main_file.exists():
        console.print("[bold red]✗ Error:[/bold red] No main.py found in current directory")
        console.print("[dim]Hint: cd into your project directory that contains main.py[/dim]")
        raise typer.Exit(code=1)

    # Get settings for display
    settings = get_settings()
    display_model = model or settings.openrouter_model

    console.print(Panel.fit(
        f"[bold cyan]Clockwork Generate[/bold cyan]\n"
        f"Directory: {Path.cwd().name}\n"
        f"Model: {display_model}",
        border_style="cyan"
    ))

    try:
        # Initialize core (uses settings if params not provided)
        core = ClockworkCore(
            openrouter_api_key=api_key,
            openrouter_model=model
        )

        # Run generation (dry run)
        result = core.plan(main_file)

        # Show summary
        console.print(f"\n[bold]Generation Summary:[/bold]")
        console.print(f"  Resources: {result['resources']}")
        console.print(f"  Artifacts generated: {result['artifacts']}")
        console.print(f"  PyInfra directory: {result['pyinfra_dir']}")
        console.print("\n[dim]Run 'clockwork apply' to deploy these resources.[/dim]")

    except Exception as e:
        console.print(f"\n[bold red]✗ Generation failed:[/bold red] {e}")
        raise typer.Exit(code=1)


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

    # Check for main.py in current directory
    main_file = Path.cwd() / "main.py"
    if not main_file.exists():
        console.print("[bold red]✗ Error:[/bold red] No main.py found in current directory")
        console.print("[dim]Hint: cd into your project directory that contains main.py[/dim]")
        raise typer.Exit(code=1)

    # Get settings for display
    settings = get_settings()
    display_model = model or settings.openrouter_model

    console.print(Panel.fit(
        f"[bold red]Clockwork Destroy[/bold red]\n"
        f"Directory: {Path.cwd().name}\n"
        f"Model: {display_model}",
        border_style="red"
    ))

    try:
        # Initialize core (uses settings if params not provided)
        core = ClockworkCore(
            openrouter_api_key=api_key,
            openrouter_model=model
        )

        # Execute destroy pipeline
        result = core.destroy(main_file)

        # Show results
        console.print("\n[bold green]✓ Resources destroyed successfully![/bold green]")
        if result.get("stdout"):
            console.print("\n[dim]PyInfra output:[/dim]")
            console.print(result["stdout"])

    except Exception as e:
        console.print(f"\n[bold red]✗ Destroy failed:[/bold red] {e}")
        raise typer.Exit(code=1)


@app.command()
def version():
    """Show Clockwork version."""
    from . import __version__
    console.print(f"Clockwork version: [bold]{__version__}[/bold]")


if __name__ == "__main__":
    app()
