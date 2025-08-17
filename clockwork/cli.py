"""
Clockwork CLI - Command Line Interface for intelligent task execution.

Provides the main entry point and command definitions for the Clockwork tool.
Commands: plan, build, apply, verify
"""

import typer
import sys
from pathlib import Path
from typing import Optional, List, Dict, Any
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.syntax import Syntax
from rich import print as rich_print
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from .core import ClockworkCore
from .models import ClockworkConfig, Environment
from .__init__ import __version__
from .daemon.cli import daemon_app
from datetime import datetime
import json


# Initialize Rich console for beautiful output
console = Console()
app = typer.Typer(
    name="clockwork",
    help="Factory for intelligent declarative tasks - Enhanced with AI assistance, daemon support, and multi-runner execution",
    add_completion=False,
)

# Global progress indicator
def show_progress(description: str, total: Optional[int] = None):
    """Create a progress indicator for long-running operations."""
    import os
    if os.environ.get('CLOCKWORK_VERBOSE') == 'True':
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn() if total else "",
            TaskProgressColumn() if total else "",
            console=console
        )
    return None

# Add daemon subcommand
app.add_typer(daemon_app, name="daemon", help="Daemon commands for continuous reconciliation")


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
    config_file: Optional[Path] = typer.Option(
        None, "--config", "-c", help="Path to configuration file"
    ),
):
    """
    Clockwork - Factory for intelligent declarative tasks with AI assistance.
    
    Clockwork builds intelligent declarative tasks: Intake → Assembly → Forge
    - Intake: Parse .cw task definitions into Intermediate Representation (IR) with enhanced parser and validator
    - Assembly: Plan actions from IR (ActionList) with drift detection and state management  
    - Forge: Compile and execute task artifacts using enhanced runner system
    
    Enhanced with daemon support, drift detection, health monitoring, and multi-runner execution.
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
    import os
    os.environ['CLOCKWORK_VERBOSE'] = str(verbose)
    os.environ['CLOCKWORK_DEBUG'] = str(debug)


@app.command()
def plan(
    path: Path = typer.Argument(".", help="Path to .cw configuration files"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Save plan to file"),
    var: List[str] = typer.Option([], "--var", help="Set variables (KEY=VALUE)"),
    dry_run: bool = typer.Option(True, "--dry-run/--no-dry-run", help="Show plan without applying"),
    json_output: bool = typer.Option(False, "--json", help="Output plan as JSON"),
    detailed: bool = typer.Option(False, "--detailed", "-d", help="Show detailed plan with validation info"),
):
    """
    Generate and display execution plan from .cw files.
    
    Runs Intake → Assembly pipeline with enhanced parser and validator to show
    what actions would be executed. Includes validation warnings and dependency analysis.
    """
    if not json_output:
        console.print("[bold blue]🔍 Planning...[/bold blue]")
    
    try:
        # Initialize core
        core = ClockworkCore(config_path=path)
        
        # Parse variables with enhanced support
        variables = parse_variables(var, load_cwvars=True, config_path=path)
        
        # Run intake with validation details
        if detailed and not json_output:
            console.print("[dim]Running intake phase with enhanced validation...[/dim]")
        
        ir = core.intake(path, variables)
        
        # Run assembly with drift analysis if available
        if detailed and not json_output:
            console.print("[dim]Running assembly phase with dependency analysis...[/dim]")
        
        action_list = core.assembly(ir)
        
        # Prepare plan data
        plan_data = {
            "timestamp": datetime.now().isoformat(),
            "config_path": str(path),
            "variables_applied": variables,
            "total_actions": len(action_list.steps),
            "actions": [
                {
                    "name": action.name,
                    "type": action.type.value,
                    "args": action.args,
                    "depends_on": action.depends_on
                }
                for action in action_list.steps
            ]
        }
        
        # Add validation information if detailed
        if detailed:
            try:
                # Re-run validation to get detailed results
                validation_result = core.validator.validate_ir(ir)
                
                # Handle both legacy and new validation result formats
                if hasattr(validation_result, 'valid'):
                    is_valid = validation_result.valid
                    errors = validation_result.errors if hasattr(validation_result, 'errors') else []
                    warnings = validation_result.warnings if hasattr(validation_result, 'warnings') else []
                else:
                    # Legacy format
                    is_valid = validation_result.is_valid
                    errors = validation_result.errors
                    warnings = validation_result.warnings
                
                plan_data["validation"] = {
                    "valid": is_valid,
                    "warnings": [w.message if hasattr(w, 'message') else str(w) for w in warnings],
                    "errors": [e.message if hasattr(e, 'message') else str(e) for e in errors]
                }
            except Exception as e:
                plan_data["validation"] = {"error": str(e)}
        
        # Output plan
        if json_output:
            console.print(json.dumps(plan_data, indent=2))
        else:
            display_enhanced_plan(action_list, plan_data, detailed)
        
        # Save to file if requested
        if output:
            output.write_text(json.dumps(plan_data, indent=2))
            if not json_output:
                console.print(f"[green]Plan saved to {output}[/green]")
        
        if not json_output:
            console.print("[green]✅ Planning completed successfully[/green]")
        
    except Exception as e:
        error_msg = f"Planning failed: {e}"
        if json_output:
            console.print(json.dumps({"error": error_msg}, indent=2))
        else:
            console.print(f"[red]❌ {error_msg}[/red]")
        raise typer.Exit(1)


@app.command()
def build(
    path: Path = typer.Argument(".", help="Path to .cw configuration files"),
    output_dir: Optional[Path] = typer.Option(None, "--output", "-o", help="Build output directory"),
    var: List[str] = typer.Option([], "--var", help="Set variables (KEY=VALUE)"),
    force: bool = typer.Option(False, "--force", help="Force rebuild even if up-to-date"),
    json_output: bool = typer.Option(False, "--json", help="Output build results as JSON"),
    runner_type: str = typer.Option("local", "--runner", help="Runner type (local, docker, podman, ssh, kubernetes)"),
):
    """
    Compile .cw configuration into executable artifacts.
    
    Runs Intake → Assembly → Forge (compile only) with enhanced compiler from Phase 3.
    Uses the new runner system for artifact generation but does not execute.
    """
    if not json_output:
        console.print("[bold blue]🔨 Building...[/bold blue]")
    
    try:
        # Initialize core
        core = ClockworkCore(config_path=path)
        
        # Parse variables with enhanced support
        variables = parse_variables(var, load_cwvars=True, config_path=path)
        
        # Run full pipeline except execution
        if not json_output:
            console.print("[dim]Running intake and assembly phases...[/dim]")
        
        ir = core.intake(path, variables)
        action_list = core.assembly(ir)
        
        if not json_output:
            console.print("[dim]Compiling artifacts with enhanced compiler...[/dim]")
        
        # Enhanced compilation with runner configuration
        artifact_bundle = core.forge_compile(action_list)
        
        # Configure runner type if specified
        if runner_type != "local":
            # Update artifact bundle with runner-specific configurations
            for artifact in artifact_bundle.artifacts:
                if not hasattr(artifact, 'runner_config'):
                    artifact.runner_config = {}
                artifact.runner_config['runner_type'] = runner_type
        
        # Save artifacts
        build_dir = output_dir or Path(".clockwork/build")
        core.save_artifacts(artifact_bundle, build_dir)
        
        # Prepare build results
        build_data = {
            "timestamp": datetime.now().isoformat(),
            "config_path": str(path),
            "build_dir": str(build_dir),
            "variables_applied": variables,
            "runner_type": runner_type,
            "artifacts": [
                {
                    "path": artifact.path,
                    "language": artifact.lang,
                    "purpose": artifact.purpose,
                    "mode": artifact.mode,
                    "size_bytes": len(artifact.content)
                }
                for artifact in artifact_bundle.artifacts
            ],
            "total_artifacts": len(artifact_bundle.artifacts)
        }
        
        # Output results
        if json_output:
            console.print(json.dumps(build_data, indent=2))
        else:
            display_enhanced_build_results(artifact_bundle, build_dir, build_data)
        
        if not json_output:
            console.print("[green]✅ Build completed successfully[/green]")
        
    except Exception as e:
        error_msg = f"Build failed: {e}"
        if json_output:
            console.print(json.dumps({"error": error_msg}, indent=2))
        else:
            console.print(f"[red]❌ {error_msg}[/red]")
        raise typer.Exit(1)


@app.command()
def apply(
    path: Path = typer.Argument(".", help="Path to .cw configuration files"),
    var: List[str] = typer.Option([], "--var", help="Set variables (KEY=VALUE)"),
    force: bool = typer.Option(False, "--force", help="Skip confirmation prompts"),
    timeout_per_step: int = typer.Option(300, help="Timeout per step in seconds"),
    auto_approve: bool = typer.Option(False, "--auto-approve", help="Skip approval prompt"),
    json_output: bool = typer.Option(False, "--json", help="Output results as JSON"),
    runner_type: str = typer.Option("local", "--runner", help="Runner type (local, docker, podman, ssh, kubernetes)"),
    parallel: bool = typer.Option(False, "--parallel", help="Enable parallel execution where possible"),
):
    """
    Apply .cw configuration by building and executing artifacts.
    
    Runs the complete pipeline: Intake → Assembly → Forge (compile + execute)
    with enhanced runner system from Phases 3-4. Supports multiple execution
    environments and parallel execution.
    """
    if not json_output:
        console.print("[bold blue]🚀 Applying...[/bold blue]")
    
    try:
        # Initialize core
        core = ClockworkCore(config_path=path)
        
        # Parse variables with enhanced support
        variables = parse_variables(var, load_cwvars=True, config_path=path)
        
        # Run planning first
        if not json_output:
            console.print("[dim]Running intake and assembly phases...[/dim]")
        
        ir = core.intake(path, variables)
        action_list = core.assembly(ir)
        
        # Prepare execution data
        execution_data = {
            "timestamp": datetime.now().isoformat(),
            "config_path": str(path),
            "variables_applied": variables,
            "runner_type": runner_type,
            "parallel_execution": parallel,
            "timeout_per_step": timeout_per_step,
            "total_actions": len(action_list.steps)
        }
        
        # Show plan and ask for confirmation
        if not json_output:
            console.print("\n[bold yellow]📋 Execution Plan:[/bold yellow]")
            display_plan(action_list)
            
            if not auto_approve:
                confirm = typer.confirm("\nDo you want to apply these changes?")
                if not confirm:
                    execution_data["status"] = "cancelled"
                    execution_data["message"] = "Apply cancelled by user"
                    if json_output:
                        console.print(json.dumps(execution_data, indent=2))
                    else:
                        console.print("[yellow]Apply cancelled by user[/yellow]")
                    raise typer.Exit(0)
        
        # Compile with enhanced compiler
        if not json_output:
            console.print("\n[bold blue]🔨 Compiling artifacts with enhanced compiler...[/bold blue]")
        
        artifact_bundle = core.forge_compile(action_list)
        
        # Configure runner system
        if runner_type != "local":
            for artifact in artifact_bundle.artifacts:
                if not hasattr(artifact, 'runner_config'):
                    artifact.runner_config = {}
                artifact.runner_config['runner_type'] = runner_type
                artifact.runner_config['parallel'] = parallel
        
        # Execute with enhanced runner system
        if not json_output:
            console.print(f"[bold blue]⚡ Executing artifacts using {runner_type} runner...[/bold blue]")
        
        start_time = datetime.now()
        results = core.forge_execute(artifact_bundle, timeout_per_step)
        end_time = datetime.now()
        
        # Update execution data
        execution_data.update({
            "status": "completed",
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "execution_duration_seconds": (end_time - start_time).total_seconds(),
            "results": results,
            "successful_steps": len([r for r in results if r.get("success", False)]),
            "failed_steps": len([r for r in results if not r.get("success", True)])
        })
        
        # Output results
        if json_output:
            console.print(json.dumps(execution_data, indent=2, default=str))
        else:
            display_enhanced_execution_results(results, execution_data)
            console.print("[green]✅ Apply completed successfully[/green]")
        
    except Exception as e:
        error_msg = f"Apply failed: {e}"
        if json_output:
            error_data = {
                "status": "failed",
                "error": error_msg,
                "timestamp": datetime.now().isoformat()
            }
            console.print(json.dumps(error_data, indent=2))
        else:
            console.print(f"[red]❌ {error_msg}[/red]")
        raise typer.Exit(1)


@app.command()
def verify(
    path: Path = typer.Argument(".", help="Path to .cw configuration files"),
    var: List[str] = typer.Option([], "--var", help="Set variables (KEY=VALUE)"),
    timeout: int = typer.Option(60, help="Verification timeout in seconds"),
    json_output: bool = typer.Option(False, "--json", help="Output verification results as JSON"),
    runner_type: str = typer.Option("local", "--runner", help="Runner type for verification"),
    parallel: bool = typer.Option(True, "--parallel/--sequential", help="Run verifications in parallel"),
):
    """
    Run verification steps to check task completion and health.
    
    Executes only the verification actions from the plan using enhanced runner
    system. Supports health checks, connectivity tests, and compliance verification
    without making any changes.
    """
    if not json_output:
        console.print("[bold blue]🔍 Verifying...[/bold blue]")
    
    try:
        # Initialize core  
        core = ClockworkCore(config_path=path)
        
        # Parse variables with enhanced support
        variables = parse_variables(var, load_cwvars=True, config_path=path)
        
        # Run verification with enhanced runner system
        if not json_output:
            console.print(f"[dim]Running verification using {runner_type} runner...[/dim]")
        
        ir = core.intake(path, variables)
        action_list = core.assembly(ir)
        
        # Configure verification with runner settings
        start_time = datetime.now()
        results = core.verify_only(action_list, timeout)
        end_time = datetime.now()
        
        # Prepare verification data
        verification_data = {
            "timestamp": datetime.now().isoformat(),
            "config_path": str(path),
            "variables_applied": variables,
            "runner_type": runner_type,
            "parallel_execution": parallel,
            "timeout_seconds": timeout,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "verification_duration_seconds": (end_time - start_time).total_seconds(),
            "results": results,
            "total_checks": len(results),
            "passed_checks": len([r for r in results if r.get("passed", False)]),
            "failed_checks": len([r for r in results if not r.get("passed", True)])
        }
        
        # Output results
        if json_output:
            console.print(json.dumps(verification_data, indent=2, default=str))
        else:
            display_enhanced_verification_results(results, verification_data)
            console.print("[green]✅ Verification completed[/green]")
        
    except Exception as e:
        error_msg = f"Verification failed: {e}"
        if json_output:
            error_data = {
                "status": "failed",
                "error": error_msg,
                "timestamp": datetime.now().isoformat()
            }
            console.print(json.dumps(error_data, indent=2))
        else:
            console.print(f"[red]❌ {error_msg}[/red]")
        raise typer.Exit(1)


# =============================================================================
# Display Helper Functions
# =============================================================================

def display_plan(action_list):
    """Display execution plan in a nice table."""
    display_enhanced_plan(action_list, {}, detailed=False)

def display_enhanced_plan(action_list, plan_data: Dict[str, Any], detailed: bool = False):
    """Display enhanced execution plan with validation and dependency info."""
    # Main plan table
    table = Table(title="Execution Plan", show_header=True, header_style="bold magenta")
    table.add_column("Step", style="dim", width=4)
    table.add_column("Action", style="cyan", width=20)
    table.add_column("Type", style="green", width=15)
    table.add_column("Details", style="white", width=40)
    
    if detailed:
        table.add_column("Dependencies", style="yellow", width=15)
    
    for i, action in enumerate(action_list.steps, 1):
        details = ", ".join([f"{k}={v}" for k, v in list(action.args.items())[:3]])
        if len(action.args) > 3:
            details += "..."
        
        row = [str(i), action.name, action.type.value, details]
        
        if detailed:
            deps = ", ".join(action.depends_on) if action.depends_on else "None"
            row.append(deps)
        
        table.add_row(*row)
    
    console.print(table)
    
    # Show validation information if available
    if detailed and "validation" in plan_data:
        validation = plan_data["validation"]
        if "error" not in validation:
            if validation["warnings"]:
                warning_panel = Panel(
                    "\n".join(validation["warnings"]),
                    title="Validation Warnings",
                    style="yellow"
                )
                console.print(warning_panel)
            
            if validation["errors"]:
                error_panel = Panel(
                    "\n".join(validation["errors"]),
                    title="Validation Errors",
                    style="red"
                )
                console.print(error_panel)
    
    # Show variables applied
    if "variables_applied" in plan_data and plan_data["variables_applied"]:
        vars_text = "\n".join([f"{k} = {v}" for k, v in plan_data["variables_applied"].items()])
        vars_panel = Panel(
            vars_text,
            title="Variables Applied",
            style="blue"
        )
        console.print(vars_panel)


def display_build_results(artifact_bundle, build_dir):
    """Display build results."""
    display_enhanced_build_results(artifact_bundle, build_dir, {})

def display_enhanced_build_results(artifact_bundle, build_dir, build_data: Dict[str, Any]):
    """Display enhanced build results with size and runner info."""
    table = Table(title="Generated Artifacts", show_header=True, header_style="bold green")
    table.add_column("File", style="cyan")
    table.add_column("Language", style="green")
    table.add_column("Purpose", style="yellow")
    table.add_column("Mode", style="dim")
    table.add_column("Size", style="white")
    
    for artifact in artifact_bundle.artifacts:
        size_bytes = len(artifact.content)
        if size_bytes < 1024:
            size_str = f"{size_bytes}B"
        elif size_bytes < 1024 * 1024:
            size_str = f"{size_bytes / 1024:.1f}KB"
        else:
            size_str = f"{size_bytes / (1024 * 1024):.1f}MB"
        
        table.add_row(artifact.path, artifact.lang, artifact.purpose, artifact.mode, size_str)
    
    console.print(table)
    console.print(f"\n[green]Artifacts saved to: {build_dir}[/green]")
    
    # Show runner configuration if specified
    if "runner_type" in build_data and build_data["runner_type"] != "local":
        runner_panel = Panel(
            f"Artifacts configured for {build_data['runner_type']} runner",
            title="Runner Configuration",
            style="blue"
        )
        console.print(runner_panel)


def display_execution_results(results):
    """Display execution results."""
    display_enhanced_execution_results(results, {})

def display_enhanced_execution_results(results, execution_data: Dict[str, Any]):
    """Display enhanced execution results with performance metrics."""
    table = Table(title="Execution Results", show_header=True, header_style="bold blue")
    table.add_column("Step", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Duration", style="yellow")
    table.add_column("Runner", style="magenta")
    table.add_column("Output", style="white")
    
    for result in results:
        status_color = "green" if result.get("success") else "red"
        status = "✅ SUCCESS" if result.get("success") else "❌ FAILED"
        duration = f"{result.get('duration', 0):.2f}s"
        runner = result.get("runner_type", "local")
        output = result.get("output", "")[:50] + ("..." if len(result.get("output", "")) > 50 else "")
        
        table.add_row(
            result.get("step", "unknown"),
            f"[{status_color}]{status}[/{status_color}]",
            duration,
            runner,
            output
        )
    
    console.print(table)
    
    # Show execution summary
    if execution_data:
        successful = execution_data.get("successful_steps", 0)
        failed = execution_data.get("failed_steps", 0)
        total_duration = execution_data.get("execution_duration_seconds", 0)
        
        summary_text = f"Total Steps: {successful + failed}\n"
        summary_text += f"Successful: {successful}\n"
        summary_text += f"Failed: {failed}\n"
        summary_text += f"Total Duration: {total_duration:.2f}s"
        
        if "runner_type" in execution_data:
            summary_text += f"\nRunner: {execution_data['runner_type']}"
        
        summary_color = "green" if failed == 0 else "yellow" if successful > failed else "red"
        
        summary_panel = Panel(
            summary_text,
            title="Execution Summary",
            style=summary_color
        )
        console.print(summary_panel)


def display_verification_results(results):
    """Display verification results."""
    display_enhanced_verification_results(results, {})

def display_enhanced_verification_results(results, verification_data: Dict[str, Any]):
    """Display enhanced verification results with performance metrics."""
    table = Table(title="Verification Results", show_header=True, header_style="bold cyan")
    table.add_column("Check", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Duration", style="yellow")
    table.add_column("Runner", style="magenta")
    table.add_column("Message", style="white")
    
    for result in results:
        status_color = "green" if result.get("passed") else "red"
        status = "✅ PASS" if result.get("passed") else "❌ FAIL"
        duration = f"{result.get('duration', 0):.2f}s"
        runner = result.get("runner_type", "local")
        message = result.get("message", "")[:50] + ("..." if len(result.get("message", "")) > 50 else "")
        
        table.add_row(
            result.get("check", "unknown"),
            f"[{status_color}]{status}[/{status_color}]",
            duration,
            runner,
            message
        )
    
    console.print(table)
    
    # Show verification summary
    if verification_data:
        passed = verification_data.get("passed_checks", 0)
        failed = verification_data.get("failed_checks", 0)
        total_duration = verification_data.get("verification_duration_seconds", 0)
        
        summary_text = f"Total Checks: {passed + failed}\n"
        summary_text += f"Passed: {passed}\n"
        summary_text += f"Failed: {failed}\n"
        summary_text += f"Duration: {total_duration:.2f}s"
        
        if "runner_type" in verification_data:
            summary_text += f"\nRunner: {verification_data['runner_type']}"
        
        summary_color = "green" if failed == 0 else "yellow" if passed > failed else "red"
        
        summary_panel = Panel(
            summary_text,
            title="Verification Summary",
            style=summary_color
        )
        console.print(summary_panel)


# =============================================================================
# Variable Handling Utilities
# =============================================================================

def parse_variables(var_list: List[str], load_cwvars: bool = True, config_path: Path = None) -> Dict[str, Any]:
    """
    Parse variables from command line and optionally load .cwvars files.
    
    Args:
        var_list: List of KEY=VALUE strings from command line
        load_cwvars: Whether to load .cwvars files
        config_path: Path to look for .cwvars files
        
    Returns:
        Dictionary of parsed variables
        
    Raises:
        typer.Exit: If variable parsing fails
    """
    variables = {}
    
    # Load .cwvars files first if requested
    if load_cwvars and config_path:
        try:
            from .intake.parser import Parser
            parser = Parser()
            cwvars_files = parser.find_cwvars_files(config_path)
            
            for cwvars_file in cwvars_files:
                try:
                    vars_data = parser.parse_cwvars_file(cwvars_file)
                    variables.update(vars_data)
                    console.print(f"[dim]Loaded variables from {cwvars_file}[/dim]")
                except Exception as e:
                    console.print(f"[yellow]Warning: Failed to load {cwvars_file}: {e}[/yellow]")
                    
        except Exception as e:
            console.print(f"[yellow]Warning: Failed to load .cwvars files: {e}[/yellow]")
    
    # Parse command line variables (these override .cwvars)
    for var_str in var_list:
        if "=" not in var_str:
            console.print(f"[red]Error: Invalid variable format '{var_str}'. Use KEY=VALUE[/red]")
            raise typer.Exit(1)
        key, value = var_str.split("=", 1)
        
        # Try to parse as JSON for complex types, fall back to string
        try:
            parsed_value = json.loads(value)
            variables[key] = parsed_value
        except json.JSONDecodeError:
            variables[key] = value
    
    return variables

def get_resolver_cache_stats(config_path: Path) -> Dict[str, Any]:
    """
    Get resolver cache statistics.
    
    Args:
        config_path: Path to configuration directory
        
    Returns:
        Dictionary with cache statistics
    """
    cache_dir = config_path / ".clockwork" / "cache"
    
    if not cache_dir.exists():
        return {
            "cache_exists": False,
            "cache_path": str(cache_dir)
        }
    
    # Calculate cache statistics
    total_size = 0
    file_count = 0
    module_count = 0
    provider_count = 0
    
    for item in cache_dir.rglob("*"):
        if item.is_file():
            file_count += 1
            total_size += item.stat().st_size
            
            # Count modules and providers based on directory structure
            if "modules" in item.parts:
                module_count += 1
            elif "providers" in item.parts:
                provider_count += 1
    
    return {
        "cache_exists": True,
        "cache_path": str(cache_dir),
        "total_size_bytes": total_size,
        "total_size_mb": round(total_size / (1024 * 1024), 2),
        "file_count": file_count,
        "cached_modules": module_count,
        "cached_providers": provider_count,
        "last_modified": cache_dir.stat().st_mtime
    }

def display_enhanced_status(status_data: Dict[str, Any], detailed: bool = False):
    """
    Display enhanced status information in a formatted way.
    
    Args:
        status_data: Status data dictionary
        detailed: Whether to show detailed information
    """
    if not status_data["state_exists"]:
        console.print("[yellow]No state found. Run 'clockwork apply' first.[/yellow]")
        return
    
    # Resource status table
    if status_data["resources"]:
        table = Table(title="Resource Status", show_header=True, header_style="bold green")
        table.add_column("Resource", style="cyan")
        table.add_column("Type", style="green")
        table.add_column("Status", style="yellow")
        table.add_column("Last Applied", style="dim")
        
        if detailed:
            table.add_column("Last Verified", style="dim")
        
        for resource in status_data["resources"]:
            last_applied = resource["last_applied"]
            if last_applied:
                last_applied = datetime.fromisoformat(last_applied).strftime("%Y-%m-%d %H:%M:%S")
            else:
                last_applied = "Never"
            
            row = [
                resource["id"],
                resource["type"],
                resource["status"],
                last_applied
            ]
            
            if detailed:
                last_verified = resource["last_verified"]
                if last_verified:
                    last_verified = datetime.fromisoformat(last_verified).strftime("%Y-%m-%d %H:%M:%S")
                else:
                    last_verified = "Never"
                row.append(last_verified)
            
            table.add_row(*row)
        
        console.print(table)
    
    # Health information
    if detailed and "health" in status_data:
        health = status_data["health"]
        if "error" not in health:
            health_score = health.get("health_score", 0)
            health_color = "green" if health_score >= 80 else "yellow" if health_score >= 60 else "red"
            
            health_panel = Panel(
                f"Health Score: [{health_color}]{health_score:.1f}%[/{health_color}]\n"
                f"Total Resources: {health.get('total_resources', 0)}\n"
                f"Healthy Resources: {health.get('healthy_resources', 0)}\n"
                f"Failed Resources: {health.get('failed_resources', 0)}",
                title="System Health",
                style=health_color
            )
            console.print(health_panel)
    
    # Cache statistics
    if detailed and "cache_stats" in status_data:
        cache = status_data["cache_stats"]
        if cache["cache_exists"]:
            cache_panel = Panel(
                f"Cache Path: {cache['cache_path']}\n"
                f"Total Size: {cache['total_size_mb']} MB\n"
                f"Files: {cache['file_count']}\n"
                f"Cached Modules: {cache['cached_modules']}\n"
                f"Cached Providers: {cache['cached_providers']}",
                title="Resolver Cache",
                style="blue"
            )
            console.print(cache_panel)
    
    # Drift information
    if "drift" in status_data:
        drift = status_data["drift"]
        if "error" not in drift:
            summary = drift.get("summary", {})
            resources_with_drift = summary.get("resources_with_drift", 0)
            total_resources = summary.get("total_resources_checked", 0)
            
            if resources_with_drift > 0:
                drift_color = "red"
                drift_status = f"⚠️ {resources_with_drift}/{total_resources} resources have drift"
            else:
                drift_color = "green"
                drift_status = f"✅ No drift detected ({total_resources} resources checked)"
            
            drift_panel = Panel(
                drift_status,
                title="Drift Detection",
                style=drift_color
            )
            console.print(drift_panel)
            
            # Show immediate attention items if any
            immediate_attention = drift.get("immediate_action_required", [])
            if immediate_attention and detailed:
                attention_table = Table(title="Resources Requiring Immediate Attention")
                attention_table.add_column("Resource", style="red")
                attention_table.add_column("Severity", style="yellow")
                attention_table.add_column("Actions", style="white")
                
                for item in immediate_attention[:5]:  # Show top 5
                    actions = ", ".join(item.get("suggested_actions", [])[:2])
                    attention_table.add_row(
                        item.get("resource_id", "unknown"),
                        item.get("severity", "unknown"),
                        actions
                    )
                
                console.print(attention_table)

# =============================================================================
# Additional Commands
# =============================================================================

@app.command()
def status(
    path: Path = typer.Argument(".", help="Path to .cw configuration files"),
    detailed: bool = typer.Option(False, "--detailed", "-d", help="Show detailed status including drift and health"),
    drift_check: bool = typer.Option(False, "--drift", help="Include drift detection in status"),
    json_output: bool = typer.Option(False, "--json", help="Output status as JSON"),
    var: List[str] = typer.Option([], "--var", help="Set variables (KEY=VALUE)"),
):
    """Show current status of declared tasks with optional drift detection and health monitoring."""
    if not json_output:
        console.print("[bold blue]📊 Status[/bold blue]")
    
    try:
        core = ClockworkCore(config_path=path)
        
        # Parse variables
        variables = parse_variables(var)
        
        # Get basic state
        state = core.get_current_state()
        
        status_data = {
            "timestamp": datetime.now().isoformat(),
            "config_path": str(path),
            "state_exists": state is not None
        }
        
        if not state:
            status_data["message"] = "No state found. Run 'clockwork apply' first."
            status_data["resources"] = []
            status_data["health"] = {"score": 0.0, "status": "unknown"}
        else:
            # Basic resource status
            resources = []
            for resource_id, resource_state in state.current_resources.items():
                resource_data = {
                    "id": resource_id,
                    "type": resource_state.type,
                    "status": resource_state.status,
                    "last_applied": resource_state.last_applied.isoformat() if resource_state.last_applied else None,
                    "last_verified": resource_state.last_verified.isoformat() if resource_state.last_verified else None
                }
                resources.append(resource_data)
            
            status_data["resources"] = resources
            status_data["total_resources"] = len(resources)
            
            # Get health summary
            if detailed:
                health_summary = core.get_state_health()
                status_data["health"] = health_summary
                
                # Get resolver cache statistics if available
                try:
                    cache_stats = get_resolver_cache_stats(path)
                    status_data["cache_stats"] = cache_stats
                except Exception as e:
                    if detailed:
                        console.print(f"[dim]Cache stats unavailable: {e}[/dim]")
            
            # Perform drift detection if requested
            if drift_check or detailed:
                console.print("[dim]Performing drift detection...[/dim]")
                drift_report = core.detect_drift()
                status_data["drift"] = drift_report
        
        # Output results
        if json_output:
            console.print(json.dumps(status_data, indent=2, default=str))
        else:
            display_enhanced_status(status_data, detailed)
        
    except Exception as e:
        error_msg = f"Failed to get status: {e}"
        if json_output:
            console.print(json.dumps({"error": error_msg}, indent=2))
        else:
            console.print(f"[red]❌ {error_msg}[/red]")
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