# Clockwork Roadmap

## Upcoming Features

### 1. `clockwork evaluate` Command
Verification command to ensure resources are running as specified.

**Purpose:**
- Validates that deployed resources match their desired state
- Returns success/failure status
- Can be run manually or integrated into CI/CD pipelines
- Foundation for the reconciliation service

**Use Cases:**
- Post-deployment validation
- Health checks in CI/CD
- Manual verification of infrastructure state
- Debugging and troubleshooting

**Example:**
```bash
# Run from project directory containing main.py
cd my-project
clockwork evaluate
# Output: ✓ All resources running as specified
#         - nginx_container: running (port 80:80)
#         - config.json: present at /etc/app/config.json
```

---

### 2. Reconciliation Service
Background daemon that continuously monitors and maintains desired state.

**Purpose:**
- Periodically runs `evaluate` to detect drift
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
from clockwork.resources import DockerServiceResource

nginx = DockerServiceResource(
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

### 3. Stateful Service Evolution
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
docker_app = DockerServiceResource(
    name="api-service",
    description="REST API with user schema",
    # ... complete initial config
)

# Later: update.py (vague specification - no need to remember exact main.py details)
docker_app = DockerServiceResource(
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
- Integration with `clockwork evaluate` for continuous verification

---

## Contributing

Have ideas for the roadmap? Open an issue or submit a pull request!
