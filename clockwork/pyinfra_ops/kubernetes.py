"""
Clockwork Kubernetes Operations

PyInfra operations for managing Kubernetes resources using kubectl and Helm.
These operations provide idempotent management of Kubernetes workloads, services,
and deployments with proper error handling and dry-run support.
"""

import json
import logging
from typing import Dict, List, Optional, Union

from pyinfra import host
from pyinfra.api import operation, OperationError
from pyinfra.api.command import StringCommand
from pyinfra.facts.server import Command

logger = logging.getLogger(__name__)


@operation()
def kubectl_apply(
    manifest_path: Optional[str] = None,
    manifest_content: Optional[str] = None,
    namespace: Optional[str] = None,
    kubeconfig: Optional[str] = None,
    context: Optional[str] = None,
    dry_run: bool = False,
    validate: bool = True,
    wait: bool = False,
    timeout: str = "300s",
):
    """
    Apply Kubernetes manifests using kubectl apply.

    Args:
        manifest_path: Path to manifest file or directory
        manifest_content: Inline manifest content (YAML/JSON)
        namespace: Target namespace
        kubeconfig: Path to kubeconfig file
        context: Kubernetes context to use
        dry_run: Perform client-side dry run
        validate: Validate manifests before applying
        wait: Wait for resources to be ready
        timeout: Timeout for wait operations

    Example:
        kubectl_apply(
            manifest_path="/app/deployment.yaml",
            namespace="production",
            wait=True
        )
    """
    if not manifest_path and not manifest_content:
        raise OperationError("Either manifest_path or manifest_content must be provided")

    if manifest_path and manifest_content:
        raise OperationError("Cannot specify both manifest_path and manifest_content")

    # Build kubectl command
    cmd_parts = ["kubectl", "apply"]

    # Add context and kubeconfig options
    if context:
        cmd_parts.extend(["--context", context])
    if kubeconfig:
        cmd_parts.extend(["--kubeconfig", kubeconfig])
    if namespace:
        cmd_parts.extend(["--namespace", namespace])

    # Add apply options
    if not validate:
        cmd_parts.append("--validate=false")
    if wait:
        cmd_parts.extend(["--wait", f"--timeout={timeout}"])
    if dry_run:
        cmd_parts.append("--dry-run=client")

    if manifest_path:
        cmd_parts.extend(["-f", manifest_path])

        # Check if manifest file exists
        file_check = host.get_fact(Command, command=f"test -f {manifest_path}")
        if not file_check.stdout and not file_check.stderr:
            raise OperationError(f"Manifest file not found: {manifest_path}")

        yield StringCommand(" ".join(cmd_parts))

    elif manifest_content:
        # Apply inline content via stdin
        cmd = " ".join(cmd_parts + ["-f", "-"])
        yield StringCommand(f'echo "{manifest_content}" | {cmd}')


@operation()
def kubectl_delete(
    resource_type: Optional[str] = None,
    resource_name: Optional[str] = None,
    manifest_path: Optional[str] = None,
    namespace: Optional[str] = None,
    kubeconfig: Optional[str] = None,
    context: Optional[str] = None,
    grace_period: Optional[int] = None,
    force: bool = False,
    wait: bool = True,
    ignore_not_found: bool = True,
):
    """
    Delete Kubernetes resources using kubectl delete.

    Args:
        resource_type: Type of resource (e.g., 'deployment', 'service')
        resource_name: Name of the resource
        manifest_path: Path to manifest file to delete
        namespace: Target namespace
        kubeconfig: Path to kubeconfig file
        context: Kubernetes context to use
        grace_period: Grace period for deletion in seconds
        force: Force deletion
        wait: Wait for deletion to complete
        ignore_not_found: Don't error if resource not found

    Example:
        kubectl_delete(
            resource_type="deployment",
            resource_name="my-app",
            namespace="production"
        )
    """
    if not any([resource_type and resource_name, manifest_path]):
        raise OperationError("Either (resource_type and resource_name) or manifest_path must be provided")

    # Build kubectl command
    cmd_parts = ["kubectl", "delete"]

    # Add context and kubeconfig options
    if context:
        cmd_parts.extend(["--context", context])
    if kubeconfig:
        cmd_parts.extend(["--kubeconfig", kubeconfig])
    if namespace:
        cmd_parts.extend(["--namespace", namespace])

    # Add delete options
    if grace_period is not None:
        cmd_parts.extend(["--grace-period", str(grace_period)])
    if force:
        cmd_parts.append("--force")
    if wait:
        cmd_parts.append("--wait")
    if ignore_not_found:
        cmd_parts.append("--ignore-not-found")

    if resource_type and resource_name:
        cmd_parts.extend([resource_type, resource_name])
    elif manifest_path:
        cmd_parts.extend(["-f", manifest_path])

    yield StringCommand(" ".join(cmd_parts))


@operation()
def kubectl_get(
    resource_type: str,
    resource_name: Optional[str] = None,
    namespace: Optional[str] = None,
    kubeconfig: Optional[str] = None,
    context: Optional[str] = None,
    output: str = "json",
    label_selector: Optional[str] = None,
    field_selector: Optional[str] = None,
):
    """
    Get Kubernetes resources using kubectl get.

    Args:
        resource_type: Type of resource to get
        resource_name: Specific resource name (optional)
        namespace: Target namespace
        kubeconfig: Path to kubeconfig file
        context: Kubernetes context to use
        output: Output format (json, yaml, wide, etc.)
        label_selector: Label selector
        field_selector: Field selector

    Example:
        kubectl_get(
            resource_type="pods",
            namespace="production",
            label_selector="app=my-app"
        )
    """
    # Build kubectl command
    cmd_parts = ["kubectl", "get", resource_type]

    if resource_name:
        cmd_parts.append(resource_name)

    # Add context and kubeconfig options
    if context:
        cmd_parts.extend(["--context", context])
    if kubeconfig:
        cmd_parts.extend(["--kubeconfig", kubeconfig])
    if namespace:
        cmd_parts.extend(["--namespace", namespace])

    # Add selectors
    if label_selector:
        cmd_parts.extend(["-l", label_selector])
    if field_selector:
        cmd_parts.extend(["--field-selector", field_selector])

    # Add output format
    cmd_parts.extend(["-o", output])

    yield StringCommand(" ".join(cmd_parts))


@operation()
def kubectl_scale(
    resource_type: str,
    resource_name: str,
    replicas: int,
    namespace: Optional[str] = None,
    kubeconfig: Optional[str] = None,
    context: Optional[str] = None,
    wait: bool = True,
    timeout: str = "300s",
):
    """
    Scale Kubernetes resources using kubectl scale.

    Args:
        resource_type: Type of resource to scale (deployment, replicaset, etc.)
        resource_name: Name of the resource
        replicas: Target number of replicas
        namespace: Target namespace
        kubeconfig: Path to kubeconfig file
        context: Kubernetes context to use
        wait: Wait for scaling to complete
        timeout: Timeout for wait operations

    Example:
        kubectl_scale(
            resource_type="deployment",
            resource_name="my-app",
            replicas=3,
            namespace="production"
        )
    """
    # Get current replica count
    get_cmd_parts = ["kubectl", "get", resource_type, resource_name]
    if context:
        get_cmd_parts.extend(["--context", context])
    if kubeconfig:
        get_cmd_parts.extend(["--kubeconfig", kubeconfig])
    if namespace:
        get_cmd_parts.extend(["--namespace", namespace])
    get_cmd_parts.extend(["-o", "jsonpath={.spec.replicas}"])

    current_replicas_result = host.get_fact(Command, command=" ".join(get_cmd_parts))

    try:
        current_replicas = int(current_replicas_result.stdout[0]) if current_replicas_result.stdout else 0
    except (ValueError, IndexError):
        current_replicas = 0

    # Only scale if needed
    if current_replicas != replicas:
        # Build kubectl scale command
        cmd_parts = ["kubectl", "scale", resource_type, resource_name]
        cmd_parts.extend(["--replicas", str(replicas)])

        # Add context and kubeconfig options
        if context:
            cmd_parts.extend(["--context", context])
        if kubeconfig:
            cmd_parts.extend(["--kubeconfig", kubeconfig])
        if namespace:
            cmd_parts.extend(["--namespace", namespace])

        if wait:
            cmd_parts.extend(["--timeout", timeout])

        yield StringCommand(" ".join(cmd_parts))


@operation()
def kubectl_rollout(
    action: str,
    resource_type: str,
    resource_name: str,
    namespace: Optional[str] = None,
    kubeconfig: Optional[str] = None,
    context: Optional[str] = None,
    timeout: str = "600s",
):
    """
    Manage Kubernetes rollouts using kubectl rollout.

    Args:
        action: Rollout action (restart, status, history, undo)
        resource_type: Type of resource (deployment, daemonset, statefulset)
        resource_name: Name of the resource
        namespace: Target namespace
        kubeconfig: Path to kubeconfig file
        context: Kubernetes context to use
        timeout: Timeout for rollout operations

    Example:
        kubectl_rollout(
            action="restart",
            resource_type="deployment",
            resource_name="my-app",
            namespace="production"
        )
    """
    valid_actions = ["restart", "status", "history", "undo"]
    if action not in valid_actions:
        raise OperationError(f"Invalid rollout action: {action}. Must be one of: {valid_actions}")

    # Build kubectl rollout command
    cmd_parts = ["kubectl", "rollout", action, f"{resource_type}/{resource_name}"]

    # Add context and kubeconfig options
    if context:
        cmd_parts.extend(["--context", context])
    if kubeconfig:
        cmd_parts.extend(["--kubeconfig", kubeconfig])
    if namespace:
        cmd_parts.extend(["--namespace", namespace])

    if action in ["restart", "undo"]:
        cmd_parts.extend(["--timeout", timeout])

    yield StringCommand(" ".join(cmd_parts))


@operation()
def helm_install(
    release_name: str,
    chart: str,
    namespace: Optional[str] = None,
    values_file: Optional[str] = None,
    values: Optional[Dict] = None,
    version: Optional[str] = None,
    repo: Optional[str] = None,
    create_namespace: bool = False,
    wait: bool = True,
    timeout: str = "300s",
    upgrade_if_exists: bool = True,
):
    """
    Install or upgrade Helm charts.

    Args:
        release_name: Name of the Helm release
        chart: Chart name or path
        namespace: Target namespace
        values_file: Path to values file
        values: Values as dictionary
        version: Chart version
        repo: Helm repository URL
        create_namespace: Create namespace if it doesn't exist
        wait: Wait for deployment to complete
        timeout: Timeout for operations
        upgrade_if_exists: Upgrade if release already exists

    Example:
        helm_install(
            release_name="my-app",
            chart="nginx",
            namespace="production",
            values={"replicaCount": 3}
        )
    """
    # Check if release exists
    check_cmd = f"helm list -n {namespace or 'default'} -q | grep -w {release_name}"
    release_exists = host.get_fact(Command, command=check_cmd)

    if release_exists.stdout and upgrade_if_exists:
        # Use helm upgrade
        cmd_parts = ["helm", "upgrade", release_name, chart]
    else:
        # Use helm install
        cmd_parts = ["helm", "install", release_name, chart]

    # Add namespace options
    if namespace:
        cmd_parts.extend(["--namespace", namespace])
        if create_namespace and not release_exists.stdout:
            cmd_parts.append("--create-namespace")

    # Add chart options
    if version:
        cmd_parts.extend(["--version", version])
    if repo:
        cmd_parts.extend(["--repo", repo])

    # Add values
    if values_file:
        cmd_parts.extend(["-f", values_file])
    if values:
        for key, value in values.items():
            cmd_parts.extend(["--set", f"{key}={value}"])

    # Add deployment options
    if wait:
        cmd_parts.extend(["--wait", "--timeout", timeout])

    yield StringCommand(" ".join(cmd_parts))


@operation()
def helm_upgrade(
    release_name: str,
    chart: str,
    namespace: Optional[str] = None,
    values_file: Optional[str] = None,
    values: Optional[Dict] = None,
    version: Optional[str] = None,
    repo: Optional[str] = None,
    wait: bool = True,
    timeout: str = "300s",
    install_if_missing: bool = True,
):
    """
    Upgrade Helm releases.

    Args:
        release_name: Name of the Helm release
        chart: Chart name or path
        namespace: Target namespace
        values_file: Path to values file
        values: Values as dictionary
        version: Chart version
        repo: Helm repository URL
        wait: Wait for deployment to complete
        timeout: Timeout for operations
        install_if_missing: Install if release doesn't exist

    Example:
        helm_upgrade(
            release_name="my-app",
            chart="nginx",
            namespace="production",
            version="1.2.0"
        )
    """
    # Build helm upgrade command
    cmd_parts = ["helm", "upgrade", release_name, chart]

    if install_if_missing:
        cmd_parts.append("--install")

    # Add namespace options
    if namespace:
        cmd_parts.extend(["--namespace", namespace])

    # Add chart options
    if version:
        cmd_parts.extend(["--version", version])
    if repo:
        cmd_parts.extend(["--repo", repo])

    # Add values
    if values_file:
        cmd_parts.extend(["-f", values_file])
    if values:
        for key, value in values.items():
            cmd_parts.extend(["--set", f"{key}={value}"])

    # Add deployment options
    if wait:
        cmd_parts.extend(["--wait", "--timeout", timeout])

    yield StringCommand(" ".join(cmd_parts))


@operation()
def helm_uninstall(
    release_name: str,
    namespace: Optional[str] = None,
    keep_history: bool = False,
    wait: bool = True,
    timeout: str = "300s",
):
    """
    Uninstall Helm releases.

    Args:
        release_name: Name of the Helm release
        namespace: Target namespace
        keep_history: Keep release history
        wait: Wait for uninstall to complete
        timeout: Timeout for operations

    Example:
        helm_uninstall(
            release_name="my-app",
            namespace="production"
        )
    """
    # Check if release exists
    check_cmd = f"helm list -n {namespace or 'default'} -q | grep -w {release_name}"
    release_exists = host.get_fact(Command, command=check_cmd)

    if release_exists.stdout:
        # Build helm uninstall command
        cmd_parts = ["helm", "uninstall", release_name]

        # Add namespace options
        if namespace:
            cmd_parts.extend(["--namespace", namespace])

        # Add uninstall options
        if keep_history:
            cmd_parts.append("--keep-history")
        if wait:
            cmd_parts.extend(["--wait", "--timeout", timeout])

        yield StringCommand(" ".join(cmd_parts))