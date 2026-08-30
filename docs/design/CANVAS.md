# Clockwork Canvas Specification

Status: normative for production spatial-canvas work.

## Contract

React Flow owns spatial interaction. Clockwork owns the graph's meaning.

The production canvas consumes a projection shaped from two independent inputs:

```text
Clockwork semantic state ─┐
                          ├─ projection adapter ─ React Flow nodes and edges
Editor spatial state ─────┘
```

Semantic state includes primitive identity, type, hierarchy, relationships, lifecycle, proposals, desired and observed values, assertions, provenance, and drift. Editor state includes positions, dimensions, selection, viewport, grouping presentation, expanded/collapsed presentation, filters, and focus lens.

A React Flow `Node` or `Edge` is disposable rendering data. Deleting the canvas adapter must not delete or make it impossible to reconstruct the Clockwork model.

## Ownership boundary

| Concern | Owner |
|---|---|
| primitive and relationship identity | Clockwork model |
| relationship kind and validity | Clockwork model |
| hierarchy and composite membership | Clockwork model |
| proposal, lifecycle, provenance, desired/observed state | Clockwork model |
| position, size, selection, zoom, pan, viewport | editor / React Flow adapter |
| node, edge, handle, overlay rendering | React Flow components using `@clockwork` primitives |
| drag/connect callbacks | React Flow adapter translating to editor actions or Clockwork operations |
| domain and proposal history | Clockwork operations |
| spatial undo/redo | editor history |

## Projection pipeline

1. Select semantic facts from the Clockwork model.
2. Select positions and presentation state from editor state.
3. Project primitives into React Flow nodes keyed by the Clockwork primitive ID.
4. Project semantic relationships into one or more rendered lanes keyed back to one Clockwork relationship ID.
5. Render through canonical `@clockwork/primitive` and `@clockwork/semantic-edge` components.
6. Translate canvas callbacks into either editor actions or typed Clockwork operations.
7. Re-project after the authoritative owner changes.

Do not write business rules inside node renderers, edge renderers, or `onConnect`/`onNodesChange` callbacks.

### Identity and mapping

- A rendered node retains `primitiveId`; its React Flow ID may equal that value but must not replace it.
- A rendered edge retains `relationshipId` and its semantic family.
- One relationship may produce multiple rendered lanes. Every lane maps back to the same semantic relationship where appropriate.
- A collapsed composite may replace several child nodes with one summary node without changing child identity or external relationships.
- Projection is deterministic for the same model and editor state.

## Callback classification

Every canvas callback is classified before it mutates state.

| Interaction | Classification | Result |
|---|---|---|
| move or resize node | editor action | update spatial state and editor history |
| select node/edge | editor action | update selection; no domain event |
| pan, zoom, fit | editor action | update viewport state |
| toggle semantic family | editor action | update projection filter; semantic relationship remains |
| expand/collapse composite | editor presentation action | preserve domain hierarchy; update presentation and spatial context |
| connect compatible handles | Clockwork operation | dispatch `ConnectPrimitives` after semantic validation |
| disconnect relationship | Clockwork operation | dispatch `DisconnectPrimitives` |
| create/delete/configure primitive | Clockwork operation | validate, record evolution, then re-project |
| accept/reject proposed node or edge | Clockwork operation | update proposal/lifecycle state, then re-project |

React Flow's `addEdge` and analogous helpers may build a temporary projection value. They must not be the authoritative relationship mutation.

## Semantic relationships

Relationships are domain records rendered through edge families. Initial canonical families are:

```text
dependency
request / call
data flow
storage
event
job
containment
ownership
deployment
proposal
unresolved relationship
drift / violated expectation
```

Each family defines:

- valid source and target capabilities;
- directionality and cardinality;
- domain label and evidence;
- canonical handle classes;
- canonical edge treatment;
- validation and operation semantics;
- proposed, active, unresolved, and drift variants.

The visual grammar starts from:

```text
──────      dependency
━━━▶        active flow
┄┄┄┄▶       proposed relationship
════▶       confirmed active relationship
- - -       unresolved relationship
⚠════       drift or violated expectation
```

These are semantic patterns, not literal ASCII styling requirements. Color supplements shape, pattern, direction, labels, and status marks.

### Handles

A handle represents a semantic capability or relationship class, not a generic source/target dot.

- Its accessible name states the capability and direction.
- Compatibility derives from the Clockwork relationship model.
- Invalid drops produce a deterministic validation result and leave the graph unchanged.
- A successful drag dispatches a Clockwork operation containing primitive IDs and relationship semantics, never screen coordinates.
- Keyboard users receive an equivalent connect flow through commands or a structured relation form.

## Composite primitives

Hierarchy belongs to Clockwork. React Flow renders it.

An expanded composite shows its children and internal semantic relationships inside a spatial group. A collapsed composite shows one semantic summary with:

- composite identity and type;
- child count;
- health and assertion summary;
- unresolved and proposal counts;
- external semantic handles;
- lifecycle and drift status.

Expansion and collapse must:

1. preserve every child and relationship ID;
2. preserve external relationship meaning and attachment;
3. restore stable child positions when re-expanded;
4. keep selection coherent if the selected child becomes hidden;
5. avoid recording a domain lifecycle event for presentation-only disclosure.

Creating, deleting, or reparenting a child is a domain operation and therefore is not equivalent to visual grouping.

## Editor history and Clockwork evolution

The two histories are independent.

### Editor history

Records presentation changes:

- node movement and resize;
- visual grouping and composite disclosure;
- selection and focus lens;
- viewport and canvas organization;
- filter and plane presentation where restoration is useful.

Editor undo/redo must not accept/reject proposals, change desired state, or roll back execution.

### Clockwork evolution

Records meaningful transitions, including:

```text
authored → unresolved → proposed → accepted → planned → applied
         → observed → drifted / failed → recovered → reconciled
```

It includes operation, actor, provenance, affected semantic IDs, validation result, before/after domain facts, execution evidence, and lifecycle outcome as applicable.

Moving a primitive from `(300, 140)` to `(420, 140)` is editor history. Changing desired replicas from 3 to 5, accepting that proposal, applying it, and observing 5 is Clockwork evolution.

## Selection, focus, and filters

- Selection changes context; it does not mutate the domain.
- Focus raises the selected primitive and its connected semantic neighborhood while unrelated context remains visible but quiet.
- Semantic-family filters hide projections without deleting relationships or rearranging topology.
- Intent / Resolution / Reality lenses change visible evidence, not positions.
- The mini-map or viewport locator, fit, pan/zoom, source inspection, and visible focus remain available.
- Reset restores the documented editor snapshot and cancels pending presentation work without rewriting Clockwork evolution.

The approved three-level edge-readability model remains: stable railway geometry, local semantic focus, and overload filtering.

## Proposed and changing state

Proposed primitives and relationships remain separate from authored/desired state until accepted. They use the proposal treatment from `DESIGN.md` and preserve the proposed operation and provenance.

During apply/observe/reconcile transitions:

- topology changes only when the accepted semantic operation changes topology;
- last observed state remains visible until a new observation arrives;
- affected primitives and relationships expose bounded progress;
- drift names the violated desired-versus-observed expectation;
- recovery fixes the underlying model or reality rather than hiding evidence.

## Acceptance gates

A production canvas change is incomplete unless the affected behavior proves:

1. serialization or model inspection contains no React Flow node/edge objects as canonical semantics;
2. human and agent-originated semantic changes reach the same operation handler;
3. moving, selecting, filtering, zooming, or collapsing does not create a domain evolution event;
4. semantic connect/disconnect validates and records history before the projection settles;
5. proposal, unresolved, desired, observed, drift, and health treatments remain distinguishable without color alone;
6. composite collapse/expand preserves identity, relationships, and spatial context;
7. keyboard and screen-reader users can inspect and create relationships without drag gestures;
8. reduced motion preserves causality and final state;
9. changing the projection does not require changing the Clockwork model contract;
10. the visible behavior remains consistent with the approved Hybrid Workbench direction.
