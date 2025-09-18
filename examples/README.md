# Clockwork Examples

This directory contains working examples of using Clockwork for service deployment.

## Examples

### Hello World (`hello-world/`)

**Status**: ✅ **Minimal Working Example**

The simplest possible Clockwork deployment - perfect for getting started.

**Features**:
- Single nginx:alpine container
- Minimal configuration
- Custom environment variables

**Usage**:
```bash
cd examples/hello-world
uv run clockwork apply --auto-approve
curl http://localhost:8080
```

### Basic Web Service (`basic-web-service/`)

**Status**: ✅ **Full Featured Example**

Complete web service deployment with health checks and comprehensive configuration.

**Features**:
- Service deployment with Docker containers
- Port mapping and environment variables
- HTTP health verification
- Variable management
- Both .cw and .hcl syntax examples

**Usage**:
```bash
cd examples/basic-web-service
uv run clockwork plan      # Preview deployment
uv run clockwork apply     # Deploy service
```

**What it deploys**:
- nginx:1.25-alpine container on port 3000
- HTTP health check verification
- Configurable via variables.cwvars

## File Structure

Each example directory contains:
- `main.cw` - Main service configuration
- `variables.cwvars` - Variable definitions and defaults
- `README.md` - Example-specific documentation

## Requirements

- Docker installed and running
- uv package manager
- Clockwork CLI

## Quick Start

1. **Try hello-world first** (simplest)
2. **Then basic-web-service** (full features)
3. **Modify variables.cwvars** to customize
