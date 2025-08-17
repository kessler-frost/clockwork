"""
Daemon CLI interface for Clockwork.

This module provides command-line interface for daemon operations:
- Starting/stopping the daemon
- Checking daemon status
- Managing auto-fix policies
- Manual drift checks
"""

import json
import logging
import sys
import time
from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from ..core import ClockworkCore
from ..models import ClockworkConfig
from .types import DaemonState, AutoFixPolicy, DaemonConfig
from .loop import ClockworkDaemon
from .rate_limiter import RateLimitConfig, SafetyController, create_default_safety_config


daemon_app = typer.Typer(help="Clockwork daemon commands for continuous reconciliation")
console = Console()
logger = logging.getLogger(__name__)


@daemon_app.command("start")
def start_daemon(
    config_path: Path = typer.Option(Path("."), "--config", "-c", help="Configuration directory path"),
    watch_paths: List[Path] = typer.Option(None, "--watch", "-w", help="Paths to watch for .cw files"),
    policy: AutoFixPolicy = typer.Option(AutoFixPolicy.CONSERVATIVE, "--policy", "-p", help="Auto-fix policy"),
    check_interval: int = typer.Option(60, "--interval", "-i", help="Check interval in seconds"),
    max_fixes_per_hour: int = typer.Option(2, "--max-fixes", help="Maximum fixes per hour"),
    cooldown_minutes: int = typer.Option(10, "--cooldown", help="Cooldown minutes after fix"),
    daemonize: bool = typer.Option(False, "--daemon", "-d", help="Run as background daemon"),
    pid_file: Optional[Path] = typer.Option(None, "--pid-file", help="PID file path"),
    log_file: Optional[Path] = typer.Option(None, "--log-file", help="Log file path")
):
    """Start the Clockwork daemon."""
    try:
        console.print("[blue]Starting Clockwork daemon...[/blue]")
        
        # Setup logging
        setup_daemon_logging(log_file)
        
        # Determine watch paths
        if not watch_paths:
            watch_paths = [config_path]
        
        # Validate watch paths
        for path in watch_paths:
            if not path.exists():
                console.print(f"[red]Error: Watch path does not exist: {path}[/red]")
                raise typer.Exit(1)
        
        # Create daemon configuration
        daemon_config = DaemonConfig(
            watch_paths=watch_paths,
            check_interval_seconds=check_interval,
            auto_fix_policy=policy,
            max_fixes_per_hour=max_fixes_per_hour,
            cooldown_minutes=cooldown_minutes
        )
        
        # Validate daemon configuration
        config_issues = daemon_config.validate()
        if config_issues:
            console.print(f"[red]Configuration errors:[/red]")
            for issue in config_issues:
                console.print(f"  - {issue}")
            raise typer.Exit(1)
        
        # Initialize core
        core = ClockworkCore(config_path=config_path)
        
        # Create and start daemon
        daemon = ClockworkDaemon(core, daemon_config)
        
        if daemonize:
            start_daemon_background(daemon, pid_file)
        else:
            start_daemon_foreground(daemon)
    
    except KeyboardInterrupt:
        console.print("\n[yellow]Daemon startup interrupted[/yellow]")
        raise typer.Exit(130)
    except Exception as e:
        console.print(f"[red]Failed to start daemon: {e}[/red]")
        raise typer.Exit(1)


@daemon_app.command("stop")
def stop_daemon(
    pid_file: Optional[Path] = typer.Option(None, "--pid-file", help="PID file path"),
    timeout: int = typer.Option(30, "--timeout", help="Shutdown timeout in seconds")
):
    """Stop the Clockwork daemon."""
    try:
        if pid_file and pid_file.exists():
            stop_daemon_by_pid_file(pid_file, timeout)
        else:
            console.print("[yellow]No PID file specified or found. Use Ctrl+C if daemon is running in foreground.[/yellow]")
    
    except Exception as e:
        console.print(f"[red]Failed to stop daemon: {e}[/red]")
        raise typer.Exit(1)


@daemon_app.command("status")
def daemon_status(
    detailed: bool = typer.Option(False, "--detailed", "-d", help="Show detailed status"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON")
):
    """Check daemon status."""
    try:
        # This is a simplified implementation
        # In practice, you'd need IPC or HTTP API to get status from running daemon
        
        status_info = {
            "status": "unknown",
            "message": "Status checking requires daemon API - not implemented in this demo"
        }
        
        if json_output:
            console.print(json.dumps(status_info, indent=2))
        else:
            display_daemon_status(status_info, detailed)
    
    except Exception as e:
        console.print(f"[red]Failed to get daemon status: {e}[/red]")
        raise typer.Exit(1)


@daemon_app.command("check")
def manual_drift_check(
    config_path: Path = typer.Option(Path("."), "--config", "-c", help="Configuration directory path"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON")
):
    """Perform manual drift check."""
    try:
        console.print("[blue]Performing manual drift check...[/blue]")
        
        # Initialize core and perform drift check
        core = ClockworkCore(config_path=config_path)
        drift_report = core.detect_drift()
        
        if json_output:
            console.print(json.dumps(drift_report, indent=2, default=str))
        else:
            display_drift_report(drift_report)
    
    except Exception as e:
        console.print(f"[red]Drift check failed: {e}[/red]")
        raise typer.Exit(1)


@daemon_app.command("policy")
def manage_policy(
    action: str = typer.Argument(..., help="Action: show, set"),
    policy: Optional[AutoFixPolicy] = typer.Argument(None, help="Policy to set"),
    config_path: Path = typer.Option(Path("."), "--config", "-c", help="Configuration directory path")
):
    """Manage auto-fix policy."""
    try:
        if action == "show":
            show_current_policy(config_path)
        elif action == "set":
            if policy is None:
                console.print("[red]Policy required for 'set' action[/red]")
                raise typer.Exit(1)
            set_auto_fix_policy(config_path, policy)
        else:
            console.print(f"[red]Unknown action: {action}. Use 'show' or 'set'[/red]")
            raise typer.Exit(1)
    
    except Exception as e:
        console.print(f"[red]Policy management failed: {e}[/red]")
        raise typer.Exit(1)


def start_daemon_foreground(daemon: ClockworkDaemon):
    """Start daemon in foreground mode."""
    console.print("[green]Starting daemon in foreground mode...[/green]")
    console.print("[dim]Press Ctrl+C to stop[/dim]")
    
    try:
        daemon.start()
        
        # Display initial status
        status = daemon.get_status()
        display_daemon_status(status, detailed=False)
        
        # Keep running until interrupted
        while daemon.state == DaemonState.RUNNING:
            time.sleep(5)
            
            # Optionally display periodic status updates
            # status = daemon.get_status()
            # console.print(f"[dim]Status: {status['state']} | Fixes: {status['metrics']['fixes_applied']} | Drift checks: {status['metrics']['drift_checks_performed']}[/dim]")
    
    except KeyboardInterrupt:
        console.print("\n[yellow]Shutting down daemon...[/yellow]")
    finally:
        daemon.stop()
        console.print("[green]Daemon stopped[/green]")


def start_daemon_background(daemon: ClockworkDaemon, pid_file: Optional[Path]):
    """Start daemon in background mode."""
    import os
    
    console.print("[green]Starting daemon in background mode...[/green]")
    
    # Simple daemonization (production would use proper daemon libraries)
    pid = os.fork()
    if pid > 0:
        # Parent process
        if pid_file:
            pid_file.write_text(str(pid))
        console.print(f"[green]Daemon started with PID: {pid}[/green]")
        return
    
    # Child process continues as daemon
    os.setsid()
    daemon.start()
    
    try:
        while daemon.state == DaemonState.RUNNING:
            time.sleep(60)
    except:
        pass
    finally:
        daemon.stop()


def stop_daemon_by_pid_file(pid_file: Path, timeout: int):
    """Stop daemon using PID file."""
    import os
    import signal
    
    try:
        pid = int(pid_file.read_text().strip())
        console.print(f"[yellow]Stopping daemon with PID: {pid}[/yellow]")
        
        # Send SIGTERM
        os.kill(pid, signal.SIGTERM)
        
        # Wait for graceful shutdown
        for _ in range(timeout):
            try:
                os.kill(pid, 0)  # Check if process exists
                time.sleep(1)
            except ProcessLookupError:
                console.print("[green]Daemon stopped gracefully[/green]")
                pid_file.unlink()
                return
        
        # Force kill if still running
        console.print("[yellow]Forcing daemon shutdown...[/yellow]")
        os.kill(pid, signal.SIGKILL)
        pid_file.unlink()
        console.print("[green]Daemon force stopped[/green]")
    
    except FileNotFoundError:
        console.print("[yellow]PID file not found[/yellow]")
    except ProcessLookupError:
        console.print("[yellow]Daemon process not found[/yellow]")
        if pid_file.exists():
            pid_file.unlink()
    except ValueError:
        console.print("[red]Invalid PID in file[/red]")


def display_daemon_status(status: dict, detailed: bool = False):
    """Display daemon status in a formatted way."""
    
    # Create main status panel
    if isinstance(status, dict) and "state" in status:
        state = status["state"]
        state_color = {
            "running": "green",
            "stopped": "red", 
            "starting": "yellow",
            "stopping": "yellow",
            "paused": "blue",
            "error": "red"
        }.get(state, "white")
        
        status_text = Text(f"Daemon Status: {state.upper()}", style=state_color)
        console.print(Panel(status_text))
        
        if detailed and "metrics" in status:
            # Display metrics in simple format
            metrics = status["metrics"]
            console.print("\n[bold]Daemon Metrics:[/bold]")
            console.print(f"  Uptime: {status.get('uptime_seconds', 0)} seconds")
            console.print(f"  Drift Checks: {metrics.get('drift_checks_performed', 0)}")
            console.print(f"  Fixes Applied: {metrics.get('fixes_applied', 0)}")
            console.print(f"  Fixes Failed: {metrics.get('fixes_failed', 0)}")
            console.print(f"  Files Processed: {metrics.get('files_processed', 0)}")
            
            # Rate limiting info
            if "rate_limiter" in status:
                rl = status["rate_limiter"]
                console.print(f"Rate Limit: {rl.get('remaining_operations', 0)} operations remaining")
            
            # Cooldown info
            if "cooldown" in status and status["cooldown"].get("in_cooldown"):
                cooldown_end = status["cooldown"].get("cooldown_end", "unknown")
                console.print(f"[yellow]In cooldown until: {cooldown_end}[/yellow]")
    else:
        console.print(Panel(Text("Daemon status unavailable", style="red")))


def display_drift_report(report: dict):
    """Display drift report in a formatted way."""
    
    if "error" in report:
        console.print(f"[red]Drift check error: {report['error']}[/red]")
        return
    
    summary = report.get("summary", {})
    
    # Summary panel
    total_resources = summary.get("total_resources_checked", 0)
    resources_with_drift = summary.get("resources_with_drift", 0)
    drift_percentage = summary.get("drift_percentage", 0)
    
    summary_text = f"""
Total Resources: {total_resources}
Resources with Drift: {resources_with_drift}
Drift Percentage: {drift_percentage:.1f}%
"""
    
    panel_style = "red" if resources_with_drift > 0 else "green"
    console.print(Panel(summary_text.strip(), title="Drift Summary", style=panel_style))
    
    # Drift details
    if resources_with_drift > 0:
        immediate_attention = report.get("immediate_action_required", [])
        if immediate_attention:
            console.print("\n[bold red]Resources Requiring Immediate Attention:[/bold red]")
            for i, resource in enumerate(immediate_attention[:10], 1):  # Limit display
                actions = ", ".join(resource.get("suggested_actions", [])[:2])
                console.print(f"  {i}. [bold]{resource.get('resource_id', 'unknown')}[/bold]")
                console.print(f"     Type: {resource.get('resource_type', 'unknown')}")
                console.print(f"     Severity: {resource.get('severity', 'unknown')}")
                console.print(f"     Actions: {actions}")
                console.print()


def show_current_policy(config_path: Path):
    """Show current auto-fix policy."""
    try:
        # This would load from daemon config or default
        console.print("[blue]Current Auto-Fix Policy: CONSERVATIVE[/blue]")
        
        # Show policy details
        from .patch_engine import PatchEngine
        engine = PatchEngine(AutoFixPolicy.CONSERVATIVE)
        policy_summary = engine.get_policy_summary(AutoFixPolicy.CONSERVATIVE)
        
        console.print("\n[bold]Policy Details:[/bold]")
        console.print(f"  Auto-apply artifact patches: {policy_summary['auto_apply_artifact_patches']}")
        console.print(f"  Auto-apply safe config patches: {policy_summary['auto_apply_safe_config_patches']}")
        console.print(f"  Auto-apply sensitive config patches: {policy_summary['auto_apply_sensitive_config_patches']}")
    
    except Exception as e:
        console.print(f"[red]Failed to show policy: {e}[/red]")


def set_auto_fix_policy(config_path: Path, policy: AutoFixPolicy):
    """Set auto-fix policy."""
    console.print(f"[yellow]Setting auto-fix policy to: {policy.value}[/yellow]")
    console.print("[dim]Note: This is a demo - in practice this would update daemon configuration[/dim]")


def setup_daemon_logging(log_file: Optional[Path] = None):
    """Setup logging for daemon operations."""
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    handlers = [logging.StreamHandler(sys.stdout)]
    
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file))
    
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        handlers=handlers
    )


if __name__ == "__main__":
    daemon_app()