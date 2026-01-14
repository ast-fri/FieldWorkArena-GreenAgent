# Testing Guide

This document provides detailed information about running tests in the FWA (Field Work Arena) project.

## Environment Variables

Integration tests require authentication tokens to be set via environment variables.

### FWA_TEST_TOKEN

HuggingFace authentication token required for running integration tests. In production, this is configured in `scenario.toml`.

#### Using .env File (Recommended)

Create a `.env` file in the project root (**Important: already included in `.gitignore`**):

```env
FWA_TEST_TOKEN=your-token-here
```

If you use `pytest-dotenv`, it will automatically load this file.

## Running Tests

### All Tests
```powershell
uv run pytest tests/ -v
```

### Integration Tests Only
```powershell
uv run pytest tests/agent/test_fwa_green_agent.py -v
```

### Unit Tests Only (No Environment Variables Required)
```powershell
uv run pytest tests/agent/metrics/ -v
```

### Using Test Markers
```powershell
# Integration tests only
uv run pytest -m integration -v

# Exclude integration tests
uv run pytest -m "not integration" -v
```

## Token Not Set

If `FWA_TEST_TOKEN` is not set, integration tests will be automatically skipped:

```
tests/agent/test_fwa_green_agent.py::test_green_agent_evaluation SKIPPED
Reason: FWA_TEST_TOKEN environment variable not set.
```

## Security Notes

⚠️ **Important**: 
- **Never commit tokens to Git repositories**
- Ensure `.env` file is included in `.gitignore` (already configured)
- Keep the `token` field in `scenario.toml` empty
- Use environment variables or secret management services for all sensitive credentials

## Test Implementation Details

Integration tests use a temporary scenario file approach to inject tokens at runtime:

1. The template `scenario.toml` contains an empty token field
2. During test execution, a temporary file is created with the token from `FWA_TEST_TOKEN`
3. The temporary file is used for the test and deleted afterward
4. This ensures no tokens are committed to version control

See [test_fwa_green_agent.py](../agent/test_fwa_green_agent.py) for implementation details.

## Test Directory Structure

```
tests/
├── README.md                       # This file
├── agent/
│   ├── test_fwa_green_agent.py    # Integration tests for Green Agent
│   └── metrics/
│       └── tasks/                  # Unit tests for Green Agent
└── fixtures/                       # Test data and fixtures
    └── scenarios/
        └── fwa/
            ├── all_task_ids.toml         # Test task ID configurations
            ├── scenario.toml             # Test scenario configuration (template)
            ├── benchmark/
            │   └── tasks/
            │       └── group2/
            │           ├── Tasks_1.1.json    # Factory task fixtures
            │           ├── Tasks_2.1.json    # Warehouse task fixtures
            │           └── Tasks_V2_1.1.json # Retail task fixtures
            └── purple_agent/
                └── test_agent.py         # Test Purple Agent implementation
```

### Directory Descriptions

- **`agent/`**: Contains integration and unit tests for agent components
  - `test_fwa_green_agent.py`: End-to-end tests that start actual agent servers
  - `metrics/tasks/`: Unit tests for task loading and processing

- **`fixtures/`**: Test data that mirrors the production structure
  - Isolated from production data in `src/fieldworkarena/benchmark/`
  - Contains minimal, controlled datasets for predictable testing
  - `scenarios/fwa/benchmark/`: Subset of production tasks for testing
  - `scenarios/fwa/purple_agent/`: Simple test agent for integration tests

