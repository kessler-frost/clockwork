# Clockwork Interaction Specification

Status: normative for production Workbench interactions.

## One semantic mutation path

Human and agent actions converge on the same typed Clockwork operation system.

```text
Human gesture ─┐
               ├─ operation request ─ validate ─ propose/execute ─ history ─ model ─ projections
Agent request ─┘
```

There is no privileged canvas mutation path and no parallel agent-only mutation API. Origin affects proposal policy and provenance; it does not bypass validation or create different semantics.

## Operation catalog

The initial semantic vocabulary includes:

```text
CreatePrimitive
DeletePrimitive
ConfigurePrimitive
ConnectPrimitives
DisconnectPrimitives
ResolvePrimitive
ProposeChange
AcceptProposal
RejectProposal
Apply
Rollback
Reconcile
```

The vocabulary may gain domain-specific operations, but UI adapters must not substitute implementation verbs such as `addEdge`, `setNodes`, or `patchForm` for a meaningful Clockwork action.

Each operation request carries, at minimum:

- operation kind and stable request identity;
- affected primitive, relationship, proposal, or subgraph IDs;
- typed semantic input;
- actor and origin (`human`, `agent`, `system`);
- provenance or source reference;
- expected model revision or equivalent concurrency boundary;
- proposal policy when execution is not immediate.

Each result exposes:

- accepted or rejected validation;
- the operation or proposal identity;
- affected semantic IDs;
- resulting lifecycle state;
- domain history entry;
- user-readable failure and recovery information when rejected or failed.

Exact transport types belong to the operations package. Components consume the typed contract rather than re-declaring local variants.

## Operation lifecycle

A meaningful mutation follows one ordered path:

1. **Translate:** turn a gesture, form submission, command, or agent request into a typed operation.
2. **Validate:** check primitive capabilities, relationship rules, scope authorization, model revision, and policy.
3. **Propose or execute:** preserve non-authoritative changes as proposals; execute only when policy permits.
4. **Record:** retain actor, provenance, reasons, constraints, affected IDs, and before/after domain facts.
5. **Transition:** update proposal and domain lifecycle state.
6. **Project:** update canvas, navigator, inspector, history, source, and status from the new authoritative state.
7. **Observe:** after materialization, retain actual state and evidence independently of desired state.
8. **Reconcile:** expose convergence or drift without erasing prior evidence.

A renderer may show optimistic spatial feedback for a drag. It must settle to the operation result and cannot declare a semantic mutation successful on its own.

## Human interactions

| Human action | Operation or editor action |
|---|---|
| drag a compatible connection | `ConnectPrimitives` |
| remove a semantic edge | `DisconnectPrimitives` |
| submit primitive configuration | `ConfigurePrimitive` |
| create/delete a primitive | `CreatePrimitive` / `DeletePrimitive` |
| reopen an authorized value | `ResolvePrimitive` flow |
| accept/reject proposal | `AcceptProposal` / `RejectProposal` |
| apply, roll back, reconcile | matching Clockwork operation |
| move/select/zoom/filter | editor action, not a Clockwork operation |

Validation failures stay attached to the action and semantic target. They explain the violated rule and preserve the previous model.

## Agent interactions

Agents operate on Clockwork concepts, never canvas implementation details.

Use:

```text
ConnectPrimitives(api, database, relationship="reads")
```

Not:

```text
addEdge(...)
```

An agent-originated request:

- receives the same schema and validation as a human request;
- records agent identity, input scope, reasons, evidence, and authorization;
- becomes a proposal unless explicit policy authorizes immediate execution;
- remains inspectable and rejectable before it changes desired state;
- never obtains screen coordinates, React Flow IDs without semantic mapping, or component-local state as authority.

“Agent-authored” is provenance, not a complete proposal presentation. The interface must show what changes, why, what it affects, what was rejected, and which policy controls acceptance.

## Proposal grammar

A proposal is a first-class domain object linked to one or more proposed operations.

It shows:

- current and proposed semantic values;
- affected primitives and relationships;
- agent or human provenance;
- reason, constraints, evidence, and rejected alternatives;
- validation state and predicted impact;
- accept and reject actions;
- lifecycle state and subsequent execution evidence.

Acceptance applies the proposal through `AcceptProposal`; rejection records `RejectProposal`. Components must not copy proposed values directly into desired state.

Proposed nodes and edges remain visually distinct until acceptance. When accepted, they retain identity and provenance while transitioning to the canonical desired treatment.

## Workbench interaction hierarchy

1. **Overview:** the stable semantic graph and system context.
2. **Selection:** context follows the selected primitive or relationship.
3. **Semantic focus:** a lens emphasizes the selected neighborhood without replacing the overview.
4. **Evidence projection:** Intent / Resolution / Reality changes visible facts without moving topology.
5. **Source and detail:** Inspector and Source provide precise editing and evidence.
6. **Lifecycle surface:** History, status, and operations explain meaningful evolution.

Avoid equal-weight modes that make the user choose a context before seeing the system. Avoid chat-first control of semantic mutations.

## Inspector interaction contract

The Inspector is one reusable Clockwork component with stable sections:

### Model

- authored intent;
- configuration and constraints;
- unresolved and revision-authorized fields;
- relationship and hierarchy meaning.

### State

- desired, resolved, last observed, and current transition values;
- health, assertions, drift, and execution evidence;
- explicit differences rather than one aggregate badge.

### Source

- inspectable source location and representation;
- source-backed changes routed through the same operation contract;
- no opaque diagram-only state.

### History

- domain evolution only;
- operation, actor, provenance, lifecycle, before/after, and evidence;
- editor undo/redo presented separately where exposed.

### Provenance

- specified, inferred, agent-resolved, accepted, and observed origins;
- reasons, constraints, rejected alternatives, and revision authority.

Changing selection updates the Inspector projection. It must not reset the lifecycle, discard a draft without warning, or create a domain event.

## Commands, menus, and forms

- Command palette entries dispatch the same operation or editor-action handlers as direct manipulation.
- Context menus expose actions valid for the selected semantic type and lifecycle.
- Forms use canonical `@clockwork` fields and Base UI interaction behavior.
- Destructive semantic actions state scope and consequences before dispatch.
- Pending operations disable only conflicting actions, not unrelated inspection.
- Escape dismisses the topmost temporary layer and restores its invoker.
- Keyboard shortcuts have discoverable labels and never become the only path.

## Feedback and errors

Every asynchronous semantic operation communicates:

```text
requested → validating → proposed or executing → succeeded or failed → observed/reconciled when applicable
```

Feedback stays near the affected semantic object and is also available in the operation/status surface. A toast may announce an outcome; it is not the only durable record.

On failure:

- retain the pre-operation model;
- retain failed operation evidence;
- name the affected scope and cause;
- expose a valid recovery, retry, rollback, or edit action;
- never clear provenance, hide a failed assertion, or represent failure as success because the projection changed.

## Interaction specification template

Every new reusable interaction documents:

1. user and agent intent;
2. semantic owner;
3. operation or editor-action classification;
4. valid states and validation rules;
5. pointer, keyboard, and assistive-technology paths;
6. pending, success, empty, disabled, and error feedback;
7. history and provenance effects;
8. canvas, inspector, source, and status projections;
9. motion and reduced-motion behavior;
10. observable verification scenario.
