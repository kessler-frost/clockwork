# Connected Services Example

Full-stack application demonstrating Clockwork's `DatabaseConnection` feature for automatic database configuration and intelligent dependency management.

## What it demonstrates

DatabaseConnection provides powerful capabilities for database integration:

1. **Automatic connection string generation** - No manual URL construction required
2. **Environment variable injection** - Automatically injects DATABASE_URL into your services
3. **Database readiness checking** - Waits for database to be healthy before deploying dependent services
4. **Schema file execution** - Optional automatic schema setup on deployment
5. **Migrations support** - Optional automatic migrations from a directory
6. **Type-safe configuration** - Pydantic validation for all connection parameters

## Architecture

This example deploys a realistic full-stack application with four services:

```
Layer 1 (Independent):
├── postgres-db      (PostgreSQL database)
└── redis-cache      (Redis cache/queue)

Layer 2 (Connected):
├── api-server       (FastAPI backend - connected to postgres + redis)
└── worker-service   (Background worker - connected to redis)
```

## How it works

### 1. Database Connection with DatabaseConnection

Instead of manually constructing connection strings, use `DatabaseConnection`:

```python
# Independent database resource (deploy first)
postgres = DockerResource(
    description="PostgreSQL database",
    name="postgres-db",
    image="postgres:15-alpine",
    ports=["5432:5432"],
    env_vars={
        "POSTGRES_DB": "appdb",
        "POSTGRES_USER": "admin",
        "POSTGRES_PASSWORD": "secret123"  # pragma: allowlist secret
    }
)

# API server resource
api = DockerResource(
    description="FastAPI backend server",
    name="api-server",
    ports=["8000:80"]
)

# Connect using DatabaseConnection for automatic configuration
api.connect(
    DatabaseConnection(
        to_resource=postgres,
        connection_string_template="postgresql://{user}:{password}@{host}:{port}/{database}",
        username="admin",
        password="secret123",  # pragma: allowlist secret
        database_name="appdb",
        env_var_name="DATABASE_URL",
        wait_for_ready=True,
        timeout=30
    )
)
```

### 2. Automatic Configuration

DatabaseConnection automatically:

1. **Extracts connection info** from the postgres resource (host=postgres-db, port=5432)
2. **Builds connection string**: `postgresql://admin:secret123@postgres-db:5432/appdb` <!-- pragma: allowlist secret -->
3. **Injects into environment**: Adds `DATABASE_URL` to api's env_vars
4. **Waits for readiness**: Runs `pg_isready` before deploying api
5. **Manages dependencies**: Ensures postgres deploys before api

Result - api container gets this environment variable automatically:
```bash
DATABASE_URL=postgresql://admin:secret123@postgres-db:5432/appdb  # pragma: allowlist secret
```

### 3. Optional Schema and Migrations

DatabaseConnection supports schema files and migrations:

```python
api.connect(
    DatabaseConnection(
        to_resource=postgres,
        connection_string_template="postgresql://{user}:{password}@{host}:{port}/{database}",
        username="admin",
        password="secret123",  # pragma: allowlist secret
        database_name="appdb",
        # Execute schema file on deployment
        schema_file="schema.sql",
        # Run migrations from directory
        migrations_dir="migrations/"
    )
)
```

This will:
1. Wait for postgres to be ready (pg_isready)
2. Execute `schema.sql` using psql
3. Execute all `.sql` files in `migrations/` directory (sorted order)
4. Then deploy the api service with DATABASE_URL injected

### 4. Deployment Order

Clockwork automatically determines deployment order based on connections:

```
1. postgres-db      (no dependencies - deploys first)
2. redis-cache      (no dependencies - deploys first)
3. Wait for postgres readiness (pg_isready check)
4. Execute schema.sql (if provided)
5. Execute migrations (if provided)
6. api-server       (depends on postgres via DatabaseConnection + redis - deploys after)
7. worker-service   (depends on redis - deploys after)
```

## Prerequisites

- Docker installed and running
- Docker daemon accessible from command line
- Network access to pull container images

## Run the example

```bash
# Navigate to example directory
cd examples/connected-services

# Deploy all services (respects connection order)
clockwork apply

# Verify deployment with assertions
clockwork assert

# Test the services
curl http://localhost:8000/health  # API health check
docker logs api-server             # Check API logs for database connection
docker logs worker-service         # Check worker logs for Redis connection

# Inspect generated environment variables
docker inspect api-server | jq '.[0].Config.Env'

# Clean up
clockwork destroy
```

## DatabaseConnection vs Simple Connection

This example shows both approaches:

### DatabaseConnection (for databases)
```python
# Full-featured database connection with automatic configuration
api.connect(
    DatabaseConnection(
        to_resource=postgres,
        connection_string_template="postgresql://{user}:{password}@{host}:{port}/{database}",
        username="admin",
        password="secret123",  # pragma: allowlist secret
        database_name="appdb",
        env_var_name="DATABASE_URL",
        wait_for_ready=True,
        schema_file="schema.sql",  # Optional
        migrations_dir="migrations/"  # Optional
    )
)
```

**Benefits:**
- Automatic connection string generation
- DATABASE_URL injection
- Database readiness checking
- Schema/migration execution
- Type-safe configuration

### Simple Connection (for other services)
```python
# Simple dependency connection (AI may generate config)
api.connect(redis)
```

**Benefits:**
- Simpler syntax for non-database connections
- AI can still generate REDIS_URL based on context
- Dependency ordering still enforced

## Verification

After running `clockwork apply`, check:

1. **DATABASE_URL injection** - Verify the environment variable was automatically added
2. **Database readiness** - Confirm pg_isready check ran successfully
3. **Deployment order** - postgres and redis start before api and worker
4. **Network connectivity** - All containers on the same Docker network
5. **Assertions pass** - All health checks and port accessibility tests succeed

```bash
# Check DATABASE_URL was injected
docker exec api-server env | grep DATABASE_URL
# Expected output: DATABASE_URL=postgresql://admin:secret123@postgres-db:5432/appdb  # pragma: allowlist secret

# Check all environment variables
docker exec api-server env | grep -E "(DATABASE|REDIS)"

# Check deployment order from docker logs
docker ps --format "table {{.Names}}\t{{.CreatedAt}}"

# Check network connectivity
docker network inspect app_network

# Run assertions
clockwork assert

# Test database connection (requires psql in api container)
docker exec api-server env | grep DATABASE_URL | cut -d= -f2 | xargs -I {} psql {} -c "SELECT version();"
```

## Key benefits demonstrated

1. **Zero boilerplate** - No manual connection string construction or environment variable management
2. **Automatic configuration** - DatabaseConnection handles URL generation and injection
3. **Database readiness** - Built-in pg_isready checks ensure database is healthy
4. **Schema/migration support** - Optional automatic schema setup and migrations
5. **Type-safe connections** - Pydantic validation ensures all parameters are correct
6. **Declarative dependencies** - Deployment order automatically determined
7. **Hybrid approach** - Use DatabaseConnection for databases, simple connections for other services

## Extending the example

### Add schema file support

Create a `schema.sql` file:
```sql
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    token VARCHAR(255) NOT NULL,
    expires_at TIMESTAMP NOT NULL
);
```

Update the connection:
```python
api.connect(
    DatabaseConnection(
        to_resource=postgres,
        connection_string_template="postgresql://{user}:{password}@{host}:{port}/{database}",
        username="admin",
        password="secret123",  # pragma: allowlist secret
        database_name="appdb",
        schema_file="schema.sql"  # Now will execute on deployment
    )
)
```

### Add migrations support

Create a `migrations/` directory with versioned files:
```
migrations/
├── 001_add_users_table.sql
├── 002_add_sessions_table.sql
└── 003_add_indexes.sql
```

Update the connection:
```python
api.connect(
    DatabaseConnection(
        to_resource=postgres,
        connection_string_template="postgresql://{user}:{password}@{host}:{port}/{database}",
        username="admin",
        password="secret123",  # pragma: allowlist secret
        database_name="appdb",
        schema_file="schema.sql",
        migrations_dir="migrations/"  # Executes all .sql files in sorted order
    )
)
```

### Add more database connections

Connect multiple services to the same database:
```python
admin_panel = DockerResource(
    description="Admin panel",
    name="admin-panel",
    ports=["8001:80"]
)

admin_panel.connect(
    DatabaseConnection(
        to_resource=postgres,
        connection_string_template="postgresql://{user}:{password}@{host}:{port}/{database}",
        username="admin",
        password="secret123",  # pragma: allowlist secret
        database_name="appdb",
        env_var_name="DATABASE_URL"  # Same database, different service
    )
)
```

## Cleanup

```bash
# Remove all services and clean up
clockwork destroy

# This will:
# 1. Remove containers in reverse order (worker, api, redis, postgres)
# 2. Remove volumes (postgres_data, redis_data)
# 3. Remove networks (app_network)
```

## Commands

```bash
# Deploy resources (respects connection order)
clockwork apply

# Run assertions (validates all services)
clockwork assert

# Destroy resources
clockwork destroy
```

## Troubleshooting

**Issue**: DATABASE_URL not injected into container
- Verify DatabaseConnection was created before `clockwork apply`
- Check that `to_resource` points to the correct database resource
- Confirm connection_string_template has correct placeholders

**Issue**: Database readiness check fails
- Ensure postgres container is healthy: `docker ps`
- Verify pg_isready is available in the system (requires postgresql-client)
- Check timeout value is sufficient for database startup
- Increase timeout: `wait_for_ready=True, timeout=60`

**Issue**: Schema file not executed
- Verify schema_file path is correct and file exists
- Check psql is available in the system
- Look for errors in Pulumi output during deployment
- Ensure connection string has correct permissions

**Issue**: Migrations not running
- Verify migrations_dir exists and contains .sql files
- Check file naming follows convention (001_*.sql, 002_*.sql, etc.)
- Ensure migrations have correct SQL syntax
- Review Pulumi logs for migration errors

**Issue**: API or worker can't connect to database
- Check DATABASE_URL value: `docker exec api-server env | grep DATABASE_URL`
- Verify postgres and redis are running: `docker ps`
- Check connection URLs use container names, not localhost
- Confirm all containers are on the same network: `docker network inspect app_network`
