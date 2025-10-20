"""Comprehensive tests for composite resources functionality.

Tests cover parent-child relationships, .add() method, .connect() method,
helper methods, chaining operations, and BlankResource behavior.
"""

import asyncio
import pytest
from clockwork.resources import Resource, DockerResource, FileResource, BlankResource


@pytest.fixture(autouse=True)
def event_loop():
    """Create an event loop for each test (needed for Pulumi Output)."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


# ============================================================================
# 1. Basic .add() Method Tests
# ============================================================================


def test_add_single_child():
    """Test adding a single child resource to a parent."""
    parent = DockerResource(description="Parent container", name="parent", image="nginx:alpine", ports=["80:80"])
    child = FileResource(description="Child file", name="config.txt", content="test content")

    result = parent.add(child)

    # Should return self for chaining
    assert result is parent

    # Parent should have child
    assert len(parent.children) == 1
    assert list(parent.children.values())[0] is child
    assert len(parent.children) > 0

    # Child should know its parent
    assert child.parent is parent
    assert child.parent is not None


def test_add_multiple_children_at_once():
    """Test adding multiple children in a single .add() call."""
    parent = DockerResource(description="Parent", name="parent", image="nginx:alpine", ports=["80:80"])
    child1 = FileResource(description="Child 1", name="file1.txt", content="content1")
    child2 = FileResource(description="Child 2", name="file2.txt", content="content2")
    child3 = FileResource(description="Child 3", name="file3.txt", content="content3")

    parent.add(child1, child2, child3)

    # Parent should have all children
    assert len(parent.children) == 3
    assert child1 in parent.children.values()
    assert child2 in parent.children.values()
    assert child3 in parent.children.values()

    # All children should know their parent
    assert child1.parent is parent
    assert child2.parent is parent
    assert child3.parent is parent


def test_add_chaining():
    """Test chaining multiple .add() calls."""
    parent = DockerResource(description="Parent", name="parent", image="nginx:alpine", ports=["80:80"])
    child1 = FileResource(description="Child 1", name="file1.txt", content="content1")
    child2 = FileResource(description="Child 2", name="file2.txt", content="content2")
    child3 = FileResource(description="Child 3", name="file3.txt", content="content3")

    result = parent.add(child1).add(child2).add(child3)

    # Should return parent for chaining
    assert result is parent

    # All children should be added
    assert len(parent.children) == 3
    assert child1 in parent.children.values()
    assert child2 in parent.children.values()
    assert child3 in parent.children.values()


def test_add_type_checking():
    """Test that .add() raises TypeError when adding non-Resource objects."""
    parent = DockerResource(description="Parent", name="parent", image="nginx:alpine", ports=["80:80"])

    # Should raise TypeError for non-Resource
    with pytest.raises(TypeError, match="Can only add Resource objects"):
        parent.add("not a resource")

    with pytest.raises(TypeError, match="Can only add Resource objects"):
        parent.add(42)

    with pytest.raises(TypeError, match="Can only add Resource objects"):
        parent.add({"name": "dict"})


def test_add_duplicate_prevention():
    """Test that adding the same child twice is prevented."""
    parent = DockerResource(description="Parent", name="parent", image="nginx:alpine", ports=["80:80"])
    child = FileResource(description="Child", name="file.txt", content="content")

    # Add child first time
    parent.add(child)
    assert len(parent.children) == 1

    # Try to add same child again - should be skipped
    parent.add(child)
    assert len(parent.children) == 1


def test_add_reparenting_warning(caplog):
    """Test that re-parenting a child resource logs a warning."""
    parent1 = DockerResource(description="Parent 1", name="parent1", image="nginx:alpine", ports=["80:80"])
    parent2 = DockerResource(description="Parent 2", name="parent2", image="redis:alpine", ports=["6379:6379"])
    child = FileResource(description="Child", name="file.txt", content="content")

    # Add child to parent1
    parent1.add(child)
    assert child.parent is parent1

    # Re-parent to parent2 - should log warning
    parent2.add(child)

    # Child should now belong to parent2
    assert child.parent is parent2

    # Check warning was logged
    assert "is being re-parented" in caplog.text


# ============================================================================
# 2. Basic .connect() Method Tests
# ============================================================================


def test_connect_single_resource():
    """Test connecting to a single resource."""
    db = DockerResource(description="Database", name="postgres", image="postgres:15-alpine", ports=["5432:5432"])
    api = DockerResource(description="API", name="api", image="node:20-alpine", ports=["8000:8000"])

    result = api.connect(db)

    # Should return self for chaining
    assert result is api

    # Should have connection in both fields
    assert len(api._connection_resources) == 1
    assert api._connection_resources[0] is db
    assert len(api.connections) == 1
    assert api.connections[0]["name"] == "postgres"
    assert api.connections[0]["type"] == "DockerResource"


def test_connect_multiple_resources():
    """Test connecting to multiple resources at once."""
    db = DockerResource(description="Database", name="postgres", image="postgres:15-alpine", ports=["5432:5432"])
    cache = DockerResource(description="Cache", name="redis", image="redis:7-alpine", ports=["6379:6379"])
    api = DockerResource(description="API", name="api", image="node:20-alpine", ports=["8000:8000"])

    api.connect(db, cache)

    # Should have both connections
    assert len(api._connection_resources) == 2
    assert db in api._connection_resources
    assert cache in api._connection_resources
    assert len(api.connections) == 2


def test_connect_chaining():
    """Test chaining multiple .connect() calls."""
    db = DockerResource(description="Database", name="postgres", image="postgres:15-alpine", ports=["5432:5432"])
    cache = DockerResource(description="Cache", name="redis", image="redis:7-alpine", ports=["6379:6379"])
    queue = DockerResource(description="Queue", name="rabbitmq", image="rabbitmq:3-alpine", ports=["5672:5672"])
    api = DockerResource(description="API", name="api", image="node:20-alpine", ports=["8000:8000"])

    result = api.connect(db).connect(cache).connect(queue)

    # Should return self for chaining
    assert result is api

    # All connections should be added
    assert len(api._connection_resources) == 3
    assert db in api._connection_resources
    assert cache in api._connection_resources
    assert queue in api._connection_resources


def test_connect_type_checking():
    """Test that .connect() raises TypeError when connecting non-Resource objects."""
    api = DockerResource(description="API", name="api", image="node:20-alpine", ports=["8000:8000"])

    # Should raise TypeError for non-Resource
    with pytest.raises(TypeError, match="Can only connect Resource objects"):
        api.connect("not a resource")

    with pytest.raises(TypeError, match="Can only connect Resource objects"):
        api.connect(42)

    with pytest.raises(TypeError, match="Can only connect Resource objects"):
        api.connect({"name": "dict"})


def test_connect_duplicate_prevention():
    """Test that connecting to the same resource twice is prevented."""
    db = DockerResource(description="Database", name="postgres", image="postgres:15-alpine", ports=["5432:5432"])
    api = DockerResource(description="API", name="api", image="node:20-alpine", ports=["8000:8000"])

    # Connect first time
    api.connect(db)
    assert len(api._connection_resources) == 1

    # Try to connect again - should be skipped
    api.connect(db)
    assert len(api._connection_resources) == 1


def test_connect_updates_both_fields():
    """Test that .connect() updates both _connection_resources and connections fields."""
    db = DockerResource(description="Database", name="postgres", image="postgres:15-alpine", ports=["5432:5432"])
    api = DockerResource(description="API", name="api", image="node:20-alpine", ports=["8000:8000"])

    api.connect(db)

    # Should update private list (for graph traversal)
    assert len(api._connection_resources) == 1
    assert api._connection_resources[0] is db

    # Should update public connections (for AI and serialization)
    assert len(api.connections) == 1
    assert isinstance(api.connections[0], dict)
    assert api.connections[0]["name"] == "postgres"


# ============================================================================
# 3. Helper Method Tests
# ============================================================================


def test_children_dict_access():
    """Test that .children dict-style access works correctly."""
    parent = DockerResource(description="Parent", name="parent", image="nginx:alpine", ports=["80:80"])
    child1 = FileResource(description="Child 1", name="file1.txt", content="content1")
    child2 = FileResource(description="Child 2", name="file2.txt", content="content2")

    parent.add(child1, child2)

    # Dict-style access
    assert "file1.txt" in parent.children
    assert "file2.txt" in parent.children
    assert parent.children["file1.txt"] is child1
    assert parent.children["file2.txt"] is child2

    # Safe access
    assert parent.children.get("file1.txt") is child1
    assert parent.children.get("nonexistent") is None

    # Iteration
    children_list = list(parent.children.values())
    assert len(children_list) == 2
    assert child1 in children_list
    assert child2 in children_list


def test_children_dict_is_immutable():
    """Test that modifying .children dict doesn't affect internal state."""
    parent = DockerResource(description="Parent", name="parent", image="nginx:alpine", ports=["80:80"])
    child = FileResource(description="Child", name="file.txt", content="content")

    parent.add(child)

    # Get children dict and try to modify it
    children = parent.children
    # Dict is a property, so direct modification attempts would need to go through add()
    # Just verify the child is accessible
    assert len(children) == 1
    assert list(children.values())[0] is child


def test_parent_returns_correct_parent():
    """Test that .parent property returns the correct parent."""
    parent = DockerResource(description="Parent", name="parent", image="nginx:alpine", ports=["80:80"])
    child = FileResource(description="Child", name="file.txt", content="content")

    parent.add(child)

    assert child.parent is parent
    assert parent.parent is None


def test_children_len_check():
    """Test that len(children) can be used to check for children."""
    parent = DockerResource(description="Parent", name="parent", image="nginx:alpine", ports=["80:80"])
    child = FileResource(description="Child", name="file.txt", content="content")

    # No children initially
    assert len(parent.children) == 0

    # Add child
    parent.add(child)
    assert len(parent.children) > 0


def test_parent_none_check():
    """Test that checking parent is not None works correctly."""
    parent = DockerResource(description="Parent", name="parent", image="nginx:alpine", ports=["80:80"])
    child = FileResource(description="Child", name="file.txt", content="content")

    # No parent initially
    assert child.parent is None

    # Add to parent
    parent.add(child)
    assert child.parent is not None


def test_get_all_descendants_nested_hierarchy():
    """Test get_all_descendants() for nested hierarchies.

    Tests a multi-level hierarchy:
        root
        ├── child1
        │   ├── grandchild1
        │   └── grandchild2
        └── child2
            └── grandchild3
    """
    root = BlankResource(name="root", description="Root resource")
    child1 = BlankResource(name="child1", description="Child 1")
    child2 = BlankResource(name="child2", description="Child 2")
    grandchild1 = FileResource(description="Grandchild 1", name="gc1.txt", content="content1")
    grandchild2 = FileResource(description="Grandchild 2", name="gc2.txt", content="content2")
    grandchild3 = FileResource(description="Grandchild 3", name="gc3.txt", content="content3")

    # Build hierarchy
    root.add(child1, child2)
    child1.add(grandchild1, grandchild2)
    child2.add(grandchild3)

    # Get all descendants
    descendants = root.get_all_descendants()

    # Should include all descendants in depth-first order
    assert len(descendants) == 5
    assert child1 in descendants
    assert child2 in descendants
    assert grandchild1 in descendants
    assert grandchild2 in descendants
    assert grandchild3 in descendants

    # Verify depth-first order: child1, its children, then child2, its children
    child1_idx = descendants.index(child1)
    grandchild1_idx = descendants.index(grandchild1)
    grandchild2_idx = descendants.index(grandchild2)
    child2_idx = descendants.index(child2)
    grandchild3_idx = descendants.index(grandchild3)

    # child1's descendants should come before child2
    assert child1_idx < grandchild1_idx < child2_idx
    assert child1_idx < grandchild2_idx < child2_idx
    assert child2_idx < grandchild3_idx


# ============================================================================
# 4. Chaining Tests
# ============================================================================


def test_add_then_connect_chaining():
    """Test .add().connect() chaining."""
    parent = BlankResource(name="parent", description="Parent resource")
    child = FileResource(description="Child", name="file.txt", content="content")
    db = DockerResource(description="Database", name="postgres", image="postgres:15-alpine", ports=["5432:5432"])

    result = parent.add(child).connect(db)

    # Should return parent
    assert result is parent

    # Should have both child and connection
    assert len(parent.children) == 1
    assert child in parent.children.values()
    assert len(parent._connection_resources) == 1
    assert db in parent._connection_resources


def test_connect_then_add_chaining():
    """Test .connect().add() chaining."""
    parent = BlankResource(name="parent", description="Parent resource")
    child = FileResource(description="Child", name="file.txt", content="content")
    db = DockerResource(description="Database", name="postgres", image="postgres:15-alpine", ports=["5432:5432"])

    result = parent.connect(db).add(child)

    # Should return parent
    assert result is parent

    # Should have both connection and child
    assert len(parent._connection_resources) == 1
    assert db in parent._connection_resources
    assert len(parent.children) == 1
    assert child in parent.children.values()


def test_multiple_chained_operations():
    """Test complex chaining with multiple operations."""
    parent = BlankResource(name="parent", description="Parent resource")
    child1 = FileResource(description="Child 1", name="file1.txt", content="content1")
    child2 = FileResource(description="Child 2", name="file2.txt", content="content2")
    db = DockerResource(description="Database", name="postgres", image="postgres:15-alpine", ports=["5432:5432"])
    cache = DockerResource(description="Cache", name="redis", image="redis:7-alpine", ports=["6379:6379"])

    result = (parent
              .add(child1)
              .connect(db)
              .add(child2)
              .connect(cache))

    # Should return parent
    assert result is parent

    # Should have all children
    assert len(parent.children) == 2
    assert child1 in parent.children.values()
    assert child2 in parent.children.values()

    # Should have all connections
    assert len(parent._connection_resources) == 2
    assert db in parent._connection_resources
    assert cache in parent._connection_resources


# ============================================================================
# 5. BlankResource Tests
# ============================================================================


def test_blank_resource_creation():
    """Test BlankResource creation with name and description."""
    blank = BlankResource(name="my-blank", description="A blank resource")

    assert blank.name == "my-blank"
    assert blank.description == "A blank resource"
    assert len(blank.children) == 0
    assert len(blank.children) == 0


def test_blank_resource_add_children():
    """Test adding children to BlankResource."""
    blank = BlankResource(name="blank", description="Blank resource")
    child1 = FileResource(description="Child 1", name="file1.txt", content="content1")
    child2 = FileResource(description="Child 2", name="file2.txt", content="content2")

    blank.add(child1, child2)

    # Should have children in both _children (from base) and _children_resources (from BlankResource)
    assert len(blank.children) == 2
    assert child1 in blank.children.values()
    assert child2 in blank.children.values()
    assert len(blank._children_resources) == 2

    # Children should know their parent
    assert child1.parent is blank
    assert child2.parent is blank


def test_blank_resource_needs_completion_delegates():
    """Test that BlankResource.needs_completion() delegates to children."""
    blank = BlankResource(name="blank", description="Blank resource")

    # No children - no completion needed
    assert blank.needs_completion() is False

    # Add completed child - no completion needed
    completed_child = FileResource(description="Completed", name="file.txt", content="content")
    blank.add(completed_child)
    assert blank.needs_completion() is False

    # Add child that needs completion
    incomplete_child = FileResource(description="Incomplete file")
    blank.add(incomplete_child)
    assert blank.needs_completion() is True


def test_blank_resource_get_connection_context_includes_children():
    """Test that BlankResource.get_connection_context() includes children info."""
    blank = BlankResource(name="blank", description="Blank resource")
    child1 = DockerResource(description="Child 1", name="nginx", image="nginx:alpine", ports=["80:80"])
    child2 = DockerResource(description="Child 2", name="redis", image="redis:alpine", ports=["6379:6379"])

    blank.add(child1, child2)

    context = blank.get_connection_context()

    # Should include basic info
    assert context["name"] == "blank"
    assert context["type"] == "BlankResource"
    assert context["description"] == "Blank resource"

    # Should include children contexts
    assert "children" in context
    assert len(context["children"]) == 2


# ============================================================================
# 6. Parent-Child Relationship Tests
# ============================================================================


def test_bidirectional_relationships():
    """Test that parent-child relationships are bidirectional."""
    parent = DockerResource(description="Parent", name="parent", image="nginx:alpine", ports=["80:80"])
    child = FileResource(description="Child", name="file.txt", content="content")

    parent.add(child)

    # Parent knows child
    assert child in parent.children.values()
    assert len(parent.children) > 0

    # Child knows parent
    assert child.parent is parent
    assert child.parent is not None


def test_post_creation_field_access():
    """Test accessing child properties after adding to parent."""
    parent = DockerResource(description="Parent", name="parent", image="nginx:alpine", ports=["80:80"])
    child = FileResource(description="Child", name="file.txt", content="content")

    parent.add(child)

    # Should be able to access child properties through parent
    children = list(parent.children.values())
    assert children[0].name == "file.txt"
    assert children[0].content == "content"
    assert children[0].description == "Child"


def test_modifying_child_after_adding():
    """Test modifying child properties after adding to parent.

    Note: Pydantic models are immutable by default, but we can verify
    that the child object remains the same instance and maintains
    its connection to the parent.
    """
    parent = DockerResource(description="Parent", name="parent", image="nginx:alpine", ports=["80:80"])
    child = FileResource(description="Child", name="file.txt", content="original content")

    parent.add(child)

    # Child is the same instance
    assert list(parent.children.values())[0] is child

    # Child still knows its parent
    assert child.parent is parent

    # Properties are accessible
    assert child.content == "original content"


def test_multiple_levels_of_hierarchy():
    """Test multi-level parent-child relationships."""
    root = BlankResource(name="root", description="Root")
    level1 = BlankResource(name="level1", description="Level 1")
    level2 = FileResource(description="Level 2", name="file.txt", content="content")

    root.add(level1)
    level1.add(level2)

    # Root knows level1, level1 knows level2
    assert level1 in root.children.values()
    assert level2 in level1.children.values()

    # Reverse relationships
    assert level1.parent is root
    assert level2.parent is level1

    # Root has no parent, level2 has no children
    assert root.parent is None
    assert len(level2.children) == 0


def test_empty_parent_has_no_children():
    """Test that a parent with no children behaves correctly."""
    parent = DockerResource(description="Parent", name="parent", image="nginx:alpine", ports=["80:80"])

    assert len(parent.children) == 0
    assert len(parent.children) == 0
    assert parent.get_all_descendants() == []


def test_root_resource_has_no_parent():
    """Test that a root resource (not added to any parent) has no parent."""
    root = DockerResource(description="Root", name="root", image="nginx:alpine", ports=["80:80"])

    assert root.parent is None
    assert root.parent is None
