# Clockwork Architecture

Clockwork is a **Factory for Intelligent Declarative Tasks** that converts
HCL2 configuration files into executable artifacts using a three-phase
pipeline with optional AI assistance.

## 🏗️ System Architecture

```text
.cw File → [INTAKE] → IR → [ASSEMBLY] → ActionList → [FORGE] → Artifacts
```

### Core Pipeline

1. **INTAKE**: Parse HCL2 `.cw` files into Intermediate Representation (IR)
2. **ASSEMBLY**: Convert IR into ActionList with dependency resolution
3. **FORGE**: Compile ActionList into executable artifacts with AI assistance

## 🔧 System Components

The system consists of 4 main components:

### 1. Intake

- Parses `.cw` (HCL-ish) → JSON → validates into **IR** (Pydantic)
- Resolves references, fills defaults
- Outputs `IR` + `EnvFacts`

### 2. Assembly

- Deterministically computes an **ActionList** (ordered steps) from IR
- Handles diffs vs observed state
- Builds desired-state graph with dependencies & ordering

### 3. Forge

- Calls the **Compiler Agent** once to produce an **ArtifactBundle**
- Writes artifacts to `.clockwork/build/**`
- Validates and executes steps with logging/timeouts
- Persists `state.json`

### 4. Daemon (optional)

- Watches services/drift
- Proposes smallest safe change → applies patch
- Re-runs the Intake → Assembly → Forge pipeline

## 📁 Project Structure

```text
clockwork/
├── 📦 clockwork/                   # Core package
│   ├── 📥 intake/                  # Phase 1: Configuration parsing
│   │   ├── parser.py              # HCL2 parser for .cw files
│   │   ├── resolver.py            # Dependency and variable resolution
│   │   └── validator.py           # Configuration validation
│   │
│   ├── 🔧 assembly/               # Phase 2: Action planning
│   │   ├── planner.py             # IR → ActionList conversion
│   │   └── differ.py              # State difference analysis
│   │
│   ├── ⚡ forge/                  # Phase 3: Artifact generation
│   │   ├── compiler.py            # ActionList → ArtifactBundle
│   │   ├── agno_agent.py          # AI agent integration (LM Studio)
│   │   ├── executor.py            # Artifact execution engine
│   │   ├── runner.py              # Multi-environment runners
│   │   └── state.py               # State management and persistence
│   │
│   ├── 🤖 daemon/                 # Background process management
│   │   ├── loop.py                # Main daemon loop
│   │   ├── patch_engine.py        # Auto-fix policy engine
│   │   └── rate_limiter.py        # Resource management
│   │
│   ├── core.py                    # Main ClockworkCore orchestrator
│   ├── models.py                  # Pydantic data models
│   ├── errors.py                  # Exception hierarchy
│   └── cli.py                     # Command-line interface
│
├── 📚 docs/                       # Documentation
│   ├── guides/                    # User guides and tutorials
│   │   └── AI_INTEGRATION.md      # AI setup and configuration
│   ├── architecture/              # Technical architecture docs
│   └── api/                       # API reference documentation
│
├── ⚙️ configs/                    # Configuration templates
│   ├── development.json           # Development environment settings
│   ├── production.json            # Production environment settings
│   └── lm_studio_config.json      # AI agent configuration
│
├── 🧪 tests/                      # Test suite
│   ├── unit/                      # Fast, isolated unit tests
│   ├── integration/               # Component integration tests
│   └── e2e/                       # End-to-end workflow tests
│
├── 📋 examples/                   # Example configurations
│   └── basic-web-service/         # Sample .cw configuration
│
└── 🔧 run_tests.py                # Test runner utility
```

## 🔄 Data Flow

### 1. Input Processing (INTAKE)

```text
main.cw + variables.cwvars → Parser → Raw Config → Resolver → Validated IR
```

**Key Components:**

- **Parser**: HCL2 syntax parsing and variable substitution
- **Resolver**: Dependency resolution and reference validation
- **Validator**: Schema validation and security checks

### 2. Action Planning (ASSEMBLY)

```text
IR → Planner → Dependency Graph → ActionList (execution-ready)
```

**Key Components:**

- **Planner**: Converts declarative IR into imperative actions
- **Differ**: Compares desired vs current state for minimal changes

### 3. Artifact Generation (FORGE)

```text
ActionList → Compiler → [AI Agent] → ArtifactBundle → Executor → Results
```

**Key Components:**

- **Compiler**: Orchestrates artifact generation (with/without AI)
- **AgnoAgent**: AI-powered script generation via LM Studio
- **Executor**: Multi-environment artifact execution
- **StateManager**: Persistent state tracking and drift detection

## 🤖 AI Integration Architecture

### AI Agent Pipeline

```text
ActionList → Prompt Generation → LM Studio API → JSON Response → ArtifactBundle
```

**Components:**

- **LM Studio Client**: Direct HTTP integration with local LLM
- **Structured Output**: Pydantic models ensure type safety
- **Security Validation**: All AI-generated code undergoes security scanning
- **Graceful Fallback**: System remains functional without AI

### Supported Models

- **Primary**: `qwen/qwen3-4b-2507` (non-thinking model for clean JSON output)
- **Alternative**: `qwen/qwen3-4b-thinking-2507` (thinking model with filtering)

## 🛡️ Security Architecture

### Multi-Layer Security

1. **Input Validation**: HCL2 syntax and schema validation
2. **Runtime Restrictions**: Allowlisted executables and restricted paths
3. **AI Code Scanning**: Pattern detection for dangerous operations
4. **Sandbox Execution**: Isolated execution environments
5. **State Integrity**: Cryptographic state validation

### Security Zones

- **Development**: Relaxed validation, AI enabled, broad permissions
- **Production**: Strict validation, AI disabled, minimal permissions

## 📊 Performance Characteristics

### Pipeline Performance

- **INTAKE**: ~50ms (HCL2 parsing + validation)
- **ASSEMBLY**: ~100ms (dependency resolution + planning)
- **FORGE**: 1-30s (AI generation varies by complexity)

### Scalability

- **Parallel Execution**: Multi-threaded artifact execution
- **Resource Limits**: Configurable memory and CPU constraints
- **Caching**: Aggressive caching of parsed configs and resolved dependencies

## 🔌 Extension Points

### Plugin Architecture

- **Custom Runners**: Implement `Runner` interface for new execution environments
- **AI Providers**: Extend `AgnoAgent` for different LLM providers
- **Validators**: Add custom validation rules via `Validator` interface
- **State Backends**: Pluggable state storage (filesystem, database, cloud)

### Configuration

All components support:

- **Environment-specific configs**: Development, staging, production
- **Runtime overrides**: CLI arguments and environment variables
- **Hot reloading**: Configuration changes without restart

## 🚀 Deployment Patterns

### Local Development

```bash
clockwork --config configs/development.json compile examples/basic-web-service/main.cw
```

### Production Deployment

```bash
clockwork daemon --config configs/production.json --state-file /var/lib/clockwork/state.json
```

### CI/CD Integration

```bash
clockwork validate configs/ && clockwork plan --dry-run && clockwork apply
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
                                            │ 1) change detected / manual run
                                            ▼
┌──────────────────────────────────────────────────────────────────────────────────────────────┐
│                                        Intake                                                │
│  ┌─────────────────────────┐   ┌──────────────────────────┐   ┌───────────────────────────┐ │
│  │ Loader                  │   │ Linter & Schema Check    │   │ Module/Provider Resolver │ │
│  │ • reads .cw/.cwvars     │   │ • HCL schema + types     │   │ • resolves imports        │ │
│  │ • merges env/overrides  │   │ • required fields        │   │ • version pinning         │ │
│  └────────────┬────────────┘   └───────────┬──────────────┘   └──────────────┬────────────┘ │
│               │                            │                               (downloads/caches)│
│               └───────────────┬────────────┴───────────────────────────────────┬─────────────┘
│                               │                                                │
│                               ▼                                                ▼
│                         normalized .cw                                   provider metadata     │
└───────────────┬───────────────────────────────────────────────────────────────────────────────┘
                │ 2) parse/normalize
                ▼
┌──────────────────────────────────────────────────────────────────────────────────────────────┐
│                                      Assembly                                                │
│  ┌──────────────────────────┐   ┌──────────────────────────┐   ┌───────────────────────────┐ │
│  │ Parser (HCL → AST)       │   │ Validator                │   │ Model Builder             │ │
│  │ • tokens → AST           │   │ • cross-resource rules   │   │ • desired-state graph     │ │
│  │                          │   │ • references/expressions │   │ • deps & ordering         │ │
│  └────────────┬─────────────┘   └────────────┬─────────────┘   └──────────────┬────────────┘ │
│               │                               │                               │               │
│               ▼                               ▼                               ▼               │
│             AST                         validated AST                  Desired State Model     │
└───────────────┬───────────────────────────────────────────────────────────────────────────────┘
                │ 3) plan/execute
                ▼
┌──────────────────────────────────────────────────────────────────────────────────────────────┐
│                                          Forge                                               │
│                (Compiler + Executor fused; no separate IR file or handoff boundary)          │
│  ┌─────────────────────────┐   ┌─────────────────────────┐   ┌─────────────────────────────┐ │
│  │ Diff Engine             │   │ Planner                 │   │ Runners / Adapters          │ │
│  │ • Desired vs Observed   │   │ • action graph          │   │ • Docker / Podman           │ │
│  │   (from State)          │   │ • ordering + retries    │   │ • k8s (kind)                │ │
│  │ • computes drift (Δ)    │   │ • idempotency guards    │   │ • SSH / local exec          │ │
│  └────────────┬────────────┘   └────────────┬────────────┘   └──────────────┬──────────────┘ │
│               │                             │                              logs/metrics       │
│               ▼                             ▼                                  │              │
│         Change Set (Δ)             Executable Action Plan  ───────────────▶ Telemetry Sink    │
│                                                                                               │
│  ┌─────────────────────────┐                                                                │ │
│  │ State/Artifact Store    │  (SQLite/JSON; caches, lockfiles)                              │ │
│  │ • resource instances    │  • provider locks • action results • module build cache        │ │
│  └─────────────────────────┘                                                                │ │
└───────────────┬──────────────────────────────────────────────────────────────────────────────┘
                │ 4) run loop / reconcile
                ▼
┌──────────────────────────────────────────────────────────────────────────────────────────────┐
│                                         Daemon                                               │
│  • Watches repo/files/timers                                                                   │
│  • Triggers full cycle on change or drift                                                      │
│  • Patches .cw when needed (recording discovered values)                                       │
│                                                                                                │
│  Cycle it drives (each tick):                                                                  │
│    core.load  →  core.planrun  →  compile  →  execute                                          │
│        │               │                │          │                                           │
│        └───────────────┴────────────────┴──────────┴── updates State/Artifacts + Telemetry ─▶ │
│                                                                                                │
└───────────────┬────────────────────────────────────────────────────────────────────────────────┘
                │ 5) feedback
                │   (if Daemon wrote patches / drift found)
                └───────────────────────────────► back to **Intake** (start over with new .cw)
```

### Simple Pipeline (Without Daemon)

```text
                ┌─────────────── .cw (HCL) ────────────────┐
                │                                           │
                ▼                                           │
           ┌───────────┐        ┌───────────┐               │
           │  Intake   │  IR +  │ Assembly  │─── ActionList ─┘
           │ parse→IR  │  facts │ plan/diff │
           └─────┬─────┘        └─────┬─────┘
                 │                    │
                 ▼                    ▼
                           ┌──────────────────┐
                           │      Forge       │
                           │ compile + execute│
                           │ (validate bundle │
                           │  → write files   │
                           │  → run steps)    │
                           └──────┬───────────┘
                                  │
                         logs + manifest + state
                                  │
                                  ▼
                         .clockwork/{build,logs,state.json}
```

## 📋 Data Contracts

### ActionList (Assembly → Forge)

```json
{
  "version": "1",
  "steps": [
    {
      "name": "fetch_repo",
      "args": {
        "url": "https://github.com/user/myapp",
        "ref": "main"
      }
    },
    {
      "name": "build_image",
      "args": {
        "contextVar": "APP_WORKDIR",
        "tags": ["myapp:latest"]
      }
    },
    {
      "name": "ensure_service",
      "args": {
        "name": "myapp",
        "imageVar": "IMAGE_REF",
        "ports": [{"external": 8080, "internal": 8080}],
        "env": {"APP_ENV": "prod"},
        "logging": {
          "driver": "json-file",
          "opts": {"max-size": "10m", "max-file": "3"}
        }
      }
    },
    {
      "name": "verify_http",
      "args": {
        "url": "http://localhost:8080",
        "expect_status": 200
      }
    }
  ]
}
```

### ArtifactBundle (Forge ← Compiler Agent)

```json
{
  "version": "1",
  "artifacts": [
    {
      "path": "scripts/01_fetch_repo.sh",
      "mode": "0755",
      "purpose": "fetch_repo",
      "lang": "bash",
      "content": "..."
    },
    {
      "path": "scripts/02_build_image.py",
      "mode": "0755",
      "purpose": "build_image",
      "lang": "python",
      "content": "..."
    },
    {
      "path": "scripts/03_ensure_service.ts",
      "mode": "0644",
      "purpose": "ensure_service",
      "lang": "deno",
      "content": "..."
    },
    {
      "path": "scripts/90_verify_http.go",
      "mode": "0755",
      "purpose": "verify_http",
      "lang": "go",
      "content": "..."
    }
  ],
  "steps": [
    {
      "purpose": "fetch_repo",
      "run": {"cmd": ["bash", "scripts/01_fetch_repo.sh"]}
    },
    {
      "purpose": "build_image",
      "run": {"cmd": ["python3", "scripts/02_build_image.py"]}
    },
    {
      "purpose": "ensure_service",
      "run": {"cmd": ["deno", "run", "--allow-all", "scripts/03_ensure_service.ts"]}
    },
    {
      "purpose": "verify_http",
      "run": {"cmd": ["./scripts/90_verify_http.go"]}
    }
  ],
  "vars": {
    "REPO_URL": "https://github.com/user/myapp",
    "REPO_REF": "main",
    "TAG": "myapp:latest",
    "NAME": "myapp",
    "INTERNAL_PORT": 8080,
    "EXTERNAL_PORT": 8080,
    "URL": "http://localhost:8080"
  }
}
```

### Forge Validations

- Paths confined to `.clockwork/build/**`
- Allowlisted runtimes only (`bash`, `python3`, `deno`, `go build && run`, etc.)
- Every `steps[].purpose` matches an ActionList step
- Executable bits/shebang sanity; no writes outside allowed roots

## 🤖 Daemon Intelligence & Auto-Fix Policy

**Goal:** Keep long-running services healthy with the smallest safe change.

### Decision Rule

1. **Artifact-only patch** (preferred)
2. **.cw patch** (if desired state must change)
3. **Runbook** (manual step if risky)

### Default Policy

- **Auto-apply**: artifact patches to retries/healthchecks/logging
- **Require approval**: `.cw` changes to ports, mounts, privileges
- **Never auto**: destructive ops or secrets rotation → runbook
- **Budgets**: ≤2 auto-fixes/hour/task; cooldown after each fix

## 🏗️ Detailed Project Structure

```text
clockwork/
  intake/{loader,linter,resolver}.py
  assembly/{parser,validator,model}.py
  forge/{diff,planner,runner,state}.py
  daemon/loop.py
  core.py, config.py, cli.py
```

## 🎯 Design Rationale

This architecture keeps Clockwork small and intuitive. Intake, Assembly, and
Forge form a simple one-shot pipeline. Daemon is optional but powerful for
long-running services, patching `.cw` as needed. Everything remains
deterministic and user-editable, with clear separation between agent proposals
and core validation/execution.

This architecture provides a robust, secure, and extensible foundation for
intelligent task automation with clear separation of concerns and comprehensive
error handling.
