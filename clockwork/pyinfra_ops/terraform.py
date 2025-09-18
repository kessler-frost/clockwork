"""
Clockwork Terraform Operations

PyInfra operations for managing Terraform infrastructure with idempotent
state management, workspace handling, and lifecycle operations.
"""

import json
import logging
import os
from typing import Dict, List, Optional, Union

from pyinfra import host
from pyinfra.api import operation, OperationError
from pyinfra.api.command import StringCommand
from pyinfra.facts.server import Command

logger = logging.getLogger(__name__)


@operation()
def terraform_init(
    terraform_dir: str = ".",
    backend_config: Optional[Dict[str, str]] = None,
    backend_config_file: Optional[str] = None,
    upgrade: bool = False,
    reconfigure: bool = False,
    migrate_state: bool = False,
    force_copy: bool = False,
    plugin_dir: Optional[str] = None,
):
    """
    Initialize Terraform working directory using terraform init.

    Args:
        terraform_dir: Directory containing Terraform configuration
        backend_config: Backend configuration as key-value pairs
        backend_config_file: Path to backend configuration file
        upgrade: Upgrade modules and plugins
        reconfigure: Reconfigure backend without migration
        migrate_state: Migrate existing state to new backend
        force_copy: Force copying of state during migration
        plugin_dir: Directory containing plugin binaries

    Example:
        terraform_init(
            terraform_dir="/infrastructure",
            backend_config={"bucket": "my-terraform-state"},
            upgrade=True
        )
    """
    # Check if terraform directory exists
    if not os.path.isabs(terraform_dir):
        terraform_dir = os.path.abspath(terraform_dir)

    dir_check = host.get_fact(Command, command=f"test -d {terraform_dir}")
    if dir_check.return_code != 0:
        raise OperationError(f"Terraform directory not found: {terraform_dir}")

    # Check if .terraform directory exists (already initialized)
    terraform_state_dir = os.path.join(terraform_dir, ".terraform")
    init_check = host.get_fact(Command, command=f"test -d {terraform_state_dir}")
    already_initialized = init_check.return_code == 0

    # Build terraform init command
    cmd_parts = ["terraform", "-chdir=" + terraform_dir, "init"]

    if upgrade:
        cmd_parts.append("-upgrade")
    if reconfigure:
        cmd_parts.append("-reconfigure")
    if migrate_state:
        cmd_parts.append("-migrate-state")
    if force_copy:
        cmd_parts.append("-force-copy")
    if plugin_dir:
        cmd_parts.extend(["-plugin-dir", plugin_dir])

    # Add backend configuration
    if backend_config:
        for key, value in backend_config.items():
            cmd_parts.extend(["-backend-config", f"{key}={value}"])
    if backend_config_file:
        cmd_parts.extend(["-backend-config", backend_config_file])

    # Only run init if not already initialized or if reconfigure/upgrade is requested
    if not already_initialized or upgrade or reconfigure or migrate_state:
        yield StringCommand(" ".join(cmd_parts))


@operation()
def terraform_plan(
    terraform_dir: str = ".",
    var_file: Optional[str] = None,
    variables: Optional[Dict[str, str]] = None,
    target: Optional[List[str]] = None,
    out: Optional[str] = None,
    destroy: bool = False,
    refresh: bool = True,
    detailed_exitcode: bool = False,
    parallelism: Optional[int] = None,
):
    """
    Create Terraform execution plan using terraform plan.

    Args:
        terraform_dir: Directory containing Terraform configuration
        var_file: Path to variables file
        variables: Variables as key-value pairs
        target: List of resource addresses to target
        out: Path to save plan file
        destroy: Create destroy plan
        refresh: Refresh state before planning
        detailed_exitcode: Return detailed exit codes
        parallelism: Limit concurrent operations

    Example:
        terraform_plan(
            terraform_dir="/infrastructure",
            var_file="prod.tfvars",
            variables={"region": "us-west-2"},
            out="plan.out"
        )
    """
    # Ensure terraform is initialized
    terraform_state_dir = os.path.join(terraform_dir, ".terraform")
    init_check = host.get_fact(Command, command=f"test -d {terraform_state_dir}")
    if init_check.return_code != 0:
        raise OperationError(f"Terraform not initialized in {terraform_dir}. Run terraform_init first.")

    # Build terraform plan command
    cmd_parts = ["terraform", "-chdir=" + terraform_dir, "plan"]

    if destroy:
        cmd_parts.append("-destroy")
    if not refresh:
        cmd_parts.append("-refresh=false")
    if detailed_exitcode:
        cmd_parts.append("-detailed-exitcode")
    if parallelism:
        cmd_parts.extend(["-parallelism", str(parallelism)])

    # Add variable file
    if var_file:
        cmd_parts.extend(["-var-file", var_file])

    # Add variables
    if variables:
        for key, value in variables.items():
            cmd_parts.extend(["-var", f"{key}={value}"])

    # Add targets
    if target:
        for tgt in target:
            cmd_parts.extend(["-target", tgt])

    # Add output file
    if out:
        cmd_parts.extend(["-out", out])

    yield StringCommand(" ".join(cmd_parts))


@operation()
def terraform_apply(
    terraform_dir: str = ".",
    plan_file: Optional[str] = None,
    var_file: Optional[str] = None,
    variables: Optional[Dict[str, str]] = None,
    target: Optional[List[str]] = None,
    auto_approve: bool = False,
    parallelism: Optional[int] = None,
    refresh: bool = True,
):
    """
    Apply Terraform configuration using terraform apply.

    Args:
        terraform_dir: Directory containing Terraform configuration
        plan_file: Path to plan file to apply
        var_file: Path to variables file
        variables: Variables as key-value pairs
        target: List of resource addresses to target
        auto_approve: Skip interactive approval
        parallelism: Limit concurrent operations
        refresh: Refresh state before applying

    Example:
        terraform_apply(
            terraform_dir="/infrastructure",
            plan_file="plan.out",
            auto_approve=True
        )
    """
    # Ensure terraform is initialized
    terraform_state_dir = os.path.join(terraform_dir, ".terraform")
    init_check = host.get_fact(Command, command=f"test -d {terraform_state_dir}")
    if init_check.return_code != 0:
        raise OperationError(f"Terraform not initialized in {terraform_dir}. Run terraform_init first.")

    # Build terraform apply command
    cmd_parts = ["terraform", "-chdir=" + terraform_dir, "apply"]

    if auto_approve:
        cmd_parts.append("-auto-approve")
    if not refresh:
        cmd_parts.append("-refresh=false")
    if parallelism:
        cmd_parts.extend(["-parallelism", str(parallelism)])

    # If plan file specified, use it
    if plan_file:
        cmd_parts.append(plan_file)
    else:
        # Add variable file
        if var_file:
            cmd_parts.extend(["-var-file", var_file])

        # Add variables
        if variables:
            for key, value in variables.items():
                cmd_parts.extend(["-var", f"{key}={value}"])

        # Add targets
        if target:
            for tgt in target:
                cmd_parts.extend(["-target", tgt])

    yield StringCommand(" ".join(cmd_parts))


@operation()
def terraform_destroy(
    terraform_dir: str = ".",
    var_file: Optional[str] = None,
    variables: Optional[Dict[str, str]] = None,
    target: Optional[List[str]] = None,
    auto_approve: bool = False,
    parallelism: Optional[int] = None,
):
    """
    Destroy Terraform-managed infrastructure using terraform destroy.

    Args:
        terraform_dir: Directory containing Terraform configuration
        var_file: Path to variables file
        variables: Variables as key-value pairs
        target: List of resource addresses to target
        auto_approve: Skip interactive approval
        parallelism: Limit concurrent operations

    Example:
        terraform_destroy(
            terraform_dir="/infrastructure",
            target=["aws_instance.web"],
            auto_approve=True
        )
    """
    # Ensure terraform is initialized
    terraform_state_dir = os.path.join(terraform_dir, ".terraform")
    init_check = host.get_fact(Command, command=f"test -d {terraform_state_dir}")
    if init_check.return_code != 0:
        raise OperationError(f"Terraform not initialized in {terraform_dir}. Run terraform_init first.")

    # Build terraform destroy command
    cmd_parts = ["terraform", "-chdir=" + terraform_dir, "destroy"]

    if auto_approve:
        cmd_parts.append("-auto-approve")
    if parallelism:
        cmd_parts.extend(["-parallelism", str(parallelism)])

    # Add variable file
    if var_file:
        cmd_parts.extend(["-var-file", var_file])

    # Add variables
    if variables:
        for key, value in variables.items():
            cmd_parts.extend(["-var", f"{key}={value}"])

    # Add targets
    if target:
        for tgt in target:
            cmd_parts.extend(["-target", tgt])

    yield StringCommand(" ".join(cmd_parts))


@operation()
def terraform_workspace(
    action: str,
    workspace_name: Optional[str] = None,
    terraform_dir: str = ".",
):
    """
    Manage Terraform workspaces using terraform workspace.

    Args:
        action: Workspace action (list, show, select, new, delete)
        workspace_name: Name of workspace (required for select, new, delete)
        terraform_dir: Directory containing Terraform configuration

    Example:
        terraform_workspace(
            action="new",
            workspace_name="production",
            terraform_dir="/infrastructure"
        )
    """
    valid_actions = ["list", "show", "select", "new", "delete"]
    if action not in valid_actions:
        raise OperationError(f"Invalid workspace action: {action}. Must be one of: {valid_actions}")

    if action in ["select", "new", "delete"] and not workspace_name:
        raise OperationError(f"workspace_name is required for action: {action}")

    # Ensure terraform is initialized
    terraform_state_dir = os.path.join(terraform_dir, ".terraform")
    init_check = host.get_fact(Command, command=f"test -d {terraform_state_dir}")
    if init_check.return_code != 0:
        raise OperationError(f"Terraform not initialized in {terraform_dir}. Run terraform_init first.")

    # Check current workspace and existing workspaces
    current_workspace_cmd = f"terraform -chdir={terraform_dir} workspace show"
    current_workspace = host.get_fact(Command, command=current_workspace_cmd)

    list_workspaces_cmd = f"terraform -chdir={terraform_dir} workspace list"
    workspaces_list = host.get_fact(Command, command=list_workspaces_cmd)

    # Build terraform workspace command based on action
    cmd_parts = ["terraform", "-chdir=" + terraform_dir, "workspace", action]

    if action == "select":
        # Only select if not already current workspace
        if current_workspace.stdout and current_workspace.stdout[0].strip() != workspace_name:
            # Check if workspace exists
            if workspace_name not in " ".join(workspaces_list.stdout):
                raise OperationError(f"Workspace '{workspace_name}' does not exist")
            cmd_parts.append(workspace_name)
            yield StringCommand(" ".join(cmd_parts))

    elif action == "new":
        # Only create if workspace doesn't exist
        if workspace_name not in " ".join(workspaces_list.stdout):
            cmd_parts.append(workspace_name)
            yield StringCommand(" ".join(cmd_parts))

    elif action == "delete":
        # Check if workspace exists and is not current
        if workspace_name in " ".join(workspaces_list.stdout):
            if current_workspace.stdout and current_workspace.stdout[0].strip() == workspace_name:
                raise OperationError(f"Cannot delete current workspace: {workspace_name}")
            cmd_parts.append(workspace_name)
            yield StringCommand(" ".join(cmd_parts))

    elif action in ["list", "show"]:
        yield StringCommand(" ".join(cmd_parts))


@operation()
def terraform_output(
    terraform_dir: str = ".",
    output_name: Optional[str] = None,
    json_format: bool = False,
    raw: bool = False,
    state: Optional[str] = None,
):
    """
    Read Terraform output values using terraform output.

    Args:
        terraform_dir: Directory containing Terraform configuration
        output_name: Specific output to read (optional)
        json_format: Output in JSON format
        raw: Output raw strings for non-list, non-map values
        state: Path to state file (defaults to terraform.tfstate)

    Example:
        terraform_output(
            terraform_dir="/infrastructure",
            output_name="vpc_id",
            json_format=True
        )
    """
    # Ensure terraform is initialized
    terraform_state_dir = os.path.join(terraform_dir, ".terraform")
    init_check = host.get_fact(Command, command=f"test -d {terraform_state_dir}")
    if init_check.return_code != 0:
        raise OperationError(f"Terraform not initialized in {terraform_dir}. Run terraform_init first.")

    # Build terraform output command
    cmd_parts = ["terraform", "-chdir=" + terraform_dir, "output"]

    if json_format:
        cmd_parts.append("-json")
    if raw:
        cmd_parts.append("-raw")
    if state:
        cmd_parts.extend(["-state", state])

    # Add specific output name
    if output_name:
        cmd_parts.append(output_name)

    yield StringCommand(" ".join(cmd_parts))


@operation()
def terraform_import(
    address: str,
    id: str,
    terraform_dir: str = ".",
    var_file: Optional[str] = None,
    variables: Optional[Dict[str, str]] = None,
    provider: Optional[str] = None,
):
    """
    Import existing infrastructure into Terraform state using terraform import.

    Args:
        address: Resource address to import to
        id: Resource ID in the target system
        terraform_dir: Directory containing Terraform configuration
        var_file: Path to variables file
        variables: Variables as key-value pairs
        provider: Provider to use for import

    Example:
        terraform_import(
            address="aws_instance.web",
            id="i-1234567890abcdef0",
            terraform_dir="/infrastructure"
        )
    """
    # Ensure terraform is initialized
    terraform_state_dir = os.path.join(terraform_dir, ".terraform")
    init_check = host.get_fact(Command, command=f"test -d {terraform_state_dir}")
    if init_check.return_code != 0:
        raise OperationError(f"Terraform not initialized in {terraform_dir}. Run terraform_init first.")

    # Check if resource is already in state
    show_cmd = f"terraform -chdir={terraform_dir} state show {address}"
    resource_exists = host.get_fact(Command, command=show_cmd)

    # Only import if resource doesn't exist in state
    if resource_exists.return_code != 0:
        # Build terraform import command
        cmd_parts = ["terraform", "-chdir=" + terraform_dir, "import"]

        # Add variable file
        if var_file:
            cmd_parts.extend(["-var-file", var_file])

        # Add variables
        if variables:
            for key, value in variables.items():
                cmd_parts.extend(["-var", f"{key}={value}"])

        # Add provider
        if provider:
            cmd_parts.extend(["-provider", provider])

        cmd_parts.extend([address, id])

        yield StringCommand(" ".join(cmd_parts))


@operation()
def terraform_refresh(
    terraform_dir: str = ".",
    var_file: Optional[str] = None,
    variables: Optional[Dict[str, str]] = None,
    target: Optional[List[str]] = None,
):
    """
    Update Terraform state to match real resources using terraform refresh.

    Args:
        terraform_dir: Directory containing Terraform configuration
        var_file: Path to variables file
        variables: Variables as key-value pairs
        target: List of resource addresses to target

    Example:
        terraform_refresh(
            terraform_dir="/infrastructure",
            var_file="prod.tfvars",
            target=["aws_instance.web"]
        )
    """
    # Ensure terraform is initialized
    terraform_state_dir = os.path.join(terraform_dir, ".terraform")
    init_check = host.get_fact(Command, command=f"test -d {terraform_state_dir}")
    if init_check.return_code != 0:
        raise OperationError(f"Terraform not initialized in {terraform_dir}. Run terraform_init first.")

    # Build terraform refresh command
    cmd_parts = ["terraform", "-chdir=" + terraform_dir, "refresh"]

    # Add variable file
    if var_file:
        cmd_parts.extend(["-var-file", var_file])

    # Add variables
    if variables:
        for key, value in variables.items():
            cmd_parts.extend(["-var", f"{key}={value}"])

    # Add targets
    if target:
        for tgt in target:
            cmd_parts.extend(["-target", tgt])

    yield StringCommand(" ".join(cmd_parts))


@operation()
def terraform_validate(
    terraform_dir: str = ".",
    json_format: bool = False,
):
    """
    Validate Terraform configuration using terraform validate.

    Args:
        terraform_dir: Directory containing Terraform configuration
        json_format: Output in JSON format

    Example:
        terraform_validate(
            terraform_dir="/infrastructure",
            json_format=True
        )
    """
    # Build terraform validate command
    cmd_parts = ["terraform", "-chdir=" + terraform_dir, "validate"]

    if json_format:
        cmd_parts.append("-json")

    yield StringCommand(" ".join(cmd_parts))


@operation()
def terraform_fmt(
    terraform_dir: str = ".",
    check: bool = False,
    diff: bool = False,
    write: bool = True,
    recursive: bool = False,
):
    """
    Format Terraform configuration files using terraform fmt.

    Args:
        terraform_dir: Directory containing Terraform configuration
        check: Check if formatting is needed (don't write)
        diff: Display formatting changes
        write: Write formatted files
        recursive: Process subdirectories

    Example:
        terraform_fmt(
            terraform_dir="/infrastructure",
            check=True,
            diff=True
        )
    """
    # Build terraform fmt command
    cmd_parts = ["terraform", "-chdir=" + terraform_dir, "fmt"]

    if check:
        cmd_parts.append("-check")
    if diff:
        cmd_parts.append("-diff")
    if not write:
        cmd_parts.append("-write=false")
    if recursive:
        cmd_parts.append("-recursive")

    yield StringCommand(" ".join(cmd_parts))