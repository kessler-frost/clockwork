# Mixed Pattern Example

## Overview

This example demonstrates how to effectively combine composite resources with standalone resources in the same project. It shows a realistic scenario where a web application (composite) depends on a shared monitoring service (standalone).

## What This Demonstrates

- **Hybrid Architecture**: Mixing composites with standalone resources
- **Shared Services**: Standalone resources shared across applications
- **Cross-Boundary Dependencies**: Composites depending on external resources
- **Design Trade-offs**: When to use each pattern
- **Real-world Patterns**: Common infrastructure scenarios

## Architecture

```
prometheus (Standalone - Shared Service)
└── Port: 9090
    └── Used by: Multiple applications

webapp (Composite - Application-Specific)
├── postgres-db
│   └── Port: 5432
└── api-service
    ├── Port: 8000
    ├── Depends on: postgres-db (internal dependency)
    └── Depends on: prometheus (external dependency)
```

## Components

### Standalone Resource

**prometheus** - Shared monitoring service
- **Type**: Standalone AppleContainerResource
- **Purpose**: Collects metrics from multiple applications
- **Why Standalone**: Shared infrastructure, independent lifecycle
- **Port**: 9090

### Composite Resource (webapp)

**webapp** - Application-specific stack
- **Type**: BlankResource composite
- **Contains**: Database and API service
- **Why Composite**: Tightly coupled, deployed together

#### Children of webapp:

1. **postgres-db** - Application database
   - **Type**: AppleContainerResource
   - **Port**: 5432
   - **Purpose**: Stores application data

2. **api-service** - REST API server
   - **Type**: AppleContainerResource
   - **Port**: 8000
   - **Dependencies**: postgres-db (internal), prometheus (external)
   - **Purpose**: Serves API requests, exposes metrics

## Deployment Order

1. `prometheus` (standalone, no dependencies)
2. `postgres-db` (part of webapp, no dependencies)
3. `api-service` (part of webapp, depends on both)

## Running This Example

### Prerequisites

Create a minimal Prometheus configuration file:

```bash
cd examples/composite-resources/mixed-pattern

cat > prometheus.yml <<EOF
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'webapp-api'
    static_configs:
      - targets: ['api-service:8000']
EOF
```

### Deploy the Stack

```bash
uv run clockwork apply
```

### Verify Assertions

```bash
uv run clockwork assert
```

Expected results:
- Prometheus running and healthy
- Database running and accessible
- API running, healthy, with metrics endpoint

### Test the Services

```bash
# Check Prometheus
curl http://localhost:9090/-/healthy

# Check API
curl http://localhost:8000/health

# Check metrics endpoint
curl http://localhost:8000/metrics

# View Prometheus targets
open http://localhost:9090/targets
```

### Clean Up

```bash
# Destroy everything
uv run clockwork destroy
```

## Key Concepts

### When to Use Standalone Resources

✅ **Use standalone when**:
- Resource is shared across multiple applications
- Resource has independent lifecycle
- Resource provides infrastructure services
- Resource doesn't logically belong to a specific app

**Examples**:
- Monitoring (Prometheus, Grafana)
- Logging (ELK stack)
- Message queues (RabbitMQ, Kafka)
- Shared databases
- API gateways

### When to Use Composite Resources

✅ **Use composites when**:
- Resources are tightly coupled
- Resources share a lifecycle (deploy/destroy together)
- Resources form a logical unit
- You want to manage them as a group

**Examples**:
- Web application stack (DB + API + Frontend)
- Microservice with dependencies
- Development environment
- Feature-specific services

### Cross-Boundary Dependencies

This example shows that composites can depend on external resources:

```python
# api (inside webapp composite) depends on monitoring (standalone)
api.connect(monitoring)
```

This is powerful because:
1. **Flexibility**: Mix organizational patterns
2. **Realism**: Real infrastructure has shared + app-specific resources
3. **Clear dependencies**: Dependencies work regardless of organization

## Design Patterns Comparison

### Pattern 1: Everything Standalone (Flat)

```python
monitoring = AppleContainerResource(...)
database = AppleContainerResource(...)
api = AppleContainerResource(...)
```

**Pros**: Simple, explicit
**Cons**: No organization, hard to see relationships

### Pattern 2: Everything Composite (Over-abstraction)

```python
infrastructure = BlankResource(...)
infrastructure.add(monitoring)
infrastructure.add(database)
infrastructure.add(api)
```

**Pros**: Grouped
**Cons**: False grouping (monitoring shouldn't be app-specific)

### Pattern 3: Mixed (This Example)

```python
monitoring = AppleContainerResource(...)  # Standalone
webapp = BlankResource(...)       # Composite
webapp.add(database)
webapp.add(api)
```

**Pros**: Reflects reality, clear separation
**Cons**: Requires judgment about what to group

## Real-World Scenarios

### Scenario 1: Multiple Apps, Shared Monitoring

```
prometheus (standalone)
├── webapp-1 (composite) → depends on prometheus
│   ├── db-1
│   └── api-1
└── webapp-2 (composite) → depends on prometheus
    ├── db-2
    └── api-2
```

### Scenario 2: Microservices with Shared Infrastructure

```
message-queue (standalone)
logging (standalone)
monitoring (standalone)

service-a (composite) → depends on queue, logging, monitoring
├── db-a
└── api-a

service-b (composite) → depends on queue, logging, monitoring
├── db-b
└── api-b
```

### Scenario 3: Development Environment

```
shared-database (standalone) - Used by all devs

alice-env (composite) → depends on shared-database
├── alice-api
└── alice-frontend

bob-env (composite) → depends on shared-database
├── bob-api
└── bob-frontend
```

## Customization Ideas

Try modifying this example to:

1. **Add more apps**: Create webapp-2, webapp-3 that all use prometheus
2. **Add Grafana**: Add standalone Grafana that depends on prometheus
3. **Add Redis**: Add standalone Redis shared by multiple apps
4. **Add app-specific monitoring**: Add per-app metrics collectors within composites
5. **Use AI completion**: Remove image fields and let AI choose

## Benefits of Mixed Pattern

1. **Realistic**: Mirrors real infrastructure topology
2. **Flexible**: Choose the right pattern for each resource
3. **Maintainable**: Clear ownership boundaries
4. **Scalable**: Easy to add more apps or shared services
5. **Efficient**: Shared services don't duplicate

## Common Mistakes to Avoid

❌ **Don't**: Put shared services inside app composites
```python
# Bad: Monitoring inside webapp
webapp = BlankResource(...)
webapp.add(monitoring)  # Wrong! Monitoring is shared
```

❌ **Don't**: Create composites for unrelated resources
```python
# Bad: Forcing things into a composite
everything = BlankResource(...)
everything.add(unrelated_service_1)
everything.add(unrelated_service_2)
```

✅ **Do**: Group related, coupled resources
```python
# Good: Related resources in composite
webapp = BlankResource(...)
webapp.add(app_database)
webapp.add(app_api)
```

✅ **Do**: Keep shared services standalone
```python
# Good: Shared service standalone
monitoring = AppleContainerResource(...)
```

## Next Steps

After understanding this example, check out:

- `post-creation-overrides/`: Advanced configuration patterns
- `simple-webapp/`: Review basic composites if needed
- `nested-composites/`: More complex composite hierarchies

## Related Examples

- `examples/connected-services/`: Real-world service connections
- `examples/showcase/`: Complete feature showcase
