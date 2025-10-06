# Clockwork Architecture

## Overview

Clockwork is a **factory for intelligent declarative infrastructure tasks** that combines:
- **Pydantic models** for declarative resource definition
- **AI-powered artifact generation** via Agno 2.0 + OpenRouter
- **PyInfra** for infrastructure deployment

Think of it as: Define what you want (Python) → AI figures out how (artifacts) → PyInfra makes it happen (deployment)

## Architecture Diagram

```
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
       │    (AI via OpenRouter/Agno)         │
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

**Example: FileResource**
```python
class FileResource(Resource):
    name: str               # filename
    description: str        # what it should contain (for AI)
    size: ArtifactSize     # size hint for AI
    path: Optional[str]     # where to create it
    content: Optional[str]  # if provided, skip AI
    mode: str = "644"       # file permissions
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
- Uses **OpenRouter API** via OpenAI client
- Model: `openai/gpt-oss-20b:free` (configurable)
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
```
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
```

### 5. CLI

**Location**: `clockwork/cli.py`

Simple Typer-based CLI:

```bash
clockwork apply main.py    # Full pipeline
clockwork plan main.py     # Dry run (no execution)
clockwork version          # Show version
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

## Design Principles

### 1. Python-First
- No custom DSL, pure Python for resource definition
- Pydantic for type safety and validation
- Full IDE support and autocompletion

### 2. Two-Stage Compilation
- **Stage 1 (AI)**: Dynamic, intelligent, for content generation
- **Stage 2 (Template)**: Deterministic, for infrastructure code

### 3. Delegation to PyInfra
- No custom executors, runners, or state management
- PyInfra handles all deployment complexity
- We just generate the PyInfra code

### 4. Simplicity
- Single linear pipeline: Load → Generate → Compile → Deploy
- No complex state graphs or dependency resolution
- Resources are independent (PyInfra handles execution order)

## Extension Points

### Adding New Resources

1. Create new class in `clockwork/resources/`:
```python
class ServiceResource(Resource):
    # Define fields

    def needs_artifact_generation(self) -> bool:
        # Logic to determine if AI needed

    def to_pyinfra_operations(self, artifacts: Dict[str, Any]) -> str:
        # Return PyInfra operation code
        return '''
        server.systemd.service(
            name="Start my service",
            service="myapp",
            running=True,
        )
        '''
```

2. Export in `__init__.py`
3. Add tests
4. Create example

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
    "pydantic>=2.0.0",      # Resource models
    "typer>=0.16.0",        # CLI
    "rich>=13.0.0",         # Terminal output
    "agno>=2.0.4",          # AI framework
    "openai>=1.99.9",       # OpenRouter client
    "pyinfra>=3.0",         # Deployment engine
]
```

## Key Features

| Feature | Implementation |
|---------|----------------|
| **Config Format** | Python (Pydantic models) |
| **AI Integration** | OpenRouter API (cloud-based) |
| **Execution** | PyInfra (battle-tested) |
| **State Management** | PyInfra handles it |
| **Code Size** | ~700 lines of core logic |
| **Dependencies** | 7 focused packages |
| **Complexity** | Simple linear pipeline |

## Future Enhancements

- More resource types (ServiceResource, DatabaseResource)
- Support for remote PyInfra targets (SSH, Kubernetes)
- Resource dependencies and ordering hints
- Caching of AI-generated artifacts
- Streaming output for long AI generations
