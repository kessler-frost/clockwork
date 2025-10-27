# Nested Composites Example

## Overview

This example demonstrates multi-level hierarchical composite structures by creating a three-tier architecture with database clustering and multiple application services. It shows how to nest `BlankResource` composites within each other for complex infrastructure modeling.

## What This Demonstrates

- **Three-Level Hierarchy**: Root → Mid-level → Leaf resources
- **Nested Composites**: BlankResources containing other BlankResources
- **Cross-Composite Dependencies**: Connections between resources in different composites
- **Separation of Concerns**: Database cluster vs application tier
- **Primary/Replica Pattern**: Database replication architecture

## Architecture Diagram

```
full-stack (Level 1: Root Composite)
│
├── database-cluster (Level 2: Database Composite)
│   │
│   ├── postgres-primary (Level 3: Primary DB)
│   │   └── Port: 5432
│   │
│   └── postgres-replica (Level 3: Read Replica)
│       ├── Port: 5433
│       └── Depends on: postgres-primary
│
└── application-tier (Level 2: Application Composite)
    │
    ├── api-service (Level 3: REST API)
    │   ├── Port: 8000
    │   └── Depends on: postgres-primary
    │
    ├── worker-service (Level 3: Background Worker)
    │   └── Depends on: postgres-primary
    │
    └── web-frontend (Level 3: Web UI)
        ├── Port: 3000
        └── Depends on: postgres-replica, api-service
```

## Components

### Level 1: Full Stack (Root Composite)

The top-level composite that contains the entire application.

### Level 2: Database Cluster (Mid-Level Composite)

**Purpose**: Groups all database resources together

1. **postgres-primary**: Read-write primary database (port 5432)
2. **postgres-replica**: Read-only replica for scaling (port 5433)

### Level 2: Application Tier (Mid-Level Composite)

**Purpose**: Groups all application services together

1. **api-service**: REST API server (port 8000)
   - Connects to primary for read-write operations
2. **worker-service**: Background job processor
   - Connects to primary for read-write operations
3. **web-frontend**: Web UI (port 3000)
   - Connects to replica for read-only operations (better performance)
   - Connects to API for dynamic data

## Deployment Order

Thanks to `.connect()` across composite boundaries, deployment order is:

1. `postgres-primary` (no dependencies)
2. `postgres-replica` (depends on primary)
3. `api-service` and `worker-service` (depend on primary) - can deploy in parallel
4. `web-frontend` (depends on replica and api-service)

## Running This Example

### Deploy the Stack

```bash
cd examples/composite-resources/nested-composites
uv run clockwork apply
```

### Verify Assertions

```bash
uv run clockwork assert
```

Expected assertions:
- All containers running
- Primary database accessible on 5432
- Replica database accessible on 5433
- API accessible on 8000 with health check
- Frontend accessible on 3000 with health check

### Test the Services

```bash
# Test API
curl http://localhost:8000/health

# Test Frontend
curl http://localhost:3000

# Check database connections
docker exec postgres-primary psql -U appuser -d appdb -c "SELECT version();"
docker exec postgres-replica psql -U appuser -d appdb -c "SELECT version();"
```

### Clean Up

```bash
uv run clockwork destroy
```

## Key Concepts

### Why Three Levels?

**Level 1 (Root)**: Represents the entire system
- Easy to deploy/destroy everything together
- Clear ownership boundary

**Level 2 (Tiers)**: Logical grouping by concern
- Database resources separate from application resources
- Can swap out entire tiers (e.g., replace database cluster with managed service)
- Clear architectural boundaries

**Level 3 (Resources)**: Actual infrastructure
- Individual containers/services
- Can be configured independently
- Can have dependencies within and across tiers

### Cross-Composite Dependencies

Dependencies work seamlessly across composite boundaries:

```python
# api-service (in app-tier) depends on db-primary (in db-cluster)
api_service.connect(db_primary)
```

This is a key feature - you can organize resources logically while maintaining any dependency structure.

### Primary/Replica Pattern

This example shows a common pattern:
- **Writes**: Go to primary database
- **Reads**: Can go to replica (reduces primary load)

Application services connect appropriately:
- `api-service`: Primary (handles writes)
- `worker-service`: Primary (handles writes)
- `web-frontend`: Replica (mostly reads)

## When to Use Nested Composites

✅ **Use nested composites when**:
- You have clear architectural layers (e.g., data tier, app tier, presentation tier)
- You want to swap out entire groups of resources
- Your infrastructure has natural hierarchical structure
- You need to manage groups independently while maintaining relationships

❌ **Don't nest when**:
- Two levels (root + resources) are sufficient
- Nesting adds complexity without clarity
- Resources don't naturally group into tiers

## Scaling This Pattern

You can extend this pattern to:

1. **Add more replicas**: Add additional read replicas to database cluster
2. **Add caching tier**: Create a new composite for Redis/Memcached
3. **Add monitoring tier**: Create a composite for Prometheus/Grafana
4. **Add more services**: Add more services to application tier
5. **Environment-specific**: Create dev/staging/prod versions with different configs

## Customization Ideas

Try modifying this example to:

1. **Add Redis cache**: Create a caching composite within full-stack
2. **Add load balancer**: Put nginx in front of api-service and web-frontend
3. **Add monitoring**: Create a monitoring composite with Prometheus and Grafana
4. **Scale replicas**: Add more database replicas
5. **Use AI completion**: Remove image specifications and let AI choose

## Comparison with Flat Structure

**Flat (simple-webapp example)**:
```
webapp
├── postgres
├── redis
└── api
```

**Nested (this example)**:
```
full-stack
├── database-cluster
│   ├── primary
│   └── replica
└── app-tier
    ├── api
    ├── worker
    └── frontend
```

Nested provides better organization for complex systems.

## Next Steps

After understanding this example, check out:

- `mixed-pattern/`: Learn when to mix composites with standalone resources
- `post-creation-overrides/`: Advanced configuration patterns
- `simple-webapp/`: Review the simpler two-level pattern if this seems complex

## Related Examples

- `examples/composite-resources/simple-webapp/`: Basic two-level composite
- `examples/connected-services/`: Real-world service patterns
