#!/usr/bin/env python3
"""
Clockwork Runner Examples

This file demonstrates how to use the different execution runners
available in the Clockwork system for various deployment scenarios.
"""

import json
import logging
from pathlib import Path
import sys

# Add clockwork to path for examples
sys.path.insert(0, str(Path(__file__).parent.parent))

from clockwork.forge.runner import (
    RunnerFactory, LocalRunner, DockerRunner, SSHRunner, KubernetesRunner,
    RunnerConfig, DockerConfig, SSHConfig, KubernetesConfig, select_runner
)
from clockwork.forge.executor import (
    ArtifactExecutor, create_secure_executor, create_development_executor,
    create_executor_for_environment, get_available_executors
)
from clockwork.models import Artifact, ArtifactBundle, ExecutionStep

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def example_local_execution():
    """Example: Local execution with UV."""
    logger.info("=== Local Execution Example ===")
    
    # Create a simple Python artifact
    artifact = Artifact(
        path="scripts/hello.py",
        mode="0755",
        purpose="hello_world",
        lang="python",
        content="""
import sys
import os
print("Hello from Clockwork!")
print(f"Running on: {sys.platform}")
print(f"Python version: {sys.version}")
print(f"Working directory: {os.getcwd()}")
"""
    )
    
    # Create bundle
    bundle = ArtifactBundle(
        version="1",
        artifacts=[artifact],
        steps=[ExecutionStep(
            purpose="hello_world",
            run={"cmd": ["uv", "run", "python", "scripts/hello.py"]}
        )],
        vars={"ENVIRONMENT": "development"}
    )
    
    # Execute with local runner
    runner = LocalRunner()
    results = runner.execute_bundle(bundle)
    
    for result in results:
        logger.info(f"Result: {result.status}, Output: {result.stdout}")


def example_docker_execution():
    """Example: Docker container execution."""
    logger.info("=== Docker Execution Example ===")
    
    # Check if Docker is available
    available = RunnerFactory.get_available_runners()
    if "docker" not in available:
        logger.info("Docker not available, skipping example")
        return
    
    # Create Docker configuration
    config = DockerConfig(
        image="python:3.12-slim",
        pull_policy="if-not-present",
        remove_container=True,
        environment_vars={"PYTHONPATH": "/workspace"}
    )
    
    # Create artifact for containerized execution
    artifact = Artifact(
        path="scripts/container_app.py",
        mode="0755",
        purpose="container_app",
        lang="python",
        content="""
import os
import platform
print("Running in Docker container!")
print(f"Platform: {platform.platform()}")
print(f"Container hostname: {os.uname().nodename}")
print("Container execution successful!")
"""
    )
    
    bundle = ArtifactBundle(
        version="1",
        artifacts=[artifact],
        steps=[ExecutionStep(
            purpose="container_app",
            run={"cmd": ["python3", "scripts/container_app.py"]}
        )],
        vars={"CONTAINER_ENV": "production"}
    )
    
    # Execute with Docker runner
    runner = DockerRunner(config)
    if runner.validate_environment():
        results = runner.execute_bundle(bundle)
        for result in results:
            logger.info(f"Docker Result: {result.status}, Output: {result.stdout}")
    else:
        logger.info("Docker environment validation failed")


def example_ssh_execution():
    """Example: SSH remote execution (requires SSH setup)."""
    logger.info("=== SSH Execution Example ===")
    
    # This is a demonstration - would need actual SSH server
    config = SSHConfig(
        hostname="remote-server.example.com",
        username="deploy",
        port=22,
        private_key_path="~/.ssh/id_rsa",
        remote_work_dir="/tmp/clockwork-deploy",
        cleanup_on_exit=True
    )
    
    artifact = Artifact(
        path="scripts/deploy_script.sh",
        mode="0755",
        purpose="remote_deploy",
        lang="bash",
        content="""#!/bin/bash
echo "Deploying application on remote server..."
echo "Server: $(hostname)"
echo "User: $(whoami)"
echo "Date: $(date)"
echo "Deployment completed successfully!"
"""
    )
    
    bundle = ArtifactBundle(
        version="1",
        artifacts=[artifact],
        steps=[ExecutionStep(
            purpose="remote_deploy",
            run={"cmd": ["bash", "scripts/deploy_script.sh"]}
        )],
        vars={"DEPLOY_ENV": "production", "VERSION": "1.0.0"}
    )
    
    logger.info(f"SSH configuration: {config.hostname}@{config.username}")
    logger.info("Note: This example requires actual SSH server configuration")


def example_kubernetes_execution():
    """Example: Kubernetes job execution."""
    logger.info("=== Kubernetes Execution Example ===")
    
    config = KubernetesConfig(
        namespace="clockwork-jobs",
        image="python:3.12-slim",
        job_name_prefix="clockwork-task",
        active_deadline_seconds=300,
        resources={
            "requests": {"memory": "128Mi", "cpu": "100m"},
            "limits": {"memory": "256Mi", "cpu": "200m"}
        }
    )
    
    artifact = Artifact(
        path="scripts/k8s_job.py",
        mode="0755",
        purpose="kubernetes_job",
        lang="python",
        content="""
import os
import time
print("Starting Kubernetes job...")
print(f"Pod name: {os.environ.get('HOSTNAME', 'unknown')}")
print(f"Namespace: {os.environ.get('POD_NAMESPACE', 'unknown')}")
print("Processing data...")
time.sleep(2)
print("Kubernetes job completed successfully!")
"""
    )
    
    bundle = ArtifactBundle(
        version="1",
        artifacts=[artifact],
        steps=[ExecutionStep(
            purpose="kubernetes_job",
            run={"cmd": ["python3", "scripts/k8s_job.py"]}
        )],
        vars={"JOB_TYPE": "batch", "PRIORITY": "high"}
    )
    
    logger.info(f"Kubernetes configuration: namespace={config.namespace}, image={config.image}")
    logger.info("Note: This example requires Kubernetes cluster access")


def example_runner_selection():
    """Example: Automatic runner selection based on context."""
    logger.info("=== Runner Selection Example ===")
    
    contexts = [
        {"description": "Default local", "context": {}},
        {"description": "Isolated execution", "context": {"requires_isolation": True}},
        {"description": "Remote deployment", "context": {"remote_host": "prod-server.com"}},
        {"description": "Kubernetes job", "context": {"kubernetes_namespace": "jobs"}},
        {"description": "Specific runner", "context": {"runner_type": "docker"}}
    ]
    
    for example in contexts:
        selected = select_runner(example["context"])
        logger.info(f"{example['description']}: {selected}")


def example_executor_integration():
    """Example: Using runners with the enhanced executor."""
    logger.info("=== Executor Integration Example ===")
    
    # Get available execution environments
    available = get_available_executors()
    logger.info(f"Available executors: {available}")
    
    # Create different types of executors
    if available["local"]:
        local_executor = create_development_executor("local")
        logger.info("Created local development executor")
    
    if available["docker"]:
        docker_executor = create_secure_executor("docker", {
            "runner_config": {"image": "python:3.12-slim"}
        })
        logger.info("Created secure Docker executor")
    
    # Create executor for specific environment
    try:
        env_executor = create_executor_for_environment("local")
        logger.info("Created environment-specific executor")
    except ValueError as e:
        logger.error(f"Failed to create executor: {e}")


def example_advanced_configuration():
    """Example: Advanced runner configurations."""
    logger.info("=== Advanced Configuration Example ===")
    
    # Docker with custom settings
    docker_config = DockerConfig(
        image="python:3.12-slim",
        pull_policy="always",
        volumes={"/host/data": "/container/data"},
        ports={8080: 8080},
        environment_vars={"DEBUG": "true"},
        labels={"project": "clockwork", "environment": "test"}
    )
    
    # SSH with advanced options
    ssh_config = SSHConfig(
        hostname="deploy.example.com",
        username="deployer",
        port=2222,
        private_key_path="~/.ssh/deploy_key",
        connect_timeout=30,
        compression=True,
        host_key_verification=False  # Only for testing!
    )
    
    # Kubernetes with resource constraints
    k8s_config = KubernetesConfig(
        namespace="production",
        image="myapp:latest",
        service_account="clockwork-runner",
        resources={
            "requests": {"memory": "512Mi", "cpu": "500m"},
            "limits": {"memory": "1Gi", "cpu": "1000m"}
        },
        node_selector={"node-type": "compute"},
        tolerations=[{
            "key": "dedicated",
            "operator": "Equal",
            "value": "clockwork",
            "effect": "NoSchedule"
        }]
    )
    
    configs = [
        ("Docker", docker_config),
        ("SSH", ssh_config),
        ("Kubernetes", k8s_config)
    ]
    
    for name, config in configs:
        logger.info(f"{name} configuration: {type(config).__name__}")


def main():
    """Run all examples."""
    logger.info("Clockwork Runner Examples")
    logger.info("=" * 50)
    
    # Run examples
    example_local_execution()
    example_docker_execution()
    example_ssh_execution()
    example_kubernetes_execution()
    example_runner_selection()
    example_executor_integration()
    example_advanced_configuration()
    
    logger.info("\nAll examples completed!")


if __name__ == "__main__":
    main()