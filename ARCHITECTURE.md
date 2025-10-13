# Clockwork Architecture

## Overview

Clockwork provides **intelligent infrastructure orchestration in Python** that combines:

- **Pydantic models** for declarative resource definition
- **AI-powered resource completion** via PydanticAI (OpenAI-compatible APIs)
- **PyInfra** for automated deployment

The approach: Define infrastructure (Python) → AI completes resources → Automated deployment (PyInfra)

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
       ├─── 3. Compile to PyInfra ────────────┤
       │    (Template-based, no AI)          │
       │    • resource.to_pyinfra_operations()│
       │    • Generate inventory.py           │
       │    • Generate deploy.py              │
       │    • Generate destroy.py             │
       │                                      │
       └─── 4. Execute Deploy ────────────────┘
            (subprocess: pyinfra -y inventory.py deploy.py)
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

    def to_pyinfra_operations(self) -> str:
        """Generate PyInfra operation code."""
        raise NotImplementedError

    def to_pyinfra_destroy_operations(self) -> str:
        """Generate PyInfra teardown code."""
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

### 3. PyInfra Compiler (Template Stage)

**Location**: `clockwork/pyinfra_compiler.py`

Converts completed resources to executable PyInfra code:

```python
class PyInfraCompiler:
    def compile(self, resources: List[Resource]) -> Path:
        """Compile resources to PyInfra deployment files."""
        operations = []
        destroy_operations = []

        for resource in resources:
            # Get PyInfra code from each resource
            operations.append(resource.to_pyinfra_operations())
            destroy_operations.append(resource.to_pyinfra_destroy_operations())

        # Generate files
        self._write_inventory()
        self._write_deploy(operations)
        self._write_destroy(destroy_operations)

        return self.output_dir
```

**Output Structure**:

```text
.clockwork/pyinfra/
├── inventory.py    # "@local" (localhost)
├── deploy.py       # All PyInfra deployment operations
└── destroy.py      # All PyInfra teardown operations
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

        # 3. Compile to PyInfra (template-based)
        pyinfra_dir = self.pyinfra_compiler.compile(completed_resources)

        # 4. Execute PyInfra deployment
        if not dry_run:
            result = self._execute_pyinfra(pyinfra_dir, "deploy.py")

        return result

    def plan(self, main_file: Path):
        """Complete and compile without deploying."""
        return self.apply(main_file, dry_run=True)

    def destroy(self, main_file: Path, dry_run: bool = False):
        """Execute pre-generated destroy operations."""
        # Get PyInfra directory (generated during apply)
        pyinfra_dir = self._get_pyinfra_dir(main_file)

        # Execute destroy operations
        if not dry_run:
            result = self._execute_pyinfra(pyinfra_dir, "destroy.py")

        return result

    def assert_resources(self, main_file: Path, dry_run: bool = False):
        """Validate deployed resources."""
        # 1. Load resources
        resources = self._load_resources(main_file)

        # 2. Complete resources (if needed)
        completed_resources = asyncio.run(
            self.resource_completer.complete(resources)
        )

        # 3. Compile assertions
        pyinfra_dir = self.pyinfra_compiler.compile_assert(completed_resources)

        # 4. Execute assertions
        if not dry_run:
            result = self._execute_pyinfra(pyinfra_dir, "assert.py")

        return result
```

### 5. CLI

**Location**: `clockwork/cli.py`

Simple Typer-based CLI:

```bash
uv run clockwork apply       # Full pipeline (deploy resources)
uv run clockwork plan        # Complete resources without deploying
uv run clockwork assert      # Validate deployed resources
uv run clockwork destroy     # Tear down resources
uv run clockwork service start   # Start monitoring service
uv run clockwork service stop    # Stop monitoring service
uv run clockwork service status  # Check service status
uv run clockwork version     # Show version
```

### 6. Monitoring Service (FastAPI)

**Location**: `clockwork/service/`

The Clockwork service provides continuous health monitoring and automatic remediation of deployed resources. It runs as a FastAPI application on the local host.

**Architecture**:
```text
┌─────────────────────────────────────┐
│   Clockwork Service (Port 8765)     │
│                                     │
│  ┌─────────────────────────────┐   │
│  │   FastAPI App (app.py)      │   │
│  │  - REST API endpoints       │   │
│  │  - AI connection validation │   │
│  └─────────────────────────────┘   │
│                                     │
│  ┌─────────────────────────────┐   │
│  │  ProjectManager (manager.py)│   │
│  │  - In-memory project state  │   │
│  │  - Registration/tracking    │   │
│  └─────────────────────────────┘   │
│                                     │
│  ┌─────────────────────────────┐   │
│  │  HealthChecker (health.py)  │   │
│  │  - Background monitoring    │   │
│  │  - Resource-specific checks │   │
│  └─────────────────────────────┘   │
│                                     │
│  ┌─────────────────────────────┐   │
│  │ RemediationEngine           │   │
│  │ (remediation.py)            │   │
│  │  - Diagnostic collection    │   │
│  │  - AI-powered fixes         │   │
│  └─────────────────────────────┘   │
│                                     │
│  ┌─────────────────────────────┐   │
│  │  ToolSelector (tools.py)    │   │
│  │  - Context-aware tools      │   │
│  │  - Resource-type tools      │   │
│  └─────────────────────────────┘   │
└─────────────────────────────────────┘
```

**Components**:

1. **FastAPI App** (`app.py`)
   - REST API for project registration and status
   - Health endpoint for service monitoring
   - AI connection validation on startup
   - Graceful shutdown handling

2. **ProjectManager** (`manager.py`)
   - In-memory storage of project state
   - Track resources, health status, remediation attempts
   - Thread-safe operations with asyncio.Lock

3. **HealthChecker** (`health.py`)
   - Background asyncio loop for continuous monitoring
   - Resource-specific check intervals:
     - FileResource: Check once after deployment, then skip
     - DockerResource/AppleContainerResource: Every 30 seconds
     - GitRepoResource: Every 5 minutes
   - Integrates with existing assertion pipeline
   - Triggers remediation on failures

4. **RemediationEngine** (`remediation.py`)
   - Collects diagnostics (logs, status, errors)
   - Enhances AI completion prompt with error context
   - Re-completes resources with updated prompt
   - Re-applies single resource in isolation
   - Max retry attempts (default: 3)

5. **ToolSelector** (`tools.py`)
   - Intelligent tool selection for AI completion
   - Resource-type based tools (containers, files, git)
   - Context-aware tool selection (search, diagnostics)
   - Lazy loading of tools and MCP servers

**REST API Endpoints**:
```
GET    /health                          - Service health check
POST   /projects/register               - Register project for monitoring
DELETE /projects/{project_id}           - Unregister project
GET    /projects                        - List all monitored projects
GET    /projects/{project_id}/status    - Get project health status
POST   /projects/{project_id}/remediate - Manual remediation trigger
```

**Service Integration**:
- `clockwork apply` → Registers project with service after deployment
- `clockwork destroy` → Unregisters project from service
- `clockwork assert` → Requires service to be running
- `clockwork plan` → Works independently (no service required)

**Remediation Flow**:
```
1. Health check fails → Assertion error detected
2. Collect diagnostics → Logs, status, error messages
3. Enhance prompt → Add error context to AI prompt
4. Re-complete resource → AI generates fixed configuration
5. Re-apply resource → Deploy the fix using PyInfra
6. Validate fix → Run assertions to verify success
7. Update state → Reset attempts on success, increment on failure
```

**Configuration** (via `.env`):
```bash
CW_SERVICE_PORT=8765                            # Service port
CW_SERVICE_CHECK_INTERVAL_DEFAULT=30            # Default check interval (seconds)
CW_SERVICE_MAX_REMEDIATION_ATTEMPTS=3           # Max retry attempts
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

### Stage 3: Compile (Template)

- Call `article.to_pyinfra_operations()`
- Generate PyInfra code:

```python
# Create file: conways_game_of_life.md
with open("_temp_conways_game_of_life.md", "w") as f:
    f.write("""# Conway's Game of Life...""")

files.put(
    name="Create conways_game_of_life.md",
    src="_temp_conways_game_of_life.md",
    dest="/path/to/conways_game_of_life.md",
    mode="644",
)
```

### Stage 4: Deploy (PyInfra)

- Run: `pyinfra -y inventory.py deploy.py`
- PyInfra executes operations
- File created at specified path

### Destroy Pipeline

The destroy pipeline uses pre-generated destroy operations:

**Stage 1-3**: Already done during `apply` - `destroy.py` is generated alongside `deploy.py`

**Stage 4 (Destroy Execute)**:

- Run: `pyinfra -y inventory.py destroy.py`
- PyInfra removes the file
- **Automatic Cleanup**: After successful destroy, the `.clockwork` directory is automatically removed (unless `--keep-files` flag is used)

```python
files.file(
    name="Remove conways_game_of_life.md",
    path="/path/to/conways_game_of_life.md",
    present=False,
)
```

**CLI Options**:
```bash
# Default: destroy resources and remove .clockwork directory
clockwork destroy

# Keep .clockwork directory for debugging
clockwork destroy --keep-files
```

### Assert Pipeline

The assert pipeline validates deployed resources:

**Stages 1-3**: Load → Complete → Compile assertions

**Stage 4**: Execute `assert.py` with PyInfra to validate resources are correctly deployed

## Design Principles

### 1. Python-First Orchestration

- No custom DSL or YAML, pure Python for infrastructure definition
- Pydantic for type safety and validation
- Full IDE support and autocompletion

### 2. Intelligent Completion

- **AI Stage**: Fills in missing fields intelligently using structured outputs
- **Compilation Stage**: Deterministic transformation to PyInfra operations
- **User Override**: User-provided values always take precedence

### 3. Automated Deployment

- Delegates execution to battle-tested PyInfra
- No custom state management or execution engines
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

    def to_pyinfra_operations(self) -> str:
        return f'''
server.systemd.service(
    name="Start {self.name}",
    service="{self.service_name}",
    running=True,
    enabled=True,
)
'''

    def to_pyinfra_destroy_operations(self) -> str:
        return f'''
server.systemd.service(
    name="Stop {self.name}",
    service="{self.service_name}",
    running=False,
    enabled=False,
)
'''
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

PyInfra supports many targets (SSH, Docker, Kubernetes). Modify `inventory.py` generation in `PyInfraCompiler`:

```python
def _generate_inventory(self) -> str:
    return '''
production_servers = [
    "ssh://user@server1.example.com",
    "ssh://user@server2.example.com",
]
'''
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
    "pyinfra>=3.0",                              # Deployment engine
]
```

## Key Features

| Feature | Implementation |
|---------|----------------|
| **Config Format** | Python (Pydantic models) |
| **AI Integration** | OpenAI-compatible APIs (cloud or local) |
| **Execution** | PyInfra (battle-tested) |
| **State Management** | PyInfra handles it |
| **Code Size** | ~1,000 lines of core logic |
| **Dependencies** | 7 focused packages |
| **Complexity** | Simple linear pipeline |

## Future Enhancements

- More resource types for broader infrastructure coverage
- Remote deployment targets (SSH, Kubernetes)
- Resource dependency orchestration
- Resource completion caching and optimization
- Streaming output for real-time feedback
- Multi-container orchestration patterns
- Advanced state tracking and lifecycle management
