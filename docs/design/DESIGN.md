# Clockwork Frontend and Design Architecture

Status: normative for production Clockwork Workbench work.

This specification turns the approved Workbench prototype direction into a production architecture. The prototype contract remains the visual and interaction reference; this directory owns the production boundaries.

## Governing rule

> **shadcn owns the component ecosystem. React Flow owns spatial interaction. Clockwork owns everything semantic.**

Clockwork is the semantic system. React Flow makes it spatial. shadcn makes it coherent.

The dependency direction is one-way:

```text
Clockwork model
    ↓ typed Clockwork operations and projections
React application
    ├── @clockwork design system
    │   └── shadcn + Base UI
    └── canvas adapter
        └── React Flow
    ↓
proposals, execution, and observed state
```

React Flow nodes and edges are projections of Clockwork state. They are never the canonical primitive or relationship records.

## Specification map

- [`DESIGN.md`](DESIGN.md): stack, visual language, component system, workbench anatomy, and repository boundaries.
- [`CANVAS.md`](CANVAS.md): projection, spatial ownership, relationships, composites, and editor history.
- [`INTERACTIONS.md`](INTERACTIONS.md): typed operations, human/agent convergence, proposals, inspector behavior, and feedback.
- [`MOTION.md`](MOTION.md): semantic motion tokens and transition choreography.
- [`ACCESSIBILITY.md`](ACCESSIBILITY.md): keyboard, focus, state communication, and canvas alternatives.
- [`../solutions/design-patterns/clockwork-workbench-prototype-direction.md`](../solutions/design-patterns/clockwork-workbench-prototype-direction.md): approved Hybrid Workbench visual direction and prototype behavior.

When documents appear to conflict, `PRODUCT.md` owns product semantics, these design specifications own the production frontend boundary, and the prototype-direction document owns the approved visual composition.

## Layer ownership

| Layer | Owns | Must not own |
|---|---|---|
| Clockwork model | primitive identity and type, hierarchy, semantic relationships, intent, resolution, desired and observed state, lifecycle, provenance, assertions | pixels, selection, zoom, component state |
| Clockwork operations | validation, proposal policy, execution, history, provenance, lifecycle transitions | React callbacks, React Flow mutations |
| React application | routing, composition, workbench state, data loading, operation dispatch | alternate domain mutation paths |
| `@clockwork` design system | tokens, semantic components, interaction patterns, state grammar | domain persistence or canvas geometry |
| shadcn + Base UI | component distribution, accessible low-level behavior, composable UI primitives | finished Clockwork visual identity or domain semantics |
| React Flow | position, selection, dragging, handles, connections, viewport, zoom/pan, grouping, node/edge rendering | canonical primitives, relationships, lifecycle, proposal acceptance |

## Production stack

- **Application:** React.
- **Component infrastructure:** shadcn.
- **Accessible interaction primitives:** Base UI.
- **Styling and tokens:** CSS variables through the existing styling stack.
- **Spatial canvas:** React Flow / xyflow with custom nodes, edges, handles, overlays, and grouping.
- **Semantics:** Clockwork primitives, relationships, lifecycle, provenance, desired/observed state, and assertions.
- **Mutations:** typed Clockwork operations shared by human and agent actions.

A library boundary is justified by ownership, not by a folder name. Do not split every component into a package prematurely; preserve the namespaces below as stable design-system identities while package topology evolves.

## Clockwork design system

shadcn is infrastructure, not the finished aesthetic. Application code should progressively depend on first-party Clockwork components rather than repeatedly composing generic cards, badges, and tooltips.

Canonical component identities include:

```text
@clockwork/button
@clockwork/input
@clockwork/menu
@clockwork/inspector
@clockwork/workbench
@clockwork/status
@clockwork/proposal
@clockwork/primitive
@clockwork/semantic-edge
@clockwork/history
```

Promote a composition when it carries recurring Clockwork semantics or interaction behavior. Keep one-off layout local. A repeated visual arrangement without a stable semantic contract is not yet a primitive.

### Token families

All visual values flow through CSS variables and these semantic families:

```text
color       surface, text, border, action, selection, lifecycle, provenance, health, drift
 typography display, UI, data/evidence, source
spacing     4px base rhythm with named density steps
radius      control, panel, primitive, overlay
 elevation   canvas, panel, overlay, focused primitive
motion      immediate, control, disclosure, state transition, reconciliation
```

Components consume semantic tokens such as `--color-state-proposed`, not raw palette values. Dark mode is the current approved Workbench default. New themes must preserve semantic contrast rather than remapping by appearance alone.

## Semantic visual grammar

The interface must distinguish these states without requiring raw metadata inspection:

- authored / generated;
- desired / observed;
- accepted / proposed;
- healthy / drifting;
- known / unresolved;
- static / changing;
- user-authored / agent-authored;
- pending / applying / applied.

Every state treatment uses at least two channels where confusion would be consequential: color plus border, icon, label, pattern, opacity, or motion. Color never carries the distinction alone.

| Semantic state | Canonical treatment |
|---|---|
| Authored | solid canonical surface and border; authorship available in provenance |
| Generated or agent-authored | canonical structure plus explicit provenance mark; never an undifferentiated “AI” badge |
| Proposed | dashed or ghost boundary, proposal accent, explicit accept/reject affordances; remains distinct from desired state |
| Accepted / desired | solid intent treatment; observed value remains independently visible until observation converges |
| Applying | bounded transition indicator tied to the affected primitive or relationship |
| Observed healthy | observation treatment and evidence; does not overwrite authorship |
| Drifted | warning pattern/icon and the desired-versus-observed difference |
| Unresolved | incomplete boundary or unresolved marker with the missing decision exposed |
| Error | error treatment with cause, affected scope, and recovery action |

Proposed relationships use the proposal edge family defined in `CANVAS.md`; acceptance transitions them to the canonical relationship family without changing semantic identity.

## Primitive anatomy

All primitive types share a stable anatomy. Type-specific content may vary inside the named regions.

```text
┌──────────────────────────────────┐
│ identity + type          health  │
│ source identity / intent         │
│                                  │
│ configuration summary            │
│ desired ↔ observed state         │
│ resolution / assertion status    │
│                                  │
│ proposal or transition surface   │
└──────────────────────────────────┘
     semantic handles + actions
```

A canonical primitive provides:

1. identity and type;
2. health and lifecycle state;
3. configuration summary;
4. resolution status;
5. desired and observed state without conflation;
6. provenance entry point;
7. proposal state and review actions;
8. semantic handles;
9. context actions;
10. visible selection and keyboard focus.

Do not invent a completely different node structure for each resource. Diverge only when the underlying semantic contract differs.

## Workbench composition

Clockwork Workbench is a dense authoring instrument, not a dashboard.

```text
┌─────────────────────────────────────────────────────────────┐
│ Toolbar / commands / context                               │
├──────────────┬─────────────────────────────┬────────────────┤
│ Navigator    │                             │ Inspector      │
│ hierarchy    │          Canvas             │ Model          │
│ resources    │                             │ State          │
│ search       │                             │ Source         │
│              │                             │ History        │
│              │                             │ Provenance     │
├──────────────┴─────────────────────────────┴────────────────┤
│ Evolution / history / status / operations                  │
└─────────────────────────────────────────────────────────────┘
```

The canvas is the primary spatial surface. Navigator, Inspector, Source, History, and the lifecycle shelf are semantic projections over the same Clockwork state. They do not maintain competing copies.

### Inspector grammar

Every primitive inspector uses the same primary sections:

- **Model:** authored intent and configuration;
- **State:** desired, resolved, and observed values with differences;
- **Source:** inspectable source representation and location;
- **History:** meaningful domain evolution;
- **Provenance:** authorship, reasons, constraints, evidence, and rejected alternatives.

Primitive-specific fields may vary. Section meaning and state comparison do not.

## Target repository architecture

```text
packages/
├── model/
│   ├── primitives/
│   ├── relationships/
│   ├── lifecycle/
│   ├── provenance/
│   ├── assertions/
│   └── state/
├── operations/
│   ├── commands/
│   ├── validation/
│   ├── proposals/
│   ├── execution/
│   └── history/
├── design/
│   ├── tokens/
│   ├── primitives/
│   ├── patterns/
│   └── registry/
├── canvas/
│   ├── adapter/
│   ├── nodes/
│   ├── edges/
│   ├── handles/
│   ├── overlays/
│   ├── grouping/
│   ├── layout/
│   └── editor-history/
└── workbench/
    ├── shell/
    ├── navigator/
    ├── canvas/
    ├── inspector/
    ├── source/
    ├── history/
    ├── provenance/
    ├── commands/
    └── status/

apps/
└── workbench/
```

This is the ownership map, not an instruction to create empty packages. Introduce a boundary when production code needs it; do not scaffold placeholders.

## Implementation workflow

For a new interface behavior:

1. read this specification and the focused document for the affected behavior;
2. find an existing `@clockwork` primitive or pattern;
3. use the shadcn registry search interface only when no Clockwork primitive fits;
4. compose or extend through Base UI behavior and Clockwork tokens;
5. translate meaningful interaction into a typed Clockwork operation;
6. project the resulting model into React Flow;
7. promote the result into `@clockwork` only when its semantic contract recurs;
8. verify visible behavior, keyboard behavior, reduced motion, and semantic-state legibility.

## Architectural invariants

1. Clockwork owns primitive, relationship, hierarchy, lifecycle, provenance, proposal, desired-state, observed-state, assertion, and execution semantics.
2. React Flow is a replaceable renderer and interaction adapter.
3. shadcn and Base UI are infrastructure; Clockwork tokens and components define the product identity.
4. Meaningful mutations pass through typed Clockwork operations.
5. Human and agent actions share validation, provenance, proposal, and history pathways.
6. Domain evolution is independent of editor undo/redo.
7. Semantic state is visible through canonical, accessible treatments.
8. Repeated semantic patterns become first-party Clockwork primitives; repeated markup alone does not.
9. Source, canvas, inspector, history, and lifecycle surfaces are projections of one semantic model.
10. Canvas coordinates never become application intent.
