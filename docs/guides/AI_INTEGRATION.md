# AI Agent Integration with Agno Framework

Clockwork now supports AI-powered artifact compilation using the Agno framework with LM Studio integration. This enables automatic generation of executable scripts from declarative task specifications.

## Features

- **AI-Powered Compilation**: Converts ActionList specifications to executable artifacts using local LLMs
- **Structured Output**: Uses Pydantic models for reliable, type-safe artifact generation
- **Fallback Support**: Gracefully handles AI unavailability with automatic fallback
- **Security Validation**: Comprehensive security checks on AI-generated artifacts
- **Local Inference**: Uses LM Studio for private, local AI processing

## Quick Setup

1. **Install LM Studio**: Download from https://lmstudio.ai/
2. **Download Model**: Search for `qwen/qwen3-4b-thinking-2507` in LM Studio and download
3. **Start Server**: Load the model and start LM Studio server on port 1234
4. **Install Dependencies**: `pip install agno>=1.7.11 openai>=1.99.9`
5. **Use Clockwork**: Run `clockwork compile your_config.cw` - AI integration is enabled by default

## Configuration

The compiler automatically detects and uses Agno when available. Configure using environment variables:

```bash
# Core AI Configuration
export CLOCKWORK_USE_AGNO=true
export CLOCKWORK_LM_STUDIO_URL=http://localhost:1234
export CLOCKWORK_LM_STUDIO_MODEL=qwen/qwen3-4b-thinking-2507

# Optional settings
export CLOCKWORK_AI_TIMEOUT=300
export CLOCKWORK_AI_MAX_TOKENS=6000
export CLOCKWORK_AI_TEMPERATURE=0.1
```

Or use a `.env` file:

```bash
# .env file
CLOCKWORK_USE_AGNO=true
CLOCKWORK_LM_STUDIO_URL=http://localhost:1234
CLOCKWORK_LM_STUDIO_MODEL=qwen/qwen3-4b-thinking-2507
```

## AI Agent Capabilities

The AI agent specializes in:

- **Multi-language Support**: Generates bash, Python, Deno, Go, and other scripts
- **Security Best Practices**: Follows security guidelines and uses safe patterns
- **Error Handling**: Includes comprehensive error handling and logging
- **Dependency Management**: Respects execution order and dependencies
- **Path Security**: Ensures all artifacts are within allowed directories

## Architecture

```
ActionList → Agno AI Agent → AgentArtifactBundle → ArtifactBundle → Validation
```

1. **Input**: Declarative ActionList with task specifications
2. **AI Processing**: Agno agent generates structured artifact bundle
3. **Conversion**: Transform AI response to Clockwork format
4. **Validation**: Security and compliance checks
5. **Output**: Validated, executable ArtifactBundle

## Error Handling

The system provides robust error handling:

- **Connection Failures**: Falls back to placeholder implementation
- **Model Unavailable**: Graceful degradation with informative logging
- **Invalid Output**: Validation catches and reports AI generation errors
- **Security Issues**: Comprehensive security validation blocks unsafe artifacts

## Troubleshooting

- **"Agno compilation failed"**: Check LM Studio is running and model is loaded
- **Connection timeout**: Verify LM Studio server URL and increase timeout
- **Import errors**: Ensure `agno` and `openai` packages are installed
- **Model not found**: Download the required model in LM Studio

## Environment Variables Reference

| Variable | Description | Default |
|----------|-------------|----------|
| `CLOCKWORK_USE_AGNO` | Enable AI integration | `true` |
| `CLOCKWORK_LM_STUDIO_URL` | LM Studio server URL | `http://localhost:1234` |
| `CLOCKWORK_LM_STUDIO_MODEL` | Model identifier | `qwen/qwen3-4b-2507` |
| `CLOCKWORK_AI_TIMEOUT` | Request timeout (seconds) | `300` |
| `CLOCKWORK_AI_MAX_TOKENS` | Maximum response tokens | `6000` |
| `CLOCKWORK_AI_TEMPERATURE` | Model temperature | `0.1` |
| `CLOCKWORK_AI_MAX_RETRIES` | Maximum retry attempts | `3` |

## Development

Run tests with: `pytest tests/test_agno_integration.py`

The integration includes comprehensive unit tests covering:
- AI agent initialization and configuration
- Compilation success and failure scenarios
- Fallback behavior and error handling
- Structured output parsing and validation
