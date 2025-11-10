# Connections Showcase

A comprehensive example demonstrating all Clockwork connection types in a realistic microservices architecture.

## Overview

This example shows how to use each connection type to build a full-stack application with:
- PostgreSQL database with schema initialization
- Redis cache for session storage
- API server connected to database and cache
- Frontend service with service mesh discovery
- Shared configuration files and data volumes

## Connection Types Demonstrated

### 1. DependencyConnection

**What it does**: Establishes simple deployment ordering between resources without creating any setup infrastructure.

**When to use**: When you just need to ensure one resource deploys before another, but don't need any configuration sharing or networking.

**Example in this showcase**:
```python
frontend.connect(redis)  # Shorthand syntax
# Or explicitly:
frontend.connect(DependencyConnection(to_resource=redis))
```

**Benefits**:
- Automatic deployment ordering
- No manual dependency management
- Cleanest syntax for simple dependencies

### 2. DatabaseConnection

**What it does**:
- Generates database connection strings
- Waits for database to be ready
- Executes SQL schema files
- Runs migration scripts
- Injects connection strings into environment variables

**When to use**: When connecting an application to a database. Handles all the complexity of database initialization and connection configuration.

**Example in this showcase**:
```python
api.connect(DatabaseConnection(
    to_resource=postgres,
    connection_string_template="postgresql://{user}:{password}@{host}:{port}/{database}",
    username="postgres",
    password="secret123",  # pragma: allowlist secret
    database_name="appdb",
    schema_file="./schema.sql",
    wait_for_ready=True,
    timeout=30
))
```

**Benefits over manual configuration**:
- No manual connection string construction
- Automatic database readiness checks
- Schema execution on first deployment
- Support for migrations
- Environment variables injected automatically

**Result**: `api.env_vars["DATABASE_URL"]` is automatically set to `"postgresql://postgres:secret123@postgres:5432/appdb"`  <!-- pragma: allowlist secret -->

### 3. NetworkConnection

**What it does**:
- Creates Docker networks
- Connects containers to networks
- Enables DNS-based service discovery
- Injects hostname environment variables

**When to use**: When you need containers to communicate using service names (DNS) instead of IP addresses. Essential for multi-container applications.

**Example in this showcase**:
```python
api.connect(NetworkConnection(
    to_resource=redis,
    network_name="backend-network",
    driver="bridge",
    internal=False
))
```

**Benefits over manual configuration**:
- No manual network creation commands
- Automatic container attachment
- Service discovery environment variables injected
- Supports advanced network configurations (subnets, gateways)

**Result**:
- Creates "backend-network" Docker network
- Connects both `api` and `redis` to the network
- Injects `REDIS_HOST=redis` into api's environment
- API can now reach Redis at `redis:6379`

### 4. FileConnection

**What it does**:
- Mounts files and directories into containers
- Creates and manages Docker volumes
- Shares FileResource outputs with containers
- Supports read-only and read-write mounts

**When to use**:
- Sharing configuration files with containers
- Persistent data storage with volumes
- Sharing data between multiple containers

**Example 1 - Config file mount**:
```python
config_file = FileResource(
    name="api-config",
    path="./config.json",
    content='{"log_level": "info"}'
)

api.connect(FileConnection(
    to_resource=config_file,
    mount_path="/etc/app/config.json",
    read_only=True
))
```

**Example 2 - Shared volume**:
```python
api.connect(FileConnection(
    to_resource=storage,
    mount_path="/data/shared",
    volume_name="app-shared-data",
    create_volume=True
))
```

**Benefits over manual configuration**:
- No manual volume creation
- Automatic mount point configuration
- FileResource integration
- AI can determine mount paths if you provide descriptions

**Result**:
- Config file mounted at `/etc/app/config.json` (read-only)
- Shared volume mounted at `/data/shared` in both containers

### 5. ServiceMeshConnection

**What it does**:
- Discovers service ports automatically
- Generates service URLs
- Injects service URLs into environment variables
- Adds health check assertions
- Supports TLS configuration

**When to use**: When services need to discover and communicate with each other in a microservices architecture.

**Example in this showcase**:
```python
frontend.connect(ServiceMeshConnection(
    to_resource=api,
    protocol="http",
    health_check_path="/health",
    load_balancing="round_robin"
))
```

**Benefits over manual configuration**:
- Automatic port discovery from target service
- Service URL generation and injection
- Built-in health checking
- TLS certificate generation (if enabled)
- No hardcoded service locations

**Result**:
- Discovers port 8000 from `api.ports`
- Injects `API_URL=http://api:8000` into frontend's environment
- Adds health check assertion for `http://api:8000/health`

## How AI Completion Works

Connections support AI completion when you provide a `description` field but leave certain fields empty:

### DatabaseConnection with AI:
```python
# Manual (no AI):
DatabaseConnection(
    to_resource=postgres,
    connection_string_template="postgresql://{user}:{password}@{host}:{port}/{database}",
    username="postgres",
    password="secret123", # pragma: allowlist secret
    database_name="appdb"
)

# With AI completion:
DatabaseConnection(
    to_resource=postgres,
    description="Connect to PostgreSQL database for user data"
)
# AI fills in: connection_string_template, username, password, database_name
```

### NetworkConnection with AI:
```python
# Manual (no AI):
NetworkConnection(
    to_resource=redis,
    network_name="backend-network",
    driver="bridge"
)

# With AI completion:
NetworkConnection(
    to_resource=redis,
    description="backend network for API and cache communication"
)
# AI fills in: network_name, driver
```

### FileConnection with AI:
```python
# Manual (no AI):
FileConnection(
    to_resource=storage,
    mount_path="/data/uploads",
    volume_name="user-uploads",
    create_volume=True
)

# With AI completion:
FileConnection(
    to_resource=storage,
    description="shared volume for user file uploads"
)
# AI fills in: mount_path, volume_name
```

## Architecture

```
┌─────────────┐
│  Frontend   │ :80
│   (nginx)   │
└──────┬──────┘
       │
       │ ServiceMeshConnection
       │ (API_URL=http://api:8000)
       ├────────────────────┐
       │                    │
       ▼                    ▼
┌──────────────┐     ┌──────────┐
│   API Server │ :8000│  Redis   │ :6379
│   (nginx)    │─────▶│ (cache)  │
└──────┬───────┘     └──────────┘
       │              NetworkConnection
       │              (backend-network)
       │
       │ DatabaseConnection
       │ (DATABASE_URL=postgresql://...)
       │
       ▼
┌──────────────┐
│  PostgreSQL  │ :5432
│  (database)  │
└──────────────┘

FileConnections:
- config.json → api:/etc/app/config.json (read-only)
- app-shared-data volume → api:/data/shared, storage:/data/shared
```

## Deployment Order

Clockwork automatically determines deployment order based on connections:

1. **postgres** (no dependencies)
2. **redis** (no dependencies)
3. **config_file** (no dependencies)
4. **storage** (no dependencies)
5. **api** (depends on: postgres, redis, config_file, storage)
6. **frontend** (depends on: api, redis)

## Environment Variables

Automatically injected by connections:

**API Server** (`api`):
- `DATABASE_URL=postgresql://postgres:secret123@postgres:5432/appdb` (DatabaseConnection) <!-- pragma: allowlist secret -->
- `REDIS_HOST=redis` (NetworkConnection)

**Frontend** (`frontend`):
- `API_URL=http://api:8000` (ServiceMeshConnection)

## Usage

### Deploy the infrastructure:
```bash
cd examples/connections-showcase
clockwork apply
```

### Verify all connections are working:
```bash
clockwork assert
```

### Check the generated environment variables:
```bash
docker inspect api | grep -A 10 Env
docker inspect frontend | grep -A 10 Env
```

### Test the network connectivity:
```bash
# Test Redis connectivity from API
docker exec api ping -c 3 redis

# Test database connectivity
docker exec api nc -zv postgres 5432

# Test API connectivity from frontend
docker exec frontend nc -zv api 8000
```

### Check the mounted config file:
```bash
docker exec api cat /etc/app/config.json
```

### Check the shared volume:
```bash
# Write to shared volume from API
docker exec api sh -c 'echo "test data" > /data/shared/test.txt'

# Read from shared volume in storage container
docker exec storage cat /data/shared/test.txt
```

### Clean up:
```bash
clockwork destroy
```

## Key Takeaways

1. **Connections are first-class components** - They can be AI-completed, have their own setup resources, and run assertions

2. **Each connection type has a specific purpose**:
   - DependencyConnection: Simple ordering
   - DatabaseConnection: Database setup and configuration
   - NetworkConnection: Container networking
   - FileConnection: File and volume sharing
   - ServiceMeshConnection: Service discovery

3. **Connections reduce boilerplate**:
   - No manual connection strings
   - No manual network creation
   - No manual volume management
   - No manual service discovery

4. **AI completion makes connections smarter**:
   - Provide a description, get proper configuration
   - Context from both endpoints informs completion
   - Less manual configuration needed

5. **Connections compose naturally**:
   - One resource can have multiple connections
   - Connections can use different types
   - Deployment order is automatic

## Next Steps

Try modifying this example:
- Add a migration directory to DatabaseConnection
- Create an internal network with `internal=True`
- Add TLS to ServiceMeshConnection with `tls_enabled=True`
- Use AI completion by replacing explicit fields with descriptions
- Add more services and connections to build a larger system
