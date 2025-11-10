# Connection Types Quick Reference

## When to Use Each Connection Type

| Connection Type | Use Case | Creates | Injects Env Vars |
|----------------|----------|---------|------------------|
| **DependencyConnection** | Simple deployment ordering | Nothing | No |
| **DatabaseConnection** | Connect to database | Schema setup commands | DATABASE_URL |
| **NetworkConnection** | Container networking | Docker network | SERVICE_HOST |
| **FileConnection** | File/volume sharing | Docker volumes | No |
| **ServiceMeshConnection** | Service discovery | Health checks | SERVICE_URL |

## Quick Examples

### DependencyConnection
```python
# Ensure database deploys before API
api.connect(db)  # Auto-creates DependencyConnection
```

### DatabaseConnection
```python
api.connect(DatabaseConnection(
    to_resource=postgres,
    connection_string_template="postgresql://{user}:{password}@{host}:{port}/{database}",
    username="postgres",
    password="secret",  # pragma: allowlist secret
    database_name="myapp"
))
# Result: api.env_vars["DATABASE_URL"] = "postgresql://postgres:secret@postgres:5432/myapp"
```

### NetworkConnection
```python
api.connect(NetworkConnection(
    to_resource=redis,
    network_name="backend"
))
# Result: Creates "backend" network, injects REDIS_HOST=redis
```

### FileConnection
```python
# Mount config file
api.connect(FileConnection(
    to_resource=config_file,
    mount_path="/app/config.json",
    read_only=True
))

# Share volume
api.connect(FileConnection(
    to_resource=storage,
    mount_path="/data",
    volume_name="shared-data"
))
```

### ServiceMeshConnection
```python
frontend.connect(ServiceMeshConnection(
    to_resource=api,
    protocol="http",
    health_check_path="/health"
))
# Result: frontend.env_vars["API_URL"] = "http://api:8000"
```

## AI Completion

Add `description` field and remove explicit fields to let AI complete them:

```python
# Without AI - explicit configuration
NetworkConnection(
    to_resource=redis,
    network_name="backend-network",
    driver="bridge"
)

# With AI - provide description only
NetworkConnection(
    to_resource=redis,
    description="backend network for API and cache"
)
# AI generates: network_name, driver
```

## Common Patterns

### Microservices Stack
```python
# Data layer
postgres = DockerResource(name="db", image="postgres:15")
redis = DockerResource(name="cache", image="redis:7")

# API layer
api = DockerResource(name="api", image="myapi:latest")
api.connect(DatabaseConnection(to_resource=postgres, ...))
api.connect(NetworkConnection(to_resource=redis, ...))

# Frontend layer
web = DockerResource(name="web", image="nginx:alpine")
web.connect(ServiceMeshConnection(to_resource=api, ...))
```

### Config + Secrets
```python
config = FileResource(name="config", path="./config.json")
secrets = FileResource(name="secrets", path="./secrets.env")

app.connect(FileConnection(to_resource=config, mount_path="/app/config.json"))
app.connect(FileConnection(to_resource=secrets, mount_path="/app/.env", read_only=True))
```

### Multi-Database Setup
```python
# Primary database
app.connect(DatabaseConnection(
    to_resource=postgres,
    env_var_name="PRIMARY_DATABASE_URL",
    ...
))

# Analytics database
app.connect(DatabaseConnection(
    to_resource=analytics_db,
    env_var_name="ANALYTICS_DATABASE_URL",
    ...
))
```

## Troubleshooting

### Connection not working?
```bash
# Check deployment order
clockwork graph

# Verify environment variables
docker inspect <container> | grep -A 20 Env

# Test network connectivity
docker exec <container> ping <target>

# Check assertions
clockwork assert
```

### Common Issues

1. **Port not accessible**: Ensure both containers are on same network
   ```python
   NetworkConnection(to_resource=target, network_name="shared-net")
   ```

2. **Database connection fails**: Check wait_for_ready is enabled
   ```python
   DatabaseConnection(..., wait_for_ready=True, timeout=30)
   ```

3. **File not found**: Verify path exists before deployment
   ```python
   config = FileResource(path="./config.json")  # Must exist in current dir
   ```

4. **Service discovery fails**: Use ServiceMeshConnection for URL injection
   ```python
   ServiceMeshConnection(to_resource=api, protocol="http")
   ```
