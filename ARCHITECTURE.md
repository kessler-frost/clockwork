# Clockwork Architecture

Clockwork converts HCL2 configuration files into executable artifacts using a three-phase pipeline.

## Core Pipeline

```text
.cw File → [INTAKE] → IR → [ASSEMBLY] → ActionList → [FORGE] → Artifacts
```

1. **INTAKE**: Parse HCL2 `.cw` files into Intermediate Representation (IR)
2. **ASSEMBLY**: Convert IR into ActionList with dependency resolution  
3. **FORGE**: Compile ActionList into executable artifacts with AI assistance

## Data Flow

```text
main.cw → Parser → IR → Planner → ActionList → Compiler → [AI Agent] → ArtifactBundle → Executor → Results
```

## Environment Variables

- `CLOCKWORK_LM_STUDIO_URL`: LM Studio server endpoint
- `CLOCKWORK_LM_STUDIO_MODEL`: AI model identifier  
- `CLOCKWORK_USE_AGNO`: Enable/disable AI integration
- `CLOCKWORK_PROJECT_NAME`: Project identifier
- `CLOCKWORK_LOG_LEVEL`: Logging verbosity