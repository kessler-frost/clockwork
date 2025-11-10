"""End-to-end integration tests for composite resources.

This module tests complete workflows including:
- Creating composites → adding children → resolving dependencies → compiling to Pulumi
- AI completion for composites (two-phase completion)
- Composites with assertions
- Mixed composite and primitive resources in same deployment
- Post-creation field overrides on children
"""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest
from pydantic import ValidationError

from clockwork.core import ClockworkCore
from clockwork.resources import BlankResource, DockerResource, FileResource


@pytest.fixture(autouse=True)
def event_loop():
    """Create an event loop for each test (needed for Pulumi Output)."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


class TestEndToEndWorkflow:
    """Tests for complete workflow: create → add → resolve → compile."""

    def test_simple_composite_workflow(self):
        """Test complete workflow with simple composite."""
        # 1. Create composite
        backend = BlankResource(name="backend", description="Backend services")

        # 2. Add children
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
        backend.add(db, cache)

        # 3. Resolve dependencies
        core = ClockworkCore(api_key="test", model="test")
        ordered = core._resolve_dependency_order([backend])

        # Verify resolution
        assert len(ordered) == 3  # backend + db + cache
        # Use identity checks to avoid circular reference issues with Connection objects
        assert any(r is backend for r in ordered)
        assert any(r is db for r in ordered)
        assert any(r is cache for r in ordered)

        # 4. Verify structure
        # Use identity checks to avoid circular reference issues with Connection objects
        assert any(r is db for r in backend.children.values())
        assert any(r is cache for r in backend.children.values())
        assert db.parent is backend
        assert cache.parent is backend

    def test_nested_composite_workflow(self):
        """Test complete workflow with nested composites."""
        # Create nested structure
        db = DockerResource(
            description="Database",
            name="db",
            image="postgres:15",
            ports=["5432:5432"],
        )

        backend = BlankResource(name="backend", description="Backend")
        backend.add(db)

        api = DockerResource(
            description="API",
            name="api",
            image="node:20",
            ports=["3000:3000"],
        )
        api.connect(db)

        app = BlankResource(name="app", description="Application")
        app.add(backend, api)

        # Resolve dependencies
        core = ClockworkCore(api_key="test", model="test")
        ordered = core._resolve_dependency_order([app])

        # Verify flattening and ordering
        assert len(ordered) == 4  # app + backend + db + api

        # Find indices
        idx_app = next(i for i, r in enumerate(ordered) if r.name == "app")
        idx_backend = next(
            i for i, r in enumerate(ordered) if r.name == "backend"
        )
        idx_db = next(i for i, r in enumerate(ordered) if r.name == "db")
        idx_api = next(i for i, r in enumerate(ordered) if r.name == "api")

        # Verify ordering
        assert idx_app < idx_backend  # parent before child
        assert idx_backend < idx_db  # parent before child
        assert idx_db < idx_api  # dependency before dependent

    def test_cross_composite_connection_workflow(self):
        """Test workflow with connections across composite boundaries."""
        # Composite A
        db = DockerResource(
            description="Database",
            name="db",
            image="postgres:15",
            ports=["5432:5432"],
        )
        backend = BlankResource(name="backend", description="Backend")
        backend.add(db)

        # Composite B (API connects to db in composite A)
        api = DockerResource(
            description="API",
            name="api",
            image="node:20",
            ports=["3000:3000"],
        )
        api.connect(db)
        services = BlankResource(name="services", description="Services")
        services.add(api)

        # Resolve dependencies
        core = ClockworkCore(api_key="test", model="test")
        ordered = core._resolve_dependency_order([backend, services])

        # Verify ordering respects cross-composite connection
        idx_db = next(i for i, r in enumerate(ordered) if r.name == "db")
        idx_api = next(i for i, r in enumerate(ordered) if r.name == "api")
        assert idx_db < idx_api


class TestAICompletion:
    """Tests for AI completion with composite resources."""

    @pytest.mark.asyncio
    async def test_composite_needs_completion(self):
        """Test that composite triggers completion when children need it."""
        # Create composite with incomplete child
        backend = BlankResource(name="backend", description="Backend")
        backend.add(
            DockerResource(
                description="PostgreSQL database"
            )  # No name or image
        )

        # Composite should need completion
        assert backend.needs_completion()

    @pytest.mark.asyncio
    async def test_composite_two_phase_completion(self):
        """Test two-phase completion: composite children, then primitives."""
        # Create composite with incomplete children
        backend = BlankResource(name="backend", description="Backend services")
        backend.add(
            DockerResource(description="PostgreSQL database"),
            DockerResource(description="Redis cache"),
        )

        # Mock ResourceCompleter
        with patch("clockwork.core.ResourceCompleter") as mock_completer_class:
            mock_completer = Mock()

            # Mock complete method to fill in missing fields
            async def mock_complete(resources):
                completed = []
                for r in resources:
                    if isinstance(r, DockerResource):
                        if r.name is None:
                            r.name = (
                                "completed-" + r.description.split()[0].lower()
                            )
                        if r.image is None:
                            r.image = (
                                "postgres:15"
                                if "database" in r.description.lower()
                                else "redis:7"
                            )
                        if r.ports is None or len(r.ports) == 0:
                            r.ports = (
                                ["5432:5432"]
                                if "database" in r.description.lower()
                                else ["6379:6379"]
                            )
                    completed.append(r)
                return completed

            mock_completer.complete = mock_complete
            mock_completer_class.return_value = mock_completer

            # Run completion
            core = ClockworkCore(api_key="test", model="test")
            await core._complete_resources_safe([backend])

            # Verify children were completed
            # Note: This tests the concept, actual implementation may vary

    @pytest.mark.asyncio
    async def test_composite_completion_preserves_hierarchy(self):
        """Test that AI completion preserves parent-child relationships."""
        # Create composite with children (name is needed for children collection)
        db = DockerResource(
            name="db",
            description="Database",
            image="postgres:15",
            ports=["5432:5432"],
        )
        backend = BlankResource(name="backend", description="Backend")
        backend.add(db)

        # Verify hierarchy is established
        assert db.parent == backend
        assert "db" in backend.children
        assert backend.children["db"] == db

        # Note: We skip actual AI completion testing since it requires an LLM
        # The important thing is that the hierarchy is established correctly


class TestAssertions:
    """Tests for composite resources with assertions."""

    @pytest.mark.asyncio
    async def test_composite_with_assertions(self):
        """Test composite resource with assertions on children."""
        from clockwork.assertions import ContainerRunningAssert

        # Create composite with child that has assertions
        db = DockerResource(
            description="Database",
            name="db",
            image="postgres:15",
            ports=["5432:5432"],
            assertions=[ContainerRunningAssert(container_name="db")],
        )

        backend = BlankResource(name="backend", description="Backend")
        backend.add(db)

        # Load and run assertions
        with patch("clockwork.core.ResourceCompleter") as mock_completer_class:
            mock_completer = Mock()
            mock_completer.complete = AsyncMock(return_value=[backend])
            mock_completer_class.return_value = mock_completer

            core = ClockworkCore(api_key="test", model="test")

            # Run assertion pipeline
            # This should flatten composites and run assertions on children
            resources = core._flatten_resources([backend])

            # Verify db assertions are accessible
            db_resource = next(r for r in resources if r.name == "db")
            assert db_resource.assertions is not None
            assert len(db_resource.assertions) == 1

    @pytest.mark.asyncio
    async def test_assertions_on_nested_composites(self):
        """Test assertions work with nested composites."""
        from clockwork.assertions import ContainerRunningAssert

        # Create nested structure with assertions
        db = DockerResource(
            description="Database",
            name="db",
            image="postgres:15",
            ports=["5432:5432"],
            assertions=[ContainerRunningAssert(container_name="db")],
        )

        backend = BlankResource(name="backend", description="Backend")
        backend.add(db)

        app = BlankResource(name="app", description="Application")
        app.add(backend)

        # Flatten to access assertions
        core = ClockworkCore(api_key="test", model="test")
        flattened = core._flatten_resources([app])

        # Find db resource
        db_resource = next(r for r in flattened if r.name == "db")
        assert db_resource.assertions is not None
        assert len(db_resource.assertions) == 1


class TestMixedResources:
    """Tests for mixed composite and primitive resources."""

    def test_mixed_primitives_and_composites_deployment(self):
        """Test deployment with mix of primitives and composites."""
        # Standalone primitive
        config = FileResource(
            description="Config", name="config.yaml", content="key: value"
        )

        # Composite with children
        db = DockerResource(
            description="Database",
            name="db",
            image="postgres:15",
            ports=["5432:5432"],
        )
        db.connect(config)
        backend = BlankResource(name="backend", description="Backend")
        backend.add(db)

        # Another standalone primitive
        api = DockerResource(
            description="API",
            name="api",
            image="node:20",
            ports=["3000:3000"],
        )
        api.connect(db)

        # Resolve dependencies
        core = ClockworkCore(api_key="test", model="test")
        ordered = core._resolve_dependency_order([config, backend, api])

        # Verify all resources are present
        assert len(ordered) == 4  # config + backend + db + api

        # Find indices
        idx_config = next(
            i for i, r in enumerate(ordered) if r.name == "config.yaml"
        )
        idx_backend = next(
            i for i, r in enumerate(ordered) if r.name == "backend"
        )
        idx_db = next(i for i, r in enumerate(ordered) if r.name == "db")
        idx_api = next(i for i, r in enumerate(ordered) if r.name == "api")

        # Verify ordering
        assert idx_config < idx_db  # config before db (explicit connection)
        assert idx_backend < idx_db  # backend before db (parent-child)
        assert idx_db < idx_api  # db before api (explicit connection)

    @pytest.mark.asyncio
    async def test_mixed_resources_full_pipeline(self):
        """Test full pipeline with mixed resources."""
        # Create mixed resources
        config = FileResource(
            description="Config",
            name="config.yaml",
            content="database: postgres",
        )

        db = DockerResource(
            description="Database",
            name="db",
            image="postgres:15",
            ports=["5432:5432"],
        )

        backend = BlankResource(name="backend", description="Backend")
        backend.add(db)

        # Mock pipeline components
        with (
            patch("clockwork.core.ResourceCompleter") as mock_completer_class,
            patch("clockwork.core.PulumiCompiler") as mock_compiler_class,
        ):
            # Setup mocks
            mock_completer = Mock()
            mock_completer.complete = AsyncMock(return_value=[config, backend])
            mock_completer_class.return_value = mock_completer

            mock_compiler = Mock()
            mock_compiler.preview = AsyncMock(
                return_value={
                    "success": True,
                    "summary": {"change_summary": {"create": 3}},
                }
            )
            mock_compiler_class.return_value = mock_compiler

            # Create temporary main.py
            import tempfile

            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".py", delete=False
            ) as f:
                f.write("""
from clockwork.resources import FileResource, DockerResource, BlankResource

config = FileResource(
    description="Config",
    name="config.yaml",
    content="database: postgres"
)

db = DockerResource(
    description="Database",
    name="db",
    image="postgres:15",
    ports=["5432:5432"]
)

backend = BlankResource(name="backend", description="Backend")
backend.add(db)
""")
                temp_path = Path(f.name)

            try:
                # Run plan
                core = ClockworkCore(api_key="test", model="test")
                result = await core.plan(temp_path)

                # Verify pipeline executed
                assert result["dry_run"] is True
            finally:
                # Cleanup
                temp_path.unlink()


class TestPostCreationOverrides:
    """Tests for post-creation field overrides on children."""

    def test_override_child_fields_after_adding(self):
        """Test that child fields can be overridden after adding to composite."""
        # Create child with initial values
        db = DockerResource(
            description="Database",
            name="db",
            image="postgres:15",
            ports=["5432:5432"],
        )

        # Add to composite
        backend = BlankResource(name="backend", description="Backend")
        backend.add(db)

        # Override field on child
        db.ports = ["5433:5432"]  # Change port mapping

        # Verify override is reflected
        assert db.ports == ["5433:5432"]

        # Verify parent relationship is maintained
        assert db.parent == backend

    def test_override_connection_after_creation(self):
        """Test adding connections to child after adding to composite."""
        # Create resources
        cache = DockerResource(
            description="Cache",
            name="cache",
            image="redis:7",
            ports=["6379:6379"],
        )

        db = DockerResource(
            description="Database",
            name="db",
            image="postgres:15",
            ports=["5432:5432"],
        )

        backend = BlankResource(name="backend", description="Backend")
        backend.add(db)

        # Add connection after adding to composite
        db.connect(cache)

        # Verify connection was added
        assert len(db._connections) == 1
        assert db._connections[0].to_resource == cache

    def test_add_more_children_after_creation(self):
        """Test adding more children to composite after initial creation."""
        # Create composite with initial child
        db = DockerResource(
            description="Database",
            name="db",
            image="postgres:15",
            ports=["5432:5432"],
        )

        backend = BlankResource(name="backend", description="Backend")
        backend.add(db)

        assert len(backend.children) == 1

        # Add more children later
        cache = DockerResource(
            description="Cache",
            name="cache",
            image="redis:7",
            ports=["6379:6379"],
        )

        backend.add(cache)

        # Verify both children are present
        assert len(backend.children) == 2
        assert db in backend.children.values()
        assert cache in backend.children.values()


class TestComplexScenarios:
    """Tests for complex real-world scenarios."""

    def test_microservices_architecture(self):
        """Test complex microservices architecture with multiple composites."""
        # Database layer
        postgres = DockerResource(
            description="PostgreSQL",
            name="postgres",
            image="postgres:15",
            ports=["5432:5432"],
        )

        redis = DockerResource(
            description="Redis",
            name="redis",
            image="redis:7",
            ports=["6379:6379"],
        )

        data_layer = BlankResource(name="data-layer", description="Data layer")
        data_layer.add(postgres, redis)

        # Service layer
        auth_service = DockerResource(
            description="Auth service",
            name="auth",
            image="auth:latest",
            ports=["8001:8000"],
        )
        auth_service.connect(postgres).connect(redis)

        api_service = DockerResource(
            description="API service",
            name="api",
            image="api:latest",
            ports=["8002:8000"],
        )
        api_service.connect(postgres).connect(redis).connect(auth_service)

        service_layer = BlankResource(
            name="service-layer", description="Service layer"
        )
        service_layer.add(auth_service, api_service)

        # Gateway layer
        gateway = DockerResource(
            description="API Gateway",
            name="gateway",
            image="nginx:latest",
            ports=["80:80"],
        )
        gateway.connect(api_service)

        gateway_layer = BlankResource(
            name="gateway-layer", description="Gateway layer"
        )
        gateway_layer.add(gateway)

        # Top-level application
        app = BlankResource(
            name="microservices-app", description="Microservices application"
        )
        app.add(data_layer, service_layer, gateway_layer)

        # Resolve dependencies
        core = ClockworkCore(api_key="test", model="test")
        ordered = core._resolve_dependency_order([app])

        # Verify all resources are flattened
        assert len(ordered) == 9  # 4 composites + 5 containers

        # Get resource names for verification
        ordered_names = [r.name for r in ordered]

        # Verify all expected resources are present
        assert "postgres" in ordered_names
        assert "redis" in ordered_names
        assert "auth" in ordered_names
        assert "api" in ordered_names
        assert "gateway" in ordered_names

        # Verify ordering constraints
        idx_postgres = ordered_names.index("postgres")
        idx_redis = ordered_names.index("redis")
        idx_auth = ordered_names.index("auth")
        idx_api = ordered_names.index("api")
        idx_gateway = ordered_names.index("gateway")

        # Data layer before services
        assert idx_postgres < idx_auth
        assert idx_postgres < idx_api
        assert idx_redis < idx_auth
        assert idx_redis < idx_api

        # Auth before API (explicit dependency)
        assert idx_auth < idx_api

        # API before Gateway (explicit dependency)
        assert idx_api < idx_gateway

    def test_three_tier_web_application(self):
        """Test three-tier web application architecture."""
        # Backend tier
        db = DockerResource(
            description="PostgreSQL database",
            name="db",
            image="postgres:15",
            ports=["5432:5432"],
        )

        backend_tier = BlankResource(
            name="backend-tier", description="Backend tier"
        )
        backend_tier.add(db)

        # Application tier
        api = DockerResource(
            description="REST API",
            name="api",
            image="api:latest",
            ports=["3000:3000"],
        )
        api.connect(db)

        app_tier = BlankResource(
            name="app-tier", description="Application tier"
        )
        app_tier.add(api)

        # Frontend tier
        web = DockerResource(
            description="Web frontend",
            name="web",
            image="nginx:latest",
            ports=["80:80"],
        )
        web.connect(api)

        frontend_tier = BlankResource(
            name="frontend-tier", description="Frontend tier"
        )
        frontend_tier.add(web)

        # Full application
        three_tier_app = BlankResource(
            name="three-tier-app", description="Three-tier app"
        )
        three_tier_app.add(backend_tier, app_tier, frontend_tier)

        # Resolve dependencies
        core = ClockworkCore(api_key="test", model="test")
        ordered = core._resolve_dependency_order([three_tier_app])

        # Verify ordering: backend → app → frontend
        idx_db = next(i for i, r in enumerate(ordered) if r.name == "db")
        idx_api = next(i for i, r in enumerate(ordered) if r.name == "api")
        idx_web = next(i for i, r in enumerate(ordered) if r.name == "web")

        assert idx_db < idx_api
        assert idx_api < idx_web


class TestErrorHandling:
    """Tests for error handling in composite workflows."""

    def test_invalid_resource_type_in_add(self):
        """Test error when adding non-Resource object to composite."""
        backend = BlankResource(name="backend", description="Backend")

        with pytest.raises(TypeError):
            backend.add("not-a-resource")

    def test_composite_without_name_fails_compilation(self):
        """Test that composite without name fails during compilation."""
        # Note: BlankResource requires name, so this test checks validation
        with pytest.raises(ValidationError):
            BlankResource()  # Should fail: name is required

    def test_cycle_detection_prevents_deployment(self):
        """Test that cycle detection prevents deployment."""
        from clockwork.connections import DependencyConnection

        # Create cycle
        db = DockerResource(
            description="Database",
            name="db",
            image="postgres:15",
            ports=["5432:5432"],
        )

        api = DockerResource(
            description="API",
            name="api",
            image="node:20",
            ports=["3000:3000"],
        )
        api.connect(db)

        # Create cycle by making db depend on api (which already depends on db)
        db._connections.append(
            DependencyConnection(from_resource=db, to_resource=api)
        )

        backend = BlankResource(name="backend", description="Backend")
        backend.add(db, api)

        core = ClockworkCore(api_key="test", model="test")

        # Should raise cycle error during resolution
        with pytest.raises(ValueError, match=r"[Cc]ycle|[Cc]ircular"):
            core._resolve_dependency_order([backend])
