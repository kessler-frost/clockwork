# Clockwork – Minimal Architecture Plan (v0)

**Goal:** Ultra-simple, agent-assisted infra tool. Deterministic core; one intelligent compiler agent that emits runnable artifacts (scripts/programs) in any language. Daemon optional for continuous reconcile.

---

## North Star

- **Simplicity first**: single-pass run; optional daemon for long-running reconcile.
- **Deterministic core**: Intake → Assembly → Forge.
- **User-editable artifacts**: everything materialized to disk.
- **Strict boundaries**: agent proposes; core validates & executes.

---

## System Overview (4 Components)

1. **Intake**\
   Parses `.cw` (HCL-ish) → JSON → validates into **IR** (Pydantic). Resolves refs, fills defaults. Outputs `IR` + `EnvFacts`.

2. **Assembly**\
   Deterministically computes an **ActionList** (ordered steps) from IR. Handles diffs vs observed state.

3. **Forge**\
   Calls the **Compiler Agent** once to produce an **ArtifactBundle**. Writes artifacts to `.clockwork/build/**`, validates, then executes steps with logging/timeouts. Persists `state.json`.

4. **Daemon** (optional)\
   Watches services/drift. Proposes smallest safe change → applies patch (`artifact` preferred, `.cw` if needed, runbook if risky) → re-runs the Intake → Assembly → Forge pipeline.

---

## ASCII Architecture

```
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

### With Daemon

```
                   ┌──────────────────────────────────────────┐
                   │                 Daemon                   │
                   │  watch health/drift                     │
                   │  diagnose → propose smallest safe change│
                   │  (artifact patch | .cw patch | runbook) │
                   │  apply .cw patch if allowed             │
                   │  trigger one-shot pipeline              │
                   └───────────────┬─────────────────────────┘
                                   │
                                   ▼
.cw ─▶ Intake ─▶ Assembly ─▶ Forge (compile→validate→execute) ─▶ state
```

---

## Data Contracts (Tiny & Strict)

### A) ActionList (Assembly → Forge)

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

### B) ArtifactBundle (Forge ← Compiler Agent)

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

**Forge validations**

- Paths confined to `.clockwork/build/**`.
- Allowlisted runtimes only (`bash`, `python3`, `deno`, `go build && run`, etc.).
- Every `steps[].purpose` matches an ActionList step.
- Executable bits/shebang sanity; no writes outside allowed roots.

---

## CLI (minimal)

- `clockwork plan`   → print ActionList (no agent call)
- `clockwork build`  → call agent; write `.clockwork/build/**` (no execute)
- `clockwork apply`  → build if needed; execute steps sequentially
- `clockwork verify` → run only verify steps

Flags: `--var KEY=VAL`, `--timeout-per-step`, `--force`.

---

## Daemon Intelligence & Auto-Fix Policy

**Goal:** Keep long-running services healthy with the smallest safe change.

**Decision Rule**

1. **Artifact-only patch** (preferred)
2. **.cw patch** (if desired state must change)
3. **Runbook** (manual step if risky)

**Default Policy**

- Auto-apply: artifact patches to retries/healthchecks/logging
- Require approval: `.cw` changes to ports, mounts, privileges
- Never auto: destructive ops or secrets rotation → runbook
- Budgets: ≤2 auto-fixes/hour/task; cooldown after each fix

---

## Next Steps (dev checklist)

1. Implement **Intake**: HCL→JSON→Pydantic IR + error reporting.
2. Implement **Assembly**: ActionList, simple diff logic.
3. Implement **Forge**: call Compiler Agent, validate, execute.
4. Define JSON Schemas for ActionList & ArtifactBundle.
5. Wire **Compiler Agent** (Agno) in `compile` mode.
6. Add CLI commands + state/logging basics.
7. (Later) add Daemon reconcile loop with patch policies.

---

## Rationale

This version keeps Clockwork small and intuitive. Intake, Assembly, and Forge form a simple one-shot pipeline. Daemon is optional but powerful for long-running services, patching `.cw` as needed. Everything remains deterministic and user-editable.

