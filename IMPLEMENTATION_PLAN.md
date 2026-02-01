# Clockwork Feature Implementation Plan

This document outlines the implementation plan for 6 new features in Clockwork, following the suggested order based on scope and impact.

## Overview

| Priority | Feature | Scope | Impact | Dependencies |
|----------|---------|-------|--------|--------------|
| 1 | `clockwork show` | Small | High (immediate UX value) | None |
| 2 | `clockwork status` | Medium | High (pairs with show) | None |
| 3 | DockerResource | Large | Critical (cross-platform) | New Pulumi provider |
| 4 | AI Completion Caching | Medium | High (reproducibility) | None |
| 5 | Better Error Messages | Medium | Medium (polish) | None |
| 6 | S3BucketResource | Medium | Medium (cloud viability) | pulumi-aws dependency |

---

## Priority 1: `clockwork show` Command

**Goal**: Display completed resources BEFORE deployment so users can see exactly what AI decided.

### Implementation Tasks

1. **Add `show` method to `ClockworkCore`** (`clockwork/core.py`)
   - Load resources from `main.py`
   - Resolve dependencies
   - Complete resources (same as `apply` but stop before Pulumi)
   - Return completed resources with metadata about which fields were AI-completed

2. **Track AI-completed fields**
   - Modify `ResourceCompleter._merge_resources()` to track which fields came from AI
   - Add `_ai_completed_fields: set[str]` attribute to completed resources
   - Compare user-provided vs completed values to determine AI contributions

3. **Add `show` command to CLI** (`clockwork/cli.py`)
   - `clockwork show` — show all resources
   - `clockwork show <resource-name>` — show specific resource
   - `--json` flag for machine-readable output
   - `--diff` flag for only AI-completed fields
   - `--yaml` flag (alternative format)

4. **Rich output formatting**
   - Use Rich library for colorful terminal output
   - Mark AI-completed fields with `[AI]` prefix or different color
   - Show resource hierarchy for composites

### Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `clockwork/core.py` | Modify | Add `show()` method |
| `clockwork/resource_completer.py` | Modify | Track AI-completed fields |
| `clockwork/cli.py` | Modify | Add `show` command |
| `clockwork/formatters.py` | Create | Output formatting utilities |
| `tests/test_show_command.py` | Create | Unit tests |

### Example Output

```
$ clockwork show

╭─ Clockwork Show ─────────────────────────────────────╮
│ Directory: simple-webapp                              │
│ Model: anthropic/claude-haiku-4.5                    │
╰───────────────────────────────────────────────────────╯

webapp (BlankResource)
├── description: "Simple web application with database"
├── name: "webapp" [AI]
└── children:
    ├── postgres (AppleContainerResource)
    │   ├── description: "PostgreSQL database"
    │   ├── name: "postgres" [AI]
    │   ├── image: "postgres:15-alpine" [AI]
    │   ├── ports: ["5432:5432"] [AI]
    │   └── env_vars: {"POSTGRES_PASSWORD": "secret"} [AI]
    └── api (AppleContainerResource)
        ├── description: "REST API server"
        ├── name: "api" [AI]
        ├── image: "node:20-alpine" [AI]
        └── ports: ["3000:3000"] [AI]
```

---

## Priority 2: `clockwork status` Command

**Goal**: Inspect currently deployed resources with their actual system state.

### Implementation Tasks

1. **Add `status` method to `ClockworkCore`** (`clockwork/core.py`)
   - Load Pulumi state file for project
   - Map Pulumi resources back to Clockwork resources
   - Query actual system state (container running, file exists, etc.)
   - Return combined state information

2. **Create resource state checkers** (`clockwork/state_checkers.py`)
   - `ContainerStateChecker` — query Docker/Apple Container CLI for status
   - `FileStateChecker` — check file existence, modification time, size
   - `GitRepoStateChecker` — check branch, last commit, clean/dirty

3. **Add `status` command to CLI** (`clockwork/cli.py`)
   - `clockwork status` — list all deployed resources
   - `--json` flag for machine-readable output
   - `--verbose` flag for additional details

4. **Integrate with Pulumi state**
   - Read from `~/.pulumi/stacks/dev/<project>.json`
   - Parse resource outputs and URNs
   - Correlate with actual system state

### Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `clockwork/core.py` | Modify | Add `status()` method |
| `clockwork/state_checkers.py` | Create | System state verification |
| `clockwork/cli.py` | Modify | Add `status` command |
| `tests/test_status_command.py` | Create | Unit tests |

### Example Output

```
$ clockwork status

╭─ Clockwork Status ────────────────────────────────────╮
│ Project: simple-webapp                                │
│ Stack: dev                                            │
╰───────────────────────────────────────────────────────╯

┏━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Name       ┃ Type                     ┃ Status   ┃ Details                ┃
┡━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━┩
│ postgres   │ AppleContainerResource   │ running  │ ports: 5432, up 2h     │
│ api        │ AppleContainerResource   │ running  │ ports: 3000, up 2h     │
│ config     │ FileResource             │ exists   │ /app/config.yaml       │
│ app-repo   │ GitRepoResource          │ clean    │ main @ abc1234         │
└────────────┴──────────────────────────┴──────────┴────────────────────────┘
```

---

## Priority 3: DockerResource (Cross-Platform Containers)

**Goal**: Create a container resource that works everywhere Docker is installed.

### Implementation Tasks

1. **Create DockerResource** (`clockwork/resources/docker_resource.py`)
   - Mirror `AppleContainerResource` API exactly
   - Fields: `name`, `description`, `image`, `ports`, `volumes`, `env_vars`, `command`, `networks`, `must_run`
   - Implement `needs_completion()` and `to_pulumi()`
   - Add `get_connection_context()` for connection support

2. **Create Docker Pulumi Provider** (`clockwork/pulumi_providers/docker_container.py`)
   - Use `docker` Python SDK or shell out to `docker` CLI
   - Implement CRUD operations: create, read, update, delete
   - Handle container lifecycle: start, stop, remove
   - Support port mappings, volume mounts, environment variables

3. **Platform detection utility** (`clockwork/platform.py`)
   - Detect OS (macOS, Linux, Windows)
   - Check for Docker availability (`docker info`)
   - Check for Apple Containers availability (`container --version`)
   - Provide recommendation based on platform

4. **Add to resource registry** (`clockwork/resources/__init__.py`)
   - Export `DockerResource`
   - Rebuild model for forward references

5. **Create example** (`examples/docker-webapp/main.py`)
   - Simple web app using DockerResource
   - Works on Linux, macOS (without Apple Containers), Windows

### Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `clockwork/resources/docker_resource.py` | Create | DockerResource class |
| `clockwork/pulumi_providers/docker_container.py` | Create | Docker dynamic provider |
| `clockwork/platform.py` | Create | Platform detection utilities |
| `clockwork/resources/__init__.py` | Modify | Export DockerResource |
| `pyproject.toml` | Modify | Add `docker` dependency |
| `examples/docker-webapp/main.py` | Create | Example project |
| `tests/test_docker_resource.py` | Create | Unit tests |
| `tests/test_docker_integration.py` | Create | Integration tests (skip if no Docker) |

### API Design

```python
from clockwork.resources import DockerResource
from clockwork.assertions import ContainerRunningAssert, HealthcheckAssert

# Minimal - AI completes everything
web = DockerResource(
    description="nginx web server for static files"
)

# Explicit - full control
db = DockerResource(
    name="postgres",
    image="postgres:15-alpine",
    ports=["5432:5432"],
    env_vars={
        "POSTGRES_PASSWORD": "secret",
        "POSTGRES_DB": "myapp"
    },
    volumes=["./data:/var/lib/postgresql/data"],
    assertions=[
        ContainerRunningAssert(),
        HealthcheckAssert(url="http://localhost:5432", timeout_seconds=30)
    ]
)
```

### Docker Provider Implementation

```python
class DockerContainerProvider(dynamic.ResourceProvider):
    def create(self, props: dict) -> dynamic.CreateResult:
        # docker run -d --name {name} -p {ports} -v {volumes} -e {env} {image}
        ...

    def delete(self, id: str, props: dict) -> None:
        # docker stop {id} && docker rm {id}
        ...

    def read(self, id: str, props: dict) -> dynamic.ReadResult:
        # docker inspect {id}
        ...
```

---

## Priority 4: AI Completion Caching

**Goal**: Make AI completions reproducible by caching results.

### Implementation Tasks

1. **Create cache module** (`clockwork/completion/cache.py`)
   - Cache key generation: hash of (resource_type, description, user_fields, model_name)
   - Cache storage: SQLite in `.clockwork/cache/completions.db`
   - TTL support (default 7 days, configurable)
   - Thread-safe access

2. **Integrate with ResourceCompleter** (`clockwork/resource_completer.py`)
   - Check cache before calling AI
   - Store results after successful completion
   - Add `use_cache` parameter (default True)

3. **Add CLI options**
   - `clockwork apply --no-cache` — force fresh completion
   - `clockwork cache clear` — wipe cache
   - `clockwork cache stats` — show cache statistics

4. **Add settings** (`clockwork/settings.py`)
   - `CW_CACHE_ENABLED` (default: True)
   - `CW_CACHE_TTL_DAYS` (default: 7)
   - `CW_CACHE_DIR` (default: `.clockwork/cache`)

5. **Verbose output**
   - Show cache hit/miss in `--verbose` mode
   - Display cache age for hits

### Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `clockwork/completion/__init__.py` | Create | Package init |
| `clockwork/completion/cache.py` | Create | Cache implementation |
| `clockwork/resource_completer.py` | Modify | Integrate cache |
| `clockwork/settings.py` | Modify | Add cache settings |
| `clockwork/cli.py` | Modify | Add cache commands |
| `tests/test_completion_cache.py` | Create | Unit tests |

### Cache Key Algorithm

```python
def compute_cache_key(resource) -> str:
    """Compute deterministic cache key for a resource."""
    key_data = {
        "resource_type": resource.__class__.__name__,
        "description": resource.description,
        "model": self.model,
        # Include all user-provided non-None fields
        "user_fields": {
            k: v for k, v in resource.model_dump().items()
            if v is not None and k not in ("tools", "assertions", "connections")
        }
    }
    # Deterministic JSON serialization
    json_str = json.dumps(key_data, sort_keys=True, default=str)
    return hashlib.sha256(json_str.encode()).hexdigest()[:16]
```

---

## Priority 5: Better Error Messages

**Goal**: Improve error handling when AI completion fails.

### Implementation Tasks

1. **Create custom exceptions** (`clockwork/exceptions.py`)
   - `CompletionError` — base class for completion failures
   - `CompletionTimeoutError` — timeout during completion
   - `CompletionValidationError` — invalid response from model
   - `CompletionRetryExhaustedError` — max retries exceeded

2. **Improve error handling in ResourceCompleter**
   - Catch and wrap exceptions with context
   - Include raw model response for debugging
   - Suggest fixes for common errors

3. **Add `--debug` flag to CLI**
   - Show full API request/response for completion calls
   - Include model parameters, timing, retries

4. **Timeout handling**
   - Configurable timeout (default 30s)
   - Clear message: "Completion timed out after 30s. Try a faster model or simplify the description."

5. **Validation error messages**
   - "Model returned invalid port format '80'. Expected 'host:container' like '8080:80'"
   - "Model returned empty image name. Ensure description mentions the service type."

### Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `clockwork/exceptions.py` | Create | Custom exception classes |
| `clockwork/resource_completer.py` | Modify | Enhanced error handling |
| `clockwork/cli.py` | Modify | Add --debug flag |
| `clockwork/settings.py` | Modify | Add timeout settings |
| `tests/test_error_handling.py` | Create | Unit tests |

### Example Error Output

```
$ clockwork apply

╭─ Clockwork Apply ─────────────────────────────────────╮
│ Directory: my-project                                 │
│ Model: meta-llama/llama-4-scout:free                 │
╰───────────────────────────────────────────────────────╯

✗ Completion failed for resource: web-server

Error: Model returned invalid port format '80'
Expected: 'host:container' format like '8080:80'
Received: '80'

Suggestions:
  • Add explicit port mapping in your resource: ports=["8080:80"]
  • Try a more capable model: --model anthropic/claude-haiku-4.5
  • Simplify the description to be more specific

Run with --debug to see the full API response.
```

---

## Priority 6: S3BucketResource

**Goal**: Add a basic cloud resource to prove the model works beyond local resources.

### Implementation Tasks

1. **Create S3BucketResource** (`clockwork/resources/s3_resource.py`)
   - Fields: `name`, `description`, `bucket_name`, `region`, `public`, `versioning`, `website_config`
   - Implement `needs_completion()` — bucket_name is required
   - Implement `to_pulumi()` — use pulumi-aws provider
   - Add `get_connection_context()` for connection support

2. **Add S3-specific assertions** (`clockwork/assertions/s3.py`)
   - `BucketExistsAssert` — check bucket exists via boto3
   - `BucketAccessibleAssert` — check read/write access
   - `BucketPublicAssert` — verify public access settings

3. **Add pulumi-aws as optional dependency** (`pyproject.toml`)
   - Add `[aws]` extra: `pip install clockwork[aws]`
   - Lazy import to avoid errors when AWS not needed

4. **Handle AWS credentials**
   - Use standard boto3 credential chain (env vars, AWS profile, IAM role)
   - Validate credentials before deployment
   - Clear error messages for missing credentials

5. **Create example** (`examples/s3-static-site/main.py`)
   - Static website hosting on S3
   - Public read access
   - Versioning enabled

### Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `clockwork/resources/s3_resource.py` | Create | S3BucketResource class |
| `clockwork/assertions/s3.py` | Create | S3-specific assertions |
| `clockwork/resources/__init__.py` | Modify | Export S3BucketResource |
| `pyproject.toml` | Modify | Add pulumi-aws optional dependency |
| `examples/s3-static-site/main.py` | Create | Example project |
| `tests/test_s3_resource.py` | Create | Unit tests |

### API Design

```python
from clockwork.resources import S3BucketResource
from clockwork.assertions import BucketExistsAssert, BucketAccessibleAssert

# Minimal - AI suggests configuration
bucket = S3BucketResource(
    description="static website hosting for marketing site"
)
# AI generates: bucket_name, region, public=True, website_config={index: "index.html"}

# Explicit - full control
bucket = S3BucketResource(
    name="my-bucket",
    bucket_name="my-company-static-assets",
    region="us-east-1",
    public=False,
    versioning=True,
    assertions=[
        BucketExistsAssert(),
        BucketAccessibleAssert()
    ]
)
```

### pyproject.toml Changes

```toml
[project.optional-dependencies]
aws = [
    "pulumi-aws>=6.0.0",
    "boto3>=1.34.0",
]
```

---

## Implementation Timeline

### Phase 1: Foundation (Priority 1-2)
- `clockwork show` command
- `clockwork status` command
- Shared utilities (formatters, state checkers)

### Phase 2: Cross-Platform (Priority 3)
- DockerResource
- Docker Pulumi provider
- Platform detection

### Phase 3: Developer Experience (Priority 4-5)
- AI completion caching
- Better error messages
- Debug mode

### Phase 4: Cloud Integration (Priority 6)
- S3BucketResource
- AWS assertions
- Optional dependencies pattern

---

## Testing Strategy

### Unit Tests
- Test each new class/function in isolation
- Mock external dependencies (Docker, AWS, Pulumi)
- Cover edge cases and error conditions

### Integration Tests
- Test full pipeline with real resources (marked for skip in CI)
- Test Docker resource on systems with Docker installed
- Test S3 resource with AWS credentials (skip if unavailable)

### Functional Tests
- Test CLI commands with real examples
- Verify output formatting
- Test cache behavior

---

## Documentation Updates

1. **README.md**
   - Add new commands section (`show`, `status`)
   - Document DockerResource
   - Document S3BucketResource with AWS setup

2. **CLAUDE.md**
   - Update with new file locations
   - Document caching behavior
   - Add error handling guidelines

3. **Examples**
   - `examples/docker-webapp/` — cross-platform container example
   - `examples/s3-static-site/` — AWS S3 example
   - Update existing examples with `clockwork show` usage

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Docker SDK compatibility | Fall back to CLI if SDK fails |
| AWS credential complexity | Clear documentation, helpful error messages |
| Cache invalidation | Include model version in cache key |
| Cross-platform testing | CI matrix for Linux, macOS, Windows |
| Breaking changes | Maintain backward compatibility with existing resources |
