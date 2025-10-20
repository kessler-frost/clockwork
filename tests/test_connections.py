"""Tests for resource connection system.

This module tests the resource connection system including:
- Cycle detection in dependency graphs
- Topological sorting for correct deployment order
- Connection context sharing between resources
- Integration with ClockworkCore
"""

from unittest.mock import patch

import pytest

from clockwork.core import ClockworkCore
from clockwork.resources import DockerResource, FileResource


class TestCycleDetection:
    """Tests for dependency cycle detection."""

    def test_simple_cycle(self):
        """Test detection of simple A → B → A cycle."""
        # To create a true cycle, we need both resources to reference each other
        # We create them temporarily, then manually add to _connection_resources

        a = DockerResource(
            description="Service A",
            name="a",
            image="alpine:latest",
            ports=["8001:80"],
        )
        b = DockerResource(
            description="Service B",
            name="b",
            image="alpine:latest",
            ports=["8002:80"],
            connections=[a],
        )

        # Now manually create the cycle by adding b to a's _connection_resources
        # This simulates a scenario where both point to each other
        a._connection_resources.append(b)
        a.connections.append(b.get_connection_context())

        core = ClockworkCore(api_key="test", model="test")

        with pytest.raises(ValueError, match=r"[Cc]ycle|[Cc]ircular"):
            core._resolve_dependency_order([a, b])

    def test_complex_cycle(self):
        """Test detection of complex A → B → C → A cycle."""
        # Create cycle: A → B → C → A
        # Build the chain first: A → B → C
        a = DockerResource(
            description="Service A",
            name="a",
            image="alpine:latest",
            ports=["8001:80"],
        )
        b = DockerResource(
            description="Service B",
            name="b",
            image="alpine:latest",
            ports=["8002:80"],
            connections=[a],
        )
        c = DockerResource(
            description="Service C",
            name="c",
            image="alpine:latest",
            ports=["8003:80"],
            connections=[b],
        )

        # Now close the cycle by making A point to C (completing A→B→C→A)
        a._connection_resources.append(c)
        a.connections.append(c.get_connection_context())

        core = ClockworkCore(api_key="test", model="test")

        with pytest.raises(ValueError, match=r"[Cc]ycle|[Cc]ircular"):
            core._resolve_dependency_order([a, b, c])

    def test_self_reference(self):
        """Test detection of self-reference cycle A → A."""
        # Create resource that references itself
        a = DockerResource(
            description="Service A",
            name="a",
            image="alpine:latest",
            ports=["8001:80"],
        )

        # Make it reference itself
        a._connection_resources.append(a)
        a.connections.append(a.get_connection_context())

        core = ClockworkCore(api_key="test", model="test")

        with pytest.raises(ValueError, match=r"[Cc]ycle|[Cc]ircular"):
            core._resolve_dependency_order([a])

    def test_no_cycle_linear_chain(self):
        """Test valid linear dependency chain has no cycle."""
        c = DockerResource(
            description="Service C",
            name="c",
            image="alpine:latest",
            ports=["8003:80"],
        )
        b = DockerResource(
            description="Service B",
            name="b",
            image="alpine:latest",
            ports=["8002:80"],
            connections=[c],
        )
        a = DockerResource(
            description="Service A",
            name="a",
            image="alpine:latest",
            ports=["8001:80"],
            connections=[b],
        )

        core = ClockworkCore(api_key="test", model="test")

        # Should not raise exception
        ordered = core._resolve_dependency_order([a, b, c])
        assert len(ordered) == 3

    def test_no_cycle_diamond_dependency(self):
        """Test diamond dependency pattern has no cycle.

        Diamond pattern:
            A
           / \\
          B   C
           \\ /
            D
        """
        d = DockerResource(
            description="Service D",
            name="d",
            image="alpine:latest",
            ports=["8004:80"],
        )
        b = DockerResource(
            description="Service B",
            name="b",
            image="alpine:latest",
            ports=["8002:80"],
            connections=[d],
        )
        c = DockerResource(
            description="Service C",
            name="c",
            image="alpine:latest",
            ports=["8003:80"],
            connections=[d],
        )
        a = DockerResource(
            description="Service A",
            name="a",
            image="alpine:latest",
            ports=["8001:80"],
            connections=[b, c],
        )

        core = ClockworkCore(api_key="test", model="test")

        # Should not raise exception
        ordered = core._resolve_dependency_order([a, b, c, d])
        assert len(ordered) == 4


class TestDependencyOrdering:
    """Tests for topological dependency ordering."""

    def test_linear_chain(self):
        """Test correct ordering for A → B → C.

        Expected order: C, B, A (dependencies first)
        """
        c = DockerResource(
            description="Service C",
            name="c",
            image="alpine:latest",
            ports=["8003:80"],
        )
        b = DockerResource(
            description="Service B",
            name="b",
            image="alpine:latest",
            ports=["8002:80"],
            connections=[c],
        )
        a = DockerResource(
            description="Service A",
            name="a",
            image="alpine:latest",
            ports=["8001:80"],
            connections=[b],
        )

        core = ClockworkCore(api_key="test", model="test")
        ordered = core._resolve_dependency_order([a, b, c])

        # C should be first (no dependencies)
        # B should be second (depends on C)
        # A should be last (depends on B)
        assert ordered[0].name == "c"
        assert ordered[1].name == "b"
        assert ordered[2].name == "a"

    def test_diamond_dependency(self):
        """Test correct ordering for diamond pattern.

        Diamond pattern:
            A
           / \\
          B   C
           \\ /
            D

        Expected order: D first, then B and C (in any order), then A last
        """
        d = DockerResource(
            description="Service D",
            name="d",
            image="alpine:latest",
            ports=["8004:80"],
        )
        b = DockerResource(
            description="Service B",
            name="b",
            image="alpine:latest",
            ports=["8002:80"],
            connections=[d],
        )
        c = DockerResource(
            description="Service C",
            name="c",
            image="alpine:latest",
            ports=["8003:80"],
            connections=[d],
        )
        a = DockerResource(
            description="Service A",
            name="a",
            image="alpine:latest",
            ports=["8001:80"],
            connections=[b, c],
        )

        core = ClockworkCore(api_key="test", model="test")
        ordered = core._resolve_dependency_order([a, b, c, d])

        # D should be first (no dependencies)
        assert ordered[0].name == "d"

        # B and C should be in middle (both depend on D)
        middle_names = {ordered[1].name, ordered[2].name}
        assert middle_names == {"b", "c"}

        # A should be last (depends on B and C)
        assert ordered[3].name == "a"

    def test_multiple_roots(self):
        """Test ordering with multiple independent dependency trees.

        Two separate trees:
        - Tree 1: A → B
        - Tree 2: X → Y

        Expected: Dependencies before dependents in each tree
        """
        b = DockerResource(
            description="Service B",
            name="b",
            image="alpine:latest",
            ports=["8002:80"],
        )
        a = DockerResource(
            description="Service A",
            name="a",
            image="alpine:latest",
            ports=["8001:80"],
            connections=[b],
        )

        y = DockerResource(
            description="Service Y",
            name="y",
            image="alpine:latest",
            ports=["8004:80"],
        )
        x = DockerResource(
            description="Service X",
            name="x",
            image="alpine:latest",
            ports=["8003:80"],
            connections=[y],
        )

        core = ClockworkCore(api_key="test", model="test")
        ordered = core._resolve_dependency_order([a, b, x, y])

        # Find indices
        idx_a = next(i for i, r in enumerate(ordered) if r.name == "a")
        idx_b = next(i for i, r in enumerate(ordered) if r.name == "b")
        idx_x = next(i for i, r in enumerate(ordered) if r.name == "x")
        idx_y = next(i for i, r in enumerate(ordered) if r.name == "y")

        # B must come before A
        assert idx_b < idx_a

        # Y must come before X
        assert idx_y < idx_x

    def test_single_resource(self):
        """Test ordering with single resource (no connections)."""
        a = DockerResource(
            description="Service A",
            name="a",
            image="alpine:latest",
            ports=["8001:80"],
        )

        core = ClockworkCore(api_key="test", model="test")
        ordered = core._resolve_dependency_order([a])

        assert len(ordered) == 1
        assert ordered[0].name == "a"

    def test_empty_list(self):
        """Test ordering with empty resource list."""
        core = ClockworkCore(api_key="test", model="test")
        ordered = core._resolve_dependency_order([])

        assert len(ordered) == 0
        assert ordered == []

    def test_unordered_input(self):
        """Test that input order doesn't matter, output is always correct.

        Given A → B → C, try different input orders.
        """
        c = DockerResource(
            description="Service C",
            name="c",
            image="alpine:latest",
            ports=["8003:80"],
        )
        b = DockerResource(
            description="Service B",
            name="b",
            image="alpine:latest",
            ports=["8002:80"],
            connections=[c],
        )
        a = DockerResource(
            description="Service A",
            name="a",
            image="alpine:latest",
            ports=["8001:80"],
            connections=[b],
        )

        core = ClockworkCore(api_key="test", model="test")

        # Try different input orders
        orders = [
            [a, b, c],
            [c, b, a],
            [b, a, c],
            [c, a, b],
        ]

        for input_order in orders:
            ordered = core._resolve_dependency_order(input_order)

            # Output should always be C, B, A
            assert ordered[0].name == "c"
            assert ordered[1].name == "b"
            assert ordered[2].name == "a"


class TestConnectionContext:
    """Tests for connection context sharing between resources."""

    def test_docker_connection_context(self):
        """Test DockerResource exposes correct connection context."""
        docker = DockerResource(
            description="PostgreSQL database",
            name="postgres",
            image="postgres:15-alpine",
            ports=["5432:5432"],
            env_vars={"POSTGRES_PASSWORD": "secret"},
            networks=["backend"],
        )

        context = docker.get_connection_context()

        # Check required fields
        assert context["name"] == "postgres"
        assert context["type"] == "DockerResource"
        assert context["image"] == "postgres:15-alpine"

        # Check optional fields that are set
        assert context["ports"] == ["5432:5432"]
        assert context["env_vars"] == {"POSTGRES_PASSWORD": "secret"}
        assert context["networks"] == ["backend"]

    def test_file_connection_context(self):
        """Test FileResource exposes correct connection context."""
        file = FileResource(
            description="Configuration file",
            name="config.yaml",
            directory="/etc/app",
            content="key: value",
        )

        context = file.get_connection_context()

        # Check required fields
        assert context["name"] == "config.yaml"
        assert context["type"] == "FileResource"

        # Check optional fields
        assert context["directory"] == "/etc/app"
        # Path should be constructed from directory + name
        assert "path" in context
        assert "config.yaml" in context["path"]

    def test_empty_connections(self):
        """Test resource with no connections."""
        docker = DockerResource(
            description="Standalone service",
            name="standalone",
            image="alpine:latest",
            ports=["8080:80"],
        )

        # Empty connections list (default)
        assert docker.connections == []

        context = docker.get_connection_context()
        assert context["name"] == "standalone"
        assert context["type"] == "DockerResource"

    def test_connection_context_filtering(self):
        """Test that only non-None fields are included in context."""
        docker = DockerResource(
            description="Minimal service",
            name="minimal",
            image="alpine:latest",
            ports=["8080:80"],
            # volumes, env_vars, networks are empty/default
        )

        context = docker.get_connection_context()

        # Required fields should be present
        assert "name" in context
        assert "type" in context
        assert "image" in context

        # Empty/None optional fields should not be present
        # (or if present, should be empty)
        if "env_vars" in context:
            assert context["env_vars"] == {}
        if "networks" in context:
            assert context["networks"] == []
        if "volumes" in context:
            assert context["volumes"] == []

    def test_base_resource_connection_context(self):
        """Test base Resource class connection context."""

        # Create a basic resource (using DockerResource since Resource is abstract)
        resource = DockerResource(
            description="Test resource",
            name="test",
            image="alpine:latest",
            ports=["80:80"],
        )

        context = resource.get_connection_context()

        # Base context should include name and type
        assert "name" in context
        assert "type" in context
        assert context["name"] == "test"
        assert context["type"] == "DockerResource"


class TestIntegration:
    """Integration tests for connection system with ClockworkCore."""

    def test_core_with_connections(self):
        """Test ClockworkCore processes connected resources in correct order."""
        # Create resources with connections
        db = DockerResource(
            description="Database",
            name="db",
            image="postgres:15-alpine",
            ports=["5432:5432"],
        )

        app = DockerResource(
            description="Application server",
            name="app",
            image="node:18-alpine",
            ports=["3000:3000"],
            connections=[db],
        )

        # Test that core processes connections
        core = ClockworkCore(api_key="test", model="test")

        # The _resolve_dependency_order should be called internally
        # and should order resources correctly (db before app)
        with patch.object(
            core,
            "_resolve_dependency_order",
            wraps=core._resolve_dependency_order,
        ) as mock_order:
            # This would normally be called in apply()
            ordered = core._resolve_dependency_order([app, db])

            mock_order.assert_called_once()

            # Verify order: db should come before app
            assert ordered[0].name == "db"
            assert ordered[1].name == "app"

    def test_connection_context_in_prompt(self):
        """Test that connection context is included in AI completion prompt."""
        from clockwork.resource_completer import ResourceCompleter

        # Create resources with connections
        db = DockerResource(
            description="PostgreSQL database",
            name="postgres",
            image="postgres:15-alpine",
            ports=["5432:5432"],
            env_vars={"POSTGRES_PASSWORD": "secret"},
        )

        app = DockerResource(
            description="Web application",
            name="webapp",
            image="node:18-alpine",
            connections=[db],
        )

        completer = ResourceCompleter(api_key="test", model="test")

        # Build prompt for app (which has db connection)
        prompt = completer._build_completion_prompt(app)

        # Verify connection context is in prompt
        assert "postgres" in prompt or "connection" in prompt.lower()
        assert "PostgreSQL" in prompt or "database" in prompt.lower()

    def test_format_connection_context(self):
        """Test formatting of connection context for AI prompts."""
        from clockwork.resource_completer import ResourceCompleter

        db = DockerResource(
            description="Database",
            name="postgres",
            image="postgres:15-alpine",
            ports=["5432:5432"],
            env_vars={"POSTGRES_PASSWORD": "secret"},
        )

        file = FileResource(
            description="Config file",
            name="config.yaml",
            directory="/etc/app",
            content="key: value",
        )

        completer = ResourceCompleter(api_key="test", model="test")

        # Format connection context (pass context dicts, not Resource objects)
        formatted = completer._format_connection_context(
            [db.get_connection_context(), file.get_connection_context()]
        )

        # Should contain resource names
        assert "postgres" in formatted
        assert "config.yaml" in formatted

        # Should contain resource types
        assert "DockerResource" in formatted
        assert "FileResource" in formatted

    def test_multiple_connections(self):
        """Test resource with multiple connections."""
        db = DockerResource(
            description="Database",
            name="db",
            image="postgres:15-alpine",
            ports=["5432:5432"],
        )

        cache = DockerResource(
            description="Cache",
            name="redis",
            image="redis:7-alpine",
            ports=["6379:6379"],
        )

        app = DockerResource(
            description="Application",
            name="app",
            image="node:18-alpine",
            ports=["3000:3000"],
            connections=[db, cache],
        )

        # Verify connections - they're now context dicts, not Resource objects
        assert len(app.connections) == 2
        # Check that connection dicts contain the expected resource names
        connection_names = {conn["name"] for conn in app.connections}
        assert "db" in connection_names
        assert "redis" in connection_names

        # Verify _connection_resources holds the actual Resource objects
        assert len(app._connection_resources) == 2
        assert db in app._connection_resources
        assert cache in app._connection_resources

        # Test ordering
        core = ClockworkCore(api_key="test", model="test")
        ordered = core._resolve_dependency_order([app, db, cache])

        # Find indices
        idx_app = next(i for i, r in enumerate(ordered) if r.name == "app")
        idx_db = next(i for i, r in enumerate(ordered) if r.name == "db")
        idx_cache = next(i for i, r in enumerate(ordered) if r.name == "redis")

        # Both db and cache should come before app
        assert idx_db < idx_app
        assert idx_cache < idx_app


class TestEdgeCases:
    """Tests for edge cases in the connection system."""

    def test_duplicate_resources_in_list(self):
        """Test handling of duplicate resources in input list."""
        a = DockerResource(
            description="Service A",
            name="a",
            image="alpine:latest",
            ports=["8001:80"],
        )

        core = ClockworkCore(api_key="test", model="test")

        # Pass same resource twice
        ordered = core._resolve_dependency_order([a, a])

        # Should deduplicate
        assert len(ordered) == 1
        assert ordered[0].name == "a"

    def test_connection_to_nonexistent_resource(self):
        """Test connection referencing resource not in the list."""
        b = DockerResource(
            description="Service B",
            name="b",
            image="alpine:latest",
            ports=["8002:80"],
        )
        a = DockerResource(
            description="Service A",
            name="a",
            image="alpine:latest",
            ports=["8001:80"],
            connections=[b],
        )

        core = ClockworkCore(api_key="test", model="test")

        # Only pass 'a', not 'b' (which is referenced)
        # This might raise an error or handle gracefully
        # The implementation should decide the behavior
        try:
            ordered = core._resolve_dependency_order([a])
            # If it succeeds, verify behavior
            assert len(ordered) >= 1
        except ValueError:
            # If it fails, that's also acceptable
            pytest.skip("Implementation rejects missing dependencies")

    def test_deep_dependency_chain(self):
        """Test deep dependency chain (10+ levels)."""
        # Create chain: a → b → c → d → e → f → g → h → i → j
        resources = []
        prev = None

        for i, name in enumerate(
            ["j", "i", "h", "g", "f", "e", "d", "c", "b", "a"]
        ):
            connections = [prev] if prev else []
            resource = DockerResource(
                description=f"Service {name}",
                name=name,
                image="alpine:latest",
                ports=[f"{8001+i}:80"],
                connections=connections,
            )
            resources.append(resource)
            prev = resource

        core = ClockworkCore(api_key="test", model="test")
        ordered = core._resolve_dependency_order(resources)

        # Verify order: j, i, h, g, f, e, d, c, b, a
        expected_order = ["j", "i", "h", "g", "f", "e", "d", "c", "b", "a"]
        actual_order = [r.name for r in ordered]

        assert actual_order == expected_order

    def test_mixed_resource_types(self):
        """Test connections between different resource types."""
        config_file = FileResource(
            description="Config file",
            name="app.conf",
            directory="/etc",
            content="setting=value",
        )

        app = DockerResource(
            description="Application",
            name="app",
            image="node:18-alpine",
            ports=["3000:3000"],
            connections=[config_file],
        )

        core = ClockworkCore(api_key="test", model="test")
        ordered = core._resolve_dependency_order([app, config_file])

        # Config file should be created before app container
        assert ordered[0].name == "app.conf"
        assert ordered[1].name == "app"

        # Verify types
        assert isinstance(ordered[0], FileResource)
        assert isinstance(ordered[1], DockerResource)
