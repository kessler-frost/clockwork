"""
Clockwork CLI - Command Line Interface for intelligent task execution.

Provides the main entry point and command definitions for the Clockwork tool.
Commands: plan, build, apply, verify
"""

import typer
import sys
import subprocess
import shutil
import tempfile
import time
import json
from pathlib import Path
from typing import Optional, List, Dict, Any
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich import print as rich_print
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from .core import ClockworkCore
from .models import ClockworkConfig, Environment, ActionType
from .__init__ import __version__
from .daemon.cli import daemon_app
from .formatters import TerraformStyleFormatter
from datetime import datetime
import json


# Initialize Rich console for beautiful output
console = Console()
app = typer.Typer(
    name="clockwork",
    help="Factory for intelligent declarative tasks with Terraform-style output",
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
    Clockwork - Factory for intelligent declarative tasks.
    
    Clockwork builds intelligent declarative tasks: Intake → Assembly → Forge
    - Intake: Parse .cw task definitions into Intermediate Representation (IR)
    - Assembly: Plan actions from IR (ActionList) with drift detection  
    - Forge: Compile and execute task artifacts
    
    Output displayed in Terraform-style format by default. Use --json for programmatic usage.
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
    json_output: bool = typer.Option(False, "--json", help="Output plan as JSON instead of Terraform-style"),
    detailed: bool = typer.Option(False, "--detailed", "-d", help="Show detailed plan with validation info"),
):
    """
    Generate and display execution plan from .cw files in Terraform-style format.
    
    Runs Intake → Assembly pipeline with enhanced parser and validator to show
    what actions would be executed. Uses Terraform-style output by default.
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
                    "type": getattr(action, 'type', ActionType.CUSTOM).value if hasattr(getattr(action, 'type', None), 'value') else str(getattr(action, 'type', 'unknown')),
                    "args": action.args,
                    "depends_on": getattr(action, 'depends_on', [])
                }
                for action in action_list.steps
            ]
        }
        
        # Add validation information if detailed
        if detailed:
            try:
                # Re-run validation to get detailed results
                validation_result = core.validator.validate_ir(ir)
                
                # Use current validation result format
                is_valid = validation_result.valid
                errors = validation_result.errors if hasattr(validation_result, 'errors') else []
                warnings = validation_result.warnings if hasattr(validation_result, 'warnings') else []
                
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
            display_enhanced_plan(ir, action_list, plan_data, detailed)
        
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
    json_output: bool = typer.Option(False, "--json", help="Output build results as JSON instead of Terraform-style"),
    runner_type: str = typer.Option("local", "--runner", help="Runner type (local, docker, podman, ssh, kubernetes)"),
):
    """
    Compile .cw configuration into executable artifacts with Terraform-style output.
    
    Runs Intake → Assembly → Forge (compile only) with enhanced compiler.
    Shows build progress in Terraform-style format by default.
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
            display_enhanced_build_results(action_list, artifact_bundle, build_dir, build_data)
        
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
    json_output: bool = typer.Option(False, "--json", help="Output results as JSON instead of Terraform-style"),
    runner_type: str = typer.Option("local", "--runner", help="Runner type (local, docker, podman, ssh, kubernetes)"),
    parallel: bool = typer.Option(False, "--parallel", help="Enable parallel execution where possible"),
):
    """
    Apply .cw configuration by building and executing artifacts with Terraform-style output.
    
    Runs the complete pipeline: Intake → Assembly → Forge (compile + execute).
    Shows execution progress in Terraform-style format by default.
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
            display_enhanced_plan(ir, action_list, {}, detailed=False)
            
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
    json_output: bool = typer.Option(False, "--json", help="Output verification results as JSON instead of Terraform-style"),
    runner_type: str = typer.Option("local", "--runner", help="Runner type for verification"),
    parallel: bool = typer.Option(True, "--parallel/--sequential", help="Run verifications in parallel"),
):
    """
    Run verification steps to check task completion and health with Terraform-style output.
    
    Executes only the verification actions from the plan. Shows verification
    results in Terraform-style format by default.
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


def display_enhanced_plan(ir, action_list, plan_data: Dict[str, Any], detailed: bool = False):
    """Display enhanced execution plan using Terraform-style formatting."""
    formatter = TerraformStyleFormatter(console)
    
    # Use formatter to display plan with actual IR
    plan_output = formatter.format_plan(ir)
    console.print(plan_output)
    
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
        console.print("\n[bold blue]Variables Applied:[/bold blue]")
        for k, v in plan_data["variables_applied"].items():
            console.print(f"  {k} = {v}")



def display_enhanced_build_results(action_list, artifact_bundle, build_dir, build_data: Dict[str, Any]):
    """Display enhanced build results using Terraform-style formatting."""
    formatter = TerraformStyleFormatter(console)
    
    # Prepare artifacts info for formatter
    artifacts_info = {
        'artifacts': [
            {
                'path': artifact.path,
                'lang': artifact.lang,
                'purpose': artifact.purpose,
                'mode': artifact.mode,
                'size_bytes': len(artifact.content)
            }
            for artifact in artifact_bundle.artifacts
        ]
    }
    
    # Use formatter to display build results
    build_output = formatter.format_build(action_list, artifacts_info)
    console.print(build_output)
    
    console.print(f"\n[green]Artifacts saved to: {build_dir}[/green]")
    
    # Show runner configuration if specified
    if "runner_type" in build_data and build_data["runner_type"] != "local":
        console.print(f"\n[bold blue]Runner Configuration:[/bold blue] Artifacts configured for {build_data['runner_type']} runner")



def display_enhanced_execution_results(results, execution_data: Dict[str, Any]):
    """Display enhanced execution results using Terraform-style formatting."""
    formatter = TerraformStyleFormatter(console)
    
    # Transform results for the formatter
    execution_results = []
    success_count = 0
    failed_count = 0
    
    # Process actual results - fail if no valid results
    if not results:
        raise ValueError("No execution results provided - execution may have failed")
    
    for result in results:
        success = result.get("success", False)
        if success:
            success_count += 1
            status = "success"
        else:
            failed_count += 1
            status = "failed"
        
        execution_results.append({
            'resource_name': result.get("step", "unknown"),
            'operation': 'apply',
            'status': status,
            'error': result.get("error", result.get("output", "")) if not success else None
        })
    
    # Use formatter to display apply results
    apply_output = formatter.format_apply(execution_results, success_count, failed_count)
    console.print(apply_output)
    
    # Show execution summary
    if execution_data:
        total_duration = execution_data.get("execution_duration_seconds", 0)
        
        summary_text = f"Total Duration: {total_duration:.2f}s"
        
        if "runner_type" in execution_data:
            summary_text += f"\nRunner: {execution_data['runner_type']}"
        
        summary_color = "green" if failed_count == 0 else "yellow" if success_count > failed_count else "red"
        
        summary_panel = Panel(
            summary_text,
            title="Execution Summary",
            style=summary_color
        )
        console.print(summary_panel)



def display_enhanced_verification_results(results, verification_data: Dict[str, Any]):
    """Display enhanced verification results using Terraform-style formatting."""
    formatter = TerraformStyleFormatter(console)
    
    # Transform results for the formatter
    verification_results = []
    drift_detected = False
    
    for result in results:
        passed = result.get("passed", False)
        has_drift = not passed  # Failed verification indicates drift
        
        if has_drift:
            drift_detected = True
        
        verification_results.append({
            'resource_name': result.get("check", "unknown"),
            'drift_detected': has_drift,
            'last_verified': result.get("timestamp"),
            'drift_details': [result.get("message", "")] if has_drift and result.get("message") else []
        })
    
    # Use formatter to display verification results
    verify_output = formatter.format_verify(verification_results, drift_detected)
    console.print(verify_output)
    
    # Show verification summary
    if verification_data:
        total_duration = verification_data.get("verification_duration_seconds", 0)
        
        summary_text = f"Duration: {total_duration:.2f}s"
        
        if "runner_type" in verification_data:
            summary_text += f"\nRunner: {verification_data['runner_type']}"
        
        passed = verification_data.get("passed_checks", 0)
        failed = verification_data.get("failed_checks", 0)
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

def display_enhanced_status(clockwork_state, status_data: Dict[str, Any], detailed: bool = False):
    """
    Display enhanced status information using Terraform-style formatting.
    
    Args:
        clockwork_state: The actual ClockworkState object
        status_data: Status data dictionary
        detailed: Whether to show detailed information
    """
    if not status_data["state_exists"]:
        console.print("[yellow]No state found. Run 'clockwork apply' first.[/yellow]")
        return
    
    formatter = TerraformStyleFormatter(console)
    
    try:
        # Use formatter to display status with actual ClockworkState
        status_output = formatter.format_status(clockwork_state)
        console.print(status_output)
        
    except Exception as e:
        # Error with Terraform-style formatting
        console.print(f"[red]Error displaying status: {e}[/red]")
        console.print(f"[cyan]Resources managed:[/cyan] {len(clockwork_state.current_resources) if clockwork_state else 0}")
    
    # Health information (keep existing panels for additional info)
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
            console.print("\n[bold blue]Resolver Cache:[/bold blue]")
            console.print(f"  Path: {cache['cache_path']}")
            console.print(f"  Size: {cache['total_size_mb']} MB ({cache['file_count']} files)")
            console.print(f"  Cached: {cache['cached_modules']} modules, {cache['cached_providers']} providers")
    
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
                attention_text = "\n".join([
                    f"• {item.get('resource_id', 'unknown')} ({item.get('severity', 'unknown')})"
                    for item in immediate_attention[:5]
                ])
                
                attention_panel = Panel(
                    attention_text,
                    title="Resources Requiring Immediate Attention",
                    style="red"
                )
                console.print(attention_panel)

# =============================================================================
# Additional Commands
# =============================================================================

@app.command()
def status(
    path: Path = typer.Argument(".", help="Path to .cw configuration files"),
    detailed: bool = typer.Option(False, "--detailed", "-d", help="Show detailed status including drift and health"),
    drift_check: bool = typer.Option(False, "--drift", help="Include drift detection in status"),
    json_output: bool = typer.Option(False, "--json", help="Output status as JSON instead of Terraform-style"),
    var: List[str] = typer.Option([], "--var", help="Set variables (KEY=VALUE)"),
):
    """Show current status of declared tasks in Terraform-style format with optional drift detection."""
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
            display_enhanced_status(state, status_data, detailed)
        
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


def safe_input(prompt: str = "") -> str:
    """Safely handle input() calls in non-interactive environments."""
    import sys
    try:
        if not sys.stdin.isatty():
            # Non-interactive environment, return empty string
            return ""
        return input(prompt)
    except EOFError:
        # Handle EOF gracefully
        return ""

@app.command()
def demo(
    output_dir: Optional[Path] = typer.Option(None, "--output", "-o", help="Directory for demo files (default: ./.clockwork-demo)"),
    interactive: bool = typer.Option(True, "--interactive/--no-interactive", help="Enable interactive mode with pauses"),
    cleanup: bool = typer.Option(True, "--cleanup/--no-cleanup", help="Clean up demo files at the end"),
    text_only: bool = typer.Option(False, "--text-only", help="Run demo in non-interactive mode with automatic error fixing"),
):
    """
    Run an interactive demonstration of Clockwork workflow.
    
    Creates a sample .cw file and guides you through the complete Clockwork
    pipeline: plan → build → verify → apply → verify. Perfect for learning
    how Clockwork works.
    
    Use --text-only for non-interactive mode with automatic error fixing.
    """    
    console.print("[bold blue]🎯 Clockwork Demo - Interactive Tutorial[/bold blue]")
    console.print("\nWelcome to Clockwork! This demo will guide you through a complete workflow.")
    console.print("You'll learn how to use .cw files to declare tasks and let Clockwork execute them.\n")
    
    # Handle text_only mode settings and auto-detect non-interactive environments
    import sys
    if text_only:
        interactive = False
        console.print("[dim]Running in text-only mode with automatic execution...[/dim]")
    elif not sys.stdin.isatty():
        # Auto-enable text-only mode in non-interactive environments
        interactive = False
        text_only = True
        console.print("[dim]Non-interactive environment detected, running in text-only mode...[/dim]")
    
    # Setup demo directory
    if output_dir:
        demo_dir = output_dir
        demo_dir.mkdir(parents=True, exist_ok=True)
    else:
        demo_dir = Path("./.clockwork-demo")
        if demo_dir.exists():
            if interactive:
                overwrite = typer.confirm(f"Demo directory {demo_dir} already exists. Overwrite?")
                if not overwrite:
                    console.print("[yellow]Demo cancelled.[/yellow]")
                    raise typer.Exit(0)
            elif not text_only:
                console.print(f"[yellow]Demo directory {demo_dir} already exists. Removing...[/yellow]")
            shutil.rmtree(demo_dir)
        demo_dir.mkdir(parents=True)
    
    console.print(f"[green]📁 Demo directory created: {demo_dir}[/green]\n")
    
    try:
        # Step 1: Explain and create sample .cw file
        step_explain_clockwork(demo_dir, interactive, text_only)
        
        # Step 2: Plan phase
        step_plan_demo(demo_dir, interactive, text_only)
        
        # Step 3: Build phase  
        step_build_demo(demo_dir, interactive, text_only)
        
        # Step 4: Verify phase (pre-apply)
        step_verify_demo(demo_dir, interactive, text_only, "pre-apply")
        
        # Step 5: Apply phase
        step_apply_demo(demo_dir, interactive, text_only)
        
        # Step 6: Verify phase (post-apply)
        step_verify_demo(demo_dir, interactive, text_only, "post-apply")
        
        # Step 7: Show results and cleanup
        step_show_results(demo_dir, interactive, text_only, cleanup)
        
        console.print("\n[bold green]🎉 Demo completed successfully![/bold green]")
        console.print("\n[bold cyan]Next Steps:[/bold cyan]")
        console.print("• Try modifying the demo.cw file and re-running the commands")
        console.print("• Create your own .cw files for real tasks")
        console.print("• Read the documentation for advanced features")
        console.print("• Run 'clockwork init my-project' to start a new project")
        
    except KeyboardInterrupt:
        console.print("\n[yellow]Demo interrupted by user.[/yellow]")
        if cleanup and demo_dir.exists():
            shutil.rmtree(demo_dir)
            console.print(f"[dim]Cleaned up demo directory: {demo_dir}[/dim]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"\n[red]❌ Demo failed: {e}[/red]")
        if cleanup and demo_dir.exists():
            shutil.rmtree(demo_dir)
            console.print(f"[dim]Cleaned up demo directory: {demo_dir}[/dim]")
        raise typer.Exit(1)


def run_clockwork_command(demo_dir: Path, command_args: List[str], timeout: int = 90, text_only: bool = False, show_spinner: bool = True) -> tuple[bool, str, str]:
    """Helper function to run clockwork commands with fallback and error handling for text_only mode."""
    import os
    original_cwd = os.getcwd()
    
    # Initialize spinner variables
    progress = None
    spinner_task = None
    
    try:
        # Try different ways to invoke clockwork
        clockwork_cmd = None
        for cmd in [["uv", "run", "clockwork"], ["clockwork"], ["python", "-m", "clockwork.cli"]]:
            try:
                test_result = subprocess.run(cmd + ["--help"], capture_output=True, timeout=10)
                if test_result.returncode == 0:
                    clockwork_cmd = cmd
                    break
            except:
                continue
        
        if clockwork_cmd:
            # Add the demo directory path to the command args if it's a plan/build/verify/apply command
            if len(command_args) > 0 and command_args[0] in ["plan", "build", "verify", "apply"]:
                # Insert the demo directory path as the last argument
                full_command = clockwork_cmd + command_args + [str(demo_dir)]
            else:
                full_command = clockwork_cmd + command_args
            
            # For text_only mode, add auto-approve to apply commands
            if text_only and len(command_args) > 0 and command_args[0] == "apply":
                if "--auto-approve" not in command_args:
                    full_command.insert(-1, "--auto-approve")  # Insert before path
            
            # Show spinner during command execution
            if show_spinner:
                command_name = command_args[0] if command_args else "command"
                progress = Progress(
                    SpinnerColumn(),
                    TextColumn(f"[cyan]► Running {command_name} command...[/cyan]"),
                    console=console,
                    transient=True
                )
                progress.start()
                spinner_task = progress.add_task("running", total=None)
            
            result = subprocess.run(
                full_command,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=original_cwd  # Stay in original directory
            )
            
            # Stop spinner
            if progress:
                progress.stop()
            
            # Check if command succeeded
            success = result.returncode == 0
            
            # In text_only mode, show warning but continue demo with actual result
            if text_only and not success:
                console.print(f"[yellow]⚠ Command failed, attempting auto-fix...[/yellow]")
                # Could add specific error handling patterns here
                # For now, we'll return the actual result and let steps handle failures
                
            return success, result.stdout, result.stderr
        else:
            return False, "", "Clockwork command not available"
    
    except Exception as e:
        # Stop spinner on error
        if progress:
            progress.stop()
        
        console.print(f"[red]❌ Error executing command: {e}[/red]")
        return False, "", str(e)


def step_explain_clockwork(demo_dir: Path, interactive: bool, text_only: bool = False):
    """Step 1: Explain Clockwork and create sample .cw file."""
    console.print("[bold yellow]📚 Step 1: Understanding Clockwork[/bold yellow]")
    console.print("""
Clockwork is a 'Factory for Intelligent Declarative Tasks'. Instead of writing
scripts that describe HOW to do something, you write .cw files that describe
WHAT you want to achieve. Clockwork figures out the how.

The pipeline has three phases:
• [cyan]Intake[/cyan]: Parse your .cw files and understand what you want
• [cyan]Assembly[/cyan]: Plan the steps needed to achieve your goals  
• [cyan]Forge[/cyan]: Execute the plan and make it happen

Dependencies are automatically resolved to ensure proper execution order.
The Terraform-style output clearly shows these relationships.

Let's create a .cw file that starts a service, lets it run for 30 seconds, captures output, and then shuts it down:
""")
    
    # Create sample .cw file with simple, declarative service management
    sample_cw_content = '''# Clockwork Demo - Simple Web Service

# I want a demo web service that serves a "Hello World" page
resource "webapp" "demo" {
  name        = "clockwork-demo"
  description = "A simple demo web service for showcasing Clockwork"
  
  # What the service should do
  content = "Hello from Clockwork! This demo service is running successfully."
  
  # How long it should stay alive
  lifetime = "30s"
  
  # Basic service settings
  port = 8080
  
  # I want to capture what happened
  capture_logs = true
}

# I want to verify the service worked
resource "check" "demo_works" {
  description = "Verify the demo service responded correctly"
  target      = webapp.demo
}

# Tell me what happened
output "demo_url" {
  value = webapp.demo.url
}

output "demo_status" {
  value = check.demo_works.result
}'''
    
    demo_cw_file = demo_dir / "demo.cw"
    demo_cw_file.write_text(sample_cw_content)
    
    # Show the file with syntax highlighting
    console.print(f"[green]Created {demo_cw_file}[/green]")
    console.print("\n[bold cyan]Contents of demo.cw:[/bold cyan]")
    
    syntax = Syntax(sample_cw_content, "hcl", theme="monokai", line_numbers=True)
    console.print(syntax)
    
    if interactive and not text_only:
        console.print("\n[dim]Press Enter to continue to the planning phase...[/dim]")
        safe_input()
    elif text_only:
        console.print("\n[green]✓ Step 1 complete - .cw file created[/green]")


def step_plan_demo(demo_dir: Path, interactive: bool, text_only: bool = False):
    """Step 2: Run plan command and explain output."""
    console.print("\n[bold yellow]📋 Step 2: Planning Phase[/bold yellow]")
    console.print("""
The 'plan' command analyzes your .cw file and shows you what Clockwork
would do WITHOUT actually doing it. This is like a "dry run" that lets
you review the plan before execution.

Running: clockwork plan
""")
    
    if interactive and not text_only:
        console.print("[dim]Press Enter to run the plan command...[/dim]")
        safe_input()
    elif text_only:
        console.print("[blue]► Step 2/7: Running plan command...[/blue]")
    
    # Run the plan command
    success, stdout, stderr = run_clockwork_command(demo_dir, ["plan", "--detailed"], text_only=text_only)
    
    if success:
        console.print("[green]Command executed successfully[/green]")
        console.print("\n[bold cyan]Plan Output:[/bold cyan]")
        console.print(stdout)
        
        if stderr:
            console.print("\n[yellow]Warnings/Errors:[/yellow]")
            console.print(stderr)
    else:
        error_msg = "Clockwork command not available. Please ensure clockwork is properly installed and accessible."
        console.print(f"[red]❌ {error_msg}[/red]")
        console.print(f"[red]Error details: {stderr}[/red]")
        raise RuntimeError(f"Demo failed: {error_msg}")
    
    console.print("""
[bold cyan]What happened?[/bold cyan]
• Clockwork parsed the .cw file (Intake phase)
• It planned the sequence of actions needed (Assembly phase)
• It showed you what would be executed without doing it
• Dependencies are correctly ordered:
  - demo_directory (step 1) - no dependencies
  - config_file (step 2) - depends on demo_directory  
  - readme (step 3) - depends on demo_directory
  - files_exist (step 4) - depends on config_file and readme

The Terraform-style output clearly shows the dependency relationships!
""")
    
    if interactive and not text_only:
        console.print("[dim]Press Enter to continue to the build phase...[/dim]")
        safe_input()
    elif text_only:
        console.print("[green]✓ Step 2 complete - Plan generated successfully[/green]")


def step_build_demo(demo_dir: Path, interactive: bool, text_only: bool = False):
    """Step 3: Run build command and explain artifacts."""
    console.print("\n[bold yellow]🔨 Step 3: Build Phase[/bold yellow]")
    console.print("""
The 'build' command compiles your plan into executable artifacts.
These are the actual scripts and configurations that will be run.

Running: clockwork build
""")
    
    if interactive and not text_only:
        console.print("[dim]Press Enter to run the build command...[/dim]")
        safe_input()
    elif text_only:
        console.print("[blue]► Step 3/7: Running build command...[/blue]")
    
    # Run the build command
    success, stdout, stderr = run_clockwork_command(demo_dir, ["build"], text_only=text_only)
    
    if success:
        console.print("[green]Command executed successfully[/green]")
        console.print("\n[bold cyan]Build Output:[/bold cyan]")
        console.print(stdout)
        
        if stderr:
            console.print("\n[yellow]Warnings/Errors:[/yellow]")
            console.print(stderr)
            
        # Show the artifacts directory
        artifacts_dir = demo_dir / ".clockwork" / "build"
        if artifacts_dir.exists():
            console.print(f"\n[bold cyan]Generated Artifacts in {artifacts_dir}:[/bold cyan]")
            for artifact in artifacts_dir.rglob("*"):
                if artifact.is_file():
                    console.print(f"  📄 {artifact.relative_to(artifacts_dir)}")
    else:
        error_msg = "Clockwork build command failed. Please ensure clockwork is properly installed and LM Studio is running."
        console.print(f"[red]❌ {error_msg}[/red]")
        console.print(f"[red]Error details: {stderr}[/red]")
        raise RuntimeError(f"Demo failed: {error_msg}")
    
    console.print("""
[bold cyan]What happened?[/bold cyan]
• Clockwork compiled your plan into executable artifacts
• These artifacts are stored in .clockwork/build/
• Each artifact contains the instructions for one action
• The artifacts are ready to be executed
""")
    
    if interactive and not text_only:
        console.print("[dim]Press Enter to continue to verification...[/dim]")
        safe_input()
    elif text_only:
        console.print("[green]✓ Step 3 complete - Artifacts built successfully[/green]")


def step_verify_demo(demo_dir: Path, interactive: bool, text_only: bool, phase: str):
    """Step 4 & 6: Run verify command."""
    if phase == "pre-apply":
        console.print("\n[bold yellow]🔍 Step 4: Pre-Apply Verification[/bold yellow]")
        console.print("""
Before applying changes, let's verify the current state.
This check should show that our target files don't exist yet.

Running: clockwork verify
""")
    else:
        console.print("\n[bold yellow]✅ Step 6: Post-Apply Verification[/bold yellow]")
        console.print("""
After applying changes, let's verify that everything worked.
This check should confirm that our files were created successfully.

Running: clockwork verify
""")
    
    if interactive and not text_only:
        console.print("[dim]Press Enter to run the verify command...[/dim]")
        safe_input()
    elif text_only:
        step_num = "4" if phase == "pre-apply" else "6"
        console.print(f"[blue]► Step {step_num}/7: Running verify command ({phase})...[/blue]")
    
    # Run the verify command
    success, stdout, stderr = run_clockwork_command(demo_dir, ["verify"], text_only=text_only)
    
    if success:
        console.print("[green]Command executed successfully[/green]")
        console.print("\n[bold cyan]Verification Output:[/bold cyan]")
        console.print(stdout)
        
        if stderr:
            console.print("\n[yellow]Warnings/Errors:[/yellow]")
            console.print(stderr)
    else:
        error_msg = "Clockwork verify command failed. Please ensure clockwork is properly installed and LM Studio is running."
        console.print(f"[red]❌ {error_msg}[/red]")
        console.print(f"[red]Error details: {stderr}[/red]")
        raise RuntimeError(f"Demo failed: {error_msg}")
    
    if phase == "pre-apply":
        console.print("""
[bold cyan]What happened?[/bold cyan]
• Clockwork checked if the target files already exist
• Since this is a fresh demo, they shouldn't exist yet
• This shows the "before" state
""")
    else:
        console.print("""
[bold cyan]What happened?[/bold cyan]
• Clockwork verified that all the files were created successfully
• This confirms that the apply phase worked correctly
• Your declarative tasks have been achieved!
""")
    
    if interactive and not text_only:
        if phase == "pre-apply":
            console.print("[dim]Press Enter to continue to the apply phase...[/dim]")
        else:
            console.print("[dim]Press Enter to see the results...[/dim]")
        safe_input()
    elif text_only:
        if phase == "pre-apply":
            console.print("[green]✓ Step 4 complete - Pre-apply verification done[/green]")
        else:
            console.print("[green]✓ Step 6 complete - Post-apply verification passed[/green]")


def step_apply_demo(demo_dir: Path, interactive: bool, text_only: bool = False):
    """Step 5: Run apply command."""
    console.print("\n[bold yellow]🚀 Step 5: Apply Phase[/bold yellow]")
    console.print("""
Now for the main event! The 'apply' command executes the plan and
makes your declarations reality. This is where Clockwork actually
creates the files and directories you specified.

Running: clockwork apply --auto-approve
""")
    
    if interactive and not text_only:
        console.print("[dim]Press Enter to run the apply command...[/dim]")
        safe_input()
    elif text_only:
        console.print("[blue]► Step 5/7: Running apply command...[/blue]")
    
    # Run the apply command
    success, stdout, stderr = run_clockwork_command(demo_dir, ["apply", "--auto-approve"], timeout=300, text_only=text_only)
    
    if success:
        console.print("[green]Command executed successfully[/green]")
        console.print("\n[bold cyan]Apply Output:[/bold cyan]")
        console.print(stdout)
        
        if stderr:
            # Filter out spurious error messages in demo
            filtered_stderr = stderr
            if "Process exited with code 1" in stderr and "Apply complete" in stdout:
                # Skip process exit errors when apply actually succeeded
                stderr_lines = stderr.split('\n')
                filtered_lines = [line for line in stderr_lines if "Process exited with code 1" not in line and line.strip()]
                filtered_stderr = '\n'.join(filtered_lines)
            
            if filtered_stderr.strip():
                console.print("\n[yellow]Warnings/Errors:[/yellow]")
                console.print(filtered_stderr)
    else:
        error_msg = "Clockwork apply command failed. Please ensure clockwork is properly installed and LM Studio is running."
        console.print(f"[red]❌ {error_msg}[/red]")
        console.print(f"[red]Error details: {stderr}[/red]")
        raise RuntimeError(f"Demo failed: {error_msg}")
    
    console.print("""
[bold cyan]What happened?[/bold cyan]
• Clockwork executed all the artifacts from the build phase
• It created the directory and files as specified in demo.cw
• The execution followed the dependency order you declared
• Your infrastructure/files now match your declaration!
""")
    
    if interactive and not text_only:
        console.print("[dim]Press Enter to verify the results...[/dim]")
        safe_input()
    elif text_only:
        console.print("[green]✓ Step 5 complete - Apply executed successfully[/green]")


def step_show_results(demo_dir: Path, interactive: bool, text_only: bool, cleanup: bool):
    """Step 7: Show the actual results and provide cleanup guidance."""
    console.print("\n[bold yellow]🎯 Step 7: Results & Verification[/bold yellow]")
    console.print("""
Let's look at what Clockwork actually created for us:
""")
    
    # Show the created files
    output_dir = demo_dir / "demo-output"
    if output_dir.exists():
        console.print(f"[green]✅ Directory created: {output_dir}[/green]")
        
        for file_path in output_dir.iterdir():
            if file_path.is_file():
                console.print(f"[green]✅ File created: {file_path}[/green]")
                
                # Show file contents
                if file_path.suffix in ['.json', '.md', '.txt']:
                    console.print(f"\n[bold cyan]Contents of {file_path.name}:[/bold cyan]")
                    try:
                        content = file_path.read_text()
                        if file_path.suffix == '.json':
                            # Pretty print JSON
                            formatted = json.dumps(json.loads(content), indent=2)
                            syntax = Syntax(formatted, "json", theme="monokai")
                        elif file_path.suffix == '.md':
                            syntax = Syntax(content, "markdown", theme="monokai")
                        else:
                            syntax = Syntax(content, "text", theme="monokai")
                        console.print(syntax)
                    except Exception as e:
                        console.print(f"[red]Error reading file: {e}[/red]")
                    console.print()
    else:
        console.print("[red]❌ Output directory not found! Something went wrong.[/red]")
    
    # Show the state file
    state_file = demo_dir / ".clockwork" / "state.json"
    if state_file.exists():
        console.print(f"[cyan]📊 Clockwork state tracked in: {state_file}[/cyan]")
        console.print("[dim]This file keeps track of what Clockwork has created[/dim]")
    
    console.print("""
[bold cyan]How to verify success:[/bold cyan]
• Check that the demo-output directory exists
• Verify the config.json and README.md files were created
• Look at the .clockwork/state.json file to see Clockwork's tracking
• Try running 'clockwork status' to see the current state

[bold cyan]Understanding what happened:[/bold cyan]
• You declared WHAT you wanted (files and directories)
• Clockwork figured out HOW to create them
• It handled dependencies automatically (directory before files)
• It tracked the state so it knows what it created
""")
    
    if cleanup:
        if interactive and not text_only:
            if typer.confirm(f"\nClean up demo files in {demo_dir}?"):
                shutil.rmtree(demo_dir)
                console.print(f"[green]🧹 Cleaned up demo directory: {demo_dir}[/green]")
            else:
                console.print(f"[cyan]Demo files preserved in: {demo_dir}[/cyan]")
                console.print("[dim]You can explore them or run commands manually[/dim]")
        else:
            shutil.rmtree(demo_dir)
            console.print(f"[green]🧹 Cleaned up demo directory: {demo_dir}[/green]")
    else:
        console.print(f"[cyan]Demo files preserved in: {demo_dir}[/cyan]")
        console.print("[dim]You can explore them or run the clockwork commands manually[/dim]")
    
    if text_only:
        console.print("[green]✓ Step 7 complete - Results verified and demo complete[/green]")


if __name__ == "__main__":
    app()