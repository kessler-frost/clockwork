# Clockwork Accessibility Specification

Status: normative for production Workbench accessibility.

## Standard

Clockwork Workbench targets WCAG 2.2 AA for the complete authoring workflow, not only the surrounding shell. Base UI supplies accessible low-level behavior; Clockwork components remain responsible for names, state, focus, semantics, and complete keyboard alternatives.

The spatial canvas cannot be the only representation of the model. Navigator, Inspector, commands, relationship forms, history, and status provide equivalent semantic access without requiring precise pointer input or spatial interpretation.

## Keyboard contract

Every action available by pointer has a keyboard path.

### Workbench navigation

- A skip path reaches toolbar, Navigator, Canvas, Inspector, and lifecycle/status regions.
- Regions have stable accessible names and landmarks where appropriate.
- `Tab` moves among actionable controls, not every decorative canvas element.
- Arrow keys move within composite widgets such as trees, menus, tabs, lists, and graph navigation.
- `Escape` closes the topmost temporary layer and restores focus to its invoker.
- Shortcuts are discoverable, remappable where the platform supports it, and never the sole path.

### Canvas navigation

- The graph exposes a deterministic reading and keyboard-navigation order independent of current pixel placement.
- Users can move to connected primitives by semantic relationship and return to the overview.
- Selected, focused, and inspected states remain distinct.
- Pan and zoom controls are operable without a wheel or pinch gesture.
- Fit and reset do not strand focus.
- Composite expansion preserves a meaningful focus target; collapse moves focus to the composite summary when a child becomes hidden.

### Relationship creation

Drag-to-connect is optional, not mandatory. An equivalent command or form lets users:

1. choose the source primitive;
2. choose a semantic capability or relationship kind;
3. choose a compatible target;
4. review validation and impact;
5. dispatch the same `ConnectPrimitives` operation.

Handle names state direction, capability, and primitive identity. Invalid relationships explain the violated rule.

## Focus

- Visible focus meets contrast requirements on every surface and semantic state.
- Selection color or border does not replace keyboard focus.
- Opening a menu, dialog, drawer, command palette, or relationship form moves focus into it according to the primitive contract.
- Closing or completing it restores focus to the invoker or the resulting semantic object.
- Canvas re-projection, proposal acceptance, observation, and reconciliation do not silently discard focus.
- When the focused semantic object is deleted, focus moves to the nearest meaningful container or sibling and the deletion is announced.

## Names, roles, and state

Clockwork components expose product meaning rather than implementation details.

- A primitive's accessible name includes identity and type.
- Health, lifecycle, unresolved, proposal, drift, desired, and observed states are exposed as structured text.
- Relationships expose source, target, semantic family, direction, status, and proposal/drift state.
- React Flow implementation roles and internal node/edge IDs never become the user-facing name.
- Expanded/collapsed, selected, pressed, invalid, pending, and disabled states use native or appropriate ARIA semantics.
- Tooltips supplement visible labels; they do not carry required instructions or state alone.

Prefer native HTML and Base UI semantics. Add ARIA only when native behavior cannot express the component.

## Semantic state communication

Color is never the sole signal. Consequential distinctions use at least one additional channel:

| State | Additional channel |
|---|---|
| proposed | dashed/ghost boundary plus explicit “Proposed” text and review actions |
| agent-authored | provenance label and accessible origin text |
| desired vs observed | labeled values and difference summary |
| drift | warning icon/pattern plus violated expectation text |
| unresolved | unresolved label plus missing decision/instruction |
| applying | operation phase text and progress semantics |
| failed | error summary, affected scope, and recovery action |
| healthy | text or icon with accessible label, not green alone |

Text and non-text contrast must remain sufficient in authored, selected, focused, proposed, pending, observed, drifted, disabled, and error combinations.

## Inspector, forms, and validation

- Inspector sections use real headings and predictable section order: Model, State, Source, History, Provenance.
- Field labels remain visible; placeholder text is not a label.
- Desired, resolved, and observed values have explicit labels and a readable difference summary.
- Validation runs through Clockwork operations and returns field-level plus operation-level explanations.
- The first invalid field receives focus only after submission; subsequent changes do not steal focus.
- Errors persist until resolved or dismissed by an explicit valid action.
- Destructive actions name the affected primitive, relationship, proposal, or subgraph.
- Source views provide selectable text and do not rely on syntax color alone.

## Announcements and asynchronous work

Use a restrained live-region strategy:

- announce operation start only when it will not complete immediately;
- announce proposal creation, validation failure, operation success/failure, observation result, drift, and reconciliation;
- include affected semantic identity and result;
- avoid announcing high-frequency selection, drag coordinates, pan, or zoom changes;
- keep durable details in History/Status rather than relying on transient speech or toasts;
- do not replay stale announcements after reset or cancellation.

Progress indicators expose a name and determinate value when known. Pending state never makes unrelated read-only content unavailable.

## Motion and sensory considerations

Follow `MOTION.md` for reduced motion. In addition:

- no content flashes more than three times per second;
- motion does not become the sole indication of causality;
- sound is not required to understand an outcome;
- patterns and edge styles remain legible at supported zoom levels;
- hover-only content is dismissible, hoverable, and available by focus;
- target sizes meet WCAG 2.2 AA, with larger hit areas around small visual handles where spatial density requires precision.

## Zoom, reflow, and density

The Workbench is dense, but density does not exempt it from reflow and zoom requirements.

- Shell controls and Inspector content support 200% text zoom without loss of action or information.
- At constrained widths, panels may become drawers or sequential regions; semantic content and operation access remain.
- Canvas zoom is independent of browser text zoom.
- Text does not scale down merely to preserve the fixed prototype artboard; production layout adapts.
- Truncation exposes the full value through focusable or otherwise accessible disclosure.
- The fixed 1280×720 contract applies only to the comparison prototypes, not the production accessibility boundary.

## Verification matrix

An affected workflow is incomplete until it is exercised with:

1. keyboard only;
2. visible focus at every step;
3. a screen-reader pass over names, roles, state, relationships, and operation results;
4. 200% browser zoom and a constrained-width layout;
5. high-contrast semantic states without relying on color;
6. reduced motion;
7. a non-drag relationship-creation path;
8. composite collapse/expand with focus preservation;
9. async success, validation failure, execution failure, drift, and recovery announcements;
10. the Navigator or Inspector alternative when the canvas is not spatially understandable.
