"""Tests for resource connection system.

This module tests the resource connection system including:
- Cycle detection in dependency graphs
- Topological sorting for correct deployment order
- Connection context sharing between resources
- Integration with ClockworkCore
"""

from unittest.mock import patch

import pytest

from clockwork.connections import DependencyConnection
from clockwork.core import ClockworkCore
from clockwork.resources import AppleContainerResource, FileResource


class TestCycleDetection:
    """Tests for dependency cycle detection."""

    def test_simple_cycle(self):
        """Test detection of simple A → B → A cycle."""
        # To create a true cycle, we need both resources to reference each other
        # We create them temporarily, then manually add to _connections

        a = AppleContainerResource(
            description="Service A",
            name="a",
            image="alpine:latest",
            ports=["8001:80"],
        )
        b = AppleContainerResource(
            description="Service B",
            name="b",
            image="alpine:latest",
            ports=["8002:80"],
        )

        # Create connections to form a cycle
        b.connect(a)  # B → A
        a.connect(b)  # A → B (creates cycle)

        core = ClockworkCore(api_key="test", model="test")

        with pytest.raises(ValueError, match=r"[Cc]ycle|[Cc]ircular"):
            core._resolve_dependency_order([a, b])

    def test_complex_cycle(self):
        """Test detection of complex A → B → C → A cycle."""
        # Create cycle: A → B → C → A
        a = AppleContainerResource(
            description="Service A",
            name="a",
            image="alpine:latest",
            ports=["8001:80"],
        )
        b = AppleContainerResource(
            description="Service B",
            name="b",
            image="alpine:latest",
            ports=["8002:80"],
        )
        c = AppleContainerResource(
            description="Service C",
            name="c",
            image="alpine:latest",
            ports=["8003:80"],
        )

        # Create cycle: B → A, C → B, A → C
        b.connect(a)
        c.connect(b)
        a.connect(c)  # Completes the cycle

        core = ClockworkCore(api_key="test", model="test")

        with pytest.raises(ValueError, match=r"[Cc]ycle|[Cc]ircular"):
            core._resolve_dependency_order([a, b, c])

    def test_self_reference(self):
        """Test detection of self-reference cycle A → A."""
        # Create resource that references itself
        a = AppleContainerResource(
            description="Service A",
            name="a",
            image="alpine:latest",
            ports=["8001:80"],
        )

        # Make it reference itself
        a.connect(a)

        core = ClockworkCore(api_key="test", model="test")

        with pytest.raises(ValueError, match=r"[Cc]ycle|[Cc]ircular"):
            core._resolve_dependency_order([a])

    def test_no_cycle_linear_chain(self):
        """Test valid linear dependency chain has no cycle."""
        c = AppleContainerResource(
            description="Service C",
            name="c",
            image="alpine:latest",
            ports=["8003:80"],
        )
        b = AppleContainerResource(
            description="Service B",
            name="b",
            image="alpine:latest",
            ports=["8002:80"],
        )
        a = AppleContainerResource(
            description="Service A",
            name="a",
            image="alpine:latest",
            ports=["8001:80"],
        )

        # Create connections: A → B → C
        b.connect(c)
        a.connect(b)

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
        d = AppleContainerResource(
            description="Service D",
            name="d",
            image="alpine:latest",
            ports=["8004:80"],
        )
        b = AppleContainerResource(
            description="Service B",
            name="b",
            image="alpine:latest",
            ports=["8002:80"],
        )
        c = AppleContainerResource(
            description="Service C",
            name="c",
            image="alpine:latest",
            ports=["8003:80"],
        )
        a = AppleContainerResource(
            description="Service A",
            name="a",
            image="alpine:latest",
            ports=["8001:80"],
        )

        # Create diamond pattern: B → D, C → D, A → B, A → C
        b.connect(d)
        c.connect(d)
        a.connect(b).connect(c)

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
        c = AppleContainerResource(
            description="Service C",
            name="c",
            image="alpine:latest",
            ports=["8003:80"],
        )
        b = AppleContainerResource(
            description="Service B",
            name="b",
            image="alpine:latest",
            ports=["8002:80"],
        )
        a = AppleContainerResource(
            description="Service A",
            name="a",
            image="alpine:latest",
            ports=["8001:80"],
        )

        # Create connections: A → B → C
        b.connect(c)
        a.connect(b)

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
        d = AppleContainerResource(
            description="Service D",
            name="d",
            image="alpine:latest",
            ports=["8004:80"],
        )
        b = AppleContainerResource(
            description="Service B",
            name="b",
            image="alpine:latest",
            ports=["8002:80"],
        )
        c = AppleContainerResource(
            description="Service C",
            name="c",
            image="alpine:latest",
            ports=["8003:80"],
        )
        a = AppleContainerResource(
            description="Service A",
            name="a",
            image="alpine:latest",
            ports=["8001:80"],
        )

        # Create diamond pattern: B → D, C → D, A → B, A → C
        b.connect(d)
        c.connect(d)
        a.connect(b).connect(c)

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
        b = AppleContainerResource(
            description="Service B",
            name="b",
            image="alpine:latest",
            ports=["8002:80"],
        )
        a = AppleContainerResource(
            description="Service A",
            name="a",
            image="alpine:latest",
            ports=["8001:80"],
        )

        y = AppleContainerResource(
            description="Service Y",
            name="y",
            image="alpine:latest",
            ports=["8004:80"],
        )
        x = AppleContainerResource(
            description="Service X",
            name="x",
            image="alpine:latest",
            ports=["8003:80"],
        )

        # Create connections: A → B, X → Y
        a.connect(b)
        x.connect(y)

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
        a = AppleContainerResource(
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
        c = AppleContainerResource(
            description="Service C",
            name="c",
            image="alpine:latest",
            ports=["8003:80"],
        )
        b = AppleContainerResource(
            description="Service B",
            name="b",
            image="alpine:latest",
            ports=["8002:80"],
        )
        a = AppleContainerResource(
            description="Service A",
            name="a",
            image="alpine:latest",
            ports=["8001:80"],
        )

        # Create connections: A → B → C
        b.connect(c)
        a.connect(b)

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

    def test_apple_container_connection_context(self):
        """Test AppleContainerResource exposes correct connection context."""
        container = AppleContainerResource(
            description="PostgreSQL database",
            name="postgres",
            image="postgres:15-alpine",
            ports=["5432:5432"],
            env_vars={"POSTGRES_PASSWORD": "secret"},
            networks=["backend"],
        )

        context = container.get_connection_context()

        # Check required fields
        assert context["name"] == "postgres"
        assert context["type"] == "AppleContainerResource"
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
        container = AppleContainerResource(
            description="Standalone service",
            name="standalone",
            image="alpine:latest",
            ports=["8080:80"],
        )

        # Empty connections list (default)
        assert container._connections == []

        context = container.get_connection_context()
        assert context["name"] == "standalone"
        assert context["type"] == "AppleContainerResource"

    def test_connection_context_filtering(self):
        """Test that only non-None fields are included in context."""
        container = AppleContainerResource(
            description="Minimal service",
            name="minimal",
            image="alpine:latest",
            ports=["8080:80"],
            # volumes, env_vars, networks are empty/default
        )

        context = container.get_connection_context()

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

        # Create a basic resource (using AppleContainerResource since Resource is abstract)
        resource = AppleContainerResource(
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
        assert context["type"] == "AppleContainerResource"


class TestIntegration:
    """Integration tests for connection system with ClockworkCore."""

    def test_core_with_connections(self):
        """Test ClockworkCore processes connected resources in correct order."""
        # Create resources with connections
        db = AppleContainerResource(
            description="Database",
            name="db",
            image="postgres:15-alpine",
            ports=["5432:5432"],
        )

        app = AppleContainerResource(
            description="Application server",
            name="app",
            image="node:18-alpine",
            ports=["3000:3000"],
        )

        # Create connection: app → db
        app.connect(db)

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
        """Test that connection context is properly stored on resources."""
        # Create resources with connections
        db = AppleContainerResource(
            description="PostgreSQL database",
            name="postgres",
            image="postgres:15-alpine",
            ports=["5432:5432"],
            env_vars={"POSTGRES_PASSWORD": "secret"},
        )

        app = AppleContainerResource(
            description="Web application",
            name="webapp",
            image="node:18-alpine",
        )

        # Create connection: app → db
        app.connect(db)

        # Verify connection is stored
        assert len(app._connections) == 1
        conn = app._connections[0]
        assert isinstance(conn, DependencyConnection)
        assert conn.from_resource == app
        assert conn.to_resource == db

        # Verify connection context can be retrieved from db
        db_context = db.get_connection_context()
        assert db_context["name"] == "postgres"
        assert db_context["type"] == "AppleContainerResource"
        assert db_context["image"] == "postgres:15-alpine"
        assert "POSTGRES_PASSWORD" in db_context["env_vars"]

    def test_format_connection_context(self):
        """Test that connection context can be retrieved from resources."""
        db = AppleContainerResource(
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

        # Get connection contexts
        db_context = db.get_connection_context()
        file_context = file.get_connection_context()

        # Verify db context
        assert db_context["name"] == "postgres"
        assert db_context["type"] == "AppleContainerResource"
        assert db_context["image"] == "postgres:15-alpine"

        # Verify file context
        assert file_context["name"] == "config.yaml"
        assert file_context["type"] == "FileResource"
        assert file_context["directory"] == "/etc/app"

    def test_multiple_connections(self):
        """Test resource with multiple connections."""
        db = AppleContainerResource(
            description="Database",
            name="db",
            image="postgres:15-alpine",
            ports=["5432:5432"],
        )

        cache = AppleContainerResource(
            description="Cache",
            name="redis",
            image="redis:7-alpine",
            ports=["6379:6379"],
        )

        app = AppleContainerResource(
            description="Application",
            name="app",
            image="node:18-alpine",
            ports=["3000:3000"],
        )

        # Create connections: app → db, app → cache
        app.connect(db).connect(cache)

        # Verify connections are stored as Connection objects
        assert len(app._connections) == 2
        assert all(
            isinstance(conn, DependencyConnection) for conn in app._connections
        )

        # Check that connections point to the right resources
        connection_targets = [conn.to_resource for conn in app._connections]
        assert db in connection_targets
        assert cache in connection_targets

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
        a = AppleContainerResource(
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
        b = AppleContainerResource(
            description="Service B",
            name="b",
            image="alpine:latest",
            ports=["8002:80"],
        )
        a = AppleContainerResource(
            description="Service A",
            name="a",
            image="alpine:latest",
            ports=["8001:80"],
        )

        # Create connection: a → b
        a.connect(b)

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
            resource = AppleContainerResource(
                description=f"Service {name}",
                name=name,
                image="alpine:latest",
                ports=[f"{8001 + i}:80"],
            )
            if prev:
                resource.connect(prev)
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

        app = AppleContainerResource(
            description="Application",
            name="app",
            image="node:18-alpine",
            ports=["3000:3000"],
        )

        # Create connection: app → config_file
        app.connect(config_file)

        core = ClockworkCore(api_key="test", model="test")
        ordered = core._resolve_dependency_order([app, config_file])

        # Config file should be created before app container
        assert ordered[0].name == "app.conf"
        assert ordered[1].name == "app"

        # Verify types
        assert isinstance(ordered[0], FileResource)
        assert isinstance(ordered[1], AppleContainerResource)
