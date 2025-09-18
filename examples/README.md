# Clockwork Examples

This directory contains working examples of using Clockwork for service deployment.

## Basic Web Service (`basic-web-service/`)

**Status**: ✅ **Complete Example**

Complete web service deployment with health checks and comprehensive configuration.

**Features**:
- Service deployment with Docker containers
- Port mapping and environment variables
- HTTP health verification
- Variable management
- Complete configuration example

**Usage**:
```bash
cd examples/basic-web-service
uv run clockwork plan main.cw      # Preview deployment
uv run clockwork apply main.cw     # Deploy service
```

**What it deploys**:
- nginx:latest container on configurable port (default: 8080)
- HTTP health check verification
- Configurable via variables.cwvars

## File Structure

The example directory contains:
- `main.cw` - Main service configuration
- `variables.cwvars` - Variable definitions and defaults
- `README.md` - Example-specific documentation

## Requirements

- Docker installed and running
- uv package manager
- Clockwork CLI

## Quick Start

1. **Navigate to the example**: `cd examples/basic-web-service`
2. **Preview deployment**: `uv run clockwork plan main.cw`
3. **Deploy service**: `uv run clockwork apply main.cw`
4. **Test service**: `curl http://localhost:8080`
5. **Modify variables.cwvars** to customize
