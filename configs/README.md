# Clockwork Configuration

This directory contains configuration files and templates for Clockwork
deployment across different environments.

## 📁 Configuration Files

### Environment-Specific Configurations

- **`development.json`** - Local development settings with AI integration enabled
- **`production.json`** - Production-ready settings with enhanced security
- **`lm_studio_config.json`** - AI agent configuration template

### Configuration Profiles

#### Development Profile (`development.json`)

- AI integration enabled with LM Studio
- Relaxed security for rapid iteration
- Detailed logging and debugging
- Local file system paths

#### Production Profile (`production.json`)

- AI integration disabled for security
- Strict validation and sandboxing
- Minimal logging to reduce attack surface
- System-level paths with proper permissions

## 🤖 AI Integration Setup

### Prerequisites

1. **Install LM Studio**: Download from <https://lmstudio.ai/>
2. **Download Model**: Search for `qwen/qwen3-4b-2507` and download
3. **Start Server**: Load model and start on port 1234
4. **Install Dependencies**: `uv add agno openai requests`

### Quick Test

```bash
# Use development config with AI enabled
clockwork --config configs/development.json compile examples/basic-web-service/main.cw
```

## 🔧 Configuration Usage

### CLI Configuration

```bash
# Use specific config file
clockwork --config configs/development.json <command>

# Override specific settings
clockwork --config configs/production.json --log-level DEBUG <command>
```

### Environment Variables

```bash
export CLOCKWORK_CONFIG=configs/development.json
export CLOCKWORK_LOG_LEVEL=DEBUG
export CLOCKWORK_AI_ENABLED=true
```

## 🛡️ Security Considerations

### Development

- AI integration enabled for rapid prototyping
- Broader runtime permissions for flexibility
- Local paths and relaxed validation

### Production

- AI integration disabled by default
- Minimal runtime permissions
- System paths with strict validation
- Enhanced logging and monitoring

## 📖 Configuration Schema

Each configuration file supports:

```json
{
  "clockwork": {
    "core": { "project_name": "...", "log_level": "..." },
    "forge": {
      "ai_agent": { "enabled": true, "provider": "lm_studio" }
    },
    "security": { "allowed_runtimes": [...], "validate_artifacts": true }
  }
}
```

See individual config files for complete schemas and available options.
