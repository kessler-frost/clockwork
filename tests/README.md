# Clockwork Test Suite

Comprehensive test suite for Clockwork covering unit tests, integration tests,
and end-to-end verification.

## 📁 Test Structure

### 🧪 [Unit Tests](./unit/)

Fast, isolated tests for individual components:

- **`test_models.py`** - Pydantic model validation and serialization
- Component-specific unit tests
- Mock-based testing for external dependencies

### 🔗 [Integration Tests](./integration/)

Component interaction and API integration tests:

- **`test_agno_integration.py`** - AI agent integration with LM Studio
- **`test_integration.py`** - Core pipeline integration
- Database and external service integration

### 🎯 [End-to-End Tests](./e2e/)

Complete workflow verification tests:

- **`test_manual_e2e.py`** - Full pipeline verification
- Real-world scenario testing
- Performance and reliability testing

## 🚀 Running Tests

### Quick Test Commands

```bash
# Run all tests
python run_tests.py all

# Run specific test types
python run_tests.py unit
python run_tests.py integration  
python run_tests.py e2e

# Run with pytest directly
uv run pytest tests/unit/ -v                    # Unit tests only
uv run pytest tests/integration/ -v             # Integration tests only
uv run pytest tests/e2e/ -v                     # E2E tests only
```

### Advanced Testing

```bash
# Run with coverage
uv run pytest tests/ --cov=clockwork --cov-report=html

# Run specific test files
uv run pytest tests/unit/test_models.py -v

# Run with specific markers
uv run pytest tests/ -m "not slow" -v
```

## 🔧 Test Configuration

### Test Markers

- `@pytest.mark.unit` - Unit tests (fast, isolated)
- `@pytest.mark.integration` - Integration tests (moderate speed)
- `@pytest.mark.e2e` - End-to-end tests (slower, comprehensive)
- `@pytest.mark.slow` - Long-running tests
- `@pytest.mark.ai` - Tests requiring AI integration

### Test Dependencies

Tests use the following fixtures and utilities:

- `conftest.py` - Shared fixtures and configuration
- Mock objects for external dependencies
- Temporary directories for file system tests
- AI agent mocking for deterministic testing

## 🛡️ Testing Best Practices

### Unit Tests

- Test individual functions and classes in isolation
- Use mocks for external dependencies
- Focus on edge cases and error conditions
- Keep tests fast (< 1 second each)

### Integration Tests

- Test component interactions
- Use real dependencies where practical
- Verify data flow between modules
- Test configuration and environment handling

### End-to-End Tests

- Test complete user workflows
- Use realistic test data and scenarios
- Verify system behavior under normal conditions
- Include performance and reliability checks

## 📊 Test Coverage

Current test coverage targets:

- **Unit Tests**: > 90% line coverage
- **Integration Tests**: > 80% feature coverage
- **E2E Tests**: > 95% critical path coverage

Run `uv run pytest --cov=clockwork --cov-report=term-missing` to see
detailed coverage reports.

## 🐛 Debugging Tests

### Common Issues

1. **Import Errors**: Ensure `PYTHONPATH` includes project root
2. **AI Integration**: Check LM Studio is running for AI tests
3. **File Permissions**: Verify test has write access to temp directories
4. **Environment**: Use appropriate config files for test environment

### Debug Commands

```bash
# Run single test with verbose output
uv run pytest tests/unit/test_models.py::TestIRModels::test_variable_creation -v -s

# Debug with pdb
uv run pytest tests/integration/test_agno_integration.py --pdb

# Show test collection
uv run pytest tests/ --collect-only
```
