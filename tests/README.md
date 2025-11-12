# Clockwork Test Suite

Test suite for Clockwork covering resources, integration, and Pulumi compilation.

## Running Tests

```bash
# Run all tests
uv run pytest tests/ -v

# Run specific test file
uv run pytest tests/test_resources.py -v

# Run with coverage
uv run pytest tests/ --cov=clockwork --cov-report=html
```

## Test Files

- **`test_resources.py`** - FileResource and base Resource tests
- **`test_apple_container_resource.py`** - AppleContainerResource tests (macOS native containers)
- **`test_connections.py`** - Resource connection and dependency tests
- **`test_tool_selector.py`** - Tool selection and integration tests
- **`test_integration.py`** - Full pipeline integration tests
- **`conftest.py`** - Shared fixtures and configuration

## Testing Best Practices

- Test individual functions and classes in isolation
- Use mocks for external dependencies (AI calls)
- Focus on edge cases and error conditions
- Verify data flow between modules
- Test complete user workflows

## Coverage

Run with coverage to see detailed reports:

```bash
uv run pytest tests/ --cov=clockwork --cov-report=term-missing
```
