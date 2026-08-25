---
title: Preserving the Clockwork Workbench Prototype Direction
date: 2026-08-24
category: design-patterns
module: clockwork-workbench
problem_type: design_pattern
component: frontend
severity: medium
applies_when:
  - regenerating or extending Clockwork Workbench canvas prototypes
  - comparing multiple visual directions against one product contract
  - presenting dense semantic graphs with intent, resolution, and runtime evidence
tags:
  - clockwork-workbench
  - stateful-canvas
  - semantic-graph
  - visual-prototyping
  - lifecycle-design
---

# Preserving the Clockwork Workbench Prototype Direction

## Context

The approved direction now has one recommended **Hybrid Workbench** plus two complete dark references: **Precision Workbench** and **Motion Compiler**. Hybrid uses Precision as the persistent operating shell and Motion as the lifecycle/evidence and physical-feedback source while all three surfaces expose the same Clockwork premise and lifecycle. The tracked surfaces are selected in `prototypes/clockwork-workbench/401-working-gallery.html`.

Clockwork Workbench is a visual co-author, not a read-only operations dashboard. Python/Pydantic remains the inspectable source of truth; visual and source edits converge on one semantic model, and intent, resolution, and reality remain separately inspectable (`PRODUCT.md:25-40`). This means a prototype must demonstrate source-backed intent, scoped authorization, provenance-bearing resolution, deterministic planning/application, observed evidence, assertions, drift, and recovery—not merely arrange attractive nodes (`docs/plans/2026-08-24-0455-feat-clockwork-stateful-canvas-prototypes-plan.md:29-44`).

The canonical comparison contract is:

- Hybrid, Precision, and Motion default to dark mode and expose the same capabilities, canonical fixture, lifecycle, history counts, and recoverable failure (`docs/plans/2026-08-24-0455-feat-clockwork-stateful-canvas-prototypes-plan.md:53-91`);
- the scenario contains six application primitives—Frontend, Photo API composite, PostgreSQL database, Media store, Image jobs queue, and Processor worker—shown in all three implementations;
- the contract calls for seven typed semantic relationships and four filterable relation families: Calls, Data, Storage, and Jobs (`docs/plans/2026-08-24-0455-feat-clockwork-stateful-canvas-prototypes-plan.md:57-65`);
- every alternative owns an exact 1280×720 internal artboard; the gallery places its iframe in a 1152×648 wrapper using `scale(.9)`, so alternatives are compared at 90% rather than auto-fit independently (`prototypes/clockwork-workbench/401-working-gallery.html:11-11`, `prototypes/clockwork-workbench/401-working-gallery.html:23-25`);
- first/second-iteration polish is the minimum acceptable finish. These are products to judge, not direction boards (`docs/plans/2026-08-24-0455-feat-clockwork-stateful-canvas-prototypes-plan.md:41-45`).

The shared model carries seven semantic relations. Precision maps the API→database semantic relation to two separately labeled railway lanes (`reads` and `writes`) using one `data-relation-id`, while Motion renders the same relation as one `reads + writes` edge. The mapping is explicit in `prototypes/clockwork-workbench/410-precision-working.html:178-187` and `prototypes/clockwork-workbench/420-motion-working.html:939-947`.

The canvas renderer is a projection rather than the source of truth: visual placement may change, but semantic identity, provenance, authorization, and lifecycle remain owned by Clockwork’s inspectable model (`PRODUCT.md:31-41`).

## Guidance

### 1. Start from the shared product contract, then fork only the visual grammar

Build or update one scenario/state specification before styling either alternative. Keep these invariant across both:

1. the same six primitive identities and source locations;
2. the same selected starting node, `DB-03 db.primary`;
3. the same Intent / Resolution / Reality projections;
4. the same lifecycle stages and evidence facts;
5. the same backup-window drift and recovery;
6. overview, contextual selection, semantic lens/focus, source inspection, composite expansion, plane filtering, pan/zoom/fit, and mini-map/viewport location;
7. meaningful hover, focus, active, disabled, pending, success, and error states.

The invariant mechanism is explicit in the requirements (`docs/plans/2026-08-24-0455-feat-clockwork-stateful-canvas-prototypes-plan.md:55-90`). The divergence belongs in chrome, hierarchy, interaction rhythm, spatial framing, and motion—not feature completeness or zoom (`docs/plans/2026-08-24-0455-feat-clockwork-stateful-canvas-prototypes-plan.md:144-151`).

Keep the graph source-derived. A user may move primitives spatially, but pixels never become the semantic source of truth. This follows Clockwork’s requirement that the UI not introduce an opaque diagram-only model or make manual diagram composition mandatory (`PRODUCT.md:31-43`).

### 2. Use the hybrid edge-readability model at three density levels

The chosen solution is a hybrid because no single mechanism solves every density level. Apply all three layers together:

- **Stable railway geometry:** draw orthogonal trunks with separated lanes, explicit bend/switch marks, under-strokes that cut through crossings, direction arrows, and labels at meaningful merges or splits. The contract is at `docs/plans/2026-08-24-0455-feat-clockwork-stateful-canvas-prototypes-plan.md:61-65`; Precision’s route primitives are styled at `prototypes/clockwork-workbench/410-precision-working.html:80-82`, and Motion’s are styled at `prototypes/clockwork-workbench/420-motion-working.html:323-336`.
- **Local focus:** selection raises the chosen primitive and its directly connected neighborhood to full contrast while unrelated nodes/routes remain visible but quiet. Never rearrange topology just to focus. Precision applies selected/neighbor/unrelated and edge quieting in `prototypes/clockwork-workbench/410-precision-working.html:270-288`; Motion computes the same neighborhood in `prototypes/clockwork-workbench/420-motion-working.html:1126-1134`.
- **Overload filtering:** Calls, Data, Storage, and Jobs toggle independently without moving nodes. Hidden relationships still report how many routes/nodes are affected. Precision toggles route visibility and count copy at `prototypes/clockwork-workbench/410-precision-working.html:313-315`; Motion retains a hidden-effects count at `prototypes/clockwork-workbench/420-motion-working.html:1291-1298`.

Focus mode is a semantic lens over the stable overview, not a replacement canvas. Evidence projections similarly change what nodes and inspectors say without changing positions (`docs/plans/2026-08-24-0455-feat-clockwork-stateful-canvas-prototypes-plan.md:67-72`).

### 3. Preserve the complete intent-to-reality lifecycle

Use this exact state progression:

`authored → unresolved → proposed → accepted → planned → applied → observed → failed → recovered → reconciled`

The action chain is:

`reopen → resolve → accept → plan → apply → observe → assert → recover → retry`

Hybrid, Precision, and Motion encode the same transition order. Hybrid’s fact snapshot is authoritative for the comparison; Precision and Motion normalize their visible proposal/update history to it (`prototypes/clockwork-workbench/430-hybrid-workbench.html`, `prototypes/clockwork-workbench/410-precision-working.html:215-229`, `prototypes/clockwork-workbench/420-motion-working.html:949-1036`).

- **Authored:** PostgreSQL 18 is explicit; observed runtime is independently 18.6.
- **Unresolved:** only `db.primary.major_version` is reopened and authorized for resolution; topology and current reality remain unchanged.
- **Proposed:** PostgreSQL 19 carries scoped AI provenance and a reason; PostgreSQL 18 remains retained context, and SQLite is an explicit rejected alternative because it conflicts with the engine/durability contract.
- **Accepted:** desired intent becomes 19, but runtime remains 18.6.
- **Planned:** one bounded deterministic update targets DB-03. The topology still does not move.
- **Applied:** desired state is 19; the last observed value is still 18.6 until Observe runs.
- **Observed:** runtime reaches 19.0, while backup time is observed at 03:20 versus intended 03:00.
- **Failed:** reachability and PostgreSQL-engine assertions pass; backup-window assertion fails.
- **Recovered:** correct the underlying observed schedule to 03:00. Do not hide, weaken, or suppress the assertion.
- **Reconciled:** runtime 19.0 and backup 03:00 satisfy all three assertions while the authored intent, accepted resolution, rejected alternative, and observed evidence remain inspectable.

Precision’s exact state facts are at `prototypes/clockwork-workbench/410-precision-working.html:216-225`; Motion’s expanded evidence copy is at `prototypes/clockwork-workbench/420-motion-working.html:949-1029`. Pending time belongs to resolver/plan/apply/observe/assert/retry work, while keyboard/high-frequency actions should be immediate; reduced-motion users receive a non-spatial fallback (`docs/plans/2026-08-24-0455-feat-clockwork-stateful-canvas-prototypes-plan.md:83-90`).

### 4. Keep each alternative’s visual grammar distinct

#### Hybrid Workbench: Precision shell, Motion lifecycle depth

Hybrid is the recommended composition. Precision owns the persistent resource tree, command and keyboard layer, semantic canvas, contextual Model/State/Source inspector, source drawer, node coordinates, and railway routing. Motion contributes one contiguous lower lifecycle/evidence shelf, copper authorization, sage observation/reconciliation, and physical feedback on disclosure and non-geometric descendants (`prototypes/clockwork-workbench/430-hybrid-workbench.html`).

The hybrid has one canonical fact snapshot, one transition owner, one pending timer/epoch, and one route engine. The lower shelf is a projection over that snapshot, not a second state machine. It opens at 202px and collapses to a 38px header; open state reserves a 474px canvas with hybrid-specific node positions that do not move on disclosure. While open, the shelf action is the sole visible primary lifecycle action; when collapsed, Precision’s lifecycle action returns.

Reset must cancel pending work before restoring lifecycle, node/view coordinates, planes, Intent evidence, composite and overlay disclosure, inspector, focus, and shelf state. Physical springs never animate outer node boxes or attachment geometry; route-safe node placement remains immediate.

#### Precision Workbench: dark, surgical, command-first

Precision is a cool-neutral instrument panel whose canvas owns the viewport and whose context follows selection. Preserve:

- near-black paper/surface/canvas layers; cool gray rules; cobalt for selection/action; restrained teal for provenance; green, amber, and red only for semantic status (`prototypes/clockwork-workbench/410-precision-working.html:28-41`);
- Manrope for compact UI labels and Fragment Mono for evidence/source, on a 4/8-based spacing rhythm (`prototypes/clockwork-workbench/410-precision-working.html:8-21`);
- one-pixel borders, small radii, dense resource tree, floating contextual inspector, source drawer, command menu, capsule tool rail, compact minimap, and 90–180ms surgical transitions (`prototypes/clockwork-workbench/410-precision-working.html:49-101`);
- cobalt selection outlines and quiet unrelated context, with a semantic-lens mask rather than a separate page (`prototypes/clockwork-workbench/410-precision-working.html:83-100`);
- command-first affordances and keyboard parity: command menu, arrows for selection, `Cmd/Ctrl+Enter` for the next lifecycle action, Escape for layered dismissal, and direct shortcuts (`prototypes/clockwork-workbench/410-precision-working.html:412-420`).

Precision explicitly refuses generic dashboard cards and the old cream railway treatment (`prototypes/clockwork-workbench/410-precision-working.html:110-116`). Do not soften it into a marketing dashboard or decorate it with gratuitous cards.

Precision nodes are directly draggable. During pointer movement, constrain them to the world, redraw every connected orthogonal path, preserve parallel-lane separation/switches/arrows/labels, and enable reset once layout becomes dirty (`prototypes/clockwork-workbench/410-precision-working.html:323-370`, `prototypes/clockwork-workbench/410-precision-working.html:378-398`). Reset must restore both authored lifecycle and the captured initial node positions (`prototypes/clockwork-workbench/410-precision-working.html:289-310`). This dynamic redraw/reset behavior is part of the approved direction, not optional polish.

#### Motion Compiler: dark, physical, state-authoring

Motion is a physical semantic compiler rather than a static property workbench. Preserve:

- layered graphite surfaces with chalk text, copper as authorization/change, sage for healthy observation, and family-specific muted relation colors (`prototypes/clockwork-workbench/420-motion-working.html:11-76`);
- Spline Sans plus Spline Sans Mono; 4/8/12/16/24 spacing; square, precise controls and handles (`prototypes/clockwork-workbench/420-motion-working.html:41-58`);
- a three-part composition: compact hierarchy / stage / inspector above, then a dark state-and-evidence compiler shelf below (`prototypes/clockwork-workbench/420-motion-working.html:116-180`, `prototypes/clockwork-workbench/420-motion-working.html:589-629`);
- copper selection handles, a framed source-derived stage, explicit rulers, an evidence slider/rail, and spring-settled spatial transitions around 420–480ms (`prototypes/clockwork-workbench/420-motion-working.html:291-423`, `prototypes/clockwork-workbench/420-motion-working.html:580-615`);
- direct manipulation with 8px settling: nodes redraw edges continuously while dragged, then snap while railway geometry follows rendered node positions and receives a final settled redraw (`prototypes/clockwork-workbench/420-motion-working.html:1059-1110`, `prototypes/clockwork-workbench/420-motion-working.html:1349-1380`);
- non-spatial reduced-motion behavior and immediate keyboard-originated state changes (`prototypes/clockwork-workbench/420-motion-working.html:632-653`, `prototypes/clockwork-workbench/420-motion-working.html:1251-1281`).

Motion explicitly refuses both static property-workbench composition and diagrams whose pixels become product truth (`prototypes/clockwork-workbench/420-motion-working.html:657-663`). Physicality should explain selection, continuity, expansion, and state—not become ambient animation.

### 5. Use a reference-first design workflow

Do not begin by improvising CSS from a verbal mood. First collect and inspect visual references for the chosen grammar, then write down the direction before implementation: palette, type roles, spacing unit, component geometry, icon treatment, canvas hierarchy, selection language, and motion rules. The contract requires each alternative to be grounded in an approved reference direction and to have one coherent typography/color/component/icon/motion system (`docs/plans/2026-08-24-0455-feat-clockwork-stateful-canvas-prototypes-plan.md:83-88`).

Use the repository’s frontend design skills deliberately:

1. use `impeccable` to define/audit information hierarchy, interaction states, accessibility, responsive boundaries, tokens, and anti-patterns;
2. use `awwwards-motion-design` when implementing Motion Compiler choreography so selection, composite expansion, lifecycle transitions, and reduced-motion behavior are intentional and performant;
3. if a supplied screenshot becomes the reference, use `pixel-perfect-replication` and treat the image as a measurable spec rather than inspiration;
4. keep a short direction block in each prototype—thesis, own-world, story, first viewport, form, and geometry—so future refinements preserve the design argument. Hybrid, Precision, and Motion retain these blocks in their tracked HTML.

References guide the visual system, never the product model. Reuse atmosphere, spatial logic, and motion principles; do not clone another product’s identity, invent customer proof, or import a diagram model that conflicts with Python authority. The repository has no established production web identity or commercial proof (`PRODUCT.md:45-54`).

### 6. Build stable verification hooks, then verify the visible product

Keep selectors/state observable without coupling verification to incidental CSS:

- lifecycle: `body[data-lifecycle]` and temporary `body[data-pending]` (`prototypes/clockwork-workbench/410-precision-working.html:289-310`, `prototypes/clockwork-workbench/420-motion-working.html:1218-1280`);
- actions: `[data-action="…"]`, especially `[data-action="reset"]`;
- projections and filters: `[data-evidence]`, `[data-plane]`, and their `aria-pressed` values;
- selection/topology: `[data-node]`, `[data-from]`, `[data-to]`, and `[data-family]`;
- disclosure: `aria-expanded` for composite, source, hierarchy, and inspector controls;
- comparison: gallery tabs use `aria-selected`, iframe title changes with the alternative, and gallery reset forwards to the prototype’s reset hook (`prototypes/clockwork-workbench/401-working-gallery.html:19-31`).

These hooks support automation, but DOM assertions alone are not proof. Verify in a real browser at the fixed surface, with no per-screen zoom normalization. Any real browser driver is acceptable if it preserves the exact artboard/presentation scale, exercises the interactions, and captures visible evidence. Do not make acceptance depend on a particular automation library.

At minimum, verify:

1. individual alternatives render at an exact 1280×720 viewport with no page scrolling or clipping of required controls;
2. the gallery shows the 1280×720 iframe at 90% in its 1152×648 frame and switches alternatives without changing scale;
3. every lifecycle action reaches the expected `data-lifecycle`, including pending, failed, recovered, reconciled, and reset states;
4. Intent / Resolution / Reality changes evidence without moving topology;
5. selection quiets unrelated context but never erases it;
6. each plane hides only its family and retains an affected-count signal;
7. composite expand/collapse preserves identity, ports, child/assertion/proposal summaries, and attached routes;
8. source, focus, fit, pan/zoom, minimap, keyboard focus, Escape/dismissal, and reduced-motion paths work;
9. dragging nodes continuously updates route endpoints, labels, switches, direction, and lane separation; Precision reset restores original placement;
10. screenshots at authored, proposed, observed-drift, failed, and reconciled states still read as one coherent product in each direction.

## Why This Matters

Clockwork’s advantage is durable semantic continuity: a builder can change intent without asking an agent to reinterpret an entire repository, because structure, provenance, constraints, alternatives, assertions, and runtime evidence survive across the lifecycle (`PRODUCT.md:13-23`). A static architecture diagram cannot demonstrate that advantage. Neither can a dashboard that collapses desired and observed state into one status badge.

The three-surface pattern isolates the design decision. Capability, data, lifecycle, viewport, and failure stay constant; Hybrid demonstrates the recommended 70% Precision / 30% Motion composition while the two source alternatives remain available for comparison.

The edge hybrid is equally load-bearing. Railway geometry supports stable tracing, neighborhood contrast supports investigation, and plane filters handle temporary overload. Removing any layer makes dense graphs ambiguous, contextless, or brittle. Keeping topology stable across focus and evidence changes also teaches users that the semantic model is persistent even when the viewing lens changes.

Finally, the recoverable failure makes the prototype credible. Repairing backup drift while retaining intent, resolution provenance, and failed evidence proves that Clockwork diagnoses and reconciles reality rather than merely generating resources.

## When to Apply

Apply this pattern when:

- regenerating either approved Workbench prototype from scratch;
- porting the static HTML/CSS/JavaScript prototypes into a production frontend stack;
- adding a new primitive, relation family, evidence projection, lifecycle stage, or composite behavior;
- comparing a future visual direction against Hybrid, Precision, and Motion;
- changing node drag, routing, focus, plane filtering, source inspection, or lifecycle presentation;
- reviewing whether a canvas proposal still represents Clockwork rather than a generic infrastructure diagram.

Do not apply it as a generic requirement for every Clockwork surface. The pattern is specific to the stateful visual canvas. CLI or text-only surfaces should preserve the same semantic distinctions but need not reproduce the canvas grammar.

## Examples

### Example: regenerate the shared DB-03 story

1. Start at `body[data-lifecycle="authored"]` with PostgreSQL 18 specified and runtime 18.6 observed.
2. Reopen only `db.primary.major_version`; show previous intent and reality unchanged.
3. Resolve to PostgreSQL 19 with scoped AI provenance, a compatibility reason, and SQLite retained as rejected.
4. Accept and plan exactly one bounded DB update; do not move topology.
5. Apply desired 19 while displaying observed 18.6 separately.
6. Observe runtime 19.0 plus backup 03:20; then assert 2 pass / 1 fail.
7. Correct backup to 03:00, retry, and show reconciled 3/3.
8. Reset to authored; in Precision also restore all initial node positions.

The shared flow is specified in `docs/plans/2026-08-24-0455-feat-clockwork-stateful-canvas-prototypes-plan.md` and implemented in all three tracked prototypes. The Hybrid contract harness at `prototypes/clockwork-workbench/490-workbench-contract.html` verifies deterministic lifecycle, parity, disclosure, reset, evidence, routing, dimensions, and gallery behavior.

### Example: drag DB-03 without breaking semantic readability

For Precision, pointer-down selects DB-03 and captures its initial pixel position. Pointer movement is divided by graph zoom, clamped to world bounds, and followed by `updateDynamicEdges()`. That routine chooses horizontal versus vertical routing, computes separated lanes for duplicate endpoint pairs, rewrites both underlay and visible path, relocates switch dots and labels, and updates the direction arrow. Pointer-up preserves the new spatial position; Reset restores the captured starting coordinates (`prototypes/clockwork-workbench/410-precision-working.html:323-398`).

For Motion, update `data-x`/`data-y`, redraw relations on every pointer move, then snap both axes to the 8px grid while edge geometry follows the rendered transform and receives a final redraw (`prototypes/clockwork-workbench/420-motion-working.html:1059-1110`, `prototypes/clockwork-workbench/420-motion-working.html:1349-1380`). The semantics (`from`, `to`, `family`, label) never change because placement changed.

### Example: reject a plausible but wrong redesign

Reject a proposal that looks polished but does any of the following:

- uses per-alternative auto-fit or nested scaling;
- removes source inspection or lets canvas pixels become product truth;
- turns the surface into chat-first generation, a read-only dashboard, or a mandatory manual diagrammer;
- replaces the hybrid with crossings-only railways, lens-only isolation, or filter-only relationship planes;
- hides unrelated context entirely on selection;
- moves nodes when switching Intent / Resolution / Reality;
- animates every action or ignores reduced-motion preferences;
- shows only a happy path, suppresses the backup assertion, or clears provenance during recovery;
- differentiates alternatives by feature omissions rather than visual/interaction grammar;
- revives the retired Direct Model Canvas direction.

These rejected boundaries follow `PRODUCT.md:31-43`, the settled design decisions at `docs/plans/2026-08-24-0455-feat-clockwork-stateful-canvas-prototypes-plan.md:35-45`, and the retirement/deferments at `docs/plans/2026-08-24-0455-feat-clockwork-stateful-canvas-prototypes-plan.md:153-164`.

## Related

- `PRODUCT.md` — canonical Clockwork Workbench product identity and UI guardrails.
- `docs/plans/2026-08-24-0455-feat-clockwork-stateful-canvas-prototypes-plan.md` — requirements, lifecycle, edge model, viewport contract, and acceptance examples.
- `prototypes/clockwork-workbench/401-working-gallery.html` — fixed-scale comparison surface.
- `prototypes/clockwork-workbench/430-hybrid-workbench.html` — recommended Hybrid Workbench implementation.
- `prototypes/clockwork-workbench/490-workbench-contract.html` — deterministic same-origin contract harness.
- `prototypes/clockwork-workbench/410-precision-working.html` — approved dark Precision Workbench alternative.
- `prototypes/clockwork-workbench/420-motion-working.html` — approved dark Motion Compiler alternative.
