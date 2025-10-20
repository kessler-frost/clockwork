# Composite Resource Examples

This directory contains examples demonstrating composite resource patterns in Clockwork. Composite resources allow you to group related infrastructure components into reusable, manageable units.

## What are Composite Resources?

Composite resources (using `BlankResource`) let you:
- Group related resources together logically
- Create reusable infrastructure patterns
- Manage complex dependencies
- Build hierarchical infrastructure stacks

## Examples Overview

### 1. Simple Web App (`simple-webapp/`)
**Level**: Beginner
**Demonstrates**: Basic composite pattern with database, cache, and API server

A straightforward example showing how to group a PostgreSQL database, Redis cache, and Node.js API server into a single composite resource. Perfect starting point for understanding composites.

**Key Concepts**:
- Creating a composite with `.add()`
- Connecting child resources with `.connect()`
- Adding assertions for verification

### 2. Nested Composites (`nested-composites/`)
**Level**: Intermediate
**Demonstrates**: Multi-level hierarchical composites

Shows how to nest composites within composites, creating a three-level architecture: database cluster → application tier → full stack. Useful for modeling complex, layered infrastructure.

**Key Concepts**:
- Three-level composite hierarchy
- Nested resource management
- When to use nested vs flat structures

### 3. Mixed Pattern (`mixed-pattern/`)
**Level**: Intermediate
**Demonstrates**: Combining composites with standalone resources

Illustrates how to mix composite resources with standalone resources in the same project. Shows a web app composite connecting to an external shared monitoring service.

**Key Concepts**:
- Hybrid composite + standalone approach
- External dependencies
- When to use each pattern

### 4. Post-Creation Overrides (`post-creation-overrides/`)
**Level**: Advanced
**Demonstrates**: Modifying child resources after creation

Compares two approaches: configuring children at creation time vs modifying them after adding to the composite. Helps you choose the right pattern for your use case.

**Key Concepts**:
- Constructor-based configuration
- Post-creation property overrides
- Trade-offs between approaches

## Running Examples

Each example can be run independently:

```bash
cd simple-webapp
uv run clockwork apply
```

To clean up:

```bash
uv run clockwork destroy
```

## Common Patterns

### Basic Composite Pattern
```python
from clockwork.resources import BlankResource, DockerResource

# Create composite
app = BlankResource(name="my-app", description="Web application stack")

# Add children
db = app.add(DockerResource(name="db", description="Database"))
api = app.add(DockerResource(name="api", description="API server"))

# Connect children
api.connect(db)  # API depends on database
```

### Nested Composites
```python
# Create parent composite
stack = BlankResource(name="full-stack", description="Complete application")

# Create child composites
db_cluster = stack.add(BlankResource(name="databases", description="Database cluster"))
app_tier = stack.add(BlankResource(name="app-tier", description="Application services"))

# Add resources to child composites
primary = db_cluster.add(DockerResource(name="primary", description="Primary DB"))
api = app_tier.add(DockerResource(name="api", description="API"))

# Connect across composites
api.connect(primary)
```

## Best Practices

1. **Logical Grouping**: Group resources that are deployed and managed together
2. **Clear Naming**: Use descriptive names for composites and children
3. **Connection Management**: Use `.connect()` to establish dependencies
4. **Assertions**: Add assertions to verify behavior
5. **Documentation**: Comment your composite structures for clarity

## When to Use Composites

✅ **Use Composites When**:
- You have multiple related resources
- You want to create reusable patterns
- You need to manage complex dependencies
- You're building hierarchical infrastructure

❌ **Don't Use Composites When**:
- You have a single resource
- Resources are completely independent
- Over-abstraction adds complexity without benefit

## Learn More

- Review each example in order (simple → advanced)
- Check the README.md in each example directory
- Experiment by modifying the examples
- See `examples/connected-services/` for real-world patterns

## Questions?

Refer to the main Clockwork documentation in `/Users/sankalp/dev/clockwork/CLAUDE.md` for more details on resource connections, assertions, and configuration.
