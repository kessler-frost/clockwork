# Clockwork Architecture

## Overview

Clockwork provides **intelligent infrastructure orchestration in Python** that combines:

- **Pydantic models** for declarative resource definition
- **AI-powered intelligence** via PydanticAI + OpenRouter
- **PyInfra** for automated deployment

The approach: Define infrastructure (Python) → AI intelligence (artifacts) → Automated deployment (PyInfra)

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
       ├─── 2. Generate Artifacts ────────────┤
       │    (AI via OpenRouter/PydanticAI)   │
       │    • Only for resources with         │
       │      needs_artifact_generation()     │
       │    • Returns Dict[name, content]     │
       │                                      │
       ├─── 3. Compile to PyInfra ────────────┤
       │    (Template-based, no AI)          │
       │    • resource.to_pyinfra_operations()│
       │    • Generate inventory.py           │
       │    • Generate deploy.py              │
       │                                      │
       └─── 4. Execute Deploy ────────────────┘
            (subprocess: pyinfra inventory.py deploy.py)
```

## Core Components

### 1. Resources (Pydantic Models)

**Location**: `clockwork/resources/`

Resources are Pydantic models that represent infrastructure components:

```python
class Resource(BaseModel):
    name: str
    description: Optional[str] = None

    def needs_artifact_generation(self) -> bool:
        """Does this resource need AI-generated content?"""
        raise NotImplementedError

    def to_pyinfra_operations(self, artifacts: Dict[str, Any]) -> str:
        """Generate PyInfra operation code."""
        raise NotImplementedError
```

#### Example: FileResource

```python
class FileResource(Resource):
    name: str               # filename
    description: str        # what it should contain (for AI)
    size: ArtifactSize     # size hint for AI
    path: Optional[str]     # where to create it
    content: Optional[str]  # if provided, skip AI
    mode: str = "644"       # file permissions
```

#### Example: AppleContainerResource

```python
class AppleContainerResource(Resource):
    name: str                         # container name
    description: str                  # what it does (for AI image suggestion)
    image: Optional[str] = None      # Container image (AI suggests if not provided)
    ports: Optional[List[str]] = None  # Port mappings ["8080:80"]
    volumes: Optional[List[str]] = None  # Volume mounts ["/host:/container"]
    env_vars: Optional[Dict[str, str]] = None  # Environment variables
    networks: Optional[List[str]] = None  # Networks
    present: bool = True              # Should container exist
    start: bool = True                # Should container be running
```

### 2. Artifact Generator (AI Stage)

**Location**: `clockwork/artifact_generator.py`

Generates content using AI when resources need it:

```python
class ArtifactGenerator:
    def generate(self, resources: List[Resource]) -> Dict[str, str]:
        """Generate artifacts for resources that need them."""
        artifacts = {}
        for resource in resources:
            if resource.needs_artifact_generation():
                content = self._generate_for_resource(resource)
                artifacts[resource.name] = content
        return artifacts
```

**Integration**:

- Uses **OpenRouter API** via PydanticAI
- Model: `meta-llama/llama-4-scout:free` (configurable)
- Smart prompts based on resource type, size, file format

### 3. PyInfra Compiler (Template Stage)

**Location**: `clockwork/pyinfra_compiler.py`

Converts resources to executable PyInfra code:

```python
class PyInfraCompiler:
    def compile(self, resources: List[Resource], artifacts: Dict[str, str]) -> Path:
        """Compile resources to PyInfra deployment files."""
        # Generate inventory.py (localhost)
        # Generate deploy.py (all operations)
        # Return path to .clockwork/pyinfra/
```

**Output Structure**:

```text
.clockwork/pyinfra/
├── inventory.py    # "@local" (localhost)
└── deploy.py       # All PyInfra operations
```

### 4. Core Orchestrator

**Location**: `clockwork/core.py`

Main pipeline coordinator:

```python
class ClockworkCore:
    def apply(self, main_file: Path, dry_run: bool = False):
        resources = self._load_resources(main_file)      # 1. Load
        artifacts = self.artifact_generator.generate(resources)  # 2. Generate
        pyinfra_dir = self.pyinfra_compiler.compile(resources, artifacts)  # 3. Compile
        if not dry_run:
            result = self._execute_pyinfra(pyinfra_dir)  # 4. Deploy
        return result

    def destroy(self, main_file: Path, dry_run: bool = False):
        resources = self._load_resources(main_file)      # 1. Load
        artifacts = self.artifact_generator.generate(resources)  # 2. Generate (if needed)
        pyinfra_dir = self.pyinfra_compiler.compile_destroy(resources, artifacts)  # 3. Compile destroy
        if not dry_run:
            result = self._execute_pyinfra(pyinfra_dir)  # 4. Execute teardown
        return result
```

#### Destroy Operations

Each resource implements `to_pyinfra_destroy_operations()` to generate teardown code. The destroy pipeline follows the same stages but generates removal operations instead of creation operations.

### 5. CLI

**Location**: `clockwork/cli.py`

Simple Typer-based CLI:

```bash
uv run clockwork apply       # Full pipeline (deploy resources)
uv run clockwork generate    # Generate artifacts without deploying
uv run clockwork assert      # Validate deployed resources
uv run clockwork destroy     # Tear down resources
uv run clockwork version     # Show version
```

## Data Flow

### Input: main.py

```python
from clockwork.resources import FileResource, ArtifactSize

article = FileResource(
    name="article.md",
    description="Write about Conway's Game of Life",
    size=ArtifactSize.MEDIUM
)
```

### Stage 1: Load

- Execute `main.py` as Python module
- Extract all `Resource` instances
- Result: `[FileResource(name="article.md", ...)]`

### Stage 2: Generate (AI)

- Check `article.needs_artifact_generation()` → True
- Call OpenRouter API with smart prompt
- Result: `{"article.md": "# Conway's Game of Life\n\n..."}`

### Stage 3: Compile (Template)

- Call `article.to_pyinfra_operations(artifacts)`
- Generate PyInfra code:

```python
files.put(
    name="Create article.md",
    src=StringIO("""# Conway's Game of Life\n\n..."""),
    dest="/tmp/article.md",
    mode="644",
)
```

### Stage 4: Deploy (PyInfra)

- Run: `pyinfra inventory.py deploy.py`
- PyInfra executes operations
- File created at `/tmp/article.md`

### Destroy Pipeline

The destroy pipeline follows the same stages but generates teardown operations:

**Stage 1-2**: Load resources and generate artifacts (same as apply)

**Stage 3 (Destroy Compile)**:

- Call `article.to_pyinfra_destroy_operations(artifacts)`
- Generate PyInfra code:

```python
files.file(
    name="Remove article.md",
    path="/tmp/article.md",
    present=False,
)
```

**Stage 4 (Destroy Execute)**:

- Run: `pyinfra inventory.py deploy.py`
- PyInfra removes the file

## Design Principles

### 1. Python-First Orchestration

- No custom DSL or YAML, pure Python for infrastructure definition
- Pydantic for type safety and validation
- Full IDE support and autocompletion

### 2. Intelligent Processing

- **AI Stage**: Dynamic, intelligent content and configuration generation
- **Compilation Stage**: Deterministic transformation to PyInfra operations

### 3. Automated Deployment

- Delegates execution to battle-tested PyInfra
- No custom state management or execution engines
- Focus on intelligent orchestration, not reimplementation

### 4. Simplicity

- Linear orchestration pipeline: Load → Generate → Compile → Deploy
- No complex dependency graphs or state management
- Clear separation of concerns between stages

## Extension Points

### Adding New Resources

1. Create new class in `clockwork/resources/`:

```python
class ServiceResource(Resource):
    # Define fields

    def needs_artifact_generation(self) -> bool:
        # Logic to determine if AI needed

    def to_pyinfra_operations(self, artifacts: Dict[str, Any]) -> str:
        # Return PyInfra operation code for deployment
        return '''
        server.systemd.service(
            name="Start my service",
            service="myapp",
            running=True,
        )
        '''

    def to_pyinfra_destroy_operations(self, artifacts: Dict[str, Any]) -> str:
        # Return PyInfra operation code for teardown
        return '''
        server.systemd.service(
            name="Stop my service",
            service="myapp",
            running=False,
            enabled=False,
        )
        '''
```

#### Real Example: AppleContainerResource

See `clockwork/resources/apple_container.py` for a complete implementation that:

- Uses AI to suggest container images when not specified
- Supports ports, volumes, environment variables, and networks
- Implements both deploy and destroy operations
- Provides comprehensive documentation and examples

1. Export in `__init__.py`
2. Add tests
3. Create example

### Custom AI Models

Change model via CLI or environment:

```bash
clockwork apply main.py --model "anthropic/claude-3.5-sonnet"
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
    "openai>=1.99.9",                            # OpenRouter client
    "pyinfra>=3.0",                              # Deployment engine
    "mcp>=1.0.0",                                # Model Context Protocol
]
```

## Key Features

| Feature | Implementation |
|---------|----------------|
| **Config Format** | Python (Pydantic models) |
| **AI Integration** | OpenRouter API (cloud-based) |
| **Execution** | PyInfra (battle-tested) |
| **State Management** | PyInfra handles it |
| **Code Size** | ~1,000 lines of core logic |
| **Dependencies** | 8 focused packages |
| **Complexity** | Simple linear pipeline |

## Future Enhancements

- More resource types for broader infrastructure coverage
- Remote deployment targets (SSH, Kubernetes)
- Resource dependency orchestration
- AI artifact caching and optimization
- Streaming output for real-time feedback
- Multi-container orchestration patterns
- Advanced state tracking and lifecycle management
