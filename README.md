# Clockwork - Factory for Intelligent Declarative Tasks

**Factory for intelligent declarative tasks with deterministic core and
AI-powered compiler that generates executable artifacts in any language.**

[![Tests](https://img.shields.io/badge/tests-passing-green)](./tests/)
[![AI Integration](https://img.shields.io/badge/AI-LM%20Studio%20%2B%20Agno-blue)](./docs/guides/AI_INTEGRATION.md)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue)](./pyproject.toml)

## 🚀 Quick Start

```bash
# Install with AI integration
uv add clockwork agno openai requests

# Run example with AI compilation
clockwork compile examples/basic-web-service/main.cw

# Or run without AI (fallback mode)
clockwork --config configs/production.json compile examples/basic-web-service/main.cw
```

## 📖 Overview

Clockwork is a factory for building intelligent declarative tasks, designed
with simplicity first. It features a deterministic core pipeline (Intake →
Assembly → Forge) with optional AI-powered compilation and daemon for
continuous reconciliation. All artifacts are materialized to disk and
user-editable, with strict boundaries where agents propose and the core
validates & executes.

### North Star Principles

- **Simplicity first**: single-pass run; optional daemon for long-running reconcile
- **Deterministic core**: Intake → Assembly → Forge pipeline
- **User-editable artifacts**: everything materialized to disk
- **Strict boundaries**: agent proposes; core validates & executes

## 📁 Project Structure

```text
clockwork/
├── 📦 clockwork/          # Core package
│   ├── 📥 intake/         # Phase 1: HCL2 parsing & validation
│   ├── 🔧 assembly/       # Phase 2: Action planning & dependency resolution
│   ├── ⚡ forge/          # Phase 3: AI-powered artifact compilation
│   ├── 🤖 daemon/         # Background reconciliation & auto-fix
│   └── core.py           # Main orchestrator
├── 📚 docs/              # Documentation (guides, architecture, API)
├── ⚙️ configs/           # Environment configurations (dev, prod, AI)
├── 🧪 tests/             # Organized test suite (unit, integration, e2e)
├── 📋 examples/          # Sample .cw configurations
└── 🔧 run_tests.py       # Test runner utility
```

See [ARCHITECTURE.md](./ARCHITECTURE.md) for detailed technical documentation.

## 🔧 Core Concepts

Clockwork operates through a simple three-phase pipeline:

1. **Intake** - Parse `.cw` configuration files into validated intermediate representation
2. **Assembly** - Plan actions and resolve dependencies
3. **Forge** - Generate and execute artifacts with optional AI assistance

For detailed architecture information, see [ARCHITECTURE.md](./ARCHITECTURE.md).

## 🔧 CLI Usage

### Basic Commands

```bash
# Plan actions without execution
clockwork plan examples/basic-web-service/main.cw

# Compile and execute with AI assistance
clockwork compile examples/basic-web-service/main.cw

# Apply configuration changes
clockwork apply --var app_name=myapp --var port=8080

# Verify service health
clockwork verify
```

### Configuration

```bash
# Use specific configuration
clockwork --config configs/development.json compile main.cw

# Override variables
clockwork apply --var KEY=VALUE --timeout-per-step 300
```

## 📚 Documentation

- **[Architecture Guide](./ARCHITECTURE.md)** - Technical architecture and system design
- **[AI Integration](./docs/guides/AI_INTEGRATION.md)** - LM Studio + Agno setup guide
- **[Configuration](./configs/README.md)** - Environment configuration options
- **[Examples](./examples/)** - Sample configurations and use cases

## 🧪 Testing

```bash
# Run all tests
python run_tests.py all

# Run specific test types
uv run pytest tests/unit/ -v
uv run pytest tests/integration/ -v
uv run pytest tests/e2e/ -v
```

## 🚀 Getting Started

1. **Install dependencies**: `uv add clockwork agno openai requests`
2. **Set up AI (optional)**: Follow [AI Integration Guide](./docs/guides/AI_INTEGRATION.md)
3. **Try an example**: `clockwork compile examples/basic-web-service/main.cw`
4. **Create your config**: Use examples as templates for your own `.cw` files
