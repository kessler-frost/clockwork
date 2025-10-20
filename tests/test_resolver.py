"""Tests for resource dependency resolver with composite resources.

This module tests the dependency resolution system including:
- Flattening composite resources to extract all children
- Parent-child implicit dependency creation
- Cross-composite connections (child in composite A connects to child in composite B)
- Cycle detection across composite boundaries
- Topological ordering with mixed composites and primitives
- Nested composites (composites containing composites)
"""

import pytest
from unittest.mock import patch

from clockwork.resources import DockerResource, FileResource, BlankResource
from clockwork.core import ClockworkCore


class TestCompositeFlattening:
    """Tests for flattening composite resources to extract all children."""

    def test_flatten_single_composite(self):
        """Test flattening a composite with children extracts all resources."""
        # Create composite with children
        db = DockerResource(description="Database", name="db", image="postgres:15")
        cache = DockerResource(description="Cache", name="cache", image="redis:7")

        backend = BlankResource(name="backend", description="Backend services")
        backend.add(db, cache)

        core = ClockworkCore(api_key="test", model="test")
        flattened = core._flatten_resources([backend])

        # Should contain parent + 2 children = 3 total
        assert len(flattened) == 3
        assert backend in flattened
        assert db in flattened
        assert cache in flattened

    def test_flatten_multiple_composites(self):
        """Test flattening multiple composites."""
        # First composite
        db = DockerResource(description="Database", name="db", image="postgres:15")
        cache = DockerResource(description="Cache", name="cache", image="redis:7")
        backend = BlankResource(name="backend", description="Backend services")
        backend.add(db, cache)

        # Second composite
        nginx = DockerResource(description="Web server", name="nginx", image="nginx:latest")
        cdn = FileResource(description="CDN config", name="cdn.conf", content="...")
        frontend = BlankResource(name="frontend", description="Frontend services")
        frontend.add(nginx, cdn)

        core = ClockworkCore(api_key="test", model="test")
        flattened = core._flatten_resources([backend, frontend])

        # Should contain 2 parents + 4 children = 6 total
        assert len(flattened) == 6
        # Check by name instead of object identity to avoid recursion issues
        names = {r.name for r in flattened}
        assert "backend" in names
        assert "db" in names
        assert "cache" in names
        assert "frontend" in names
        assert "nginx" in names
        assert "cdn.conf" in names

    def test_flatten_nested_composites(self):
        """Test flattening nested composites (composites containing composites)."""
        # Innermost resources
        db = DockerResource(description="Database", name="db", image="postgres:15")
        cache = DockerResource(description="Cache", name="cache", image="redis:7")

        # Middle layer composite
        backend = BlankResource(name="backend", description="Backend services")
        backend.add(db, cache)

        # API resource
        api = DockerResource(description="API", name="api", image="node:20")

        # Top-level composite
        app = BlankResource(name="app", description="Full application")
        app.add(backend, api)

        core = ClockworkCore(api_key="test", model="test")
        flattened = core._flatten_resources([app])

        # Should contain: app (1) + backend (1) + db (1) + cache (1) + api (1) = 5 total
        assert len(flattened) == 5
        assert app in flattened
        assert backend in flattened
        assert db in flattened
        assert cache in flattened
        assert api in flattened

    def test_flatten_mixed_primitives_and_composites(self):
        """Test flattening mix of primitive and composite resources."""
        # Standalone primitives
        config = FileResource(description="Config", name="config.yaml", content="...")

        # Composite with children
        db = DockerResource(description="Database", name="db", image="postgres:15")
        backend = BlankResource(name="backend", description="Backend")
        backend.add(db)

        core = ClockworkCore(api_key="test", model="test")
        flattened = core._flatten_resources([config, backend])

        # Should contain: config (1) + backend (1) + db (1) = 3 total
        assert len(flattened) == 3
        assert config in flattened
        assert backend in flattened
        assert db in flattened

    def test_flatten_empty_composite(self):
        """Test flattening composite with no children."""
        backend = BlankResource(name="backend", description="Empty backend")

        core = ClockworkCore(api_key="test", model="test")
        flattened = core._flatten_resources([backend])

        # Should contain only the parent
        assert len(flattened) == 1
        assert backend in flattened

    def test_flatten_preserves_hierarchy(self):
        """Test that flattening preserves parent-child relationships."""
        db = DockerResource(description="Database", name="db", image="postgres:15")
        backend = BlankResource(name="backend", description="Backend")
        backend.add(db)

        core = ClockworkCore(api_key="test", model="test")
        flattened = core._flatten_resources([backend])

        # Verify parent-child relationship is preserved
        assert db.parent == backend
        assert db in backend.children.values()


class TestImplicitParentChildDependencies:
    """Tests for implicit dependency creation between parents and children."""

    def test_add_implicit_dependency_parent_to_child(self):
        """Test that child has implicit dependency on parent after resolution."""
        db = DockerResource(description="Database", name="db", image="postgres:15")
        backend = BlankResource(name="backend", description="Backend")
        backend.add(db)

        core = ClockworkCore(api_key="test", model="test")

        # Flatten and add implicit dependencies
        flattened = core._flatten_resources([backend])
        core._add_implicit_parent_child_dependencies(flattened)

        # Child should now depend on parent
        assert backend in db._connection_resources

    def test_implicit_dependencies_nested_composites(self):
        """Test implicit dependencies in nested composites."""
        db = DockerResource(description="Database", name="db", image="postgres:15")
        backend = BlankResource(name="backend", description="Backend")
        backend.add(db)

        app = BlankResource(name="app", description="Application")
        app.add(backend)

        core = ClockworkCore(api_key="test", model="test")

        # Flatten and add implicit dependencies
        flattened = core._flatten_resources([app])
        core._add_implicit_parent_child_dependencies(flattened)

        # backend should depend on app (its parent)
        assert app in backend._connection_resources

        # db should depend on backend (its parent)
        assert backend in db._connection_resources

    def test_implicit_dependencies_multiple_children(self):
        """Test implicit dependencies with multiple children."""
        db = DockerResource(description="Database", name="db", image="postgres:15")
        cache = DockerResource(description="Cache", name="cache", image="redis:7")
        api = DockerResource(description="API", name="api", image="node:20")

        backend = BlankResource(name="backend", description="Backend")
        backend.add(db, cache, api)

        core = ClockworkCore(api_key="test", model="test")

        # Flatten and add implicit dependencies
        flattened = core._flatten_resources([backend])
        core._add_implicit_parent_child_dependencies(flattened)

        # All children should depend on parent
        assert backend in db._connection_resources
        assert backend in cache._connection_resources
        assert backend in api._connection_resources


class TestCrossCompositConnections:
    """Tests for connections between children in different composites."""

    def test_cross_composite_connection(self):
        """Test connection from child in composite A to child in composite B."""
        # Composite A
        db = DockerResource(description="Database", name="db", image="postgres:15")
        backend = BlankResource(name="backend", description="Backend")
        backend.add(db)

        # Composite B (API connects to db in composite A)
        api = DockerResource(
            description="API", name="api", image="node:20",
            connections=[db]
        )
        services = BlankResource(name="services", description="Services")
        services.add(api)

        core = ClockworkCore(api_key="test", model="test")
        ordered = core._resolve_dependency_order([backend, services])

        # Find indices
        idx_backend = next(i for i, r in enumerate(ordered) if r.name == "backend")
        idx_db = next(i for i, r in enumerate(ordered) if r.name == "db")
        idx_services = next(i for i, r in enumerate(ordered) if r.name == "services")
        idx_api = next(i for i, r in enumerate(ordered) if r.name == "api")

        # db should come before api (explicit connection)
        assert idx_db < idx_api

        # backend should come before db (implicit parent-child)
        assert idx_backend < idx_db

        # services should come before api (implicit parent-child)
        assert idx_services < idx_api

    def test_multiple_cross_composite_connections(self):
        """Test multiple connections across composite boundaries."""
        # Composite A
        db = DockerResource(description="Database", name="db", image="postgres:15")
        cache = DockerResource(description="Cache", name="cache", image="redis:7")
        backend = BlankResource(name="backend", description="Backend")
        backend.add(db, cache)

        # Composite B (API connects to both db and cache)
        api = DockerResource(
            description="API", name="api", image="node:20",
            connections=[db, cache]
        )
        services = BlankResource(name="services", description="Services")
        services.add(api)

        core = ClockworkCore(api_key="test", model="test")
        ordered = core._resolve_dependency_order([backend, services])

        # Find indices
        idx_db = next(i for i, r in enumerate(ordered) if r.name == "db")
        idx_cache = next(i for i, r in enumerate(ordered) if r.name == "cache")
        idx_api = next(i for i, r in enumerate(ordered) if r.name == "api")

        # Both db and cache should come before api
        assert idx_db < idx_api
        assert idx_cache < idx_api

    def test_bidirectional_cross_composite_cycle_detection(self):
        """Test cycle detection across composite boundaries."""
        # Composite A
        db = DockerResource(description="Database", name="db", image="postgres:15")
        backend = BlankResource(name="backend", description="Backend")
        backend.add(db)

        # Composite B (API connects to db)
        api = DockerResource(
            description="API", name="api", image="node:20",
            connections=[db]
        )
        services = BlankResource(name="services", description="Services")
        services.add(api)

        # Create cycle: db → api (this would create a cycle)
        db._connection_resources.append(api)
        db.connections.append(api.get_connection_context())

        core = ClockworkCore(api_key="test", model="test")

        # Should detect cycle
        with pytest.raises(ValueError, match="[Cc]ycle|[Cc]ircular"):
            core._resolve_dependency_order([backend, services])


class TestCycleDetectionComposites:
    """Tests for cycle detection with composite resources."""

    def test_simple_composite_cycle(self):
        """Test detection of cycle within composite."""
        # Create resources that reference each other
        db = DockerResource(description="Database", name="db", image="postgres:15")
        api = DockerResource(
            description="API", name="api", image="node:20",
            connections=[db]
        )

        # Add to composite first
        backend = BlankResource(name="backend", description="Backend")
        backend.add(db, api)

        # Create cycle by adding opposite direction connection
        db._connection_resources.append(api)
        # Don't add to db.connections to avoid recursion in get_connection_context

        core = ClockworkCore(api_key="test", model="test")

        with pytest.raises(ValueError, match="[Cc]ycle|[Cc]ircular"):
            core._resolve_dependency_order([backend])

    def test_nested_composite_cycle(self):
        """Test detection of cycle in nested composites."""
        # Inner composite
        db = DockerResource(description="Database", name="db", image="postgres:15")
        inner = BlankResource(name="inner", description="Inner")
        inner.add(db)

        # Middle composite with connection to db
        api = DockerResource(description="API", name="api", image="node:20", connections=[db])
        middle = BlankResource(name="middle", description="Middle")
        middle.add(api)

        # Outer composite
        outer = BlankResource(name="outer", description="Outer")
        outer.add(inner, middle)

        # Create cycle by adding opposite direction (db -> api)
        # Only add to _connection_resources to avoid recursion
        db._connection_resources.append(api)

        core = ClockworkCore(api_key="test", model="test")

        with pytest.raises(ValueError, match="[Cc]ycle|[Cc]ircular"):
            core._resolve_dependency_order([outer])

    def test_no_cycle_composite_linear_chain(self):
        """Test valid linear dependency chain in composite has no cycle."""
        # Create linear dependency: c → b → a
        c = DockerResource(description="Service C", name="c", image="alpine:latest")
        b = DockerResource(description="Service B", name="b", image="alpine:latest", connections=[c])
        a = DockerResource(description="Service A", name="a", image="alpine:latest", connections=[b])

        backend = BlankResource(name="backend", description="Backend")
        backend.add(a, b, c)

        core = ClockworkCore(api_key="test", model="test")

        # Should not raise exception
        ordered = core._resolve_dependency_order([backend])
        assert len(ordered) == 4  # backend + 3 children


class TestTopologicalOrderingComposites:
    """Tests for topological ordering with composite resources."""

    def test_ordering_simple_composite(self):
        """Test correct ordering of composite with children."""
        # Create composite with dependencies
        db = DockerResource(description="Database", name="db", image="postgres:15")
        api = DockerResource(
            description="API", name="api", image="node:20",
            connections=[db]
        )

        backend = BlankResource(name="backend", description="Backend")
        backend.add(db, api)

        core = ClockworkCore(api_key="test", model="test")
        ordered = core._resolve_dependency_order([backend])

        # Find indices
        idx_backend = next(i for i, r in enumerate(ordered) if r.name == "backend")
        idx_db = next(i for i, r in enumerate(ordered) if r.name == "db")
        idx_api = next(i for i, r in enumerate(ordered) if r.name == "api")

        # Order should be: backend (parent), db (no deps), api (depends on db)
        assert idx_backend < idx_db
        assert idx_backend < idx_api
        assert idx_db < idx_api

    def test_ordering_multiple_composites(self):
        """Test ordering with multiple composites and cross-composite connections."""
        # Backend composite
        db = DockerResource(description="Database", name="db", image="postgres:15")
        cache = DockerResource(description="Cache", name="cache", image="redis:7")
        backend = BlankResource(name="backend", description="Backend")
        backend.add(db, cache)

        # Services composite (depends on backend children)
        api = DockerResource(
            description="API", name="api", image="node:20",
            connections=[db, cache]
        )
        services = BlankResource(name="services", description="Services")
        services.add(api)

        core = ClockworkCore(api_key="test", model="test")
        ordered = core._resolve_dependency_order([backend, services])

        # Find indices
        idx_backend = next(i for i, r in enumerate(ordered) if r.name == "backend")
        idx_db = next(i for i, r in enumerate(ordered) if r.name == "db")
        idx_cache = next(i for i, r in enumerate(ordered) if r.name == "cache")
        idx_services = next(i for i, r in enumerate(ordered) if r.name == "services")
        idx_api = next(i for i, r in enumerate(ordered) if r.name == "api")

        # Backend should come first (parent)
        assert idx_backend < idx_db
        assert idx_backend < idx_cache

        # Services should come before api (parent)
        assert idx_services < idx_api

        # db and cache should come before api (explicit connections)
        assert idx_db < idx_api
        assert idx_cache < idx_api

    def test_ordering_nested_composites(self):
        """Test ordering with deeply nested composites."""
        # Innermost resources
        db = DockerResource(description="Database", name="db", image="postgres:15")
        cache = DockerResource(description="Cache", name="cache", image="redis:7")

        # Middle layer
        backend = BlankResource(name="backend", description="Backend")
        backend.add(db, cache)

        # API depends on db
        api = DockerResource(
            description="API", name="api", image="node:20",
            connections=[db]
        )

        # Top level
        app = BlankResource(name="app", description="Application")
        app.add(backend, api)

        core = ClockworkCore(api_key="test", model="test")
        ordered = core._resolve_dependency_order([app])

        # Find indices
        idx_app = next(i for i, r in enumerate(ordered) if r.name == "app")
        idx_backend = next(i for i, r in enumerate(ordered) if r.name == "backend")
        idx_db = next(i for i, r in enumerate(ordered) if r.name == "db")
        idx_api = next(i for i, r in enumerate(ordered) if r.name == "api")

        # app should be first (top-level parent)
        assert idx_app < idx_backend
        assert idx_app < idx_api

        # backend should come before db (parent)
        assert idx_backend < idx_db

        # db should come before api (explicit connection)
        assert idx_db < idx_api

    def test_ordering_mixed_primitives_and_composites(self):
        """Test ordering with mix of primitives and composites."""
        # Standalone primitive
        config = FileResource(description="Config", name="config.yaml", content="...")

        # Composite depending on primitive
        db = DockerResource(
            description="Database", name="db", image="postgres:15",
            connections=[config]
        )
        backend = BlankResource(name="backend", description="Backend")
        backend.add(db)

        # Another primitive depending on composite child
        api = DockerResource(
            description="API", name="api", image="node:20",
            connections=[db]
        )

        core = ClockworkCore(api_key="test", model="test")
        ordered = core._resolve_dependency_order([config, backend, api])

        # Find indices
        idx_config = next(i for i, r in enumerate(ordered) if r.name == "config.yaml")
        idx_backend = next(i for i, r in enumerate(ordered) if r.name == "backend")
        idx_db = next(i for i, r in enumerate(ordered) if r.name == "db")
        idx_api = next(i for i, r in enumerate(ordered) if r.name == "api")

        # config should come before db (explicit connection)
        assert idx_config < idx_db

        # backend should come before db (parent)
        assert idx_backend < idx_db

        # db should come before api (explicit connection)
        assert idx_db < idx_api


class TestCompositeEdgeCases:
    """Tests for edge cases with composite resources."""

    def test_empty_composite_ordering(self):
        """Test ordering with empty composite (no children)."""
        backend = BlankResource(name="backend", description="Empty backend")
        config = FileResource(description="Config", name="config.yaml", content="...")

        core = ClockworkCore(api_key="test", model="test")
        ordered = core._resolve_dependency_order([backend, config])

        # Should handle empty composite gracefully
        assert len(ordered) == 2
        assert backend in ordered
        assert config in ordered

    def test_composite_with_duplicate_children(self):
        """Test handling of duplicate children (should be deduplicated)."""
        db = DockerResource(description="Database", name="db", image="postgres:15")
        backend = BlankResource(name="backend", description="Backend")

        # Try to add same child twice
        backend.add(db)
        backend.add(db)

        # Should only have one instance
        assert len(backend.children) == 1

    def test_deeply_nested_composites(self):
        """Test deeply nested composite hierarchy."""
        # Create 4-level hierarchy
        db = DockerResource(description="Database", name="db", image="postgres:15")

        level3 = BlankResource(name="level3", description="Level 3")
        level3.add(db)

        level2 = BlankResource(name="level2", description="Level 2")
        level2.add(level3)

        level1 = BlankResource(name="level1", description="Level 1")
        level1.add(level2)

        root = BlankResource(name="root", description="Root")
        root.add(level1)

        core = ClockworkCore(api_key="test", model="test")
        ordered = core._resolve_dependency_order([root])

        # Should flatten all levels
        assert len(ordered) == 5  # root + level1 + level2 + level3 + db

        # Verify hierarchy is preserved
        assert db.parent == level3
        assert level3.parent == level2
        assert level2.parent == level1
        assert level1.parent == root

    def test_composite_self_reference_prevention(self):
        """Test that composite self-reference causes recursion during flattening."""
        backend = BlankResource(name="backend", description="Backend")

        # Add self as child - this creates an infinite recursion
        backend.add(backend)

        # The recursion happens during flattening, not cycle detection
        core = ClockworkCore(api_key="test", model="test")

        # Should raise RecursionError during flattening (not cycle detection)
        with pytest.raises(RecursionError):
            core._resolve_dependency_order([backend])
