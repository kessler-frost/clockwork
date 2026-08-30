# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

General primitive builders who model application architectures in Python, choosing per primitive how much to specify and how much to delegate to deterministic or intelligent resolution.

## Product Purpose

Clockwork is a persistent executable representation of software intent. It lets builders define typed primitives, preserve unresolved decisions as first-class state, resolve authorized ambiguity, materialize a runnable system, and verify whether observed reality satisfies the original intent.

Success means changing intent without asking an agent to reinterpret an entire repository: the semantic model retains structure, provenance, constraints, alternatives, assertions, and runtime evidence.

## Positioning

Clockwork is not an AI boilerplate generator or a nicer wrapper around Pulumi. It combines a pure-Python, Pydantic source of truth with adjustable resolution at field and primitive scope. Specified, inferred, AI-resolved, observed, and drifted values remain distinct and inspectable throughout the lifecycle.

The initial wedge is application architecture: define services and their semantic relationships at a high level, then turn that intent into a runnable, inspectable, self-validating system.

## Operating Context

A project-local `main.py` defines primitives, semantic connections, composites, and assertions. The current CLI exposes `show`, `plan`, `apply`, `status`, `assert`, and `destroy`; Pulumi materializes supported infrastructure.

The planned web surface is **Clockwork Workbench**—also called the Clockwork UI. It is a visual co-author rather than a read-only dashboard, keeping source inspectable while making the semantic graph, unresolved decisions, scoped proposals, deployment state, and observed reality directly manipulable.

The production boundary is fixed: React composes the application, shadcn and Base UI supply component infrastructure, the first-party `@clockwork` design system owns the product language, and React Flow renders spatial interaction as a projection of Clockwork state.

## Capabilities and Constraints

- Python/Pydantic remains an inspectable source of truth; the UI must not introduce an opaque diagram-only or YAML-only model.
- Visual and source edits must resolve to one stable semantic model.
- Meaningful changes pass through typed Clockwork operations shared by human and agent actions; canvas callbacks and components do not create alternate mutation paths.
- React Flow node and edge objects are replaceable projection data. Primitive identity, relationships, hierarchy, lifecycle, provenance, proposals, desired state, and observed state remain in Clockwork.
- Domain evolution and editor history remain independent: applying or reconciling intent is not canvas undo/redo, and moving or selecting a node is not domain history.
- Intent, resolution, and reality remain simultaneously inspectable.
- The model distinguishes specified, inferred, AI-resolved, observed, and drifted state.
- Each resolved decision can retain authorship, reason, constraints, rejected alternatives, related assertions, and revision authority.
- Intelligence operates on selected primitives and authorized omissions, never silently on the whole project.
- Deterministic functions take precedence when available; legality, validation, application, and reconciliation remain deterministic.
- Semantic edges, expandable composites, assertions, resource health, deployment changes, outputs, and errors are first-class data.
- The UI must not collapse into a chat-first app builder or make manual diagram composition the mandatory programming interface.
- Initial application primitives should focus on services, containers, databases, queues, object stores, volumes, endpoints, jobs, and secrets. Broader software primitives remain deliberately deferred.
- The existing runtime requires Python 3.12+ and currently uses Typer, Rich, Pydantic, and Pulumi. The production Workbench stack is React, shadcn over Base UI, the `@clockwork` design system, and React Flow / xyflow; the tracked comparison prototypes remain static HTML, CSS, and JavaScript.

## Brand Commitments

The product name is Clockwork. **Clockwork Workbench** is the canonical name for its visual canvas surface; **Clockwork UI** is equivalent shorthand. Existing copy is technical, direct, and control-oriented. No logo or established web identity exists.

## Evidence on Hand

- `README.md` documents the product mechanism, current resource examples, and CLI workflow.
- `clockwork/cli.py` and `clockwork/formatters.py` define the current lifecycle actions, hierarchy, statuses, and provenance display.
- `docs/plans/2026-08-24-0455-feat-clockwork-stateful-canvas-prototypes-plan.md` records the Clockwork Workbench graph grammar, visual co-authoring guardrails, lifecycle, interaction requirements, and current prototype directions.
- `docs/design/` defines the production frontend stack, layer ownership, canvas adapter, operation pathways, motion, and accessibility contracts.
- The repository has no existing production web frontend, implemented component registry, logo, customer proof, benchmarks, or production UI imagery. Future surfaces must not fabricate commercial claims.

## Product Principles

1. Preserve agency at every level of abstraction.
2. Keep intent, resolution, and reality visibly connected.
3. Make ambiguity, provenance, and revision authority first-class.
4. Let visual and Python authoring converge on one semantic model.
5. Treat assertions and observed state as part of authoring, not postscript diagnostics.
6. Prove the model on a concrete application-architecture wedge before expanding to everything software.
7. Route meaningful human and agent actions through the same typed operations, validation, provenance, and history.
8. Keep Clockwork evolution independent of canvas presentation and editor undo/redo.
9. Treat React Flow as a replaceable spatial projection and shadcn/Base UI as infrastructure beneath Clockwork’s first-party design language.
