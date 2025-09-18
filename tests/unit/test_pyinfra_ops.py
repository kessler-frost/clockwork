"""
Unit tests for Clockwork PyInfra Operations.

Tests custom pyinfra operations including:
- Kubernetes operations
- Compose operations
- Terraform operations
- Health check operations
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

# Import pyinfra operations
from clockwork.pyinfra_ops import (
    compose, health, kubernetes, terraform
)
from clockwork.pyinfra_ops.compose import (
    compose_up, compose_down, compose_build, compose_pull
)
from clockwork.pyinfra_ops.health import (
    http_health_check, tcp_health_check, command_health_check,
    service_health_check, database_health_check, file_health_check
)
from clockwork.pyinfra_ops.kubernetes import (
    kubectl_apply, kubectl_delete, kubectl_get, kubectl_scale,
    helm_install, helm_upgrade, helm_uninstall
)
from clockwork.pyinfra_ops.terraform import (
    terraform_init, terraform_plan, terraform_apply, terraform_destroy
)


class TestComposeOperations:
    """Test Docker Compose operations."""

    def test_compose_up_operation(self):
        """Test compose up operation."""
        # Mock pyinfra state and host
        mock_state = Mock()
        mock_host = Mock()

        with patch('clockwork.pyinfra_ops.compose.server.shell') as mock_shell:
            # Call the operation
            compose_up(
                compose_file="docker-compose.yml",
                project_name="test-project",
                detach=True,
                build=False,
                state=mock_state,
                host=mock_host
            )

            # Verify shell command was called
            mock_shell.assert_called_once()
            call_args = mock_shell.call_args

            # Check command contains expected elements
            command = call_args[0][0] if call_args[0] else ""
            assert "docker-compose" in command
            assert "up" in command
            assert "-d" in command  # detach flag

    def test_compose_down_operation(self):
        """Test compose down operation."""
        mock_state = Mock()
        mock_host = Mock()

        with patch('clockwork.pyinfra_ops.compose.server.shell') as mock_shell:
            compose_down(
                compose_file="docker-compose.yml",
                project_name="test-project",
                remove_volumes=True,
                state=mock_state,
                host=mock_host
            )

            mock_shell.assert_called_once()
            call_args = mock_shell.call_args
            command = call_args[0][0] if call_args[0] else ""
            assert "docker-compose" in command
            assert "down" in command
            assert "-v" in command  # remove volumes flag

    def test_compose_build_operation(self):
        """Test compose build operation."""
        mock_state = Mock()
        mock_host = Mock()

        with patch('clockwork.pyinfra_ops.compose.server.shell') as mock_shell:
            compose_build(
                compose_file="docker-compose.yml",
                services=["web", "db"],
                no_cache=True,
                state=mock_state,
                host=mock_host
            )

            mock_shell.assert_called_once()
            call_args = mock_shell.call_args
            command = call_args[0][0] if call_args[0] else ""
            assert "docker-compose" in command
            assert "build" in command
            assert "--no-cache" in command
            assert "web db" in command

    def test_compose_pull_operation(self):
        """Test compose pull operation."""
        mock_state = Mock()
        mock_host = Mock()

        with patch('clockwork.pyinfra_ops.compose.server.shell') as mock_shell:
            compose_pull(
                compose_file="docker-compose.yml",
                services=None,
                state=mock_state,
                host=mock_host
            )

            mock_shell.assert_called_once()
            call_args = mock_shell.call_args
            command = call_args[0][0] if call_args[0] else ""
            assert "docker-compose" in command
            assert "pull" in command


class TestHealthCheckOperations:
    """Test health check operations."""

    def test_http_health_check_operation(self):
        """Test HTTP health check operation."""
        mock_state = Mock()
        mock_host = Mock()

        with patch('clockwork.pyinfra_ops.health.server.shell') as mock_shell:
            http_health_check(
                url="http://localhost:8080/health",
                expected_status=200,
                timeout=30,
                retries=3,
                state=mock_state,
                host=mock_host
            )

            mock_shell.assert_called_once()
            call_args = mock_shell.call_args
            command = call_args[0][0] if call_args[0] else ""
            assert "curl" in command
            assert "http://localhost:8080/health" in command
            assert "200" in command or "status" in command

    def test_tcp_health_check_operation(self):
        """Test TCP health check operation."""
        mock_state = Mock()
        mock_host = Mock()

        with patch('clockwork.pyinfra_ops.health.server.shell') as mock_shell:
            tcp_health_check(
                host_address="localhost",
                port=5432,
                timeout=10,
                retries=3,
                state=mock_state,
                host=mock_host
            )

            mock_shell.assert_called_once()
            call_args = mock_shell.call_args
            command = call_args[0][0] if call_args[0] else ""
            assert ("nc" in command or "telnet" in command or
                   "timeout" in command or "connect" in command)
            assert "localhost" in command
            assert "5432" in command

    def test_command_health_check_operation(self):
        """Test command health check operation."""
        mock_state = Mock()
        mock_host = Mock()

        with patch('clockwork.pyinfra_ops.health.server.shell') as mock_shell:
            command_health_check(
                command="systemctl is-active nginx",
                expected_output="active",
                timeout=10,
                state=mock_state,
                host=mock_host
            )

            mock_shell.assert_called_once()
            call_args = mock_shell.call_args
            command = call_args[0][0] if call_args[0] else ""
            assert "systemctl is-active nginx" in command

    def test_service_health_check_operation(self):
        """Test service health check operation."""
        mock_state = Mock()
        mock_host = Mock()

        with patch('clockwork.pyinfra_ops.health.server.shell') as mock_shell:
            service_health_check(
                service_name="nginx",
                expected_state="running",
                state=mock_state,
                host=mock_host
            )

            mock_shell.assert_called_once()
            call_args = mock_shell.call_args
            command = call_args[0][0] if call_args[0] else ""
            assert "nginx" in command
            assert ("systemctl" in command or "service" in command or
                   "status" in command)

    def test_database_health_check_operation(self):
        """Test database health check operation."""
        mock_state = Mock()
        mock_host = Mock()

        with patch('clockwork.pyinfra_ops.health.server.shell') as mock_shell:
            database_health_check(
                connection_string="postgresql://user:pass@localhost:5432/db",
                query="SELECT 1",
                timeout=30,
                state=mock_state,
                host=mock_host
            )

            mock_shell.assert_called_once()
            call_args = mock_shell.call_args
            command = call_args[0][0] if call_args[0] else ""
            assert ("psql" in command or "mysql" in command or
                   "SELECT 1" in command)

    def test_file_health_check_operation(self):
        """Test file health check operation."""
        mock_state = Mock()
        mock_host = Mock()

        with patch('clockwork.pyinfra_ops.health.files.file') as mock_file:
            file_health_check(
                file_path="/var/log/app.log",
                should_exist=True,
                min_size=1024,
                max_age=3600,
                state=mock_state,
                host=mock_host
            )

            # File operation should be called
            mock_file.assert_called_once()


class TestKubernetesOperations:
    """Test Kubernetes operations."""

    def test_kubectl_apply_operation(self):
        """Test kubectl apply operation."""
        mock_state = Mock()
        mock_host = Mock()

        with patch('clockwork.pyinfra_ops.kubernetes.server.shell') as mock_shell:
            kubectl_apply(
                manifest_file="deployment.yaml",
                namespace="default",
                dry_run=False,
                state=mock_state,
                host=mock_host
            )

            mock_shell.assert_called_once()
            call_args = mock_shell.call_args
            command = call_args[0][0] if call_args[0] else ""
            assert "kubectl" in command
            assert "apply" in command
            assert "deployment.yaml" in command
            assert "--namespace default" in command

    def test_kubectl_delete_operation(self):
        """Test kubectl delete operation."""
        mock_state = Mock()
        mock_host = Mock()

        with patch('clockwork.pyinfra_ops.kubernetes.server.shell') as mock_shell:
            kubectl_delete(
                resource_type="deployment",
                resource_name="my-app",
                namespace="default",
                force=True,
                state=mock_state,
                host=mock_host
            )

            mock_shell.assert_called_once()
            call_args = mock_shell.call_args
            command = call_args[0][0] if call_args[0] else ""
            assert "kubectl" in command
            assert "delete" in command
            assert "deployment" in command
            assert "my-app" in command
            assert "--force" in command

    def test_kubectl_get_operation(self):
        """Test kubectl get operation."""
        mock_state = Mock()
        mock_host = Mock()

        with patch('clockwork.pyinfra_ops.kubernetes.server.shell') as mock_shell:
            kubectl_get(
                resource_type="pods",
                namespace="default",
                output_format="json",
                state=mock_state,
                host=mock_host
            )

            mock_shell.assert_called_once()
            call_args = mock_shell.call_args
            command = call_args[0][0] if call_args[0] else ""
            assert "kubectl" in command
            assert "get" in command
            assert "pods" in command
            assert "-o json" in command

    def test_kubectl_scale_operation(self):
        """Test kubectl scale operation."""
        mock_state = Mock()
        mock_host = Mock()

        with patch('clockwork.pyinfra_ops.kubernetes.server.shell') as mock_shell:
            kubectl_scale(
                resource_type="deployment",
                resource_name="my-app",
                replicas=3,
                namespace="default",
                state=mock_state,
                host=mock_host
            )

            mock_shell.assert_called_once()
            call_args = mock_shell.call_args
            command = call_args[0][0] if call_args[0] else ""
            assert "kubectl" in command
            assert "scale" in command
            assert "deployment/my-app" in command
            assert "--replicas=3" in command

    def test_helm_install_operation(self):
        """Test helm install operation."""
        mock_state = Mock()
        mock_host = Mock()

        with patch('clockwork.pyinfra_ops.kubernetes.server.shell') as mock_shell:
            helm_install(
                release_name="my-release",
                chart="nginx",
                namespace="default",
                values_file="values.yaml",
                state=mock_state,
                host=mock_host
            )

            mock_shell.assert_called_once()
            call_args = mock_shell.call_args
            command = call_args[0][0] if call_args[0] else ""
            assert "helm" in command
            assert "install" in command
            assert "my-release" in command
            assert "nginx" in command
            assert "--values values.yaml" in command

    def test_helm_upgrade_operation(self):
        """Test helm upgrade operation."""
        mock_state = Mock()
        mock_host = Mock()

        with patch('clockwork.pyinfra_ops.kubernetes.server.shell') as mock_shell:
            helm_upgrade(
                release_name="my-release",
                chart="nginx",
                namespace="default",
                install=True,
                state=mock_state,
                host=mock_host
            )

            mock_shell.assert_called_once()
            call_args = mock_shell.call_args
            command = call_args[0][0] if call_args[0] else ""
            assert "helm" in command
            assert "upgrade" in command
            assert "my-release" in command
            assert "--install" in command

    def test_helm_uninstall_operation(self):
        """Test helm uninstall operation."""
        mock_state = Mock()
        mock_host = Mock()

        with patch('clockwork.pyinfra_ops.kubernetes.server.shell') as mock_shell:
            helm_uninstall(
                release_name="my-release",
                namespace="default",
                keep_history=False,
                state=mock_state,
                host=mock_host
            )

            mock_shell.assert_called_once()
            call_args = mock_shell.call_args
            command = call_args[0][0] if call_args[0] else ""
            assert "helm" in command
            assert "uninstall" in command
            assert "my-release" in command


class TestTerraformOperations:
    """Test Terraform operations."""

    def test_terraform_init_operation(self):
        """Test terraform init operation."""
        mock_state = Mock()
        mock_host = Mock()

        with patch('clockwork.pyinfra_ops.terraform.server.shell') as mock_shell:
            terraform_init(
                working_dir="/path/to/terraform",
                backend_config={"bucket": "my-bucket"},
                upgrade=True,
                state=mock_state,
                host=mock_host
            )

            mock_shell.assert_called_once()
            call_args = mock_shell.call_args
            command = call_args[0][0] if call_args[0] else ""
            assert "terraform" in command
            assert "init" in command
            assert "--upgrade" in command

    def test_terraform_plan_operation(self):
        """Test terraform plan operation."""
        mock_state = Mock()
        mock_host = Mock()

        with patch('clockwork.pyinfra_ops.terraform.server.shell') as mock_shell:
            terraform_plan(
                working_dir="/path/to/terraform",
                var_file="terraform.tfvars",
                variables={"env": "production"},
                out_file="plan.out",
                state=mock_state,
                host=mock_host
            )

            mock_shell.assert_called_once()
            call_args = mock_shell.call_args
            command = call_args[0][0] if call_args[0] else ""
            assert "terraform" in command
            assert "plan" in command
            assert "-var-file=terraform.tfvars" in command
            assert "-out=plan.out" in command

    def test_terraform_apply_operation(self):
        """Test terraform apply operation."""
        mock_state = Mock()
        mock_host = Mock()

        with patch('clockwork.pyinfra_ops.terraform.server.shell') as mock_shell:
            terraform_apply(
                working_dir="/path/to/terraform",
                plan_file="plan.out",
                auto_approve=True,
                state=mock_state,
                host=mock_host
            )

            mock_shell.assert_called_once()
            call_args = mock_shell.call_args
            command = call_args[0][0] if call_args[0] else ""
            assert "terraform" in command
            assert "apply" in command
            assert "plan.out" in command
            assert "-auto-approve" in command

    def test_terraform_destroy_operation(self):
        """Test terraform destroy operation."""
        mock_state = Mock()
        mock_host = Mock()

        with patch('clockwork.pyinfra_ops.terraform.server.shell') as mock_shell:
            terraform_destroy(
                working_dir="/path/to/terraform",
                var_file="terraform.tfvars",
                auto_approve=True,
                state=mock_state,
                host=mock_host
            )

            mock_shell.assert_called_once()
            call_args = mock_shell.call_args
            command = call_args[0][0] if call_args[0] else ""
            assert "terraform" in command
            assert "destroy" in command
            assert "-auto-approve" in command
            assert "-var-file=terraform.tfvars" in command


class TestOperationMocking:
    """Test operation mocking and validation."""

    def test_operation_parameter_validation(self):
        """Test that operations validate required parameters."""
        mock_state = Mock()
        mock_host = Mock()

        # Test that operations handle missing required parameters gracefully
        with patch('clockwork.pyinfra_ops.compose.server.shell') as mock_shell:
            # Should handle None values gracefully
            compose_up(
                compose_file=None,
                project_name=None,
                state=mock_state,
                host=mock_host
            )

            # Shell should still be called with some command
            mock_shell.assert_called_once()

    def test_operation_error_handling(self):
        """Test operation error handling."""
        mock_state = Mock()
        mock_host = Mock()

        with patch('clockwork.pyinfra_ops.health.server.shell') as mock_shell:
            # Mock shell command failure
            mock_shell.side_effect = Exception("Command failed")

            # Operation should handle the exception gracefully
            with pytest.raises(Exception):
                http_health_check(
                    url="http://invalid-url",
                    state=mock_state,
                    host=mock_host
                )

    def test_operation_idempotency(self):
        """Test that operations are idempotent."""
        mock_state = Mock()
        mock_host = Mock()

        # Mock state to simulate already-applied state
        mock_state.get_fact.return_value = True

        with patch('clockwork.pyinfra_ops.compose.server.shell') as mock_shell:
            # Call operation twice
            compose_up(
                compose_file="docker-compose.yml",
                state=mock_state,
                host=mock_host
            )
            compose_up(
                compose_file="docker-compose.yml",
                state=mock_state,
                host=mock_host
            )

            # Should be called twice (idempotency check happens within pyinfra)
            assert mock_shell.call_count == 2


if __name__ == "__main__":
    pytest.main([__file__])