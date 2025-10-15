# Clockwork Roadmap

## Completed Features

### `clockwork assert` Command ✅

**Completed:** October 6, 2024

Verification command to ensure resources are running as specified through type-safe assertions.

**Purpose:**

- Validates that deployed resources match their desired state
- Returns success/failure status
- Can be run manually or integrated into CI/CD pipelines
- Foundation for the reconciliation service
- Supports type-safe built-in assertion classes

**Use Cases:**

- Post-deployment validation
- Health checks in CI/CD
- Manual verification of infrastructure state
- Debugging and troubleshooting

**Implementation Details:**

Clockwork uses a **type-safe assertion system** with built-in assertion classes:

1. **Built-in Assertion Classes** (type-safe, no AI required):
   - `HealthcheckAssert(url)` - HTTP health endpoint validation
   - `PortAccessibleAssert(port)` - Network port accessibility checks
   - `ContainerRunningAssert()` - Container status verification
   - `FileExistsAssert(path)` - File presence validation
   - `ResponseTimeAssert(url, max_ms)` - Performance validation
   - And many more (see CLAUDE.md for full list)

2. **Direct Execution**:
   - Assertions execute directly on resources
   - Independent of deployment mechanism
   - Idempotent and reliable verification

**Example Usage:**

```python
from clockwork.resources import AppleContainerResource
from clockwork.assertions import HealthcheckAssert, ContainerRunningAssert, PortAccessibleAssert

nginx = AppleContainerResource(
    name="nginx-web",
    description="Web server",
    ports=["8080:80", "8443:443"],
    assertions=[
        # Type-safe built-in assertions
        HealthcheckAssert(url="http://localhost:8080/health"),
        ContainerRunningAssert(),
        PortAccessibleAssert(port=8080),
        PortAccessibleAssert(port=8443),
        ResponseTimeAssert(url="http://localhost:8080", max_ms=200),
    ]
)
```

```bash
# Run assertions from project directory
cd my-project
clockwork assert
# Output: ✓ All assertions passed
#         ✓ nginx-web: HealthcheckAssert (http://localhost:8080/health)
#         ✓ nginx-web: ContainerRunningAssert
#         ✓ nginx-web: PortAccessibleAssert (port 8080)
#         ✓ nginx-web: PortAccessibleAssert (port 8443)
#         ✓ nginx-web: ResponseTimeAssert (< 200ms)
```

---

## Upcoming Features

### 1. Reconciliation Service

Background daemon that continuously monitors and maintains desired state.

**Purpose:**

- Periodically runs `assert` to detect drift
- Automatically corrects configuration drift
- Enforces time-based policies (e.g., "run for 2 hours only")
- Sends alerts on failures or drift detection

**Features:**

- Configurable evaluation intervals
- Automatic remediation
- Duration limits for resources
- Alerting and notifications (Slack, email, webhooks)
- Graceful degradation on failures

**Use Cases:**

- Production infrastructure monitoring
- Auto-healing services
- Temporary resource management (dev environments)
- Cost control via time-limited resources

**Example Configuration:**

```python
from clockwork.resources import AppleContainerResource

nginx = AppleContainerResource(
    name="nginx",
    description="Web server",
    reconcile=True,              # Enable reconciliation
    check_interval=60,           # Check every 60 seconds
    max_duration="2h",           # Auto-destroy after 2 hours
    on_drift="auto_correct",     # Auto-fix drift
    alert_on=["drift", "failure"]  # Send alerts
)
```

---

### 2. Stateful Service Evolution

Transform Clockwork from one-time deployments to long-lived project management.

**Purpose:**

- Track deployed services as evolving projects, not just one-time tasks
- Intelligently update existing infrastructure based on vague/partial specifications
- Maintain context of previous deployments to infer correct updates
- Automatically validate changes don't break existing functionality

**Features:**

- State tracking of deployed resources (schemas, configs, endpoints)
- Vague update support: "add new schema" interprets intent vs. exact specification
- Smart diff and merge: update only what changed, preserve what works
- Automatic evaluation parameter generation for new features
- Version history and rollback capabilities

**Use Cases:**

- Evolving database schemas without rewriting full definitions
- Adding/modifying API endpoints with natural language descriptions
- Updating service configurations while preserving working state
- Incremental feature additions to deployed applications

**Key Difference from `clockwork apply`:**

The `clockwork update` command allows vague, intent-based specifications without needing the original `main.py`:

- **`clockwork apply`**: Requires complete, exact resource definitions in `main.py`
- **`clockwork update`**: Accepts partial, vague specifications in `update.py` and infers changes

This is crucial when you vaguely remember what was deployed but don't have access to the original `main.py` file or exact specifications.

**Example Workflow:**

```python
# Initial deployment in main.py
api_app = AppleContainerResource(
    name="api-service",
    description="REST API with user schema",
    # ... complete initial config
)

# Later: update.py (vague specification - no need to remember exact main.py details)
api_app = AppleContainerResource(
    name="api-service",
    description="Add organization schema and update user endpoints",
    # Clockwork infers: keep existing user schema, add org schema,
    # modify related endpoints, add new evaluation checks
)
```

```bash
# Initial deployment
cd my-api-project
clockwork apply

# Later: apply updates with new clockwork update command
# Looks for update.py and intelligently merges with deployed state
# No need to have the original main.py or remember exact details!
clockwork update
# Output: ✓ Detected existing deployment: api-service
#         ✓ Inferred current state from deployed resources
#         ✓ Added organization schema
#         ✓ Updated /api/users endpoint to include org_id
#         ✓ Created /api/organizations endpoints
#         ✓ Evaluation checks updated
#         ✓ All tests passing
```

**Implementation Considerations:**

- New `clockwork update` command that looks for `update.py`
- Diff engine to compare current deployment with update specifications
- AI-powered intent inference from vague specifications
- Validation that updates don't break existing functionality
- Integration with `clockwork assert` for continuous verification

---

## Future Enhancements

These enhancements will be considered after core features are implemented.

### 3. Cross-Resource Assertions

Validate interactions and dependencies between multiple resources.

**Purpose:**

- Verify that resources can communicate with each other
- Ensure dependencies are properly configured
- Test end-to-end workflows across services
- Validate data consistency across distributed systems

**Features:**

- Multi-resource assertion definitions
- Relationship-based validation (e.g., "service A can connect to database B")
- Dependency graph verification
- Integration testing capabilities
- Transaction-based consistency checks

**Use Cases:**

- Microservice communication validation
- Database replication verification
- Load balancer → backend connectivity
- Message queue → consumer relationships
- Multi-tier application health checks

**Example:**

```python
from clockwork.resources import AppleContainerResource
from clockwork.assertions import CrossResourceAssert, ServiceConnectivityAssert

api = AppleContainerResource(
    name="api-service",
    description="REST API",
    ports=["8080:8080"]
)

database = AppleContainerResource(
    name="postgres-db",
    description="PostgreSQL database",
    ports=["5432:5432"]
)

# Cross-resource assertion
connectivity = CrossResourceAssert(
    source=api,
    target=database,
    assertion="API can successfully query the database and retrieve user records"
)

# Or use built-in connectivity check
connectivity = ServiceConnectivityAssert(
    from_service=api,
    to_service=database,
    protocol="postgresql",
    timeout=5
)
```

**Implementation Considerations:**

- Resource dependency graph construction
- Context passing between resources during assertion execution
- Network isolation handling for containerized services
- Assertion ordering based on dependencies
- Failure isolation to identify which relationship failed

---

### 4. Python-Based Assertions

Support programmatic assertions using Python callable functions.

**Purpose:**

- Enable complex validation logic beyond natural language
- Allow developers to write custom assertion code
- Support assertions that require external libraries or APIs
- Provide debugging and inspection capabilities

**Features:**

- Python function decorators for assertion definition
- Access to resource metadata and state
- Support for external dependencies (requests, psycopg2, etc.)
- Rich return values (pass/fail + detailed diagnostics)
- IDE autocomplete and type checking

**Use Cases:**

- Complex data validation requiring parsing/transformation
- Third-party API integration checks
- Custom business logic validation
- Performance benchmarking and profiling
- Advanced security scanning

**Example:**

```python
from clockwork.resources import AppleContainerResource
from clockwork.assertions import PythonAssert
import requests
import json

nginx = AppleContainerResource(
    name="nginx-web",
    description="Web server",
    ports=["8080:80"]
)

@PythonAssert(resource=nginx)
def validate_api_response(resource):
    """Check that API returns valid JSON with expected schema."""
    response = requests.get(f"http://localhost:8080/api/health")

    if response.status_code != 200:
        return False, f"Expected status 200, got {response.status_code}"

    try:
        data = response.json()
    except json.JSONDecodeError:
        return False, "Response is not valid JSON"

    required_fields = ["status", "version", "uptime"]
    missing = [f for f in required_fields if f not in data]

    if missing:
        return False, f"Missing required fields: {missing}"

    return True, f"API health check passed: {data['status']}"

# Alternative: inline lambda for simple checks
nginx.assertions.append(
    PythonAssert(
        lambda r: (True, "Pass") if os.path.exists("/var/log/nginx/access.log") else (False, "Log file missing")
    )
)
```

**Implementation Considerations:**

- Sandboxing and security for user-provided code
- Dependency management for custom assertions
- Error handling and exception propagation
- Performance impact of complex Python assertions
- Serialization for caching (pickle/dill)

---

### 5. Additional Built-in Assertions

Expand the library of type-safe assertion classes for common scenarios.

**Purpose:**

- Reduce reliance on AI for common validation tasks
- Provide performant, deterministic assertions
- Cover standard infrastructure patterns
- Improve IDE support and discoverability

**Planned Assertion Classes:**

**Database Assertions:**
- `DatabaseConnectionAssert(host, port, database, credentials)` - Connection validation
- `TableExistsAssert(table_name)` - Schema verification
- `RowCountAssert(table, min, max)` - Data presence validation
- `QuerySuccessAssert(sql_query)` - Custom query execution

**Network Assertions:**
- `DNSResolveAssert(hostname, expected_ip)` - DNS resolution validation
- `SSLCertificateAssert(url, min_days_valid)` - Certificate validation
- `ResponseTimeAssert(url, max_ms)` - Performance validation
- `HTTPStatusAssert(url, expected_status)` - Endpoint validation

**Security Assertions:**
- `NoOpenPortsAssert(except_ports)` - Security scanning
- `FilePermissionsAssert(path, expected_perms)` - Permission validation
- `SecretsPresentAssert(env_vars)` - Configuration validation
- `VulnerabilityScanAssert()` - Container/package scanning

**File System Assertions:**
- `DirectoryExistsAssert(path)` - Directory presence
- `FileContentMatchesAssert(path, regex)` - Content validation
- `DiskSpaceAssert(path, min_gb_free)` - Storage validation
- `FileModifiedWithinAssert(path, max_age)` - Freshness validation

**Example:**

```python
from clockwork.resources import AppleContainerResource
from clockwork.assertions import (
    DatabaseConnectionAssert,
    TableExistsAssert,
    ResponseTimeAssert,
    SSLCertificateAssert,
    NoOpenPortsAssert
)

postgres = AppleContainerResource(
    name="postgres-db",
    description="PostgreSQL database",
    ports=["5432:5432"],
    assertions=[
        DatabaseConnectionAssert(
            host="localhost",
            port=5432,
            database="myapp",
            credentials={"user": "admin", "password_env": "DB_PASSWORD"}
        ),
        TableExistsAssert(table="users"),
        TableExistsAssert(table="orders"),
        RowCountAssert(table="users", min=1),
    ]
)

nginx = AppleContainerResource(
    name="nginx-web",
    description="Web server",
    ports=["8080:80", "8443:443"],
    assertions=[
        ResponseTimeAssert(url="http://localhost:8080", max_ms=200),
        SSLCertificateAssert(url="https://localhost:8443", min_days_valid=30),
        HTTPStatusAssert(url="http://localhost:8080/health", expected_status=200),
        NoOpenPortsAssert(except_ports=[8080, 8443, 22]),
    ]
)
```

**Implementation Considerations:**

- Consistent API design across assertion classes
- Dependency management (e.g., psycopg2 for database assertions)
- Error messages and debugging information
- Cross-platform compatibility
- Performance optimization for frequently-run assertions

---

## Contributing

Have ideas for the roadmap? Open an issue or submit a pull request!
