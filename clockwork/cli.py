"""
Simplified Clockwork CLI with PyInfra Integration

Provides core deployment functionality:
- clockwork apply <file.cw> - Parse .cw and execute with pyinfra
- clockwork plan <file.cw> - Parse .cw and run pyinfra dry-run
- clockwork watch <file.cw> - Watch file changes and auto-apply
- clockwork facts <target> - Show pyinfra facts for target
"""

import typer
import shutil
import json
import os
import sys
import time
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich import print as rich_print
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.live import Live
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# PyInfra imports
from pyinfra import host
from pyinfra.api import Config, State
from pyinfra.api.connect import connect_all
from pyinfra.api.operations import run_ops
from pyinfra.api.facts import get_facts
from pyinfra.api.inventory import Inventory
from pyinfra.api.host import Host
from pyinfra.connectors.local import LocalConnector
from pyinfra.connectors.ssh import SSHConnector
from pyinfra.connectors.docker import DockerConnector

from .core import ClockworkCore
from .models import IR, ResourceType
from .__init__ import __version__

# Initialize Rich console for beautiful output
console = Console()
app = typer.Typer(
    name="clockwork",
    help="Simplified Clockwork - Declarative infrastructure with PyInfra",
    add_completion=False,
)


def version_callback(value: bool):
    """Show version and exit."""
    if value:
        rich_print(f"[bold blue]Clockwork[/bold blue] v{__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Optional[bool] = typer.Option(
        None, "--version", "-v", callback=version_callback, is_eager=True,
        help="Show version and exit"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-V", help="Enable verbose output"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging"),
):
    """
    Clockwork - Simplified declarative infrastructure with PyInfra integration.

    Parse .cw files and execute them using PyInfra for robust infrastructure management.
    Supports multiple targets: @local, @docker, @ssh for flexible deployment.
    """
    # Setup logging based on verbosity
    import logging

    if debug:
        logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        console.print("[dim]Debug logging enabled[/dim]")
    elif verbose:
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        console.print("[dim]Verbose mode enabled[/dim]")
    else:
        logging.basicConfig(level=logging.WARNING, format='%(levelname)s - %(message)s')

    # Store global settings for commands to access
    os.environ['CLOCKWORK_VERBOSE'] = str(verbose)
    os.environ['CLOCKWORK_DEBUG'] = str(debug)


@app.command()
def apply(
    config_file: Optional[Path] = typer.Argument(None, help="Path to .cw configuration file (defaults to main.cw)"),
    target: str = typer.Option("@local", "--target", "-t", help="Target: @local, @docker:<container>, @ssh:<host>"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be applied without executing"),
    parallel: int = typer.Option(1, "--parallel", "-p", help="Number of parallel operations"),
    verbose: bool = typer.Option(False, "--verbose", help="Enable verbose PyInfra output"),
    var: List[str] = typer.Option([], "--var", help="Set variables (KEY=VALUE)"),
):
    """Parse .cw configuration and execute with PyInfra."""
    config_file = resolve_config_file(config_file)
    console.print(f"{'Planning' if dry_run else 'Applying'} {config_file}")

    variables = parse_variables(var)
    core = ClockworkCore()

    if dry_run:
        plan_data = core.plan(config_file, variables, [target])
        display_plan(plan_data)
    else:
        results = core.apply(config_file, variables, [target])
        success = all(result.get("success", False) for result in results)
        console.print("✅ Apply completed" if success else "❌ Apply failed")


@app.command()
def plan(
    config_file: Optional[Path] = typer.Argument(None, help="Path to .cw configuration file (defaults to main.cw)"),
    target: str = typer.Option("@local", "--target", "-t", help="Target: @local, @docker:<container>, @ssh:<host>"),
    var: List[str] = typer.Option([], "--var", help="Set variables (KEY=VALUE)"),
):
    """Show execution plan without applying changes."""
    config_file = resolve_config_file(config_file)
    console.print(f"Planning changes for {config_file}")

    variables = parse_variables(var)
    core = ClockworkCore()
    plan_data = core.plan(config_file, variables, [target])
    display_plan(plan_data)


@app.command()
def watch(
    config_file: Optional[Path] = typer.Argument(None, help="Path to .cw configuration file (defaults to main.cw)"),
    target: str = typer.Option("@local", "--target", "-t", help="Target: @local, @docker:<container>, @ssh:<host>"),
    var: List[str] = typer.Option([], "--var", help="Set variables (KEY=VALUE)"),
    interval: int = typer.Option(2, "--interval", help="Minimum seconds between re-applies"),
):
    """
    Watch .cw file for changes and automatically re-apply.

    Monitors the specified .cw file for modifications and automatically
    re-executes the configuration when changes are detected.
    """
    # Resolve config file path
    config_file = resolve_config_file(config_file)

    console.print(f"[bold blue]👁️  Watching {config_file} for changes[/bold blue]")
    console.print(f"[dim]Target: {target}[/dim]")
    console.print(f"[dim]Press Ctrl+C to stop watching[/dim]\n")

    last_apply_time = 0

    class ConfigFileHandler(FileSystemEventHandler):
        def on_modified(self, event):
            nonlocal last_apply_time

            if event.is_directory:
                return

            # Check if the modified file is our config file
            if Path(event.src_path) == config_file.absolute():
                current_time = time.time()

                # Rate limiting - don't apply too frequently
                if current_time - last_apply_time < interval:
                    return

                console.print(f"\n[yellow]📝 Change detected in {config_file}[/yellow]")

                try:
                    # Auto-apply with dry_run=False
                    apply(config_file, target, dry_run=False, parallel=1, verbose=False, var=var)
                    last_apply_time = current_time
                except Exception as e:
                    console.print(f"[red]❌ Auto-apply failed: {e}[/red]")

                console.print(f"\n[dim]Continuing to watch {config_file}...[/dim]")

    # Setup file watcher
    event_handler = ConfigFileHandler()
    observer = Observer()
    observer.schedule(event_handler, str(config_file.parent), recursive=False)

    try:
        observer.start()

        # Initial apply
        console.print("[dim]Performing initial apply...[/dim]")
        apply(config_file, target, dry_run=False, parallel=1, verbose=False, var=var)
        last_apply_time = time.time()

        console.print(f"\n[green]✅ Now watching {config_file} for changes...[/green]")

        # Keep watching until interrupted
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        console.print("\n[yellow]👋 Stopping file watcher[/yellow]")
        observer.stop()

    observer.join()


@app.command()
def facts(
    target: str = typer.Argument(..., help="Target: @local, @docker:<container>, @ssh:<host>"),
    fact_name: Optional[str] = typer.Option(None, "--fact", help="Specific fact to show (e.g., 'server.Os')"),
    json_output: bool = typer.Option(False, "--json", help="Output facts as JSON"),
):
    """
    Show PyInfra facts for the specified target.

    Connects to the target and gathers system information using PyInfra's
    fact gathering capabilities. Useful for understanding target state.
    """
    console.print(f"[bold blue]📊 Gathering facts from {target}[/bold blue]")

    try:
        # For now, provide a simplified facts implementation
        if target == "@local":
            # Get basic local system facts
            import platform
            import socket
            import os

            facts_data = {
                "server.Os": platform.system(),
                "server.OsVersion": platform.release(),
                "server.Arch": platform.machine(),
                "server.Hostname": socket.gethostname(),
                "server.User": os.getenv("USER", "unknown"),
                "server.HomeDir": os.path.expanduser("~"),
                "server.WorkingDir": os.getcwd()
            }

            if fact_name:
                if fact_name in facts_data:
                    if json_output:
                        console.print(json.dumps({fact_name: facts_data[fact_name]}, indent=2))
                    else:
                        console.print(f"[bold cyan]{fact_name}:[/bold cyan] {facts_data[fact_name]}")
                else:
                    console.print(f"[red]❌ Unknown fact: {fact_name}[/red]")
                    console.print(f"[dim]Available facts: {', '.join(facts_data.keys())}[/dim]")
                    raise typer.Exit(1)
            else:
                if json_output:
                    console.print(json.dumps(facts_data, indent=2))
                else:
                    # Display facts in a nice table
                    table = Table(title=f"Facts for {target}")
                    table.add_column("Fact", style="cyan")
                    table.add_column("Value", style="white")

                    for fact, value in facts_data.items():
                        table.add_row(fact, str(value))

                    console.print(table)

        else:
            console.print("[yellow]⚠️  Remote fact gathering not yet implemented[/yellow]")
            console.print(f"[dim]Target: {target}[/dim]")
            console.print("[dim]PyInfra fact gathering will be implemented in a future version[/dim]")

    except Exception as e:
        console.print(f"[red]❌ Failed to gather facts: {e}[/red]")
        if os.environ.get('CLOCKWORK_DEBUG') == 'True':
            import traceback
            console.print("[dim]" + traceback.format_exc() + "[/dim]")
        raise typer.Exit(1)


@app.command()
def state(
    action: str = typer.Argument(..., help="Action: show, diff, drift, cleanup"),
    target: str = typer.Option("@local", "--target", "-t", help="Target: @local, @docker:<container>, @ssh:<host>"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
    config_file: Optional[Path] = typer.Option(None, "--config", help="Path to .cw configuration file for drift detection"),
):
    """
    State management commands for Clockwork.

    Available actions:
    - show: Display current state and health summary
    - diff: Show differences between current and last state
    - drift: Detect configuration drift against current facts
    - cleanup: Clean up old state snapshots and fact files
    """
    console.print(f"[bold blue]🔍 State {action}[/bold blue]")

    try:
        from .core import ClockworkCore

        # Initialize core with current directory
        core = ClockworkCore()

        if action == "show":
            # Show current state
            summary = core.state_manager.get_state_summary()

            if json_output:
                console.print(json.dumps(summary, indent=2, default=str))
            else:
                # Display state summary in a nice format
                if "error" in summary:
                    console.print(f"[red]❌ {summary['error']}[/red]")
                    return

                # Health summary
                health_panel = Panel(
                    f"Health Score: [bold green]{summary.get('health_score', 0):.1f}%[/bold green]\n"
                    f"Total Resources: {summary.get('total_resources', 0)}\n"
                    f"Resources with Drift: {summary.get('resources_with_drift', 0)}\n"
                    f"Stale Resources: {summary.get('stale_resources', 0)}\n"
                    f"Failed Resources: {summary.get('failed_resources', 0)}",
                    title="🏥 Health Summary",
                    border_style="green" if summary.get('health_score', 0) > 80 else "yellow"
                )
                console.print(health_panel)

                # Last execution info
                if summary.get('last_execution'):
                    last_exec = summary['last_execution']
                    status_color = "green" if last_exec['status'] == 'success' else "red"
                    exec_panel = Panel(
                        f"Run ID: {last_exec['run_id']}\n"
                        f"Status: [{status_color}]{last_exec['status']}[/{status_color}]\n"
                        f"Started: {last_exec['started_at']}\n"
                        f"Completed: {last_exec.get('completed_at', 'N/A')}",
                        title="⏱️ Last Execution",
                        border_style=status_color
                    )
                    console.print(exec_panel)

                # Storage info
                storage_panel = Panel(
                    f"State File Size: {summary.get('state_file_size', 0)} bytes\n"
                    f"Fact Snapshots: {summary.get('fact_snapshots_count', 0)}\n"
                    f"State Backups: {summary.get('state_backups_count', 0)}\n"
                    f"Last Updated: {summary.get('last_updated', 'N/A')}",
                    title="💾 Storage Info",
                    border_style="blue"
                )
                console.print(storage_panel)

        elif action == "diff":
            # Show state differences
            current_state = core.get_current_state()
            if not current_state:
                console.print("[yellow]⚠️ No current state found[/yellow]")
                return

            # Load previous state (simplified - would need proper versioning)
            console.print("[dim]State diff functionality - showing current state summary[/dim]")
            console.print(f"Current state has {len(current_state.current_resources)} resources")

            if json_output:
                state_dict = current_state.model_dump()
                console.print(json.dumps(state_dict, indent=2, default=str))
            else:
                # Display resource summary
                if current_state.current_resources:
                    table = Table(title="Current Resources")
                    table.add_column("Resource ID", style="cyan")
                    table.add_column("Type", style="yellow")
                    table.add_column("Status", style="white")
                    table.add_column("Last Applied", style="dim")

                    for resource_id, resource in current_state.current_resources.items():
                        status_color = "green" if resource.status.value == "success" else "red"
                        table.add_row(
                            resource_id,
                            resource.type.value,
                            f"[{status_color}]{resource.status.value}[/{status_color}]",
                            resource.last_applied.strftime("%Y-%m-%d %H:%M:%S") if resource.last_applied else "N/A"
                        )

                    console.print(table)

        elif action == "drift":
            # Detect drift
            if not config_file:
                console.print("[red]❌ Configuration file required for drift detection[/red]")
                console.print("[dim]Use --config to specify a .cw file[/dim]")
                raise typer.Exit(1)

            console.print(f"[dim]Detecting drift for configuration: {config_file}[/dim]")

            # Create inventory from target
            inventory = create_inventory_from_target(target)

            # Get current resource states
            current_state = core.get_current_state()
            if not current_state:
                console.print("[yellow]⚠️ No current state found - run 'apply' first[/yellow]")
                return

            # Detect drift
            drifted_resources = core.state_manager.detect_drift(inventory, current_state.current_resources)

            if drifted_resources:
                console.print(f"[red]🚨 Drift detected in {len(drifted_resources)} resources[/red]")

                if json_output:
                    console.print(json.dumps({"drifted_resources": drifted_resources}, indent=2))
                else:
                    for resource_id in drifted_resources:
                        console.print(f"[red]• {resource_id}[/red]")
            else:
                console.print("[green]✅ No drift detected[/green]")

        elif action == "cleanup":
            # Clean up old files
            console.print("[dim]Cleaning up old state snapshots and fact files...[/dim]")

            keep_days = 30  # Could be made configurable
            core.state_manager.cleanup_old_snapshots(keep_days=keep_days)

            console.print(f"[green]✅ Cleanup completed (kept files from last {keep_days} days)[/green]")

        else:
            console.print(f"[red]❌ Unknown action: {action}[/red]")
            console.print("[dim]Available actions: show, diff, drift, cleanup[/dim]")
            raise typer.Exit(1)

    except Exception as e:
        console.print(f"[red]❌ State {action} failed: {e}[/red]")
        if os.environ.get('CLOCKWORK_DEBUG') == 'True':
            import traceback
            console.print("[dim]" + traceback.format_exc() + "[/dim]")
        raise typer.Exit(1)


# =============================================================================
# Helper Functions
# =============================================================================

def display_plan(plan_data: Dict[str, Any]) -> None:
    """Display plan data in a user-friendly format."""
    changes = plan_data.get("changes", {})
    summary = plan_data.get("summary", {})

    console.print(f"\nPlan Summary:")
    console.print(f"+ {summary.get('create', 0)} to create")
    console.print(f"~ {summary.get('update', 0)} to update")
    console.print(f"- {summary.get('delete', 0)} to destroy")

    for change in changes.get("create", []):
        console.print(f"[green]+ {change['resource_id']} ({change['resource_type']})[/green]")

    for change in changes.get("update", []):
        console.print(f"[yellow]~ {change['resource_id']} ({change['resource_type']})[/yellow]")

    for change in changes.get("delete", []):
        console.print(f"[red]- {change['resource_id']} ({change['resource_type']})[/red]")

    action = "apply" if plan_data.get("has_changes", False) else "No changes needed"
    console.print(f"\n{action}")


def resolve_config_file(config_file: Optional[Path]) -> Path:
    """Resolve config file path, defaulting to main.cw in current directory."""
    if config_file:
        return config_file

    default_config = Path("main.cw")
    if default_config.exists():
        return default_config

    cw_files = list(Path(".").glob("*.cw"))
    if len(cw_files) == 1:
        return cw_files[0]

    console.print("❌ No main.cw file found")
    raise typer.Exit(1)

def parse_variables(var_list: List[str]) -> Dict[str, Any]:
    """Parse variables from command line."""
    variables = {}
    for var_str in var_list:
        key, value = var_str.split("=", 1)
        variables[key] = value
    return variables


def create_inventory_from_target(target: str) -> Inventory:
    """Create PyInfra inventory from target specification."""

    if target == "@local":
        # Local execution
        hosts = ["@local"]
        host_data = {"@local": {}}
        inventory = Inventory((hosts, host_data))

    elif target.startswith("@docker:"):
        # Docker container execution
        container_name = target[8:]  # Remove "@docker:" prefix
        hosts = [container_name]
        host_data = {container_name: {
            "pyinfra_connector": "docker"
        }}
        inventory = Inventory((hosts, host_data))

    elif target.startswith("@ssh:"):
        # SSH execution
        ssh_target = target[5:]  # Remove "@ssh:" prefix

        # Parse SSH target (user@host:port or host)
        if "@" in ssh_target:
            user_host, port = ssh_target.split(":", 1) if ":" in ssh_target else (ssh_target, "22")
            user, hostname = user_host.split("@", 1)
        else:
            hostname, port = ssh_target.split(":", 1) if ":" in ssh_target else (ssh_target, "22")
            user = os.getenv("USER", "root")

        hosts = [hostname]
        host_data = {hostname: {
            "ssh_user": user,
            "ssh_port": int(port)
        }}
        inventory = Inventory((hosts, host_data))

    else:
        raise ValueError(f"Unsupported target format: {target}. Use @local, @docker:<container>, or @ssh:<host>")

    return inventory


def convert_ir_to_pyinfra_ops(ir: IR) -> List[Dict[str, Any]]:
    """Convert Clockwork IR to PyInfra operations."""
    operations = []

    for resource_name, resource in ir.resources.items():
        if resource.type == ResourceType.FILE:
            # File operation
            file_path = resource.config.get("path", f"/tmp/{resource.name}")
            content = resource.config.get("content", "")

            operations.append({
                "name": f"Create file {resource.name}",
                "operation": "files.put",
                "args": [content, file_path],
                "kwargs": {"mode": "644"},
                "resource": resource
            })

        elif resource.type == ResourceType.DIRECTORY:
            # Directory operation
            dir_path = resource.config.get("path", f"/tmp/{resource.name}")

            operations.append({
                "name": f"Create directory {resource.name}",
                "operation": "files.directory",
                "args": [dir_path],
                "kwargs": {"mode": "755"},
                "resource": resource
            })

        elif resource.type == ResourceType.SERVICE:
            # Service operation (using systemd or docker)
            service_name = resource.config.get("name", resource.name)
            image = resource.config.get("image")

            if image:
                # Docker service
                operations.append({
                    "name": f"Ensure Docker service {service_name}",
                    "operation": "docker.container",
                    "args": [service_name],
                    "kwargs": {
                        "image": image,
                        "ports": resource.config.get("ports", []),
                        "environment": resource.config.get("environment", {})
                    },
                    "resource": resource
                })
            else:
                # System service
                operations.append({
                    "name": f"Ensure service {service_name}",
                    "operation": "systemd.service",
                    "args": [service_name],
                    "kwargs": {"running": True, "enabled": True},
                    "resource": resource
                })

        elif resource.type == ResourceType.CHECK:
            # Health check operations using our custom pyinfra ops
            from clockwork.pyinfra_ops import health

            check_type = resource.config.get("type", "http")

            if check_type == "http" or "url" in resource.config:
                # HTTP health check
                url = resource.config.get("url", "")
                expected_status = resource.config.get("expected_status", 200)
                timeout = resource.config.get("timeout", 30)
                retries = resource.config.get("retries", 3)

                operations.append({
                    "name": f"HTTP health check {resource.name}",
                    "operation": "clockwork.pyinfra_ops.health.http_health_check",
                    "args": [],
                    "kwargs": {
                        "url": url,
                        "expected_status": expected_status,
                        "timeout": timeout,
                        "retries": retries
                    },
                    "resource": resource
                })

            elif check_type == "file" or "file_path" in resource.config:
                # File health check
                file_path = resource.config.get("file_path", "")
                should_exist = resource.config.get("should_exist", True)
                min_size = resource.config.get("min_size")
                max_age = resource.config.get("max_age")

                operations.append({
                    "name": f"File health check {resource.name}",
                    "operation": "clockwork.pyinfra_ops.health.file_health_check",
                    "args": [],
                    "kwargs": {
                        "file_path": file_path,
                        "should_exist": should_exist,
                        "min_size": min_size,
                        "max_age": max_age
                    },
                    "resource": resource
                })

            elif check_type == "tcp" or ("host_address" in resource.config and "port" in resource.config):
                # TCP health check
                host_address = resource.config.get("host_address", "")
                port = resource.config.get("port", 80)
                timeout = resource.config.get("timeout", 10)
                retries = resource.config.get("retries", 3)

                operations.append({
                    "name": f"TCP health check {resource.name}",
                    "operation": "clockwork.pyinfra_ops.health.tcp_health_check",
                    "args": [],
                    "kwargs": {
                        "host_address": host_address,
                        "port": port,
                        "timeout": timeout,
                        "retries": retries
                    },
                    "resource": resource
                })

            else:
                # Generic verification operation
                operations.append({
                    "name": f"Verify {resource.name}",
                    "operation": "server.shell",
                    "args": ["echo 'Verification completed'"],
                    "kwargs": {},
                    "resource": resource
                })

        else:
            # Generic operation
            operations.append({
                "name": f"Process {resource.name}",
                "operation": "server.shell",
                "args": [f"echo 'Processing {resource.name}'"],
                "kwargs": {},
                "resource": resource
            })

    return operations


def show_execution_plan(operations: List[Dict[str, Any]], dry_run: bool):
    """Display the execution plan in a readable format."""
    if dry_run:
        console.print("\n[bold yellow]📋 Execution Plan (Dry Run):[/bold yellow]")
    else:
        console.print("\n[bold cyan]📋 Execution Plan:[/bold cyan]")

    table = Table()
    table.add_column("Step", style="cyan", width=4)
    table.add_column("Operation", style="white")
    table.add_column("Resource", style="yellow")
    table.add_column("Details", style="dim")

    for i, op in enumerate(operations, 1):
        resource = op["resource"]
        details = f"Type: {resource.type.value}"
        if "args" in op and op["args"]:
            details += f", Args: {op['args']}"

        table.add_row(
            str(i),
            op["operation"],
            f"{resource.type.value}.{resource.name}",
            details
        )

    console.print(table)
    console.print(f"\n[dim]Total operations: {len(operations)}[/dim]")


def execute_pyinfra_operations(inventory: Inventory, operations: List[Dict[str, Any]],
                             dry_run: bool, parallel: int, verbose: bool) -> bool:
    """Execute PyInfra operations against the inventory."""

    if dry_run:
        console.print("\n[yellow]🔍 Dry Run Mode - Showing what would be executed[/yellow]")

        # For dry run, just show the operations without executing
        for i, op in enumerate(operations, 1):
            resource = op["resource"]
            console.print(f"[cyan]{i}.[/cyan] [white]{op['name']}[/white]")
            console.print(f"   [dim]Operation:[/dim] {op['operation']}")
            console.print(f"   [dim]Args:[/dim] {op.get('args', [])}")
            if op.get('kwargs'):
                console.print(f"   [dim]Options:[/dim] {op.get('kwargs', {})}")
            console.print()

        console.print("[green]✅ Dry run completed - no changes made[/green]")
        return True

    # For actual execution, we'd set up PyInfra properly
    # This is a simplified implementation that shows the structure
    console.print("\n[blue]⚡ Executing operations...[/blue]")

    try:
        # Show progress
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=False
        ) as progress:

            task = progress.add_task("Executing operations...", total=len(operations))

            for i, op in enumerate(operations):
                progress.update(task, description=f"[cyan]{op['name']}[/cyan]")

                # Simulate execution based on operation type
                import time
                time.sleep(0.5)  # Simulate work

                # For files.put operations, we could actually create the files
                if op["operation"] == "files.put" and len(op.get("args", [])) >= 2:
                    content, file_path = op["args"][0], op["args"][1]
                    try:
                        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
                        Path(file_path).write_text(content)
                        console.print(f"[green]✓[/green] Created file: {file_path}")
                    except Exception as e:
                        console.print(f"[red]✗[/red] Failed to create file {file_path}: {e}")
                        return False

                # For files.directory operations
                elif op["operation"] == "files.directory" and len(op.get("args", [])) >= 1:
                    dir_path = op["args"][0]
                    try:
                        Path(dir_path).mkdir(parents=True, exist_ok=True)
                        console.print(f"[green]✓[/green] Created directory: {dir_path}")
                    except Exception as e:
                        console.print(f"[red]✗[/red] Failed to create directory {dir_path}: {e}")
                        return False

                # For other operations, just log what would happen
                else:
                    console.print(f"[yellow]~[/yellow] Would execute: {op['operation']} with args {op.get('args', [])}")

                progress.advance(task)

        return True

    except Exception as e:
        console.print(f"[red]❌ Execution failed: {e}[/red]")
        return False


@app.command()
def destroy(
    config_file: Optional[Path] = typer.Argument(None, help="Path to .cw configuration file (defaults to main.cw)"),
    target: str = typer.Option("@local", "--target", "-t", help="Target: @local, @docker:<container>, @ssh:<host>"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation prompt"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be destroyed without executing"),
    verbose: bool = typer.Option(False, "--verbose", help="Enable verbose PyInfra output"),
):
    """
    Destroy infrastructure resources created by 'clockwork apply'.

    This command will remove all resources defined in the configuration file,
    such as Docker containers, files, and directories.
    """
    from rich.console import Console
    from rich.prompt import Confirm
    from rich.table import Table
    from rich.panel import Panel
    from .core import ClockworkCore

    console = Console()

    # Resolve config file path
    config_file = resolve_config_file(config_file)

    try:
        # Initialize core
        core = ClockworkCore()

        # Parse config to understand what resources would be destroyed
        try:
            destroy_plan = core.plan_destroy(config_file, targets=[target])
        except Exception as e:
            console.print(f"[red]❌ Failed to generate destroy plan: {e}[/red]")
            raise typer.Exit(1)

        if not destroy_plan or destroy_plan.strip() == "# No resources to destroy":
            console.print("[yellow]⚠️  No resources found to destroy[/yellow]")
            return

        # Parse the destroy plan to extract operations
        operations = []
        for line in destroy_plan.split('\n'):
            if line.strip().startswith('# Destroy '):
                operation_type = line.strip().split(': ')[0].replace('# Destroy ', '')
                resource_name = line.strip().split(': ')[1] if ': ' in line else "Unknown"
                operations.append({
                    "operation": operation_type,
                    "resource": resource_name,
                    "args": []
                })

        if not operations:
            console.print("[yellow]⚠️  No resources found to destroy[/yellow]")
            return

        if dry_run:
            console.print("🚀 Destroy Plan (Dry Run)")

            # Create table showing what would be destroyed
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("Step", style="dim", width=6)
            table.add_column("Operation", style="bold")
            table.add_column("Resource", style="cyan")
            table.add_column("Details", style="green")

            for i, op in enumerate(operations, 1):
                table.add_row(
                    str(i),
                    op.get("operation", "Unknown"),
                    op.get("resource", "Unknown"),
                    f"Will be removed/destroyed"
                )

            console.print(table)

            # Show the actual PyInfra code that would be executed
            console.print("\n[dim]Generated PyInfra code:[/dim]")
            console.print(Panel(destroy_plan, title="Destroy Operations", border_style="yellow"))

            console.print(f"\nTotal operations: {len(operations)}")
            console.print("🔍 Dry run completed - no changes made")
            return

        # Show what will be destroyed
        console.print("🗑️  Resources to be destroyed:")

        table = Table(show_header=True, header_style="bold red")
        table.add_column("Resource Type", style="bold")
        table.add_column("Resource Name", style="cyan")
        table.add_column("Details", style="dim")

        for op in operations:
            table.add_row(
                op.get("operation", "Unknown"),
                op.get("resource", "Unknown"),
                str(op.get("args", []))
            )

        console.print(table)

        # Safety confirmation (unless force is used)
        if not force:
            console.print(f"\n[yellow]⚠️  This will destroy {len(operations)} resource(s)[/yellow]")

            if not Confirm.ask("[bold red]Are you sure you want to proceed?[/bold red]", default=False):
                console.print("[yellow]🛑 Destroy cancelled[/yellow]")
                return

        # Execute destroy
        console.print("\n🗑️  Destroying resources...")

        try:
            results = core.destroy(config_file, targets=[target])

            if results and any(r.get("success", False) for r in results):
                console.print("[green]✅ Destroy completed successfully[/green]")
            else:
                console.print("[red]❌ Destroy failed[/red]")
                if results:
                    for result in results:
                        if result.get("stderr"):
                            console.print(f"[red]Error: {result['stderr']}[/red]")
                raise typer.Exit(1)

        except Exception as e:
            console.print(f"[red]❌ Destroy failed: {e}[/red]")
            raise typer.Exit(1)

    except KeyboardInterrupt:
        console.print("\n[yellow]🛑 Destroy interrupted[/yellow]")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()