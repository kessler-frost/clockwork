# Clockwork - Factory of Intelligent Declarative Tasks

**Factory of intelligent declarative tasks with deterministic core and AI-powered compiler that generates executable artifacts in any language.**

## Overview

Clockwork is a factory for building intelligent declarative tasks, designed with simplicity first. It features a deterministic core pipeline (Intake → Assembly → Forge) with optional daemon for continuous reconciliation. All artifacts are materialized to disk and user-editable, with strict boundaries where agents propose and the core validates & executes. Start with infrastructure tasks, expand to any domain.

### North Star Principles

- **Simplicity first**: single-pass run; optional daemon for long-running reconcile
- **Deterministic core**: Intake → Assembly → Forge pipeline
- **User-editable artifacts**: everything materialized to disk
- **Strict boundaries**: agent proposes; core validates & executes

## Architecture

### System Components

The system consists of 4 main components:

1. **Intake**
   - Parses `.cw` (HCL-ish) → JSON → validates into **IR** (Pydantic)
   - Resolves references, fills defaults
   - Outputs `IR` + `EnvFacts`

2. **Assembly**
   - Deterministically computes an **ActionList** (ordered steps) from IR
   - Handles diffs vs observed state
   - Builds desired-state graph with dependencies & ordering

3. **Forge**
   - Calls the **Compiler Agent** once to produce an **ArtifactBundle**
   - Writes artifacts to `.clockwork/build/**`
   - Validates and executes steps with logging/timeouts
   - Persists `state.json`

4. **Daemon** (optional)
   - Watches services/drift
   - Proposes smallest safe change → applies patch
   - Re-runs the Intake → Assembly → Forge pipeline

### Architecture Flow

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

## Data Contracts

### ActionList (Assembly → Forge)

```json
{
  "version": "1",
  "steps": [
    {"name": "fetch_repo",   "args": {"url": "https://github.com/user/myapp", "ref": "main"}},
    {"name": "build_image",  "args": {"contextVar": "APP_WORKDIR", "tags": ["myapp:latest"]}},
    {"name": "ensure_service","args": {
      "name":"myapp","imageVar":"IMAGE_REF",
      "ports":[{"external":8080,"internal":8080}],
      "env":{"APP_ENV":"prod"},
      "logging":{"driver":"json-file","opts":{"max-size":"10m","max-file":"3"}}
    }},
    {"name": "verify_http",  "args": {"url": "http://localhost:8080", "expect_status": 200}}
  ]
}
```

### ArtifactBundle (Forge ← Compiler Agent)

```json
{
  "version": "1",
  "artifacts": [
    {"path":"scripts/01_fetch_repo.sh","mode":"0755","purpose":"fetch_repo","lang":"bash","content":"..."},
    {"path":"scripts/02_build_image.py","mode":"0755","purpose":"build_image","lang":"python","content":"..."},
    {"path":"scripts/03_ensure_service.ts","mode":"0644","purpose":"ensure_service","lang":"deno","content":"..."},
    {"path":"scripts/90_verify_http.go","mode":"0755","purpose":"verify_http","lang":"go","content":"..."}
  ],
  "steps": [
    {"purpose":"fetch_repo",   "run":{"cmd":["bash","scripts/01_fetch_repo.sh"]}},
    {"purpose":"build_image",  "run":{"cmd":["python3","scripts/02_build_image.py"]}},
    {"purpose":"ensure_service","run":{"cmd":["deno","run","--allow-all","scripts/03_ensure_service.ts"]}},
    {"purpose":"verify_http",  "run":{"cmd":["./scripts/90_verify_http.go"]}}
  ],
  "vars": {
    "REPO_URL":"https://github.com/user/myapp","REPO_REF":"main",
    "TAG":"myapp:latest","NAME":"myapp",
    "INTERNAL_PORT":8080,"EXTERNAL_PORT":8080,
    "URL":"http://localhost:8080"
  }
}
```

### Forge Validations

- Paths confined to `.clockwork/build/**`
- Allowlisted runtimes only (`bash`, `python3`, `deno`, `go build && run`, etc.)
- Every `steps[].purpose` matches an ActionList step
- Executable bits/shebang sanity; no writes outside allowed roots

## CLI Commands

- `clockwork plan`   → print ActionList (no agent call)
- `clockwork build`  → call agent; write `.clockwork/build/**` (no execute)
- `clockwork apply`  → build if needed; execute steps sequentially
- `clockwork verify` → run only verify steps

### Flags

- `--var KEY=VAL`
- `--timeout-per-step`
- `--force`

## Daemon Intelligence & Auto-Fix Policy

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

## Project Structure

```text
clockwork/
  intake/{loader,linter,resolver}.py
  assembly/{parser,validator,model}.py
  forge/{diff,planner,runner,state}.py
  daemon/loop.py
  core.py, config.py, cli.py
```

## Development Checklist

1. Implement **Intake**: HCL→JSON→Pydantic IR + error reporting
2. Implement **Assembly**: ActionList, simple diff logic
3. Implement **Forge**: call Compiler Agent, validate, execute
4. Define JSON Schemas for ActionList & ArtifactBundle
5. Wire **Compiler Agent** (Agno) in `compile` mode
6. Add CLI commands + state/logging basics
7. (Later) add Daemon reconcile loop with patch policies

## Rationale

This architecture keeps Clockwork small and intuitive. Intake, Assembly, and Forge form a simple one-shot pipeline. Daemon is optional but powerful for long-running services, patching `.cw` as needed. Everything remains deterministic and user-editable, with clear separation between agent proposals and core validation/execution.
