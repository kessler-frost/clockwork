# Clockwork Motion Specification

Status: normative for production Workbench motion.

## Purpose

Motion explains causality, continuity, and lifecycle. It is not ambient decoration.

A transition must help answer at least one question:

- what changed;
- where it changed;
- why it changed;
- whether it is proposed or real;
- whether work is complete;
- whether desired and observed state converged.

If motion answers none of these, remove it.

## Motion tokens

Centralize timing and easing as CSS variables. Components use semantic token names rather than literal durations.

| Token | Default | Use |
|---|---:|---|
| `--motion-immediate` | `0ms` | keyboard-originated geometry, route attachment, state that must not lag input |
| `--motion-control` | `90ms` | hover, pressed, focus-adjacent feedback |
| `--motion-transition` | `150ms` | selection, compact state changes, edge emphasis |
| `--motion-disclosure` | `180ms` | menus, inspector sections, drawers, lifecycle shelf |
| `--motion-state-settle` | `420ms` | proposal acceptance, lifecycle convergence, composite descendant settling |
| `--motion-state-settle-max` | `480ms` | upper bound for spring-like state choreography |

Use a precise ease-out for controls and disclosure. Use a critically damped or low-overshoot spring only for semantic state continuity. Never use elastic motion for errors, destructive actions, or route geometry.

## Choreography

### Proposal appears

```text
operation proposed
    → affected primitive/relationship receives proposal treatment
    → proposed value or ghost structure appears
    → provenance and review actions become available
```

Do not move unrelated topology. The current value remains legible.

### Proposal accepted

```text
accept operation validated
    → proposal boundary settles into desired treatment
    → provenance remains available
    → observed state stays unchanged until observation
```

Acceptance must not visually imply that apply or observation already completed.

### Apply and observe

```text
apply begins
    → bounded progress appears on affected semantic objects
    → desired state remains explicit
apply completes
    → applied state records execution
observe completes
    → observed value updates independently
    → convergence or drift treatment appears
```

### Drift and reconciliation

Drift appears at the violated desired-versus-observed comparison and related relationship/assertion. Reconciliation removes the active warning treatment only after evidence converges; prior drift remains in history.

### Composite disclosure

The outer semantic identity and external handles remain stable. Descendants may settle into view, but route attachment updates synchronously. Collapse reverses descendant disclosure without moving unrelated primitives.

## Canvas constraints

- React Flow node positions and connected route geometry update immediately during drag.
- Edge endpoints, labels, switches, direction, and parallel-lane separation never trail the pointer.
- Do not spring the outer node box while dragging or after a direct placement; it breaks attachment geometry.
- Selection and semantic focus change contrast without rearranging topology.
- Intent / Resolution / Reality projections do not move nodes.
- Pan and zoom follow direct input without decorative easing that reduces control.
- Animate `transform` and `opacity` when safe; avoid layout-triggering animation in dense graph paths.

The approved Hybrid direction uses surgical 90–180ms workbench feedback and reserves 420–480ms physical settling for meaningful state continuity on non-geometric descendants.

## Loading and pending behavior

Pending feedback is proportional to the operation:

- immediate editor actions do not show loaders;
- validation shows only if it outlives immediate feedback;
- resolve, plan, apply, observe, assert, rollback, and reconcile expose bounded pending state;
- unrelated inspection remains usable;
- repeated dispatch of the same conflicting operation is disabled;
- cancellation or reset invalidates stale transitions before restoring presentation state.

Avoid indefinite shimmer on semantic objects. Prefer explicit operation, affected scope, and current phase.

## Reduced motion

Under `prefers-reduced-motion: reduce`:

- remove springs, parallax, travel, scale, and path-drawing effects;
- preserve state changes with immediate layout plus short opacity/color changes no longer than `100ms`;
- keep progress, labels, patterns, icons, and final state fully visible;
- do not auto-pan or animate viewport changes unless the user explicitly requested navigation;
- maintain focus and announcement order;
- never make a reduced-motion user wait for a hidden animation timer.

Reduced motion changes presentation, not lifecycle timing or result semantics.

## Performance contract

- Target 60fps for direct manipulation and state transitions.
- Update only affected nodes, edges, and overlays.
- Keep geometry calculation deterministic and outside decorative animation loops.
- Pause nonessential motion when the document is hidden.
- Do not allocate per-frame objects where stable values can be reused.
- Use one transition owner for a semantic change; nested components project that state rather than starting competing timelines.

## Verification

For every new motion sequence, verify:

1. the semantic cause is visible before or with the effect;
2. the current, desired, and observed states are not conflated;
3. final state is correct when animation is interrupted;
4. rapid repeated actions do not allow a stale transition to win;
5. node drag and route geometry remain attached at full speed;
6. keyboard-originated actions do not depend on pointer choreography;
7. reduced motion reaches the same final state without spatial travel;
8. focus does not disappear or move unexpectedly;
9. frame performance remains stable on the representative dense graph;
10. no motion is present solely to make the interface feel busy.
