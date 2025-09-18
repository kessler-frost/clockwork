"""
Clockwork PyInfra Operations Library

This module provides custom pyinfra operations specifically designed for Clockwork's
infrastructure management needs. These operations extend pyinfra's capabilities
with Clockwork-specific functionality for Kubernetes, Docker Compose, Terraform,
and health checking.

All operations follow pyinfra conventions:
- Idempotent execution
- Dry-run support
- Proper error handling and logging
- State comparison and command generation
"""

from . import compose
from . import health
from . import kubernetes
from . import terraform

# Import specific operations for direct access
from .compose import (
    compose_up,
    compose_down,
    compose_build,
    compose_pull,
    compose_logs,
    compose_ps,
    compose_restart,
    compose_stop,
    compose_exec,
    compose_config,
)

from .health import (
    http_health_check,
    tcp_health_check,
    command_health_check,
    service_health_check,
    database_health_check,
    file_health_check,
)

from .kubernetes import (
    kubectl_apply,
    kubectl_delete,
    kubectl_get,
    kubectl_scale,
    kubectl_rollout,
    helm_install,
    helm_upgrade,
    helm_uninstall,
)

from .terraform import (
    terraform_init,
    terraform_plan,
    terraform_apply,
    terraform_destroy,
    terraform_workspace,
    terraform_output,
    terraform_import,
    terraform_refresh,
    terraform_validate,
    terraform_fmt,
)

__all__ = [
    # Modules
    "compose",
    "health",
    "kubernetes",
    "terraform",
    # Compose operations
    "compose_up",
    "compose_down",
    "compose_build",
    "compose_pull",
    "compose_logs",
    "compose_ps",
    "compose_restart",
    "compose_stop",
    "compose_exec",
    "compose_config",
    # Health operations
    "http_health_check",
    "tcp_health_check",
    "command_health_check",
    "service_health_check",
    "database_health_check",
    "file_health_check",
    # Kubernetes operations
    "kubectl_apply",
    "kubectl_delete",
    "kubectl_get",
    "kubectl_scale",
    "kubectl_rollout",
    "helm_install",
    "helm_upgrade",
    "helm_uninstall",
    # Terraform operations
    "terraform_init",
    "terraform_plan",
    "terraform_apply",
    "terraform_destroy",
    "terraform_workspace",
    "terraform_output",
    "terraform_import",
    "terraform_refresh",
    "terraform_validate",
    "terraform_fmt",
]