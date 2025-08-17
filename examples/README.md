# Clockwork Examples

This directory contains practical examples of using Clockwork for different scenarios.

## Examples

### Basic Web Service (`basic-web-service/`)
Simple web service deployment with health checks.

### Microservices (`microservices/`)
Multi-service application with dependencies and networking.

### Development Environment (`dev-environment/`)
Local development setup with multiple tools and services.

### Production Deployment (`production/`)
Production-ready configuration with security and monitoring.

## Running Examples

Each example directory contains:
- `main.cw` - Main configuration
- `variables.cwvars` - Variable overrides
- `README.md` - Specific instructions

To run an example:

```bash
cd examples/basic-web-service
clockwork plan
clockwork apply
```