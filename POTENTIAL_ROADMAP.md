# Clockwork - Potential Roadmap

_This is a living document of potential features and enhancements. Updated frequently as priorities and ideas evolve._

---

## ✅ Implemented Features

### Core Primitives & CLI Commands
- **Primitive Types**: FileResource, TemplateFileResource, DockerResource, AppleContainerResource, GitRepoResource
- **CLI Commands**:
  - `clockwork apply` - Deploy primitives
  - `clockwork plan` - Preview without deploying
  - `clockwork destroy` - Remove deployed infrastructure
  - `clockwork assert` - Validate deployed primitives
  - `clockwork service start/stop/status` - Basic service management
  - `clockwork version` - Show version

### AI Completion & Flexibility
- **Adjustable Intelligence**: Choose per-primitive control level
  - Full control (specify everything, no AI)
  - Hybrid mode (specify key details, AI fills gaps)
  - Fast mode (describe requirements, AI handles implementation)
- **PydanticAI Integration**: Structured outputs with Pydantic validation
- **Tool Support**: Web search (DuckDuckGo), custom Python tools
- **MCP Server Support**: Filesystem, databases, GitHub, Google Drive

### Resource Connections
- **Dependency Declarations**: Connect primitives to express dependencies
- **Topological Sorting**: Automatic deployment ordering (O(V+E))
- **Cycle Detection**: Prevents circular dependencies
- **AI Context Sharing**: Connected primitives share configuration data for intelligent completion

### Type-Safe Assertions
Built-in assertion classes (no AI required):

**HTTP/Network:**
- `HealthcheckAssert(url, expected_status, timeout_seconds)` - HTTP health checks
- `PortAccessibleAssert(port, host, protocol)` - Port accessibility validation

**Container:**
- `ContainerRunningAssert(timeout_seconds)` - Container status verification

**File:**
- `FileExistsAssert(path)` - File presence validation
- `FileContentMatchesAssert(path, pattern)` - Content validation with regex

**Example:**
```python
nginx = DockerResource(
    name="nginx-web",
    description="Web server",
    ports=["8080:80"],
    assertions=[
        ContainerRunningAssert(timeout_seconds=10),
        PortAccessibleAssert(port=8080, host="localhost", protocol="tcp"),
        HealthcheckAssert(url="http://localhost:8080", expected_status=200, timeout_seconds=5),
    ]
)
```

```bash
clockwork assert  # Validates all deployed primitives
```

### Basic Service Infrastructure
- Simple FastAPI health check endpoint on port 8765
- Basic project registration
- Service lifecycle management (start/stop/status)
- **Note**: Does not yet perform active monitoring, drift detection, or remediation

---

## 🤔 Under Consideration

### 1. Enhanced Reconciliation Service with AI Remediation

**Current State**: Basic service exists but doesn't actively monitor or remediate.

**Potential Enhancements**:

**Continuous Monitoring & Drift Detection:**
- Periodically run assertions to detect drift
- Configurable check intervals per primitive or project
- Multi-project monitoring support

**AI-Powered Intelligent Remediation:**
- **Diagnostic Collection**: Gather logs, errors, resource state when assertions fail
- **Root Cause Analysis**: Use AI to analyze diagnostic data and identify issues
- **Remediation Strategy Generation**: AI proposes fixes based on:
  - Primitive description and intended behavior
  - Connection context and dependencies
  - Historical failure patterns
  - Available corrective actions
- **Automated Fix Execution**: Apply remediation with validation
- **Learning**: Improve remediation strategies over time

**Additional Features:**
- **Automatic Drift Correction**: Re-apply primitives when assertions fail
- **Time-Based Policies**: Auto-destroy resources after duration limits (cost control)
- **Alerting & Notifications**: Slack, email, webhooks for drift/failures
- **Graceful Degradation**: Handle partial failures intelligently

**Example Configuration:**
```python
nginx = DockerResource(
    name="nginx",
    description="Web server",
    reconcile=True,                    # Enable reconciliation
    check_interval=60,                 # Check every 60 seconds
    max_duration="2h",                 # Auto-destroy after 2 hours
    on_drift="auto_correct",           # Re-apply when drift detected
    on_failure="remediate_ai",         # Use AI for complex failures
    remediation_context={              # Additional context for AI
        "critical": True,
        "max_downtime": "30s",
        "fallback_strategy": "rollback"
    },
    alert_on=["drift", "failure", "remediation_attempt"]
)
```

**Remediation Flow:**
```
1. Assertion fails → Collect diagnostics
2. AI analyzes → Identifies root cause
3. AI generates → Remediation strategy
4. Execute fix → Validate with assertions
5. If still failing → Alert + escalate
6. Record outcome → Improve future remediation
```

**Use Cases:**
- Production auto-healing with intelligent diagnostics
- Dev environment lifecycle management
- Complex failure scenarios requiring analysis
- Reducing manual intervention for common issues

---

### 2. Stateful Service Evolution (`clockwork update`)

Transform Clockwork from one-time deployments to long-lived project management.

**Purpose:**
- Track deployed services as evolving projects, not one-time tasks
- Update infrastructure based on vague/partial specifications
- Maintain context of previous deployments for intelligent updates
- Validate changes don't break existing functionality

**Features:**
- State tracking of deployed primitives (configs, schemas, endpoints)
- Vague update support: "add new schema" interprets intent
- Smart diff and merge: update only what changed
- Automatic assertion generation for new features
- Version history and rollback capabilities

**Key Difference:**
- `clockwork apply`: Requires complete primitive definitions in `main.py`
- `clockwork update`: Accepts partial specs in `update.py`, infers changes from deployed state

**Example:**
```python
# Initial: main.py
api = DockerResource(
    name="api-service",
    description="REST API with user schema"
)

# Later: update.py (no need for original main.py!)
api = DockerResource(
    name="api-service",
    description="Add organization schema and update user endpoints"
)
```

```bash
clockwork update
# → Infers current state
# → Adds org schema
# → Updates endpoints
# → Generates new assertions
# → Validates all still works
```

---

### 3. Additional Built-in Assertions

Expand the type-safe assertion library for common scenarios.

**Container:**
- `ContainerHealthyAssert()` - Docker health status
- `LogContainsAssert(pattern, since)` - Log content validation
- `ContainerRestartCountAssert(max_restarts)` - Stability check

**HTTP/Network:**
- `ResponseTimeAssert(url, max_ms)` - Performance validation
- `HTTPStatusAssert(url, expected_status)` - Specific status code check
- `DNSResolveAssert(hostname, expected_ip)` - DNS validation
- `SSLCertificateAssert(url, min_days_valid)` - Certificate expiry

**File System:**
- `FilePermissionsAssert(path, expected_perms)` - Permission validation
- `FileSizeAssert(path, min_bytes, max_bytes)` - Size validation
- `DirectoryExistsAssert(path)` - Directory presence
- `DiskSpaceAssert(path, min_gb_free)` - Storage validation

**Database:**
- `DatabaseConnectionAssert(host, port, database, credentials)` - Connection validation
- `TableExistsAssert(table_name)` - Schema verification
- `RowCountAssert(table, min, max)` - Data presence
- `QuerySuccessAssert(sql_query)` - Custom query execution

**System Resources:**
- `MemoryUsageAssert(max_percent)` - Memory monitoring
- `CpuUsageAssert(max_percent)` - CPU monitoring
- `ProcessRunningAssert(process_name)` - Process validation

**Security:**
- `NoOpenPortsAssert(except_ports)` - Port scanning
- `SecretsPresentAssert(env_vars)` - Configuration validation
- `VulnerabilityScanAssert()` - Container/package scanning

---

### 4. Cross-Primitive Assertions

Validate interactions and dependencies between multiple primitives.

**Purpose:**
- Verify primitives can communicate
- Test end-to-end workflows across services
- Validate data consistency

**Examples:**
```python
# Service connectivity
connectivity = ServiceConnectivityAssert(
    from_service=api,
    to_service=database,
    protocol="postgresql",
    timeout=5
)

# End-to-end workflow
workflow = WorkflowAssert(
    steps=[
        ("api", "POST /users", {"name": "test"}),
        ("database", "SELECT * FROM users WHERE name='test'"),
        ("api", "GET /users/1")
    ],
    expected_results=[201, 1, 200]
)
```

---

### 5. Python-Based Custom Assertions

Support programmatic assertions using Python functions.

**Purpose:**
- Complex validation logic beyond built-in assertions
- External library/API integration
- Custom business logic validation

**Example:**
```python
@PythonAssert(resource=nginx)
def validate_api_response(resource):
    """Custom validation logic."""
    response = requests.get(f"http://localhost:8080/api/health")

    if response.status_code != 200:
        return False, f"Expected 200, got {response.status_code}"

    data = response.json()
    required_fields = ["status", "version", "uptime"]
    missing = [f for f in required_fields if f not in data]

    if missing:
        return False, f"Missing fields: {missing}"

    return True, f"Health check passed: {data['status']}"
```

---

### 6. More Primitive Types

Expand beyond current primitives:

**Cloud Resources:**
- S3BucketResource
- LambdaFunctionResource
- CloudFunctionResource

**Databases:**
- PostgresSchemaResource
- MySQLDatabaseResource
- MongoCollectionResource

**Services:**
- SystemdServiceResource
- LaunchdServiceResource
- CronJobResource

**Configuration:**
- EnvFileResource
- SecretsManagerResource
- ConfigMapResource

---

## 📝 Notes

- This roadmap is speculative and priorities may change
- Features move from "Under Consideration" to implementation based on user needs
- Contributions and feedback welcome via GitHub issues

## Contributing

Have ideas for the roadmap? Open an issue or submit a pull request!
