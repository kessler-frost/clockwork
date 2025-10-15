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
import urllib.parse
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


def _register_project_with_service(main_file: Path) -> bool:
    """Register project with monitoring service.

    Args:
        main_file: Path to main.py file

    Returns:
        True if registration succeeded, False otherwise.
    """
    settings = get_settings()
    try:
        response = httpx.post(
            f"http://localhost:{settings.service_port}/projects/register",
            json={"main_file": str(main_file.absolute())},
            timeout=5.0
        )
        return response.status_code == 201
    except Exception:
        return False


def _unregister_project_from_service(main_file: Path) -> bool:
    """Unregister project from monitoring service.

    Args:
        main_file: Path to main.py file

    Returns:
        True if unregistration succeeded, False otherwise.
    """
    settings = get_settings()
    try:
        # URL-encode the main_file path for use as project_id
        project_id = urllib.parse.quote(str(main_file.absolute()), safe='')
        response = httpx.delete(
            f"http://localhost:{settings.service_port}/projects/{project_id}",
            timeout=5.0
        )
        return response.status_code == 204
    except Exception:
        return False


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
    skip_service_check: bool = typer.Option(
        False,
        "--skip-service-check",
        help="Skip service health check"
    ),
):
    """Apply infrastructure: complete resources + compile + deploy."""
    # Check service health (unless skipped)
    if not skip_service_check:
        if not check_service_running():
            console.print("[bold red]✗ Clockwork service not running[/bold red]")
            console.print("[dim]Start the service first:[/dim]")
            console.print("  [cyan]clockwork service start[/cyan]")
            raise typer.Exit(code=1)

    main_file = _get_main_file()

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

        # Register project with service
        if not skip_service_check and result.get("success"):
            if _register_project_with_service(main_file):
                console.print("[dim]✓ Project registered with monitoring service[/dim]")
            else:
                console.print("[yellow]⚠ Could not register with service[/yellow]")

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
    skip_service_check: bool = typer.Option(
        False,
        "--skip-service-check",
        help="Skip service health check"
    ),
):
    """Destroy infrastructure: remove all deployed resources."""
    # Check service health (unless skipped)
    if not skip_service_check:
        if not check_service_running():
            console.print("[bold red]✗ Clockwork service not running[/bold red]")
            console.print("[dim]Start the service first:[/dim]")
            console.print("  [cyan]clockwork service start[/cyan]")
            raise typer.Exit(code=1)

    main_file = _get_main_file()

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

        # Unregister project from service
        if not skip_service_check and result.get("success"):
            if _unregister_project_from_service(main_file):
                console.print("[dim]✓ Project unregistered from monitoring service[/dim]")
            else:
                console.print("[yellow]⚠ Could not unregister from service[/yellow]")

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
    skip_service_check: bool = typer.Option(
        False,
        "--skip-service-check",
        help="Skip service health check"
    ),
):
    """Run assertions to validate deployed resources."""
    # Check service health (unless skipped)
    if not skip_service_check:
        if not check_service_running():
            console.print("[bold red]✗ Clockwork service not running[/bold red]")
            console.print("[dim]Start the service first:[/dim]")
            console.print("  [cyan]clockwork service start[/cyan]")
            raise typer.Exit(code=1)

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
    """Start Clockwork monitoring service."""
    settings = get_settings()

    # Check if already running
    if check_service_running():
        console.print("[yellow]Service already running[/yellow]")
        console.print(f"[dim]Port: {settings.service_port}[/dim]")
        return

    # Ensure service directory exists
    pid_file = _get_service_pid_file()
    pid_file.parent.mkdir(parents=True, exist_ok=True)

    # Start uvicorn in background
    # Redirect uvicorn's stdout/stderr to /dev/null to suppress its access logs
    # The service itself logs to both console and file via configured handlers
    try:
        process = subprocess.Popen(
            [
                'uvicorn',
                'clockwork.service.app:app',
                '--host', '0.0.0.0',
                '--port', str(settings.service_port),
                '--log-level', 'warning',  # Only show warnings/errors from uvicorn
                '--reload',  # Enable auto-reload when code changes
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,  # Keep stderr to see uvicorn errors
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
            console.print("[dim]Check that clockwork.service.app module exists[/dim]")
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
    """Stop Clockwork monitoring service."""
    pid = _read_service_pid()

    if pid is None:
        console.print("[yellow]Service PID file not found[/yellow]")
        console.print("[dim]Service may not be running[/dim]")
        return

    # Try to stop the process
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
    """Restart Clockwork monitoring service."""
    settings = get_settings()

    # Check if service is running
    is_running = check_service_running()

    if is_running:
        # Stop the service
        pid = _read_service_pid()

        if pid is not None:
            try:
                os.kill(pid, signal.SIGTERM)
                console.print(f"[dim]Stopping service (PID: {pid})[/dim]")

                # Clean up PID file
                pid_file = _get_service_pid_file()
                if pid_file.exists():
                    pid_file.unlink()

                # Wait for service to stop
                time.sleep(2)

            except ProcessLookupError:
                console.print("[yellow]Process not found (already stopped?)[/yellow]")
                pid_file = _get_service_pid_file()
                if pid_file.exists():
                    pid_file.unlink()
            except PermissionError:
                console.print(f"[red]✗ Permission denied (PID: {pid})[/red]")
                raise typer.Exit(code=1)
            except Exception as e:
                console.print(f"[red]✗ Failed to stop service: {e}[/red]")
                raise typer.Exit(code=1)
    else:
        console.print("[dim]Service not running, starting...[/dim]")

    # Start the service
    pid_file = _get_service_pid_file()
    pid_file.parent.mkdir(parents=True, exist_ok=True)

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

        # Wait and verify service started
        time.sleep(2)
        if check_service_running():
            console.print(f"[green]✓ Service restarted on port {settings.service_port}[/green]")
            console.print(f"[dim]PID: {process.pid}[/dim]")
        else:
            console.print("[red]✗ Service failed to start[/red]")
            console.print("[dim]Check that clockwork.service.app module exists[/dim]")
            raise typer.Exit(code=1)

    except FileNotFoundError:
        console.print("[red]✗ uvicorn not found[/red]")
        console.print("[dim]Install with: uv pip install uvicorn[/dim]")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[red]✗ Failed to start service: {e}[/red]")
        raise typer.Exit(code=1)


@service_app.command("status")
def service_status():
    """Check Clockwork service status."""
    settings = get_settings()

    if not check_service_running():
        console.print("[red]✗ Service not running[/red]")
        console.print("[dim]Start with: clockwork service start[/dim]")
        raise typer.Exit(code=1)

    # Get service info
    try:
        response = httpx.get(
            f"http://localhost:{settings.service_port}/health",
            timeout=5.0
        )
        health_data = response.json()

        console.print("[green]✓ Service running[/green]")
        console.print(f"[dim]Port: {settings.service_port}[/dim]")
        console.print(f"[dim]Status: {health_data.get('status', 'unknown')}[/dim]")

        # Try to get projects count
        try:
            projects_response = httpx.get(
                f"http://localhost:{settings.service_port}/projects",
                timeout=5.0
            )
            if projects_response.status_code == 200:
                projects = projects_response.json()
                console.print(f"[dim]Registered projects: {len(projects)}[/dim]")
        except Exception:
            pass

    except Exception as e:
        console.print("[yellow]⚠ Service running but unable to get details[/yellow]")
        console.print(f"[dim]{e}[/dim]")


@app.command()
def version():
    """Show Clockwork version."""
    from . import __version__
    console.print(f"Clockwork version: [bold]{__version__}[/bold]")


if __name__ == "__main__":
    app()
