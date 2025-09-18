# Clockwork - Declarative Infrastructure with PyInfra

**Simplified declarative infrastructure management using PyInfra for reliable, deterministic deployments.**

[![Tests](https://img.shields.io/badge/tests-passing-green)](./tests/)
[![PyInfra](https://img.shields.io/badge/pyinfra-integrated-green)](https://pyinfra.com/)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue)](./pyproject.toml)

## 🚀 Quick Start

```bash
# Install Clockwork
uv add clockwork

# Apply a configuration (dry-run first)
uv run clockwork plan examples/basic-web-service/main.cw
uv run clockwork apply examples/basic-web-service/main.cw
```

## 📖 Overview

Clockwork is a simplified declarative infrastructure tool built on PyInfra for reliable,
deterministic deployments. It uses a straightforward two-phase pipeline (Parse → Execute)
to convert `.cw` configuration files into PyInfra operations that manage your infrastructure.

### Key Benefits

- **Simple and reliable**: Two-phase pipeline for predictable deployments
- **PyInfra powered**: Leverages mature, battle-tested infrastructure automation
- **Declarative syntax**: Easy-to-read `.cw` configuration files
- **Multi-target support**: Deploy to local, SSH, Docker, and Kubernetes environments
- **Built-in safety**: Dry-run mode and state management prevent accidents

## 📁 Project Structure

```text
clockwork/
├── 📦 clockwork/          # Core package
│   ├── 📥 intake/         # Configuration parsing and validation
│   ├── 🔧 pyinfra_ops/    # PyInfra operations (Docker, K8s, health checks)
│   ├── parser.py          # Main .cw file parser
│   ├── core.py           # Parse → Execute pipeline orchestrator
│   └── cli.py            # Command-line interface
├── 📚 docs/              # Documentation
├── 🧪 tests/             # Test suite
├── 📋 examples/          # Sample .cw configurations
└── run_tests.py         # Test runner utility
```

See [ARCHITECTURE.md](./ARCHITECTURE.md) for detailed technical documentation.

## 🔧 Core Concepts

Clockwork operates through a simple two-phase pipeline:

1. **Parse** - Convert `.cw` configuration files into PyInfra operations
2. **Execute** - Run PyInfra operations on target infrastructure

### Supported Resources

- **Docker containers**: Service deployment and management
- **Docker Compose**: Multi-container application stacks
- **Kubernetes**: Pod and service deployments
- **Health checks**: HTTP endpoint verification
- **Terraform**: Infrastructure provisioning (experimental)

For detailed architecture information, see [ARCHITECTURE.md](./ARCHITECTURE.md).

## 🔧 CLI Usage

### Basic Commands

```bash
# Show execution plan without applying changes (dry-run)
uv run clockwork plan examples/basic-web-service/main.cw

# Apply configuration to infrastructure
uv run clockwork apply examples/basic-web-service/main.cw

# Watch file for changes and auto-apply
uv run clockwork watch examples/basic-web-service/main.cw

# Show PyInfra facts for a target
uv run clockwork facts localhost

# Manage deployment state
uv run clockwork state show
uv run clockwork state reset
```

### Configuration

```bash
# Override variables and settings
uv run clockwork apply --var KEY=VALUE --timeout 300 examples/app.cw

# Target different environments
uv run clockwork apply --target production examples/app.cw
```

## 📚 Documentation

- **[Architecture Guide](./ARCHITECTURE.md)** - Technical architecture and system design
- **[Configuration](#configuration)** - Environment variable configuration
- **[Examples](./examples/)** - Sample configurations and use cases

## 🧪 Testing

```bash
# Run all tests
uv run python run_tests.py all

# Run specific test types
uv run pytest tests/unit/ -v
uv run pytest tests/integration/ -v
uv run pytest tests/e2e/ -v
```

## 🚀 Getting Started

1. **Install Clockwork**: `uv add clockwork`
2. **Try an example**: `uv run clockwork plan examples/basic-web-service/main.cw`
3. **Apply the example**: `uv run clockwork apply examples/basic-web-service/main.cw`
4. **Create your config**: Use examples as templates for your own `.cw` files

## Configuration

Clockwork uses environment variables for configuration. Key variables include:

- `CLOCKWORK_PROJECT_NAME`: Project name (default: current directory name)
- `CLOCKWORK_LOG_LEVEL`: Log level (default: INFO)
- `CLOCKWORK_TARGET`: Default deployment target (default: localhost)
- `CLOCKWORK_PARALLEL_LIMIT`: Parallel execution limit (default: 4)
- `CLOCKWORK_DEFAULT_TIMEOUT`: Default operation timeout in seconds (default: 300)
- `CLOCKWORK_STATE_FILE`: State file location (default: .clockwork/state.json)

You can also create a `.env` file in your project root with these variables.
