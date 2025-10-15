# Monitored Service Example

This example demonstrates Clockwork's **service monitoring** and **auto-remediation** capabilities.

## What This Example Shows

1. **Continuous Health Monitoring** - The Clockwork service monitors resources at configurable intervals
2. **Auto-Remediation** - When failures occur, the service automatically fixes them using AI
3. **Resource-Specific Check Intervals** - Containers checked every 30s, files checked once
4. **Multi-Project Support** - One service can monitor multiple projects concurrently

## Architecture

```
┌─────────────────────────────────────────┐
│     Clockwork Service (Port 8765)       │
│                                         │
│  - Health checking loop                 │
│  - Diagnostic collection                │
│  - AI-powered remediation               │
│  - Resource-specific intervals          │
└─────────────────────────────────────────┘
                  │
                  │ Monitors
                  ▼
┌─────────────────────────────────────────┐
│           Deployed Resources            │
│                                         │
│  ┌──────────────┐   ┌──────────────┐   │
│  │    Redis     │   │    Nginx     │   │
│  │ (Port 6380)  │◄──│ (Port 8081)  │   │
│  └──────────────┘   └──────────────┘   │
│                                         │
│  Redis: Check every 30s                 │
│  Nginx: Check every 30s                 │
└─────────────────────────────────────────┘
```

## Prerequisites

1. **Docker installed** - `docker --version`
2. **Clockwork service running** - `clockwork service start`
3. **AI configured** - Valid API key in `.env` file

## Usage

### 1. Start the Service

```bash
# Start the Clockwork monitoring service
clockwork service start

# Verify it's running
clockwork service status
```

### 2. Deploy Resources

```bash
cd examples/monitored-service
clockwork apply
```

The resources will be deployed and automatically registered with the monitoring service.

### 3. View Service Status

```bash
# Check overall service status
clockwork service status

# Output:
# ✓ Service running
# Port: 8765
# Status: healthy
# Registered projects: 1
```

### 4. Test Auto-Remediation (Step-by-Step Guide)

This section provides a detailed walkthrough to test the auto-remediation feature:

```bash
# Stop a container manually
docker stop nginx-monitored

# Watch the service detect and fix it (check service logs)
# The service will:
# 1. Detect nginx-monitored is not running (within 30s)
# 2. Collect diagnostics (container status, logs)
# 3. Enhance the completion prompt with error context
# 4. Re-complete the resource with AI
# 5. Re-apply the resource
# 6. Validate it's healthy again
```

### 5. Check Resource Health

```bash
# Run assertions manually
clockwork assert

# Output:
# ✓ All assertions passed
#   ✓ redis-monitored: ContainerRunningAssert
#   ✓ redis-monitored: PortAccessibleAssert (port 6380)
#   ✓ nginx-monitored: ContainerRunningAssert
#   ✓ nginx-monitored: PortAccessibleAssert (port 8081)
#   ✓ nginx-monitored: HealthcheckAssert (http://localhost:8081)
```

### 6. Clean Up

```bash
# Destroy resources (this also unregisters from service)
clockwork destroy

# Stop the service (optional)
clockwork service stop
```

## Service Configuration

The service behavior can be configured via environment variables:

```bash
# .env file
CW_SERVICE_PORT=8765                              # Service port
CW_SERVICE_CHECK_INTERVAL_DEFAULT=30              # Default check interval (seconds)
CW_SERVICE_MAX_REMEDIATION_ATTEMPTS=3             # Max retry attempts
```

## Monitoring Behavior

### Check Intervals

- **Containers** (DockerResource, AppleContainerResource): Every 30 seconds
- **Files** (FileResource): Once after deployment, then skipped
- **Git Repos** (GitRepoResource): Every 5 minutes

### Remediation Flow

When a resource fails health checks:

1. **Detect Failure** - Assertion fails (container not running, port not accessible, etc.)
2. **Collect Diagnostics** - Retrieve logs, status, error messages
3. **Enhance Prompt** - Add diagnostic context to AI completion prompt
4. **Re-Complete** - AI generates fixed configuration
5. **Re-Apply** - Deploy the fixed resource
6. **Validate** - Run assertions to verify the fix
7. **Retry Logic** - Up to 3 attempts before giving up

### Example Remediation

If nginx fails because it can't connect to redis:

```
[Diagnostic] Container 'nginx-monitored' not running
[Diagnostic] Logs: "Error: Cannot connect to redis:6379"
[Remediation] Updating completion prompt with error context...
[Remediation] AI suggests: Add shared network with redis
[Remediation] Re-applying nginx with network configuration...
[Remediation] ✓ nginx-monitored healthy again
```

## Project Registration

The service tracks which projects it's monitoring:

- **Registration**: Happens automatically after successful `clockwork apply`
- **Unregistration**: Happens automatically after `clockwork destroy`
- **Manual check**: `clockwork service status` shows registered project count

## Troubleshooting

### Service Not Running

```bash
# Error: Clockwork service not running
# Solution: Start the service first
clockwork service start
```

### Port Conflicts

If ports 6380 or 8081 are already in use:

1. Modify ports in `main.py`
2. Run `clockwork apply` again

### Remediation Not Working

Check the service logs to diagnose issues:

```bash
# View service logs (in separate terminal)
tail -f .clockwork/service/service.log
```

### AI Connection Issues

The service requires a valid AI connection:

```bash
# Check .env file
cat .env

# Verify:
# CW_API_KEY=your-api-key
# CW_MODEL=meta-llama/llama-4-scout:free
# CW_BASE_URL=https://openrouter.ai/api/v1
```

## Advanced Usage

### Multiple Projects

The service can monitor multiple projects:

```bash
# Terminal 1: Start service
clockwork service start

# Terminal 2: Deploy project 1
cd examples/monitored-service
clockwork apply

# Terminal 3: Deploy project 2
cd examples/docker-service
clockwork apply

# Check status (shows 2 registered projects)
clockwork service status
```

### Skip Service Check

For development, you can skip the service health check:

```bash
clockwork apply --skip-service-check
clockwork assert --skip-service-check
clockwork destroy --skip-service-check
```

## What's Next?

- Explore other examples: `examples/connected-services/` for complex dependencies
- Read the full documentation: `CLAUDE.md`
- Customize check intervals in `.env` file
- Build your own resources with custom assertions
