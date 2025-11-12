# Clockwork - Potential Roadmap

_This is a living document of potential features and enhancements. Updated frequently as priorities and ideas evolve._

---

## ✅ Implemented Features

### Core Primitives & CLI Commands

- **Primitive Types**: FileResource, AppleContainerResource, AppleContainerResource, GitRepoResource
- **CLI Commands**:
  - `clockwork apply` - Deploy primitives
  - `clockwork plan` - Preview without deploying
  - `clockwork destroy` - Remove deployed infrastructure
  - `clockwork assert` - Validate deployed primitives
  - `clockwork version` - Show version

### AI Completion & Flexibility

- **Adjustable Intelligence**: Choose per-primitive control level
  - Full control (specify everything, no AI)
  - Hybrid mode (specify key details, AI fills gaps)
  - Fast mode (describe requirements, AI handles implementation)
- **PydanticAI Integration**: Structured outputs with Pydantic validation
- **Tool Support**:
  - DuckDuckGo web search
  - Custom Python functions
  - Filesystem MCP server
  - User-provided tools via `tools` parameter
- **Tool Selection**: Automatic tool selection based on resource type and context

### Resource Connections

- **Dependency Declarations**: Connect primitives to express dependencies
- **Topological Sorting**: Automatic deployment ordering (O(V+E))
- **Cycle Detection**: Prevents circular dependencies
- **AI Context Sharing**: Connected primitives share configuration data for intelligent completion

### Type-Safe Assertions

Built-in assertion classes for validating deployed resources (no AI required, Pydantic-based):

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
nginx = AppleContainerResource(
    description="Web server",
    name="nginx-web",
    ports=["8080:80"],
    assertions=[
        ContainerRunningAssert(timeout_seconds=10),
        PortAccessibleAssert(port=8080, host="localhost", protocol="tcp"),
        HealthcheckAssert(url="http://localhost:8080", expected_status=200, timeout_seconds=5),
    ]
)
```

Run assertions:
```bash
clockwork assert  # Validates all deployed primitives
```

---

## 🤔 Under Consideration

### 1. Expanded Tool Support

Integrate additional PydanticAI built-in tools and enhance tool capabilities.

**Additional Built-in Tools:**

**Web & Content:**
- `WebSearchTool` - Enhanced web search with configurable max results and search context
- `UrlContextTool` - Extract and process content from URLs for AI analysis
- `BrowserTool` (future) - Full browser automation for dynamic content

**Memory & State:**
- `MemoryTool` - Persistent storage across agent runs (user sessions, preferences)
- `VectorStoreTool` (future) - Semantic search over past deployments and configurations

**Code & Execution:**
- `CodeExecutionTool` - Sandboxed Python code execution for dynamic logic
- `ShellCommandTool` (future) - Controlled shell command execution with safety policies

**Multi-Modal:**
- `ToolReturn` with rich content - Images, binary data, structured metadata
- `ImageAnalysisTool` (future) - Analyze screenshots, diagrams, architecture visuals
- `DocumentParserTool` (future) - Parse PDFs, Word docs, spreadsheets

**External Integrations (via MCP):**
- `PostgresMCP` - Database schema inspection and queries
- `GitHubMCP` - Repository analysis, PR context, issue tracking
- `SlackMCP` - Team notifications and context gathering
- `GoogleDriveMCP` - Document access for configuration templates
- `AWSMCP` (future) - Cloud resource inspection
- `KubernetesMCP` (future) - Cluster state and pod information

**Tool Composition:**
- `FunctionToolset` - Group related tools for organized access
- `ConditionalToolset` - Enable/disable tools based on runtime context
- `ApprovalRequiredToolset` - Require user approval for sensitive operations

**Example - Enhanced Resource with Tools:**
```python
api_docs = FileResource(
    name="api_documentation.md",
    description="Generate API docs from the codebase and latest best practices",
    tools=[
        WebSearchTool(max_results=5, search_context="prioritize official docs"),
        UrlContextTool(),  # Extract content from reference URLs
        CodeExecutionTool(timeout=30),  # Run code examples
        MCPServerStdio('npx', args=['-y', '@modelcontextprotocol/server-filesystem', '.']),
        custom_api_analyzer  # Your own function
    ],
    assertions=[
        FileExistsAssert(path="api_documentation.md"),
        FileContentMatchesAssert(path="api_documentation.md", pattern="API Reference")
    ]
)
```

**Smart Tool Selection Enhancements:**
- Context-aware tool filtering based on resource state
- Cost-aware tool selection (prefer cached/local tools)
- Tool performance metrics and optimization
- User-defined tool selection policies

**Tool Security & Safety:**
- Sandboxing for code execution tools
- Rate limiting for API-based tools
- Audit logging for all tool invocations
- Tool approval workflows for sensitive operations

---

### 2. Enhanced Reconciliation Service with AI Remediation

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
nginx = AppleContainerResource(
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

### 3. Stateful Service Evolution (`clockwork update`)

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
api = AppleContainerResource(
    name="api-service",
    description="REST API with user schema"
)

# Later: update.py (no need for original main.py!)
api = AppleContainerResource(
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

### 4. Additional Built-in Assertions

Expand the type-safe assertion library for common scenarios (not yet implemented):

**Container:**
- `ContainerHealthyAssert()` - Container health status
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

### 5. Cross-Primitive Assertions

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

### 6. Python-Based Custom Assertions

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

### 7. More Primitive Types

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
