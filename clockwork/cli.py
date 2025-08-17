"""
Clockwork CLI - Command Line Interface for intelligent task execution.

Provides the main entry point and command definitions for the Clockwork tool.
Commands: plan, build, apply, verify
"""

import typer
import sys
from pathlib import Path
from typing import Optional, List
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.syntax import Syntax
from rich import print as rich_print

from .core import ClockworkCore
from .models import ClockworkConfig, Environment
from .__init__ import __version__


# Initialize Rich console for beautiful output
console = Console()
app = typer.Typer(
    name="clockwork",
    help="Factory for intelligent declarative tasks",
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
    config_file: Optional[Path] = typer.Option(
        None, "--config", "-c", help="Path to configuration file"
    ),
):
    """
    Clockwork - Factory for intelligent declarative tasks with AI assistance.
    
    Clockwork builds intelligent declarative tasks: Intake → Assembly → Forge
    - Intake: Parse .cw task definitions into Intermediate Representation (IR)
    - Assembly: Plan actions from IR (ActionList)  
    - Forge: Compile and execute task artifacts
    """
    # Set global verbose mode
    if verbose:
        console.print("[dim]Verbose mode enabled[/dim]")


@app.command()
def plan(
    path: Path = typer.Argument(".", help="Path to .cw configuration files"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Save plan to file"),
    var: List[str] = typer.Option([], "--var", help="Set variables (KEY=VALUE)"),
    dry_run: bool = typer.Option(True, "--dry-run/--no-dry-run", help="Show plan without applying"),
):
    """
    Generate and display execution plan from .cw files.
    
    Runs Intake → Assembly pipeline to show what actions would be executed.
    Does not call the compiler agent or execute anything.
    """
    console.print("[bold blue]🔍 Planning...[/bold blue]")
    
    try:
        # Initialize core
        core = ClockworkCore(config_path=path)
        
        # Parse variables
        variables = {}
        for var_str in var:
            if "=" not in var_str:
                console.print(f"[red]Error: Invalid variable format '{var_str}'. Use KEY=VALUE[/red]")
                raise typer.Exit(1)
            key, value = var_str.split("=", 1)
            variables[key] = value
        
        # Run intake and assembly
        ir = core.intake(path, variables)
        action_list = core.assembly(ir)
        
        # Display plan
        display_plan(action_list)
        
        # Save to file if requested
        if output:
            output.write_text(action_list.to_json())
            console.print(f"[green]Plan saved to {output}[/green]")
            
        console.print("[green]✅ Planning completed successfully[/green]")
        
    except Exception as e:
        console.print(f"[red]❌ Planning failed: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def build(
    path: Path = typer.Argument(".", help="Path to .cw configuration files"),
    output_dir: Optional[Path] = typer.Option(None, "--output", "-o", help="Build output directory"),
    var: List[str] = typer.Option([], "--var", help="Set variables (KEY=VALUE)"),
    force: bool = typer.Option(False, "--force", help="Force rebuild even if up-to-date"),
):
    """
    Compile .cw configuration into executable artifacts.
    
    Runs Intake → Assembly → Forge (compile only) to generate scripts.
    Calls the compiler agent but does not execute the artifacts.
    """
    console.print("[bold blue]🔨 Building...[/bold blue]")
    
    try:
        # Initialize core
        core = ClockworkCore(config_path=path)
        
        # Parse variables
        variables = {}
        for var_str in var:
            if "=" not in var_str:
                console.print(f"[red]Error: Invalid variable format '{var_str}'. Use KEY=VALUE[/red]")
                raise typer.Exit(1)
            key, value = var_str.split("=", 1)
            variables[key] = value
        
        # Run full pipeline except execution
        ir = core.intake(path, variables)
        action_list = core.assembly(ir)
        artifact_bundle = core.forge_compile(action_list)
        
        # Save artifacts
        build_dir = output_dir or Path(".clockwork/build")
        core.save_artifacts(artifact_bundle, build_dir)
        
        # Display build results
        display_build_results(artifact_bundle, build_dir)
        
        console.print("[green]✅ Build completed successfully[/green]")
        
    except Exception as e:
        console.print(f"[red]❌ Build failed: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def apply(
    path: Path = typer.Argument(".", help="Path to .cw configuration files"),
    var: List[str] = typer.Option([], "--var", help="Set variables (KEY=VALUE)"),
    force: bool = typer.Option(False, "--force", help="Skip confirmation prompts"),
    timeout_per_step: int = typer.Option(300, help="Timeout per step in seconds"),
    auto_approve: bool = typer.Option(False, "--auto-approve", help="Skip approval prompt"),
):
    """
    Apply .cw configuration by building and executing artifacts.
    
    Runs the complete pipeline: Intake → Assembly → Forge (compile + execute).
    This will execute your declared tasks.
    """
    console.print("[bold blue]🚀 Applying...[/bold blue]")
    
    try:
        # Initialize core
        core = ClockworkCore(config_path=path)
        
        # Parse variables
        variables = {}
        for var_str in var:
            if "=" not in var_str:
                console.print(f"[red]Error: Invalid variable format '{var_str}'. Use KEY=VALUE[/red]")
                raise typer.Exit(1)
            key, value = var_str.split("=", 1)
            variables[key] = value
        
        # Run planning first
        ir = core.intake(path, variables)
        action_list = core.assembly(ir)
        
        # Show plan and ask for confirmation
        console.print("\n[bold yellow]📋 Execution Plan:[/bold yellow]")
        display_plan(action_list)
        
        if not auto_approve:
            confirm = typer.confirm("\nDo you want to apply these changes?")
            if not confirm:
                console.print("[yellow]Apply cancelled by user[/yellow]")
                raise typer.Exit(0)
        
        # Compile and execute
        console.print("\n[bold blue]🔨 Compiling artifacts...[/bold blue]")
        artifact_bundle = core.forge_compile(action_list)
        
        console.print("[bold blue]⚡ Executing artifacts...[/bold blue]")
        results = core.forge_execute(artifact_bundle, timeout_per_step)
        
        # Display results
        display_execution_results(results)
        
        console.print("[green]✅ Apply completed successfully[/green]")
        
    except Exception as e:
        console.print(f"[red]❌ Apply failed: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def verify(
    path: Path = typer.Argument(".", help="Path to .cw configuration files"),
    var: List[str] = typer.Option([], "--var", help="Set variables (KEY=VALUE)"),
    timeout: int = typer.Option(60, help="Verification timeout in seconds"),
):
    """
    Run verification steps to check task completion and health.
    
    Executes only the verification actions from the plan (e.g., health checks, 
    connectivity tests) without making any changes.
    """
    console.print("[bold blue]🔍 Verifying...[/bold blue]")
    
    try:
        # Initialize core  
        core = ClockworkCore(config_path=path)
        
        # Parse variables
        variables = {}
        for var_str in var:
            if "=" not in var_str:
                console.print(f"[red]Error: Invalid variable format '{var_str}'. Use KEY=VALUE[/red]")
                raise typer.Exit(1)
            key, value = var_str.split("=", 1)
            variables[key] = value
        
        # Run verification
        ir = core.intake(path, variables)
        action_list = core.assembly(ir)
        results = core.verify_only(action_list, timeout)
        
        # Display verification results
        display_verification_results(results)
        
        console.print("[green]✅ Verification completed[/green]")
        
    except Exception as e:
        console.print(f"[red]❌ Verification failed: {e}[/red]")
        raise typer.Exit(1)


# =============================================================================
# Display Helper Functions
# =============================================================================

def display_plan(action_list):
    """Display execution plan in a nice table."""
    table = Table(title="Execution Plan", show_header=True, header_style="bold magenta")
    table.add_column("Step", style="dim", width=4)
    table.add_column("Action", style="cyan", width=20)
    table.add_column("Type", style="green", width=15)
    table.add_column("Details", style="white", width=40)
    
    for i, action in enumerate(action_list.steps, 1):
        details = ", ".join([f"{k}={v}" for k, v in list(action.args.items())[:3]])
        if len(action.args) > 3:
            details += "..."
        table.add_row(str(i), action.name, action.type.value, details)
    
    console.print(table)


def display_build_results(artifact_bundle, build_dir):
    """Display build results."""
    table = Table(title="Generated Artifacts", show_header=True, header_style="bold green")
    table.add_column("File", style="cyan")
    table.add_column("Language", style="green")
    table.add_column("Purpose", style="yellow")
    table.add_column("Mode", style="dim")
    
    for artifact in artifact_bundle.artifacts:
        table.add_row(artifact.path, artifact.lang, artifact.purpose, artifact.mode)
    
    console.print(table)
    console.print(f"\n[green]Artifacts saved to: {build_dir}[/green]")


def display_execution_results(results):
    """Display execution results."""
    table = Table(title="Execution Results", show_header=True, header_style="bold blue")
    table.add_column("Step", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Duration", style="yellow")
    table.add_column("Output", style="white")
    
    for result in results:
        status_color = "green" if result.get("success") else "red"
        status = "✅ SUCCESS" if result.get("success") else "❌ FAILED"
        duration = f"{result.get('duration', 0):.2f}s"
        output = result.get("output", "")[:50] + ("..." if len(result.get("output", "")) > 50 else "")
        
        table.add_row(
            result.get("step", "unknown"),
            f"[{status_color}]{status}[/{status_color}]",
            duration,
            output
        )
    
    console.print(table)


def display_verification_results(results):
    """Display verification results."""
    table = Table(title="Verification Results", show_header=True, header_style="bold cyan")
    table.add_column("Check", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Message", style="white")
    
    for result in results:
        status_color = "green" if result.get("passed") else "red"
        status = "✅ PASS" if result.get("passed") else "❌ FAIL"
        
        table.add_row(
            result.get("check", "unknown"),
            f"[{status_color}]{status}[/{status_color}]",
            result.get("message", "")
        )
    
    console.print(table)


# =============================================================================
# Additional Commands
# =============================================================================

@app.command()
def status(
    path: Path = typer.Argument(".", help="Path to .cw configuration files"),
):
    """Show current status of declared tasks."""
    console.print("[bold blue]📊 Status[/bold blue]")
    
    try:
        core = ClockworkCore(config_path=path)
        state = core.get_current_state()
        
        if not state:
            console.print("[yellow]No state found. Run 'clockwork apply' first.[/yellow]")
            return
        
        # Display state summary
        table = Table(title="Task Status", show_header=True, header_style="bold green")
        table.add_column("Resource", style="cyan")
        table.add_column("Type", style="green")
        table.add_column("Status", style="yellow")
        table.add_column("Last Applied", style="dim")
        
        for resource_id, resource_state in state.current_resources.items():
            last_applied = resource_state.last_applied.strftime("%Y-%m-%d %H:%M:%S") if resource_state.last_applied else "Never"
            table.add_row(
                resource_id,
                resource_state.type.value,
                resource_state.status.value,
                last_applied
            )
        
        console.print(table)
        
    except Exception as e:
        console.print(f"[red]❌ Failed to get status: {e}[/red]")
        raise typer.Exit(1)


@app.command() 
def init(
    name: str = typer.Argument(..., help="Project name"),
    path: Path = typer.Argument(".", help="Directory to initialize"),
):
    """Initialize a new Clockwork project."""
    console.print(f"[bold blue]🏗️  Initializing Clockwork project '{name}'[/bold blue]")
    
    try:
        project_path = path / name if path != Path(".") else path
        project_path.mkdir(exist_ok=True)
        
        # Create basic project structure
        (project_path / ".clockwork").mkdir(exist_ok=True)
        (project_path / "modules").mkdir(exist_ok=True)
        
        # Create main.cw example
        main_cw = project_path / "main.cw"
        main_cw.write_text(f'''# {name} - Clockwork Task Configuration

variable "app_name" {{
  type        = "string"
  default     = "{name}"
  description = "Application name"
}}

variable "port" {{
  type    = "number"
  default = 8080
}}

resource "service" "app" {{
  name    = var.app_name
  image   = "nginx:latest"
  ports   = [{{
    external = var.port
    internal = 80
  }}]
  
  health_check {{
    path     = "/"
    interval = "30s"
  }}
}}

output "app_url" {{
  value = "http://localhost:${{var.port}}"
}}
''')
        
        # Create .clockworkignore
        ignore_file = project_path / ".clockworkignore" 
        ignore_file.write_text("""# Clockwork ignore file
.git/
*.log
.clockwork/build/
.clockwork/cache/
""")
        
        console.print(f"[green]✅ Project '{name}' initialized at {project_path}[/green]")
        console.print(f"\nNext steps:")
        console.print(f"  cd {project_path}")
        console.print(f"  clockwork plan")
        console.print(f"  clockwork apply")
        
    except Exception as e:
        console.print(f"[red]❌ Failed to initialize project: {e}[/red]")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()