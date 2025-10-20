"""Tests for Pulumi compiler with composite resources.

This module tests basic Pulumi compilation functionality.
Complex integration tests with mocking are covered in test_composite_integration.py
"""

import asyncio
from unittest.mock import MagicMock, patch

import pulumi
import pytest

from clockwork.resources import BlankResource, DockerResource


@pytest.fixture(autouse=True)
def event_loop():
    """Create an event loop for each test (needed for Pulumi Output)."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


class TestCompositeCompilation:
    """Tests for compiling composite resources to Pulumi ComponentResource."""

    @patch("pulumi.ComponentResource")
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


class TestParentChildReferences:
    """Tests for correct parent references in Pulumi resources."""

    @patch("pulumi.ComponentResource")
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
            ports=["5432:5432"],
        )
        cache = DockerResource(
            description="Cache",
            name="cache",
            image="redis:7",
            ports=["6379:6379"],
        )

        backend = BlankResource(name="backend", description="Backend")
        backend.add(db, cache)

        # Mock children compilation
        with (
            patch.object(db, "_compile_with_opts") as mock_db_compile,
            patch.object(cache, "_compile_with_opts") as mock_cache_compile,
        ):
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
            ports=["8080:80"],
        )

        opts = resource._build_dependency_options()
        assert opts is None

    def test_merge_resource_options_both_none(self):
        """Test _merge_resource_options returns None when both inputs are None."""
        resource = DockerResource(
            description="Test",
            name="test",
            image="alpine:latest",
            ports=["8080:80"],
        )

        merged = resource._merge_resource_options(None, None)
        assert merged is None

    def test_merge_resource_options_parent_only(self):
        """Test _merge_resource_options with only parent options."""
        resource = DockerResource(
            description="Test",
            name="test",
            image="alpine:latest",
            ports=["8080:80"],
        )

        parent_mock = MagicMock()
        parent_opts = pulumi.ResourceOptions(parent=parent_mock)

        merged = resource._merge_resource_options(parent_opts, None)
        assert merged == parent_opts


class TestCompositeOutputs:
    """Tests for Pulumi outputs from composite resources."""

    @patch("pulumi.ComponentResource")
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

    @patch("pulumi.ComponentResource")
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
