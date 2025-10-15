# Clockwork Architecture

## Overview

Clockwork provides **intelligent infrastructure orchestration in Python** that combines:

- **Pydantic models** for declarative resource definition
- **AI-powered resource completion** via PydanticAI (OpenAI-compatible APIs)
- **Pulumi** for automated deployment

The approach: Define infrastructure (Python) → AI completes resources → Automated deployment (Pulumi)

## Architecture Diagram

```text
┌─────────────┐
│   main.py   │  User defines resources in Python
│  (Pydantic) │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────┐
│      ClockworkCore.apply()          │
└─────────────────────────────────────┘
       │
       ├─── 1. Load Resources ────────────────┐
       │    (Execute main.py, collect        │
       │     Resource instances)              │
       │                                      │
       ├─── 2. Complete Resources ────────────┤
       │    (AI via PydanticAI)              │
       │    • Only for resources with         │
       │      needs_completion()              │
       │    • Returns completed Resource objs │
       │                                      │
       ├─── 3. Compile to Pulumi ─────────────┤
       │    (Object-based, Automation API)   │
       │    • resource.to_pulumi()            │
       │    • Returns Pulumi Resource objects │
       │    • Create Pulumi program function  │
       │                                      │
       └─── 4. Execute Deploy ────────────────┘
            (Pulumi Automation API: stack.up())
```

## Core Components

### 1. Resources (Pydantic Models)

**Location**: `clockwork/resources/`

Resources are Pydantic models that represent infrastructure components:

```python
class Resource(BaseModel):
    name: str
    description: Optional[str] = None

    def needs_completion(self) -> bool:
        """Does this resource need AI completion?"""
        raise NotImplementedError

    def to_pulumi(self) -> Any:
        """Generate Pulumi Resource object."""
        raise NotImplementedError
```

#### Example: FileResource

```python
class FileResource(Resource):
    description: str                  # what it should contain (for AI) - required
    name: Optional[str] = None        # filename (AI suggests if None)
    content: Optional[str] = None     # if provided, skips AI
    directory: Optional[str] = None   # where to create it (AI suggests if None)
    mode: Optional[str] = None        # file permissions (AI suggests if None)
    path: Optional[str] = None        # full path (overrides directory + name if provided)
```

#### Example: AppleContainerResource

```python
class AppleContainerResource(Resource):
    description: str                         # what it does (for AI) - required
    name: Optional[str] = None               # container name (AI suggests if None)
    image: Optional[str] = None              # Container image (AI suggests if None)
    ports: Optional[List[str]] = None        # Port mappings ["8080:80"]
    volumes: Optional[List[str]] = None      # Volume mounts ["/host:/container"]
    env_vars: Optional[Dict[str, str]] = None  # Environment variables
    networks: Optional[List[str]] = None     # Networks
    present: bool = True                     # Should container exist
    start: bool = True                       # Should container be running
```

### 2. Resource Completer (AI Stage)

**Location**: `clockwork/resource_completer.py`

Completes missing fields in resources using AI via PydanticAI structured outputs:

```python
class ResourceCompleter:
    async def complete(self, resources: List[Resource]) -> List[Resource]:
        """Complete partial resources using AI."""
        completed_resources = []

        for resource in resources:
            if resource.needs_completion():
                # Use PydanticAI to complete missing fields
                completed = await self._complete_resource(resource)
                completed_resources.append(completed)
            else:
                # Resource is already complete
                completed_resources.append(resource)

        return completed_resources
```

**How It Works**:

1. **Check Completion Needs**: For each resource, call `needs_completion()` to see if any fields are missing (None)
2. **Build Prompt**: Create a detailed prompt describing what fields need to be filled
3. **PydanticAI Agent**: Create an agent with the resource's Pydantic model as the output type
4. **Structured Output**: AI returns a complete resource object with all fields filled
5. **Merge**: User-provided values override AI suggestions

**Integration**:

- Uses **OpenAI-compatible APIs** (OpenRouter, LM Studio, Ollama, etc.)
- Model: `meta-llama/llama-4-scout:free` (configurable)
- Supports PydanticAI tools (web search, file access via MCP)
- Uses Tool Output mode (default) for reliable structured data generation
- Models must support tool calls (function calling)

### 3. Pulumi Compiler (Automation API Stage)

**Location**: `clockwork/pulumi_compiler.py`

Converts completed resources to Pulumi infrastructure using Automation API:

```python
class PulumiCompiler:
    def create_program(self, resources: List[Resource]) -> Callable:
        """Create a Pulumi program function from resources."""
        def pulumi_program():
            for resource in resources:
                # Call resource's to_pulumi() to create Pulumi resources
                resource.to_pulumi()
        return pulumi_program

    async def apply(self, resources: List[Resource], project_name: str) -> dict:
        """Apply infrastructure changes using Pulumi."""
        program = self.create_program(resources)
        stack = auto.create_or_select_stack(
            stack_name="dev",
            project_name=project_name,
            program=program,
        )
        up_result = stack.up()
        return {"success": True, "summary": up_result.summary}
```

**Output Structure**:

```text
.clockwork/state/
├── .pulumi/        # Pulumi state files
└── Pulumi.*.yaml   # Stack configuration
```

### 4. Core Orchestrator

**Location**: `clockwork/core.py`

Main pipeline coordinator:

```python
class ClockworkCore:
    def apply(self, main_file: Path, dry_run: bool = False):
        # 1. Load resources from main.py
        resources = self._load_resources(main_file)

        # 2. Complete resources (AI fills missing fields)
        completed_resources = asyncio.run(
            self.resource_completer.complete(resources)
        )

        # 3. Compile to Pulumi (object-based)
        # 4. Execute Pulumi deployment
        if not dry_run:
            result = asyncio.run(
                self.pulumi_compiler.apply(completed_resources)
            )

        return result

    def plan(self, main_file: Path):
        """Complete and preview without deploying."""
        resources = self._load_resources(main_file)
        completed_resources = asyncio.run(
            self.resource_completer.complete(resources)
        )
        result = asyncio.run(
            self.pulumi_compiler.preview(completed_resources)
        )
        return result

    def destroy(self, main_file: Path, dry_run: bool = False):
        """Destroy infrastructure using Pulumi."""
        if not dry_run:
            result = asyncio.run(
                self.pulumi_compiler.destroy()
            )
        return result

    def assert_resources(self, main_file: Path, dry_run: bool = False):
        """Validate deployed resources."""
        # 1. Load resources
        resources = self._load_resources(main_file)

        # 2. Complete resources (if needed)
        completed_resources = asyncio.run(
            self.resource_completer.complete(resources)
        )

        # 3. Run assertions directly (no compilation)
        if not dry_run:
            result = self._execute_assertions(completed_resources)

        return result
```

### 5. CLI

**Location**: `clockwork/cli.py`

Simple Typer-based CLI:

```bash
uv run clockwork apply       # Full pipeline (deploy resources via Pulumi)
uv run clockwork plan        # Preview resources without deploying
uv run clockwork assert      # Validate deployed resources
uv run clockwork destroy     # Tear down resources via Pulumi
uv run clockwork version     # Show version
```

## Data Flow

### Input: main.py

```python
from clockwork.resources import FileResource

article = FileResource(
    description="Write about Conway's Game of Life",  # required
    name=None,  # AI will suggest filename
    directory=None,  # AI will suggest directory
    content=None,  # AI will generate content
    mode=None  # AI will suggest permissions
)
```

### Stage 1: Load

- Execute `main.py` as Python module
- Extract all `Resource` instances
- Result: `[FileResource(name=None, description="...", ...)]`

### Stage 2: Complete (AI)

- Check `article.needs_completion()` → True (has None fields)
- Build prompt: "Complete this FileResource with name, directory, content, and mode"
- Create PydanticAI Agent with `output_type=FileResource` (Tool Output mode)
- AI returns: `FileResource(name="conways_game_of_life.md", content="# Conway's...", directory=".", mode="644")`
- Merge with user values (user values override AI)
- Result: Fully completed `FileResource`

### Stage 3: Compile (Pulumi)

- Call `article.to_pulumi()`
- Returns Pulumi Resource object (dynamic provider for file operations)
- Create Pulumi program function wrapping all resources

### Stage 4: Deploy (Pulumi Automation API)

- Execute: `stack.up()` via Automation API
- Pulumi creates/updates infrastructure
- State stored in `.clockwork/state/`
- File created at specified path

### Destroy Pipeline

The destroy pipeline uses Pulumi's state management:

**Destroy Execute**:

- Execute: `stack.destroy()` via Automation API
- Pulumi reads state from `.clockwork/state/`
- All tracked resources are destroyed
- **Automatic Cleanup**: After successful destroy, the `.clockwork` directory is automatically removed (unless `--keep-files` flag is used)

**CLI Options**:
```bash
# Default: destroy resources and remove .clockwork directory
clockwork destroy

# Keep .clockwork directory for debugging
clockwork destroy --keep-files
```

### Assert Pipeline

The assert pipeline validates deployed resources:

**Stages 1-2**: Load → Complete resources

**Stage 3**: Execute assertions directly on resources (no Pulumi compilation needed)

## Design Principles

### 1. Python-First Orchestration

- No custom DSL or YAML, pure Python for infrastructure definition
- Pydantic for type safety and validation
- Full IDE support and autocompletion

### 2. Intelligent Completion

- **AI Stage**: Fills in missing fields intelligently using structured outputs
- **Compilation Stage**: Object-based transformation to Pulumi resources
- **User Override**: User-provided values always take precedence

### 3. Automated Deployment

- Delegates execution to battle-tested Pulumi
- Pulumi handles state management and resource lifecycles
- Focus on intelligent orchestration, not reimplementation

### 4. Simplicity

- Linear orchestration pipeline: Load → Complete → Compile → Deploy
- No complex dependency graphs or state management
- Clear separation of concerns between stages

## Extension Points

### Adding New Resources

1. Create new class in `clockwork/resources/`:

```python
class ServiceResource(Resource):
    name: str
    service_name: Optional[str] = None  # AI can suggest
    port: Optional[int] = None          # AI can suggest

    def needs_completion(self) -> bool:
        return self.service_name is None or self.port is None

    def to_pulumi(self) -> Any:
        """Create Pulumi resource using pulumi-command provider."""
        from pulumi_command import local

        return local.Command(
            f"systemd-{self.name}",
            create=f"systemctl start {self.service_name}",
            delete=f"systemctl stop {self.service_name}",
        )
```

2. Export in `__init__.py`
3. Add tests
4. Create example

### Custom AI Models

Change model via CLI or environment:

```bash
# Cloud (OpenRouter)
clockwork apply --model "openai/gpt-4o-mini"

# Local (LM Studio)
export CW_BASE_URL="http://localhost:1234/v1"
export CW_MODEL="local-model"
clockwork apply
```

### Different Deployment Targets

Pulumi supports many backends (local file, S3, Azure Blob, etc.). Configure via Pulumi settings:

```bash
# Use S3 backend
pulumi login s3://my-pulumi-state-bucket

# Use Azure Blob Storage
pulumi login azblob://my-container
```

## Dependencies

```toml
[project]
dependencies = [
    "pydantic>=2.0.0",                           # Resource models
    "pydantic-settings>=2.0.0",                  # Configuration management
    "typer>=0.16.0",                             # CLI
    "rich>=13.0.0",                              # Terminal output
    "pydantic-ai-slim[mcp,duckduckgo]>=0.0.49", # AI framework with MCP support
    "openai>=1.99.9",                            # OpenAI-compatible client
    "pulumi>=3.0",                               # Infrastructure as code engine
    "pulumi-docker>=4.0",                        # Docker provider
    "pulumi-command>=1.0",                       # Command provider
]
```

## Key Features

| Feature | Implementation |
|---------|----------------|
| **Config Format** | Python (Pydantic models) |
| **AI Integration** | OpenAI-compatible APIs (cloud or local) |
| **Execution** | Pulumi (battle-tested IaC) |
| **State Management** | Pulumi Automation API |
| **Code Size** | ~1,000 lines of core logic |
| **Dependencies** | 9 focused packages |
| **Complexity** | Simple linear pipeline |

## Future Enhancements

- More resource types for broader infrastructure coverage
- Remote deployment targets (SSH, Kubernetes)
- Resource dependency orchestration
- Resource completion caching and optimization
- Streaming output for real-time feedback
- Multi-container orchestration patterns
- Advanced state tracking and lifecycle management
