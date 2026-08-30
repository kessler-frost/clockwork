# Concepts

Shared domain vocabulary for this project — entities, named processes, and status concepts with project-specific meaning. Seeded with core domain vocabulary, then accretes as ce-compound and ce-compound-refresh process learnings; direct edits are fine. Glossary only, not a spec or catch-all.

## Clockwork Workbench

### Clockwork Workbench
The visual canvas surface where builders co-author and inspect Clockwork’s semantic model while source remains authoritative.
*Alias:* Clockwork UI

### Primitive
A typed model element that carries intent, resolution policy, semantic relationships, materialization behavior, observed state, and assertions as applicable.

### Semantic Relationship
A typed connection between Primitives whose domain meaning provides context for resolution, materialization, and observation.

### Composite Primitive
A Primitive that groups child Primitives behind one source-preserved identity and can expand or collapse without changing its semantic contract.

### Canvas Projection
A replaceable rendering of Clockwork primitives and semantic relationships combined with editor-owned position, selection, grouping, and viewport state. React Flow may implement this projection but never becomes the domain model.

### Clockwork Operation
A typed semantic mutation—such as creating, configuring, connecting, proposing, accepting, applying, rolling back, or reconciling—that carries validation, provenance, lifecycle, and domain-history effects regardless of whether a human or agent initiated it.

### Editor History
Undoable spatial and presentation changes such as movement, resize, selection, viewport, filtering, and visual grouping. Editor History does not mutate desired or observed state.

## Lifecycle

### Intent
The human-authored goals, fixed values, assertions, and permissions that define what Clockwork may resolve.

### Resolution
The deterministic and intelligence-assisted decisions that fill authorized uncertainty while retaining provenance, reasons, constraints, and rejected alternatives.

### Reality
The materialized and observed system state, including identifiers, health, endpoints, versions, assertion evidence, and drift.

### Scoped Proposal
A proposed change to a specific authorized field, Primitive, or subgraph that remains separate from desired state until policy or human acceptance.

### Provenance
The retained authorship and evidence that distinguishes specified, inferred, AI-resolved, observed, and drifted values.

### Desired State
The accepted semantic state Clockwork intends to materialize. It remains distinct from the last observed reality while work is pending or drift exists.

### Observed State
Evidence of current materialized reality, retained independently from authored and desired state.

### Clockwork Evolution
The domain history of authored, unresolved, proposed, accepted, planned, applied, observed, drifted, recovered, and reconciled transitions. It survives independently of canvas implementation and Editor History.

## Relationships

Intent constrains Resolution; accepted Resolution defines desired state; Reality records what materialized; assertions compare Reality with Intent; reconciliation preserves the evidence connecting all three.
