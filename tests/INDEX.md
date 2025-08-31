

# Tests Index – Gregor Zwanzig

This folder contains all test suites for the project.

---

## Test Suites

- `test_core.py` → Tests for core logic and mailer functions.
- `test_debug.py` → Tests for DebugBuffer consistency and debug output.
- `conftest.py` → Shared pytest configuration and fixtures.

---

## Running Tests

Run all tests with:

```bash
uv run pytest
```

Run a specific test file:

```bash
uv run pytest tests/test_core.py
```

Run with verbose output:

```bash
uv run pytest -v
```

---

## Notes
- All new functions must be covered by tests (see `.cursor/rules/02_test_first.mdc`).
- Tests must validate both success cases and boundary conditions.
- Fixtures in `fixtures/` are the single source of truth for expected results.