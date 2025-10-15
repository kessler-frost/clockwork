"""
Clockwork CLI - Intelligent Infrastructure Orchestration in Python.
"""

import asyncio
import logging
import os
import shutil
import signal
import subprocess
import time
from pathlib import Path

import httpx
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


# Service helper functions
def check_service_running() -> bool:
    """Check if Clockwork service is running.

    Returns:
        True if service is running and healthy, False otherwise.
    """
    settings = get_settings()
    try:
        response = httpx.get(
            f"http://localhost:{settings.service_port}/health",
            timeout=1.0
        )
        return response.status_code == 200
    except Exception:
        return False


def _get_service_pid_file() -> Path:
    """Get path to service PID file.

    Returns:
        Path to service.pid file.
    """
    return Path.cwd() / ".clockwork" / "service" / "service.pid"


def _read_service_pid() -> int | None:
    """Read service PID from file.

    Returns:
        PID as integer, or None if file doesn't exist or is invalid.
    """
    pid_file = _get_service_pid_file()
    if not pid_file.exists():
        return None
    try:
        return int(pid_file.read_text().strip())
    except (ValueError, OSError):
        return None


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
        method = getattr(core, core_method)

        # Check if method is async and run accordingly
        if asyncio.iscoroutinefunction(method):
            result = asyncio.run(method(main_file))
        else:
            result = method(main_file)

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
        if result.get("success"):
            console.print("\n[bold green]✓ Deployment successful![/bold green]")

            # Show Pulumi summary
            if result.get("summary"):
                summary = result["summary"]
                console.print(f"\n[dim]Result: {summary.get('result', 'unknown')}[/dim]")

                changes = summary.get("resource_changes", {})
                if changes:
                    console.print(f"[dim]Resources: +{changes.get('create', 0)} ~{changes.get('update', 0)} -{changes.get('delete', 0)}[/dim]")

                if summary.get("duration"):
                    console.print(f"[dim]Duration: {summary['duration']}s[/dim]")

            # Show outputs if any
            if result.get("outputs"):
                console.print("\n[dim]Outputs:[/dim]")
                for key, value in result["outputs"].items():
                    console.print(f"  {key}: {value}")
        else:
            console.print(f"\n[bold red]✗ Deployment failed:[/bold red] {result.get('error', 'Unknown error')}")

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
    """Preview Pulumi changes without deploying."""
    def _handle_success(result):
        console.print(f"\n[bold]Plan Summary:[/bold]")
        console.print(f"  Resources: {result['resources']}")
        console.print(f"  Completed resources: {result['completed_resources']}")

        # Show preview details
        preview = result.get("preview", {})
        if preview.get("success"):
            summary = preview.get("summary", {})
            change_summary = summary.get("change_summary", {})

            console.print(f"\n[bold]Preview Changes:[/bold]")
            console.print(f"  Create: {change_summary.get('create', 0)}")
            console.print(f"  Update: {change_summary.get('update', 0)}")
            console.print(f"  Delete: {change_summary.get('delete', 0)}")
            console.print(f"  Total steps: {summary.get('steps', 0)}")
        elif preview.get("error"):
            console.print(f"\n[yellow]⚠ Preview error:[/yellow] {preview['error']}")

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
):
    """Destroy infrastructure: remove all deployed resources."""
    def _handle_success(result):
        if result.get("success"):
            console.print("\n[bold green]✓ Resources destroyed successfully![/bold green]")

            # Show Pulumi summary
            if result.get("summary"):
                summary = result["summary"]
                console.print(f"\n[dim]Result: {summary.get('result', 'unknown')}[/dim]")

                if summary.get("duration"):
                    console.print(f"[dim]Duration: {summary['duration']}s[/dim]")
        else:
            console.print(f"\n[bold red]✗ Destroy failed:[/bold red] {result.get('error', 'Unknown error')}")

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
        if result.get("success"):
            console.print("\n[bold green]✓ All assertions passed![/bold green]")
        else:
            console.print("\n[bold red]✗ Some assertions failed[/bold red]")

        # Show assertion summary
        console.print(f"\n[bold]Assertion Summary:[/bold]")
        console.print(f"  Total: {result.get('total', 0)}")
        console.print(f"  Passed: {result.get('passed', 0)}")
        console.print(f"  Failed: {result.get('failed', 0)}")

        # Show failed assertions if any
        if result.get("failed", 0) > 0:
            details = result.get("details", {})
            failed = details.get("failed", [])
            if failed:
                console.print(f"\n[bold red]Failed Assertions:[/bold red]")
                for failure in failed:
                    console.print(f"  • {failure['resource']}: {failure['assertion']}")
                    if failure.get("error"):
                        console.print(f"    [dim]Error: {failure['error']}[/dim]")

    _run_command(
        command_name="assert",
        panel_title="Clockwork Assert",
        panel_color="blue",
        core_method="assert_resources",
        success_handler=_handle_success,
        api_key=api_key,
        model=model,
    )


# Service commands
service_app = typer.Typer(
    name="service",
    help="Manage Clockwork monitoring service"
)
app.add_typer(service_app, name="service")


@service_app.command("start")
def service_start():
    """Start Clockwork service."""
    settings = get_settings()

    # Check if already running
    if check_service_running():
        console.print("[yellow]Service already running[/yellow]")
        console.print(f"[dim]Port: {settings.service_port}[/dim]")
        return

    # Ensure service directory exists
    pid_file = _get_service_pid_file()
    pid_file.parent.mkdir(parents=True, exist_ok=True)

    # Start uvicorn in background with autoreload
    try:
        process = subprocess.Popen(
            [
                'uvicorn',
                'clockwork.service.app:app',
                '--host', '0.0.0.0',
                '--port', str(settings.service_port),
                '--log-level', 'warning',
                '--reload',
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )

        # Save PID
        pid_file.write_text(str(process.pid))

        # Wait a moment and check if service started
        time.sleep(2)
        if check_service_running():
            console.print(f"[green]✓ Service started on port {settings.service_port}[/green]")
            console.print(f"[dim]PID: {process.pid}[/dim]")
        else:
            console.print("[red]✗ Service failed to start[/red]")
            raise typer.Exit(code=1)

    except FileNotFoundError:
        console.print("[red]✗ uvicorn not found[/red]")
        console.print("[dim]Install with: uv pip install uvicorn[/dim]")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[red]✗ Failed to start service: {e}[/red]")
        raise typer.Exit(code=1)


@service_app.command("stop")
def service_stop():
    """Stop Clockwork service."""
    pid = _read_service_pid()

    if pid is None:
        console.print("[yellow]Service PID file not found[/yellow]")
        return

    try:
        os.kill(pid, signal.SIGTERM)
        console.print(f"[green]✓ Service stopped (PID: {pid})[/green]")

        # Clean up PID file
        pid_file = _get_service_pid_file()
        if pid_file.exists():
            pid_file.unlink()

    except ProcessLookupError:
        console.print("[yellow]Process not found (already stopped?)[/yellow]")
        # Clean up stale PID file
        pid_file = _get_service_pid_file()
        if pid_file.exists():
            pid_file.unlink()
    except PermissionError:
        console.print(f"[red]✗ Permission denied (PID: {pid})[/red]")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[red]✗ Failed to stop service: {e}[/red]")
        raise typer.Exit(code=1)


@service_app.command("restart")
def service_restart():
    """Restart Clockwork service."""
    console.print("[dim]Stopping service...[/dim]")
    service_stop()
    time.sleep(1)
    console.print("[dim]Starting service...[/dim]")
    service_start()


@service_app.command("status")
def service_status():
    """Check Clockwork service status."""
    settings = get_settings()

    if not check_service_running():
        console.print("[red]✗ Service not running[/red]")
        console.print("[dim]Start with: clockwork service start[/dim]")
        raise typer.Exit(code=1)

    console.print("[green]✓ Service running[/green]")
    console.print(f"[dim]Port: {settings.service_port}[/dim]")

    # Try to get health info
    try:
        response = httpx.get(
            f"http://localhost:{settings.service_port}/health",
            timeout=5.0
        )
        health_data = response.json()
        console.print(f"[dim]Status: {health_data.get('status', 'unknown')}[/dim]")
    except Exception:
        pass


@app.command()
def version():
    """Show Clockwork version."""
    from . import __version__
    console.print(f"Clockwork version: [bold]{__version__}[/bold]")


if __name__ == "__main__":
    app()
