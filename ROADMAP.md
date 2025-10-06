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
clockwork evaluate main.py
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

## Contributing

Have ideas for the roadmap? Open an issue or submit a pull request!
