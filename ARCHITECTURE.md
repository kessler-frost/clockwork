# Clockwork Architecture

Clockwork is a **simplified declarative infrastructure tool** that converts
`.cw` configuration files into PyInfra operations for reliable, deterministic
infrastructure management.

## 🏗️ System Architecture

```text
.cw File → [PARSE] → PyInfra Operations → [EXECUTE] → Infrastructure
```

### Core Pipeline

Clockwork uses a streamlined two-phase pipeline:

1. **PARSE**: Convert `.cw` configuration files into PyInfra operations
2. **EXECUTE**: Run PyInfra operations on target infrastructure (local, SSH, Docker, K8s)

## 🔧 System Components

### 1. Parser

- Parses `.cw` (HCL-style) configuration files
- Validates resource definitions and dependencies
- Converts to PyInfra operations directly
- Outputs ready-to-execute PyInfra operation list

### 2. PyInfra Operations

Clockwork provides specialized PyInfra operations for:

- **Docker containers**: Service deployment and management
- **Docker Compose**: Multi-container application stacks
- **Kubernetes**: Pod and service deployments
- **Health checks**: HTTP endpoint verification
- **Terraform**: Infrastructure provisioning (experimental)

### 3. Executor

- Runs PyInfra operations on target infrastructure
- Supports multiple connectors (local, SSH, Docker, K8s)
- Provides dry-run capabilities for safe planning
- Manages state and tracks deployment history

### 4. State Manager

- Tracks deployment state and resource status
- Enables drift detection and state reconciliation
- Stores state in `.clockwork/state.json` by default
- Supports state inspection and reset operations

## 📁 Project Structure

```text
clockwork/
├── 📦 clockwork/                   # Core package
│   ├── 🔧 pyinfra_ops/            # PyInfra operations
│   │   ├── __init__.py            # Package initialization
│   │   ├── compose.py             # Docker Compose operations
│   │   ├── health.py              # Health check operations
│   │   ├── kubernetes.py          # Kubernetes operations
│   │   └── terraform.py           # Terraform operations
│   │
│   ├── __init__.py                # Package initialization
│   ├── __main__.py                # CLI entry point
│   ├── core.py                    # Main pipeline orchestrator
│   ├── parser.py                  # Configuration parser
│   ├── state_manager.py           # State management
│   ├── models.py                  # Pydantic data models
│   ├── errors.py                  # Exception hierarchy
│   ├── formatters.py              # Output formatting
│   └── cli.py                     # Command-line interface
│
├── 📚 docs/                       # Documentation
│   ├── guides/                    # User guides
│   └── README.md                  # Documentation index
│
├── 🧪 tests/                      # Test suite
│   ├── unit/                      # Fast, isolated unit tests
│   ├── integration/               # Component integration tests
│   ├── conftest.py                # Shared test fixtures
│   └── README.md                  # Test documentation
│
├── 📋 examples/                   # Example configurations
│   ├── hello-world/               # Simple example
│   └── basic-web-service/         # Full-featured example
│
├── run_tests.py                   # Test runner utility
├── pyproject.toml                 # Project configuration
└── README.md                      # Project overview
```

## 🔄 Data Flow

### 1. Configuration Processing (PARSE)

```text
main.cw → Parser → Validated Config → PyInfra Operations
```

**Key Components:**

- **Parser**: HCL-style syntax parsing and variable substitution
- **Core**: Dependency resolution and reference validation
- **Models**: Schema validation and data modeling
- **PyInfra Ops**: Converts config to PyInfra operations

### 2. Infrastructure Execution (EXECUTE)

```text
PyInfra Operations → Target Selection → Connector → Infrastructure Changes
```

**Key Components:**

- **Target Manager**: Selects appropriate infrastructure target
- **Connector**: Handles connection to target (local, SSH, Docker, K8s)
- **Operation Executor**: Runs PyInfra operations with proper ordering
- **State Tracker**: Records changes and maintains deployment state

## 🛡️ Security Architecture

### Multi-Layer Security

1. **Input Validation**: HCL syntax and schema validation
2. **Operation Sandboxing**: PyInfra operations run in controlled environments
3. **Path Restrictions**: File operations limited to allowed directories
4. **State Integrity**: Cryptographic validation of state files
5. **Dry-run Safety**: All changes can be previewed before execution

### Security Zones

- **Development**: Relaxed validation, verbose logging, local-only by default
- **Production**: Strict validation, minimal permissions, comprehensive auditing

## 📊 Performance Characteristics

### Pipeline Performance

- **PARSE**: ~50ms (configuration parsing + validation)
- **EXECUTE**: Variable (depends on infrastructure complexity and target)

### Scalability

- **Parallel Operations**: PyInfra handles parallel execution internally
- **Resource Limits**: Configurable memory and CPU constraints
- **Caching**: State caching reduces redundant operations

## 🔌 Extension Points

### Custom Operations

- **PyInfra Operations**: Implement custom operations following PyInfra patterns
- **Connectors**: Add support for new infrastructure targets
- **Validators**: Extend validation rules for custom resource types
- **State Backends**: Pluggable state storage (filesystem, database, cloud)

### Configuration

All components support configuration via:

- **Environment variables**: Configure all aspects via environment variables
- **Command-line arguments**: Override environment variables at runtime
- **Configuration files**: Use `.env` files for persistent settings

Key environment variables:

- `CLOCKWORK_PROJECT_NAME`: Project identifier
- `CLOCKWORK_LOG_LEVEL`: Logging verbosity (DEBUG, INFO, WARNING, ERROR)
- `CLOCKWORK_TARGET`: Default deployment target
- `CLOCKWORK_PARALLEL_LIMIT`: Maximum parallel operations
- `CLOCKWORK_DEFAULT_TIMEOUT`: Default timeout for operations
- `CLOCKWORK_STATE_FILE`: State persistence file path

## 🚀 Deployment Patterns

### Local Development

```bash
# Set environment variables or use .env file
export CLOCKWORK_PROJECT_NAME=myproject
export CLOCKWORK_LOG_LEVEL=DEBUG
uv run clockwork apply examples/basic-web-service/main.cw
```

### Production Deployment

```bash
# Production environment variables
export CLOCKWORK_PROJECT_NAME=production-app
export CLOCKWORK_LOG_LEVEL=INFO
export CLOCKWORK_TARGET=production
export CLOCKWORK_STATE_FILE=/var/lib/clockwork/state.json
uv run clockwork apply --target production configs/production.cw
```

### CI/CD Integration

```bash
# Validate, plan, then apply
uv run clockwork plan configs/app.cw
uv run clockwork apply configs/app.cw
```

## 🔄 Detailed Architecture Flow

```text
                                        (Git / FS)
                                  ┌───────────────────┐
                                  │   .cw repository  │
                                  │  modules, vars,   │
                                  │  providers, etc.  │
                                  └─────────┬─────────┘
                                            │
                                            │ 1) file change / manual run
                                            ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                                    Parse Phase                               │
│  ┌─────────────────────────┐   ┌──────────────────────────┐                 │
│  │ Configuration Loader    │   │ PyInfra Operation Gen    │                 │
│  │ • reads .cw/.cwvars     │   │ • converts to operations │                 │
│  │ • merges env/overrides  │   │ • validates dependencies │                 │
│  │ • resolves variables    │   │ • prepares execution     │                 │
│  └────────────┬────────────┘   └───────────┬──────────────┘                 │
│               │                            │                                │
│               └───────────────┬────────────┴───────────────────────────────┘
│                               │
│                               ▼
│                         PyInfra Operations
└───────────────┬───────────────────────────────────────────────────────────────
                │ 2) execute on target
                ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                                Execute Phase                                │
│  ┌──────────────────────────┐   ┌──────────────────────────┐               │
│  │ Target Connection        │   │ Operation Execution      │               │
│  │ • local/SSH/Docker/K8s   │   │ • runs PyInfra ops       │               │
│  │ • establishes connection │   │ • handles dependencies   │               │
│  │ • validates permissions  │   │ • tracks state changes   │               │
│  └────────────┬─────────────┘   └────────────┬─────────────┘               │
│               │                               │                             │
│               ▼                               ▼                             │
│         Connected Target                State Updates                       │
└───────────────┬───────────────────────────────────────────────────────────────
                │ 3) track results
                ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                                State Management                              │
│  • Records operation results and resource states                            │
│  • Enables drift detection and state inspection                             │
│  • Provides rollback and troubleshooting capabilities                       │
│                                                                              │
│  State file: .clockwork/state.json                                          │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Simple Pipeline Flow

```text
                ┌─────────────── .cw (HCL) ────────────────┐
                │                                           │
                ▼                                           │
           ┌───────────┐        ┌───────────┐               │
           │   Parse   │ ops +  │  Execute  │─── Results ───┘
           │ .cw → ops │ state  │ PyInfra   │
           └─────┬─────┘        └─────┬─────┘
                 │                    │
                 ▼                    ▼
                           ┌──────────────────┐
                           │   Infrastructure │
                           │   (local/remote) │
                           │                  │
                           └──────┬───────────┘
                                  │
                         logs + state updates
                                  │
                                  ▼
                         .clockwork/state.json
```

## 📋 Data Contracts

### PyInfra Operations

The parser generates standard PyInfra operations that can be executed directly:

```python
# Example: Docker container operation
docker.containers(
    name="myapp",
    image="nginx:1.25-alpine",
    ports=["3000:80"],
    environment={"APP_ENV": "production"},
    restart_policy="unless-stopped",
    state.cwd="/app"
)

# Example: Health check operation
http.request(
    url="http://localhost:3000",
    method="GET",
    expected_status=200,
    timeout=30
)
```

### State File Format

```json
{
  "version": "1.0",
  "project": "myproject",
  "last_applied": "2024-01-15T10:30:00Z",
  "resources": {
    "docker_container_myapp": {
      "type": "docker_container",
      "status": "running",
      "last_changed": "2024-01-15T10:30:00Z",
      "checksum": "abc123..."
    }
  },
  "operations": [
    {
      "name": "ensure_container",
      "status": "completed",
      "duration": 2.5,
      "changes": ["created container myapp"]
    }
  ]
}
```

## 🎯 Design Rationale

This architecture prioritizes simplicity and reliability over complexity. The two-phase
pipeline (Parse → Execute) leverages PyInfra's mature ecosystem while providing a
declarative interface that's easy to understand and maintain.

Key benefits:

- **Familiar PyInfra patterns**: Leverages existing PyInfra knowledge and tooling
- **Simple mental model**: Two phases are easier to understand than complex multi-stage pipelines
- **Reliable execution**: PyInfra's battle-tested execution engine handles edge cases
- **Extensible**: Easy to add new operations and connectors following PyInfra patterns
- **Debuggable**: Clear separation between parsing and execution phases

This architecture provides a solid foundation for declarative infrastructure management
with the reliability of PyInfra and the simplicity of a focused tool.