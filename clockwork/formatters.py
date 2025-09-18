"""
Terraform-style output formatting for Clockwork operations.

This module provides Terraform-like formatting for plan, build, apply, verify,
and status operations to give users familiar output patterns.
"""

from typing import Dict, List, Any, Optional, Union
from rich.console import Console
from rich.text import Text
from rich.panel import Panel
from datetime import datetime

from .models import (
    Resource, ResourceState, ActionList, ActionStep, ExecutionStatus,
    ResourceType, ClockworkState, IR
)


class TerraformStyleFormatter:
    """
    Terraform-style formatter for Clockwork operations.
    
    Provides methods to format different types of output with Terraform-like
    symbols and structure:
    - `+` for create operations
    - `~` for modify operations  
    - `-` for destroy operations
    """
    
    def __init__(self, console: Optional[Console] = None):
        """Initialize formatter with Rich console."""
        self.console = console or Console()
        
        # Color scheme matching Terraform output
        self.colors = {
            'create': 'green',
            'modify': 'yellow', 
            'destroy': 'red',
            'no_change': 'dim',
            'header': 'bold blue',
            'resource_name': 'bright_white',
            'attribute': 'cyan',
            'value': 'white',
            'comment': 'dim'
        }
        
        # Operation symbols
        self.symbols = {
            'create': '+',
            'modify': '~', 
            'destroy': '-',
            'no_change': ' '
        }

    def format_plan(self, ir: IR, current_state: Optional[ClockworkState] = None) -> str:
        """
        Format a plan operation showing what Clockwork will do.
        
        Args:
            ir: Intermediate representation with planned resources
            current_state: Current system state for comparison
            
        Returns:
            Formatted plan output string
        """
        output = Text()
        
        # Header
        output.append("Clockwork will perform the following actions:\n\n", style=self.colors['header'])
        
        # Analyze changes
        changes = self._analyze_changes(ir, current_state)
        
        # Format each resource change
        for resource_id, change_info in changes.items():
            resource = change_info['resource']
            operation = change_info['operation']
            
            # Resource header comment
            resource_comment = self._format_resource_comment(resource, operation)
            output.append(f"  # {resource_comment}\n", style=self.colors['comment'])
            
            # Resource definition with symbol
            symbol = self.symbols[operation]
            color = self.colors[operation]
            
            resource_line = f"  {symbol} resource \"{resource.type.value}\" \"{resource.name}\" {{\n"
            output.append(resource_line, style=color)
            
            # Resource attributes
            attributes = self._format_resource_attributes(resource, operation, change_info.get('changes', {}))
            for attr_line in attributes:
                output.append(f"      {attr_line}\n", style=color)
            
            # Dependencies
            if resource.depends_on:
                deps_line = f"      depends_on = {self._format_dependency_list(resource.depends_on)}"
                output.append(f"{deps_line}\n", style=color)
            
            output.append("    }\n\n", style=color)
        
        # Summary
        summary = self._format_plan_summary(changes)
        output.append(summary, style=self.colors['header'])
        
        return str(output)

    def format_build(self, action_list: ActionList, artifacts_info: Optional[Dict[str, Any]] = None) -> str:
        """
        Format build operation showing compilation of artifacts.
        
        Args:
            action_list: Generated action list
            artifacts_info: Information about generated artifacts
            
        Returns:
            Formatted build output string
        """
        output = Text()
        
        # Header
        output.append("Clockwork is building the following artifacts:\n\n", style=self.colors['header'])
        
        # Show actions being compiled
        for i, step in enumerate(action_list.steps, 1):
            output.append(f"  {i}. ", style=self.colors['comment'])
            output.append(f"Compiling action: {step.name}\n", style=self.colors['create'])
            
            # Show key arguments
            if step.args:
                key_args = self._extract_key_args(step.args)
                for key, value in key_args.items():
                    output.append(f"     {key} = {self._format_value(value)}\n", style=self.colors['attribute'])
        
        output.append("\n")
        
        # Artifacts summary
        if artifacts_info:
            output.append("Generated artifacts:\n", style=self.colors['header'])
            
            if 'artifacts' in artifacts_info:
                for artifact in artifacts_info['artifacts']:
                    output.append(f"  + {artifact.get('path', 'unknown')}", style=self.colors['create'])
                    output.append(f" ({artifact.get('lang', 'text')}, {artifact.get('mode', '644')})\n", style=self.colors['comment'])
        
        # Build summary
        total_steps = len(action_list.steps)
        output.append(f"\nBuild complete: {total_steps} actions compiled into executable artifacts.\n", style=self.colors['header'])
        
        return str(output)

    def format_apply(self, execution_results: List[Dict[str, Any]], success_count: int, failed_count: int) -> str:
        """
        Format apply operation showing execution results.
        
        Args:
            execution_results: List of execution step results
            success_count: Number of successful operations
            failed_count: Number of failed operations
            
        Returns:
            Formatted apply output string
        """
        output = Text()
        
        # Header
        output.append("Clockwork is applying the configuration:\n\n", style=self.colors['header'])
        
        # Show execution results
        for result in execution_results:
            resource_name = result.get('resource_name', 'unknown')
            operation = result.get('operation', 'unknown')
            status = result.get('status', 'unknown')
            
            if status == 'success':
                symbol = '✓'
                color = self.colors['create']
            elif status == 'failed':
                symbol = '✗'
                color = self.colors['destroy']
            else:
                symbol = '⋯'
                color = self.colors['modify']
            
            output.append(f"  {symbol} {resource_name}: ", style=color)
            output.append(f"{operation}\n", style=self.colors['resource_name'])
            
            # Show error details if failed
            if status == 'failed' and result.get('error'):
                output.append(f"    Error: {result['error']}\n", style=self.colors['destroy'])
        
        output.append("\n")
        
        # Apply summary with accurate reporting
        total = success_count + failed_count
        if total == 0:
            output.append("No resources to apply.\n", style=self.colors['comment'])
        elif failed_count == 0:
            output.append(f"Apply complete! Resources: {success_count} applied, 0 failed.\n", style=self.colors['create'])
        else:
            output.append(f"Apply finished with errors. Resources: {success_count} applied, {failed_count} failed.\n", style=self.colors['destroy'])
        
        return str(output)

    def format_verify(self, verification_results: List[Dict[str, Any]], drift_detected: bool = False) -> str:
        """
        Format verify operation showing drift detection results.
        
        Args:
            verification_results: List of verification check results
            drift_detected: Whether any drift was detected
            
        Returns:
            Formatted verify output string
        """
        output = Text()
        
        # Header
        if drift_detected:
            output.append("Clockwork detected configuration drift:\n\n", style=self.colors['modify'])
        else:
            output.append("Clockwork verification results:\n\n", style=self.colors['header'])
        
        # Show verification results
        for result in verification_results:
            resource_name = result.get('resource_name', 'unknown')
            has_drift = result.get('drift_detected', False)
            last_verified = result.get('last_verified')
            
            if has_drift:
                symbol = '~'
                color = self.colors['modify']
                status_text = "configuration drift detected"
            else:
                symbol = '✓'
                color = self.colors['create']
                status_text = "configuration matches desired state"
            
            output.append(f"  {symbol} {resource_name}: ", style=color)
            output.append(f"{status_text}\n", style=self.colors['resource_name'])
            
            if last_verified:
                time_str = last_verified.strftime("%Y-%m-%d %H:%M:%S") if isinstance(last_verified, datetime) else str(last_verified)
                output.append(f"    Last verified: {time_str}\n", style=self.colors['comment'])
            
            # Show drift details
            if has_drift and result.get('drift_details'):
                for detail in result['drift_details']:
                    output.append(f"    • {detail}\n", style=self.colors['modify'])
        
        output.append("\n")
        
        # Verification summary
        total_resources = len(verification_results)
        drifted_resources = sum(1 for r in verification_results if r.get('drift_detected', False))
        
        if drift_detected:
            output.append(f"Verification complete: {drifted_resources} of {total_resources} resources have drift.\n", style=self.colors['modify'])
        else:
            output.append(f"Verification complete: All {total_resources} resources match desired state.\n", style=self.colors['create'])
        
        return str(output)

    def format_status(self, clockwork_state: ClockworkState) -> str:
        """
        Format status operation showing current system state.
        
        Args:
            clockwork_state: Current Clockwork system state
            
        Returns:
            Formatted status output string
        """
        output = Text()
        
        # Header
        output.append("Current Clockwork status:\n\n", style=self.colors['header'])
        
        # Overall health summary
        health = clockwork_state.get_health_summary()
        health_score = health.get('health_score', 0)
        
        if health_score >= 90:
            health_color = self.colors['create']
            health_status = "Healthy"
        elif health_score >= 70:
            health_color = self.colors['modify'] 
            health_status = "Warning"
        else:
            health_color = self.colors['destroy']
            health_status = "Critical"
        
        output.append(f"  System Health: ", style=self.colors['attribute'])
        output.append(f"{health_status} ({health_score}%)\n", style=health_color)
        output.append(f"  Total Resources: {health['total_resources']}\n", style=self.colors['attribute'])
        
        if health['last_updated']:
            output.append(f"  Last Updated: {health['last_updated']}\n", style=self.colors['comment'])
        
        output.append("\n")
        
        # Resource status breakdown
        if clockwork_state.current_resources:
            output.append("Resource Status:\n", style=self.colors['header'])
            
            for resource_id, resource_state in clockwork_state.current_resources.items():
                status = resource_state.status
                
                if status == ExecutionStatus.SUCCESS:
                    symbol = '✓'
                    color = self.colors['create']
                elif status == ExecutionStatus.FAILED:
                    symbol = '✗'
                    color = self.colors['destroy']
                elif status == ExecutionStatus.RUNNING:
                    symbol = '⋯'
                    color = self.colors['modify']
                else:
                    symbol = '?'
                    color = self.colors['no_change']
                
                output.append(f"  {symbol} {resource_state.type.value}.{resource_id}: ", style=color)
                output.append(f"{status.value}", style=self.colors['resource_name'])
                
                if resource_state.drift_detected:
                    output.append(" (drift detected)", style=self.colors['modify'])
                
                output.append("\n")
                
                # Show error if present
                if resource_state.error_message:
                    output.append(f"    Error: {resource_state.error_message}\n", style=self.colors['destroy'])
        else:
            output.append("No resources found.\n", style=self.colors['comment'])
        
        return str(output)

    def _analyze_changes(self, ir: IR, current_state: Optional[ClockworkState] = None) -> Dict[str, Dict[str, Any]]:
        """Analyze what changes will be made based on IR and current state."""
        changes = {}
        
        current_resources = {}
        if current_state:
            current_resources = current_state.current_resources
        
        # Analyze each resource in the IR
        for resource_id, resource in ir.resources.items():
            if resource_id in current_resources:
                # Compare configurations to detect changes
                current_resource = current_resources[resource_id]
                if self._resource_configs_differ(resource, current_resource):
                    changes[resource_id] = {
                        'resource': resource,
                        'operation': 'modify',
                        'changes': self._get_config_differences(resource, current_resource)
                    }
                else:
                    changes[resource_id] = {
                        'resource': resource,
                        'operation': 'no_change'
                    }
            else:
                # New resource
                changes[resource_id] = {
                    'resource': resource,
                    'operation': 'create'
                }
        
        # Check for resources to destroy (in current state but not in IR)
        for resource_id, resource_state in current_resources.items():
            if resource_id not in ir.resources:
                # Create a resource object from state for formatting
                resource = Resource(
                    type=resource_state.type,
                    name=resource_id,
                    config=resource_state.config
                )
                changes[resource_id] = {
                    'resource': resource,
                    'operation': 'destroy'
                }
        
        return changes

    def _format_resource_comment(self, resource: Resource, operation: str) -> str:
        """Format the comment line for a resource."""
        action_map = {
            'create': 'will be created',
            'modify': 'will be updated in-place', 
            'destroy': 'will be destroyed',
            'no_change': 'is up-to-date'
        }
        
        action_text = action_map.get(operation, 'will be modified')
        return f"{resource.type.value}.{resource.name} {action_text}"

    def _format_resource_attributes(self, resource: Resource, operation: str, changes: Dict[str, Any] = None) -> List[str]:
        """Format resource attributes with proper indentation."""
        attributes = []
        
        # Format main configuration attributes
        for key, value in resource.config.items():
            if changes and key in changes:
                # Show both old and new values for modifications
                old_value = changes[key]['old']
                new_value = changes[key]['new']
                attributes.append(f"~ {key} = {self._format_value(old_value)} -> {self._format_value(new_value)}")
            else:
                symbol = '+' if operation == 'create' else ' '
                attributes.append(f"{symbol} {key} = {self._format_value(value)}")
        
        # Add standard attributes
        if resource.type == ResourceType.FILE:
            # File-specific attributes
            if 'path' not in resource.config:
                symbol = '+' if operation == 'create' else ' '
                attributes.append(f"{symbol} path = {self._format_value(resource.config.get('path', ''))}")
                
            if 'type' not in resource.config:
                symbol = '+' if operation == 'create' else ' '
                file_type = resource.config.get('type', 'file')
                attributes.append(f"{symbol} type = {self._format_value(file_type)}")
                
            if 'mode' not in resource.config:
                symbol = '+' if operation == 'create' else ' '
                mode = resource.config.get('mode', '644')
                attributes.append(f"{symbol} mode = {self._format_value(mode)}")
        
        return attributes

    def _format_dependency_list(self, dependencies: List[str]) -> str:
        """Format a list of dependencies."""
        formatted_deps = [f'"{dep}"' for dep in dependencies]
        if len(formatted_deps) == 1:
            return formatted_deps[0]
        return f"[{', '.join(formatted_deps)}]"

    def _format_value(self, value: Any) -> str:
        """Format a configuration value for display."""
        if isinstance(value, str):
            return f'"{value}"'
        elif isinstance(value, bool):
            return str(value).lower()
        elif isinstance(value, (list, dict)):
            return str(value)
        else:
            return str(value)

    def _format_plan_summary(self, changes: Dict[str, Dict[str, Any]]) -> str:
        """Format the plan summary line."""
        create_count = sum(1 for c in changes.values() if c['operation'] == 'create')
        modify_count = sum(1 for c in changes.values() if c['operation'] == 'modify')
        destroy_count = sum(1 for c in changes.values() if c['operation'] == 'destroy')
        
        return f"Plan: {create_count} to add, {modify_count} to change, {destroy_count} to destroy.\n"

    def _extract_key_args(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Extract key arguments for display in build output."""
        # Show the most important args
        key_fields = ['name', 'image', 'url', 'path', 'type', 'namespace']
        return {k: v for k, v in args.items() if k in key_fields}

    def _resource_configs_differ(self, resource: Resource, current_state: ResourceState) -> bool:
        """Check if resource configuration differs from current state."""
        # Simple comparison for now - could be enhanced with deep comparison
        return resource.config != current_state.config

    def _get_config_differences(self, resource: Resource, current_state: ResourceState) -> Dict[str, Dict[str, Any]]:
        """Get specific configuration differences between resource and current state."""
        differences = {}
        
        for key, new_value in resource.config.items():
            old_value = current_state.config.get(key)
            if old_value != new_value:
                differences[key] = {
                    'old': old_value,
                    'new': new_value
                }
        
        # Check for removed keys
        for key, old_value in current_state.config.items():
            if key not in resource.config:
                differences[key] = {
                    'old': old_value,
                    'new': None
                }
        
        return differences