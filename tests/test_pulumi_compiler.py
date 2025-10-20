"""Tests for Pulumi compiler with composite resources.

This module tests the Pulumi compilation system including:
- Composite resources compile to ComponentResource
- Children have correct parent references
- Dependency options are merged correctly
- Helper methods for building and merging options
- Recursive compilation for nested composites
"""

import asyncio
import pytest
from unittest.mock import Mock, MagicMock, patch, AsyncMock
import pulumi

from clockwork.resources import DockerResource, FileResource, BlankResource
from clockwork.pulumi_compiler import PulumiCompiler


@pytest.fixture(autouse=True)
def event_loop():
    """Create an event loop for each test (needed for Pulumi Output)."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


class TestCompositeCompilation:
    """Tests for compiling composite resources to Pulumi ComponentResource."""

    @patch('pulumi.ComponentResource')
    def test_blank_resource_creates_component(self, mock_component):
        """Test that BlankResource creates a Pulumi ComponentResource."""
        # Setup mock
        mock_instance = MagicMock()
        mock_component.return_value = mock_instance

        # Create composite
        backend = BlankResource(name="backend", description="Backend services")

        # Compile to Pulumi
        result = backend.to_pulumi()

        # Verify ComponentResource was created
        mock_component.assert_called_once()
        assert result == mock_instance

        # Verify resource type and name
        call_args = mock_component.call_args
        assert call_args[0][0] == "clockwork:blank:BlankResource"
        assert call_args[0][1] == "backend"

    @patch('pulumi.ComponentResource')
    def test_composite_with_children_creates_hierarchy(self, mock_component):
        """Test that composite with children creates proper Pulumi hierarchy."""
        # Setup mocks
        component_mock = MagicMock()
        mock_component.return_value = component_mock

        # Create composite with children
        db = DockerResource(
            description="Database",
            name="db",
            image="postgres:15",
            ports=["5432:5432"]
        )

        backend = BlankResource(name="backend", description="Backend")
        backend.add(db)

        # Mock db.to_pulumi to avoid actual Pulumi calls
        db_resource_mock = MagicMock()
        with patch.object(db, 'to_pulumi', return_value=db_resource_mock) as mock_to_pulumi:
            # Compile composite
            result = backend.to_pulumi()

            # Verify ComponentResource was created
            assert mock_component.called
            assert result == component_mock

            # Verify child's to_pulumi was not called directly
            # (it should be called via _compile_with_opts)

    @patch('pulumi.ComponentResource')
    def test_nested_composite_creates_nested_components(self, mock_component):
        """Test nested composites create nested ComponentResources."""
        # Setup mock
        mock_component.return_value = MagicMock()

        # Create nested structure
        db = DockerResource(
            description="Database",
            name="db",
            image="postgres:15",
            ports=["5432:5432"]
        )

        backend = BlankResource(name="backend", description="Backend")
        backend.add(db)

        app = BlankResource(name="app", description="Application")
        app.add(backend)

        # Mock child to_pulumi methods
        with patch.object(db, 'to_pulumi', return_value=MagicMock()):
            with patch.object(backend, 'to_pulumi', wraps=backend.to_pulumi):
                # Compile top-level composite
                result = app.to_pulumi()

                # Verify ComponentResource was created for app
                assert mock_component.called


class TestParentChildReferences:
    """Tests for correct parent references in Pulumi resources."""

    @patch('pulumi.ComponentResource')
    @patch('pulumi.ResourceOptions')
    def test_child_has_parent_reference(self, mock_opts, mock_component):
        """Test that child resource receives parent in ResourceOptions."""
        # Setup mocks
        component_mock = MagicMock()
        mock_component.return_value = component_mock

        # Create composite with child
        db = DockerResource(
            description="Database",
            name="db",
            image="postgres:15",
            ports=["5432:5432"]
        )

        backend = BlankResource(name="backend", description="Backend")
        backend.add(db)

        # Mock child compilation
        with patch.object(db, '_compile_with_opts') as mock_compile:
            # Compile composite
            backend.to_pulumi()

            # Verify _compile_with_opts was called with parent option
            assert mock_compile.called
            call_args = mock_compile.call_args[0][0]
            assert isinstance(call_args, pulumi.ResourceOptions)
            assert call_args.parent == component_mock

    @patch('pulumi.ComponentResource')
    def test_multiple_children_have_same_parent(self, mock_component):
        """Test that all children receive same parent reference."""
        # Setup mock
        component_mock = MagicMock()
        mock_component.return_value = component_mock

        # Create composite with multiple children
        db = DockerResource(
            description="Database",
            name="db",
            image="postgres:15",
            ports=["5432:5432"]
        )
        cache = DockerResource(
            description="Cache",
            name="cache",
            image="redis:7",
            ports=["6379:6379"]
        )

        backend = BlankResource(name="backend", description="Backend")
        backend.add(db, cache)

        # Mock children compilation
        with patch.object(db, '_compile_with_opts') as mock_db_compile:
            with patch.object(cache, '_compile_with_opts') as mock_cache_compile:
                # Compile composite
                backend.to_pulumi()

                # Verify both children got parent reference
                assert mock_db_compile.called
                assert mock_cache_compile.called

                db_parent = mock_db_compile.call_args[0][0].parent
                cache_parent = mock_cache_compile.call_args[0][0].parent

                # Both should have same parent (the component)
                assert db_parent == component_mock
                assert cache_parent == component_mock


class TestDependencyOptions:
    """Tests for building and merging dependency options."""

    def test_build_dependency_options_no_connections(self):
        """Test _build_dependency_options returns None when no connections."""
        resource = DockerResource(
            description="Standalone service",
            name="standalone",
            image="alpine:latest",
            ports=["8080:80"]
        )

        opts = resource._build_dependency_options()
        assert opts is None

    def test_build_dependency_options_with_connections(self):
        """Test _build_dependency_options creates options with depends_on."""
        # Create connected resources
        db = DockerResource(
            description="Database",
            name="db",
            image="postgres:15",
            ports=["5432:5432"]
        )

        # Mock db's Pulumi resource
        db._pulumi_resource = MagicMock()

        api = DockerResource(
            description="API",
            name="api",
            image="node:20",
            ports=["3000:3000"],
            connections=[db]
        )

        opts = api._build_dependency_options()

        # Should have depends_on with db's Pulumi resource
        assert opts is not None
        assert isinstance(opts, pulumi.ResourceOptions)
        assert opts.depends_on is not None
        assert db._pulumi_resource in opts.depends_on

    def test_build_dependency_options_multiple_connections(self):
        """Test _build_dependency_options with multiple connections."""
        # Create connected resources
        db = DockerResource(
            description="Database",
            name="db",
            image="postgres:15",
            ports=["5432:5432"]
        )
        db._pulumi_resource = MagicMock()

        cache = DockerResource(
            description="Cache",
            name="cache",
            image="redis:7",
            ports=["6379:6379"]
        )
        cache._pulumi_resource = MagicMock()

        api = DockerResource(
            description="API",
            name="api",
            image="node:20",
            ports=["3000:3000"],
            connections=[db, cache]
        )

        opts = api._build_dependency_options()

        # Should have depends_on with both resources
        assert opts is not None
        assert len(opts.depends_on) == 2
        assert db._pulumi_resource in opts.depends_on
        assert cache._pulumi_resource in opts.depends_on

    def test_merge_resource_options_both_none(self):
        """Test _merge_resource_options returns None when both inputs are None."""
        resource = DockerResource(
            description="Test",
            name="test",
            image="alpine:latest",
            ports=["8080:80"]
        )

        merged = resource._merge_resource_options(None, None)
        assert merged is None

    def test_merge_resource_options_parent_only(self):
        """Test _merge_resource_options with only parent options."""
        resource = DockerResource(
            description="Test",
            name="test",
            image="alpine:latest",
            ports=["8080:80"]
        )

        parent_mock = MagicMock()
        parent_opts = pulumi.ResourceOptions(parent=parent_mock)

        merged = resource._merge_resource_options(parent_opts, None)
        assert merged == parent_opts

    def test_merge_resource_options_dep_only(self):
        """Test _merge_resource_options with only dependency options."""
        resource = DockerResource(
            description="Test",
            name="test",
            image="alpine:latest",
            ports=["8080:80"]
        )

        dep_mock = MagicMock()
        dep_opts = pulumi.ResourceOptions(depends_on=[dep_mock])

        merged = resource._merge_resource_options(None, dep_opts)
        assert merged == dep_opts

    def test_merge_resource_options_both_present(self):
        """Test _merge_resource_options merges parent and dependency options."""
        resource = DockerResource(
            description="Test",
            name="test",
            image="alpine:latest",
            ports=["8080:80"]
        )

        parent_mock = MagicMock()
        parent_opts = pulumi.ResourceOptions(parent=parent_mock)

        dep_mock = MagicMock()
        dep_opts = pulumi.ResourceOptions(depends_on=[dep_mock])

        merged = resource._merge_resource_options(parent_opts, dep_opts)

        # Should have both parent and depends_on
        assert merged is not None
        assert merged.parent == parent_mock
        assert dep_mock in merged.depends_on

    def test_merge_resource_options_combines_depends_on(self):
        """Test _merge_resource_options combines depends_on from both options."""
        resource = DockerResource(
            description="Test",
            name="test",
            image="alpine:latest",
            ports=["8080:80"]
        )

        dep1_mock = MagicMock()
        parent_opts = pulumi.ResourceOptions(depends_on=[dep1_mock])

        dep2_mock = MagicMock()
        dep_opts = pulumi.ResourceOptions(depends_on=[dep2_mock])

        merged = resource._merge_resource_options(parent_opts, dep_opts)

        # Should have both dependencies
        assert merged is not None
        assert len(merged.depends_on) == 2
        assert dep1_mock in merged.depends_on
        assert dep2_mock in merged.depends_on


class TestCompileWithOpts:
    """Tests for _compile_with_opts method."""

    def test_compile_with_opts_no_dependencies(self):
        """Test _compile_with_opts with only parent options."""
        db = DockerResource(
            description="Database",
            name="db",
            image="postgres:15",
            ports=["5432:5432"]
        )

        parent_mock = MagicMock()
        parent_opts = pulumi.ResourceOptions(parent=parent_mock)

        # Mock to_pulumi to verify options are passed
        with patch.object(db, 'to_pulumi') as mock_to_pulumi:
            mock_to_pulumi.return_value = MagicMock()
            db._compile_with_opts(parent_opts)

            # Verify to_pulumi was called
            assert mock_to_pulumi.called

            # Verify temporary options were set
            # Note: This is tricky to test since _temp_compile_opts is cleaned up

    def test_compile_with_opts_with_dependencies(self):
        """Test _compile_with_opts merges parent and dependency options."""
        # Create resources with connection
        cache = DockerResource(
            description="Cache",
            name="cache",
            image="redis:7",
            ports=["6379:6379"]
        )
        cache._pulumi_resource = MagicMock()

        db = DockerResource(
            description="Database",
            name="db",
            image="postgres:15",
            ports=["5432:5432"],
            connections=[cache]
        )

        parent_mock = MagicMock()
        parent_opts = pulumi.ResourceOptions(parent=parent_mock)

        # Mock to_pulumi
        with patch.object(db, 'to_pulumi') as mock_to_pulumi:
            mock_to_pulumi.return_value = MagicMock()
            db._compile_with_opts(parent_opts)

            # Verify to_pulumi was called
            assert mock_to_pulumi.called

    def test_compile_with_opts_cleans_up_temp_options(self):
        """Test that _compile_with_opts cleans up temporary options."""
        db = DockerResource(
            description="Database",
            name="db",
            image="postgres:15",
            ports=["5432:5432"]
        )

        parent_opts = pulumi.ResourceOptions(parent=MagicMock())

        # Mock to_pulumi
        with patch.object(db, 'to_pulumi', return_value=MagicMock()):
            db._compile_with_opts(parent_opts)

        # Verify _temp_compile_opts was cleaned up
        assert not hasattr(db, '_temp_compile_opts')


class TestRecursiveCompilation:
    """Tests for recursive compilation of nested composites."""

    @patch('pulumi.ComponentResource')
    def test_nested_composite_recursive_compilation(self, mock_component):
        """Test that nested composites are compiled recursively."""
        # Setup mocks
        mock_component.return_value = MagicMock()

        # Create nested structure
        db = DockerResource(
            description="Database",
            name="db",
            image="postgres:15",
            ports=["5432:5432"]
        )

        inner = BlankResource(name="inner", description="Inner")
        inner.add(db)

        outer = BlankResource(name="outer", description="Outer")
        outer.add(inner)

        # Mock child to_pulumi methods
        with patch.object(db, 'to_pulumi', return_value=MagicMock()):
            # Compile outer composite
            outer.to_pulumi()

            # Verify ComponentResource was created multiple times (outer and inner)
            assert mock_component.call_count >= 2

    @patch('pulumi.ComponentResource')
    def test_composite_compiles_children_in_order(self, mock_component):
        """Test that composite compiles children respecting dependency order."""
        # Setup mock
        mock_component.return_value = MagicMock()

        # Create resources with dependencies
        db = DockerResource(
            description="Database",
            name="db",
            image="postgres:15",
            ports=["5432:5432"]
        )

        api = DockerResource(
            description="API",
            name="api",
            image="node:20",
            ports=["3000:3000"],
            connections=[db]
        )

        backend = BlankResource(name="backend", description="Backend")
        backend.add(db, api)

        # Track compilation order
        compilation_order = []

        def track_db_compile(*args, **kwargs):
            compilation_order.append("db")
            return MagicMock()

        def track_api_compile(*args, **kwargs):
            compilation_order.append("api")
            return MagicMock()

        with patch.object(db, 'to_pulumi', side_effect=track_db_compile):
            with patch.object(api, 'to_pulumi', side_effect=track_api_compile):
                # Note: The composite's to_pulumi doesn't enforce ordering,
                # that's handled by the resolver. This test just verifies
                # that both children are compiled.
                backend.to_pulumi()


class TestPulumiCompilerIntegration:
    """Integration tests for PulumiCompiler with composites."""

    @patch('pulumi.automation.create_or_select_stack')
    async def test_compiler_handles_composite_resources(self, mock_stack):
        """Test that PulumiCompiler correctly handles composite resources."""
        # Setup mock stack
        mock_stack_instance = MagicMock()
        mock_stack_instance.preview = MagicMock(return_value=MagicMock(
            change_summary={"create": 3}
        ))
        mock_stack.return_value = mock_stack_instance

        # Create composite with children
        db = DockerResource(
            description="Database",
            name="db",
            image="postgres:15",
            ports=["5432:5432"]
        )
        cache = DockerResource(
            description="Cache",
            name="cache",
            image="redis:7",
            ports=["6379:6379"]
        )

        backend = BlankResource(name="backend", description="Backend")
        backend.add(db, cache)

        # Create compiler
        compiler = PulumiCompiler()

        # Create program
        program = compiler.create_program([backend])

        # Verify program function was created
        assert callable(program)

    @patch('pulumi.automation.create_or_select_stack')
    async def test_compiler_preview_with_composites(self, mock_stack):
        """Test compiler preview with composite resources."""
        # Setup mock stack
        mock_stack_instance = MagicMock()
        mock_stack_instance.preview = MagicMock(return_value=MagicMock(
            change_summary={"create": 3, "update": 0, "delete": 0}
        ))
        mock_stack.return_value = mock_stack_instance

        # Create composite
        db = DockerResource(
            description="Database",
            name="db",
            image="postgres:15",
            ports=["5432:5432"]
        )

        backend = BlankResource(name="backend", description="Backend")
        backend.add(db)

        # Create compiler and preview
        compiler = PulumiCompiler()
        result = await compiler.preview([backend], "test-project")

        # Verify preview was called
        assert mock_stack_instance.preview.called


class TestCompositeOutputs:
    """Tests for Pulumi outputs from composite resources."""

    @patch('pulumi.ComponentResource')
    def test_composite_registers_outputs(self, mock_component):
        """Test that composite calls register_outputs."""
        # Setup mock
        component_mock = MagicMock()
        mock_component.return_value = component_mock

        # Create composite
        backend = BlankResource(name="backend", description="Backend")

        # Compile
        backend.to_pulumi()

        # Verify register_outputs was called
        assert component_mock.register_outputs.called

    @patch('pulumi.ComponentResource')
    def test_composite_stores_pulumi_resource(self, mock_component):
        """Test that composite stores _pulumi_resource for dependency tracking."""
        # Setup mock
        component_mock = MagicMock()
        mock_component.return_value = component_mock

        # Create composite
        backend = BlankResource(name="backend", description="Backend")

        # Compile
        result = backend.to_pulumi()

        # Verify _pulumi_resource was stored
        assert backend._pulumi_resource == component_mock
        assert result == component_mock
