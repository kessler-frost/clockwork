# Clockwork Architecture

## Overview

Clockwork provides **intelligent, composable primitives for infrastructure** that combine:

- **Pydantic models** for declarative primitive definition
- **AI-powered completion** via PydanticAI (OpenAI-compatible APIs)
- **Pulumi** for automated deployment

Primitives are atomic building blocks - containers, files, containerized services - that you compose freely. Each primitive can be fully specified, partially specified, or AI-completed based on your preference.

The approach: Compose primitives (Python) → AI completes what you left unspecified → Automated deployment (Pulumi)

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
## Design Principles

### 1. Composable Primitives

- Primitives are atomic building blocks that compose freely
- No rigid constraints on how primitives combine
- Mix and match to build what you need
- Pure Python - no custom DSL or YAML

### 2. Adjustable Intelligence

- **Full Control**: Specify everything → AI does nothing
- **Hybrid**: Specify key details → AI fills gaps
- **Fast Mode**: Describe requirements → AI handles implementation
- **User Override**: User-provided values always take precedence
- You choose the level per primitive, per project

### 3. Functional Determinism Through Validation

Clockwork achieves reliable outcomes without sacrificing AI flexibility:

**Structural Determinism**: Pydantic models enforce output schemas
```python
class FileResource(Resource):
    name: str        # AI must provide a string
    content: str     # AI must provide a string
    directory: str   # AI must provide a string
```

**Behavioral Determinism**: Assertions validate functionality, not implementation
```python
web_server = DockerResource(
    description="web server for static files",
    assertions=[
        ContainerRunningAssert(),           # Must be running
        HealthcheckAssert(url="http://..."), # Must respond HTTP 200
    ]
)
# AI picks implementation (nginx, caddy, etc.)
# Assertions verify behavior → functionally deterministic
```

**User-Controlled Variance**: More specification → less AI variance → higher determinism

### 4. Automated Deployment

- Delegates execution to battle-tested Pulumi
- Pulumi handles state management and resource lifecycles
- Focus on intelligent primitives, not reimplementation

### 5. Simplicity

- Linear pipeline: Load → Complete → Compile → Deploy
- No complex dependency graphs or state management
- Clear separation of concerns between stages


## Core Pipeline Components

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
    must_run: bool = True                    # Whether container must be running
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

Pulumi manages state in the current working directory:

```text
.pulumi/          # Pulumi state backend
Pulumi.yaml       # Project configuration
Pulumi.dev.yaml   # Stack configuration (dev stack)
```

### 4. Core Orchestrator

**Location**: `clockwork/core.py`

The `ClockworkCore` class coordinates the entire pipeline by orchestrating the three previous components (Resources, ResourceCompleter, PulumiCompiler).

**Key Responsibilities**:

1. **Resource Loading**: Executes user's `main.py` and collects Resource instances
2. **Pipeline Coordination**: Chains together Load → Complete → Compile → Deploy stages
3. **Workflow Management**: Provides different pipeline workflows (apply, plan, destroy, assert)
4. **Dependency Resolution**: Orders resources correctly using topological sort (see Advanced Patterns)

**Available Workflows**:
- `apply()`: Full deployment pipeline (Load → Complete → Compile → Deploy)
- `plan()`: Preview changes without deploying (Load → Complete → Compile → Preview)
- `destroy()`: Tear down deployed infrastructure
- `assert_resources()`: Validate deployed resources meet assertions

Each workflow is covered in detail in the **Pipeline Workflows** section below.

## Advanced Architecture Patterns

### Composite Resources

Composite resources enable building complex infrastructure from simpler components through hierarchical composition. At the core of Clockwork's philosophy: **all resources are composites** - some are just atomic (zero children). This unifying principle allows consistent patterns whether building simple containers or complex multi-tier systems.

#### Key Building Blocks

##### BlankResource: Pure Composition

`BlankResource` (`/Users/fimbulwinter/dev/clockwork/clockwork/resources/blank.py`) serves as a lightweight container for grouping related resources without adding infrastructure-specific logic. It creates a Pulumi `ComponentResource` for proper dependency tracking while delegating all functionality to its children.

**Key characteristics:**
- **Zero infrastructure footprint**: No actual resources deployed
- **Organizational primitive**: Groups resources into logical units
- **AI-aware completion**: Triggers completion when children need it
- **Pulumi integration**: Compiles to `ComponentResource` with parent-child hierarchy

```python
from clockwork.resources import BlankResource, DockerResource

# Simple grouping
webapp = BlankResource(
    name="web-app",
    description="Complete web application stack"
).add(
    DockerResource(description="PostgreSQL database", ports=["5432:5432"]),
    DockerResource(description="Redis cache", ports=["6379:6379"]),
    DockerResource(description="FastAPI backend", ports=["8000:8000"])
)
```

##### ChildrenCollection: Dict-Like Access Pattern

The `ChildrenCollection` class (`/Users/fimbulwinter/dev/clockwork/clockwork/resources/base.py:20-120`) implements the `Mapping` protocol to provide intuitive, dict-like access to child resources by name.

```python
# Dict-style access
webapp.children["postgres-db"].ports = ["5433:5432"]

# Safe access with default
redis = webapp.children.get("redis", None)

# Membership test
if "postgres-db" in webapp.children:
    webapp.children["postgres-db"].restart_policy = "always"
```

**Benefits over index-based access:**
- **Semantic clarity**: `children["postgres"]` vs `get_children()[2]`
- **Refactoring safety**: Adding/removing children doesn't break references
- **Familiar API**: Standard Python dict patterns

#### Composition vs Connection: Critical Distinction

Understanding when to use `.add()` versus `.connect()` is fundamental to Clockwork's architecture:

| Aspect | `.add()` (Composition) | `.connect()` (Dependency) |
|--------|------------------------|---------------------------|
| **Relationship** | Parent contains child | Resource depends on resource |
| **Resource count** | 1 composite resource | N independent resources |
| **Lifecycle** | Atomic (deploy/destroy together) | Independent lifecycles |
| **Pulumi type** | `ComponentResource` with children | Separate resources with `depends_on` |
| **Use case** | "Is part of" | "Needs reference to" |

```python
# Composition (.add) - One "web-app" resource with 3 children
web_app = BlankResource(name="web-app").add(
    DockerResource(description="nginx", name="web"),
    FileResource(description="nginx config", name="config")
)

# Connection (.connect) - 2 separate resources with dependencies
db = DockerResource(name="postgres", ports=["5432:5432"])
api = DockerResource(name="api", ports=["8000:8000"]).connect(db)
```

See `examples/composite-resources/` for complete examples.

### Two-Phase AI Completion

Composite resources require a fundamentally different completion strategy than atomic resources. Clockwork implements **two-phase completion** to achieve system-level AI reasoning.

**Phase 1: Parent Completion with Children Context**
- AI sees the composite description + all child descriptions
- Plans overall architecture and relationships
- Determines compatibility requirements

**Phase 2: Child Completion with Parent Context**
- Each child receives completion with parent context
- AI knows about siblings through parent's context
- Makes coordinated decisions (compatible versions, shared networks)

**Implementation** (`clockwork/resource_completer.py`, lines 331-635):

```python
async def _complete_composite(self, resource, parent_context=None):
    # PHASE 1: Complete parent with children visible as context
    children_context = self._build_children_context(children)
    completed_parent = await self._complete_resource_with_message(...)

    # PHASE 2: Complete each child with parent context
    parent_context_for_children = self._build_parent_context(completed_parent)
    for child in children:
        if self._is_composite(child):
            # Recursive for nested composites
            completed_child = await self._complete_composite(child, parent_context_for_children)
        else:
            completed_child = await self._complete_child_resource(child, parent_context_for_children)
```

This architecture transforms AI from a "field filler" into a "system designer" that understands how infrastructure components compose into functioning applications.

### Resource Connections & Dependencies

#### Dual-Storage Pattern

Resource connections use a **dual-storage pattern** to maintain both serializable data (for AI context) and object references (for graph traversal).

**Storage Components** (`clockwork/resources/base.py`, lines 172-178):

```python
connections: list[dict[str, Any]] = Field(
    default_factory=list,
    description="Connection context dicts (Resource objects auto-converted)",
)
_connection_resources: list["Resource"] = PrivateAttr(default_factory=list)
```

**Why This Pattern?**

1. **AI Completion**: `connections` stores serializable dicts for AI models
2. **Graph Traversal**: `_connection_resources` stores Resource objects for dependency resolution
3. **Pydantic Compatibility**: Public field remains `list[dict]` to avoid circular schema references
4. **State Preservation**: Resource objects maintain their `_pulumi_resource` attributes

**Example Connection Context** (DockerResource):

```python
def get_connection_context(self) -> dict[str, Any]:
    context = {
        "name": self.name,
        "type": "DockerResource",
        "image": self.image,
    }
    if self.ports:
        context["ports"] = self.ports
    if self.env_vars:
        context["env_vars"] = self.env_vars
    return context
```

When a resource connects to a database, the AI sees the database's image, ports, and environment variables, enabling intelligent auto-configuration (e.g., generating `DATABASE_URL` environment variables).

#### Dependency Resolution & Deployment Ordering

Clockwork ensures safe deployments through a four-phase dependency resolution pipeline (`clockwork/core.py`, lines 240-369):

1. **Composite Flattening**: Recursively extract all children from composite resources
2. **Implicit Dependencies**: Add parent→child dependencies for correct lifecycle
3. **Cycle Detection**: Use DFS to detect circular dependencies before deployment
4. **Topological Sort**: Order resources so dependencies deploy first

**Cycle Detection Example**:
```python
# Detects cycles and provides helpful error messages
ValueError: Dependency cycle detected: postgres → api → postgres
```

**Topological Sort Example**:
```python
# Input: api depends on [postgres, redis]
# Output: [postgres, redis, api]  # Dependencies first
```

This prevents deployment failures from missing dependencies and catches circular dependency errors early with clear error messages.

## Pipeline Workflows

### Apply Pipeline (Deployment)

The apply pipeline is the primary workflow for deploying infrastructure. It follows a four-stage process: Load → Complete → Compile → Deploy.

#### Input: main.py

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

#### Stage 1: Load

- Execute `main.py` as Python module
- Extract all `Resource` instances
- Result: `[FileResource(name=None, description="...", ...)]`

#### Stage 2: Complete (AI)

- Check `article.needs_completion()` → True (has None fields)
- Build prompt: "Complete this FileResource with name, directory, content, and mode"
- Create PydanticAI Agent with `output_type=FileResource` (Tool Output mode)
- AI returns: `FileResource(name="conways_game_of_life.md", content="# Conway's...", directory=".", mode="644")`
- Merge with user values (user values override AI)
- Result: Fully completed `FileResource`

#### Stage 3: Compile (Pulumi)

- Call `article.to_pulumi()`
- Returns Pulumi Resource object (dynamic provider for file operations)
- Create Pulumi program function wrapping all resources

#### Stage 4: Deploy (Pulumi Automation API)

- Execute: `stack.up()` via Automation API
- Pulumi creates/updates infrastructure
- State managed by Pulumi in `.pulumi/` directory
- File created at specified path

### Plan Pipeline (Preview)

**Location**: `clockwork/core.py`

The plan pipeline previews infrastructure changes without deploying them. It's useful for reviewing what would be created, updated, or destroyed before running `apply`.

#### Pipeline Flow

The plan pipeline follows the same stages as Apply, but uses Pulumi's preview instead of deployment:

1. **Load**: Execute `main.py` and extract resources
2. **Complete**: AI fills missing fields (same as Apply)
3. **Compile**: Convert to Pulumi resources (same as Apply)
4. **Preview**: Use `stack.preview()` instead of `stack.up()`

#### Key Differences from Apply

- **No Infrastructure Changes**: Resources are compiled but not deployed
- **Preview Output**: Shows planned changes (creates, updates, deletes)
- **Fast Iteration**: Validate AI completions without deployment overhead
- **Safety Check**: Verify changes before committing to deployment

#### Usage

```bash
# Preview what would be deployed
uv run clockwork plan

# Review output to verify AI decisions
# Then deploy if satisfied
uv run clockwork apply
```

**Output Example**:
```
Previewing (dev)

     Type                 Name           Plan
 +   pulumi:pulumi:Stack  showcase-dev   create
 +   ├─ docker:Container  postgres-db    create
 +   ├─ docker:Container  redis-cache    create
 +   └─ docker:Container  api-server     create

Resources:
    + 4 to create
```

The plan pipeline is particularly useful when:
- Testing AI completion behavior without deployment
- Reviewing infrastructure changes before applying
- Validating complex composite resource hierarchies
- Verifying dependency ordering is correct

### Destroy Pipeline

**Location**: `clockwork/core.py` (lines 420-472)

The destroy pipeline removes deployed infrastructure and automatically cleans up working directories.

#### Pipeline Stages

**Stage 1: Load Resources and Extract Working Directories**

```python
async def destroy(self, main_file: Path, dry_run: bool = False, keep_files: bool = False):
    project_name = main_file.parent.name
    resources = self._load_resources(main_file)
    working_dirs = self._extract_working_directories(resources)
```

**Stage 2: Working Directory Extraction Logic**

The `_extract_working_directories` method (lines 371-418) identifies directories created by resources:

```python
def _extract_working_directories(self, resources: list[Any]) -> set[Path]:
    """Extract unique top-level working directories from resources."""
    directories = set()
    cwd = Path.cwd()

    for resource in resources:
        # Extract directory from FileResource
        if hasattr(resource, "directory") and resource.directory:
            dir_path = Path(resource.directory)
            # Get top-level directory relative to cwd
            top_level = cwd / dir_path.parts[0]
            if top_level != cwd:
                directories.add(top_level)

        # Extract directory from GitRepoResource
        if hasattr(resource, "dest") and resource.dest:
            dest_path = Path(resource.dest)
            top_level = cwd / dest_path.parts[0]
            if top_level != cwd:
                directories.add(top_level)

    return directories
```

**Key Logic**:
- **Resource-Specific Extraction**: Handles `FileResource.directory` and `GitRepoResource.dest`
- **Top-Level Extraction**: Extracts first path component (e.g., `scratch/foo/bar` → `scratch`)
- **Safety Check**: Skips paths outside cwd and excludes cwd itself
- **Deduplication**: Returns `set[Path]` to avoid duplicate deletions

**Stage 3: Pulumi Destroy**

```python
result = await self.pulumi_compiler.destroy(project_name)
```

**Stage 4: Automatic Cleanup with --keep-files Flag**

After successful destroy, working directories are automatically removed unless `--keep-files` is specified (lines 454-468):

```python
if result.get("success", False):
    if keep_files:
        logger.info("Keeping working directories (--keep-files flag set)")
        result["working_directories_kept"] = [str(d) for d in working_dirs]
    else:
        for directory in working_dirs:
            if directory.exists():
                logger.info(f"Removing working directory: {directory}")
                shutil.rmtree(directory)  # Recursive deletion
                logger.info(f"Deleted: {directory}")
```

**Behavior**:
- **Default (no flag)**: Automatically removes working directories like `scratch/`
- **With --keep-files**: Preserves working directories
- **Only on Success**: Cleanup only occurs if `result["success"]` is `True`
- **Recursive Deletion**: Uses `shutil.rmtree()` to remove directories and all contents

**CLI Usage**:
```bash
# Default: destroy infrastructure and remove working directories
clockwork destroy

# Keep working directories created by resources
clockwork destroy --keep-files

# Dry run: preview what would be destroyed
clockwork destroy --dry-run
```

### Assert Pipeline

**Location**: `clockwork/core.py` (lines 474-581)

The assert pipeline validates deployed resources by running assertions directly without Pulumi compilation.

#### Pipeline Stages

**Stages 1-2: Load and Complete Resources**

```python
async def assert_resources(self, main_file: Path, dry_run: bool = False):
    # 1. Load resources from main.py
    resources = self._load_resources(main_file)

    # 2. Resolve dependency order
    resources = self._resolve_dependency_order(resources)

    # 3. Complete resources if needed
    completed_resources = await self._complete_resources_safe(resources)
```

**Stage 3: Assertion Execution with Detailed Result Tracking**

**Results Structure**:
```python
# Initialize results dictionary
results = {"passed": [], "failed": [], "total": 0}
```

**Per-Resource Assertion Loop** (lines 520-571):

```python
for resource in completed_resources:
    if not resource.assertions:
        continue

    resource_name = resource.name or resource.__class__.__name__

    for assertion in resource.assertions:
        results["total"] += 1
        assertion_desc = assertion.description or assertion.__class__.__name__

        try:
            passed = await assertion.check(resource)

            if passed:
                results["passed"].append({
                    "resource": resource_name,
                    "assertion": assertion_desc,
                })
                logger.info(f"  ✓ Passed: {assertion_desc}")
            else:
                results["failed"].append({
                    "resource": resource_name,
                    "assertion": assertion_desc,
                    "error": "Assertion check returned False",
                })
                logger.error(f"  ✗ Failed: {assertion_desc}")

        except Exception as e:
            # Error handling and timeout behavior
            results["failed"].append({
                "resource": resource_name,
                "assertion": assertion_desc,
                "error": str(e),
            })
            logger.error(f"  ✗ Failed: {assertion_desc} - {e}")
```

**Detailed Result Tracking**:
- **Passed Assertions**: Records resource name and assertion description
- **Failed Assertions**: Records resource name, assertion description, and error message
- **Exception Handling**: Captures all exceptions (including timeouts) and stores as failures
- **Total Count**: Increments for each assertion run

**Final Results** (lines 574-581):

```python
return {
    "success": len(results["failed"]) == 0,  # True if all assertions passed
    "passed": len(results["passed"]),
    "failed": len(results["failed"]),
    "total": results["total"],
    "details": results,  # Full details with resource names and errors
}
```

**Return Structure Example**:
```python
{
    "success": False,
    "passed": 2,
    "failed": 1,
    "total": 3,
    "details": {
        "passed": [
            {"resource": "nginx-web", "assertion": "ContainerRunningAssert"}
        ],
        "failed": [
            {
                "resource": "api-server",
                "assertion": "HealthcheckAssert",
                "error": "Connection refused: http://localhost:8000"
            }
        ],
        "total": 3
    }
}
```

**Error Handling**:
- All exceptions during `assertion.check()` are caught
- Exceptions include: network timeouts, connection errors, file access errors
- Pipeline continues to next assertion (no early termination)

## Configuration & Tooling

### Settings Management

**Location**: `clockwork/settings.py`

Clockwork uses Pydantic Settings with environment variable loading and caching:

```python
class ClockworkSettings(BaseSettings):
    # AI Configuration
    api_key: str | None = Field(default=None)
    model: str = Field(default="meta-llama/llama-4-scout:free")
    base_url: str = Field(default="https://openrouter.ai/api/v1")

    # Pulumi Configuration (accepts both CW_PULUMI_CONFIG_PASSPHRASE and PULUMI_CONFIG_PASSPHRASE)
    pulumi_config_passphrase: str = Field(
        default="clockwork",
        validation_alias="PULUMI_CONFIG_PASSPHRASE",
    )

    # Resource Completion Configuration
    completion_max_retries: int = Field(
        default=3,
        description="Maximum retry attempts for AI resource completion",
    )
```

**Settings Caching Pattern**:
```python
_settings: ClockworkSettings | None = None

def get_settings() -> ClockworkSettings:
    """Get cached settings instance."""
    global _settings
    if _settings is None:
        _settings = ClockworkSettings()
    return _settings
```

Settings are loaded once on first access and cached for performance.

### CLI

**Location**: `clockwork/cli.py`

Simple Typer-based CLI:

```bash
uv run clockwork apply       # Full pipeline (deploy resources via Pulumi)
uv run clockwork plan        # Preview resources without deploying
uv run clockwork assert      # Validate deployed resources
uv run clockwork destroy     # Tear down resources via Pulumi
uv run clockwork version     # Show version
```

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
clockwork apply --model "anthropic/claude-haiku-4.5"

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
