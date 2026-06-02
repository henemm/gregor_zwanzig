# Phase 5: TDD RED - Write Failing Tests

You are in **Phase 5 - TDD RED Phase**.

## Purpose

Write tests BEFORE implementation. Tests MUST FAIL because the functionality doesn't exist yet.

**If tests pass → you're not doing TDD, you're testing existing code.**

## Prerequisites

- Spec approved (`phase4_approved`)
- Test plan defined in spec

Check status:
```bash
python3 .claude/hooks/workflow_state_multi.py status
```

## Your Tasks

### 1. Enter TDD RED Phase

```bash
python3 .claude/hooks/workflow_state_multi.py phase phase5_tdd_red
```

### 2. Write Tests Based on Spec

From the spec's Test Plan, create test files:

```python
# tests/test_[feature].py

def test_new_functionality():
    """
    GIVEN: [precondition]
    WHEN: [action]
    THEN: [expected result]
    """
    # This test MUST FAIL because feature doesn't exist
    result = feature_that_doesnt_exist()
    assert result == expected_value
```

### 3. Run Tests - MUST BE RED

Execute the tests:
```bash
pytest tests/test_[feature].py -v > docs/artifacts/[workflow]/test-output-red.txt 2>&1
```

**Expected:** Tests FAIL with clear error messages.

### 4. Capture REAL Artifacts

Save actual test output as artifacts:

```bash
# Create artifacts directory
mkdir -p docs/artifacts/[workflow-name]

# Save test output
pytest tests/ -v > docs/artifacts/[workflow]/test-red-output.txt 2>&1

# For UI tests, take actual screenshots
# For API tests, save actual responses
```

### 5. Register Artifacts

```bash
GZ_ACTIVE_WORKFLOW=<name> python3 -c "
import os, sys; sys.path.insert(0, '.claude/hooks')
from workflow_state_multi import add_test_artifact

active = os.environ['GZ_ACTIVE_WORKFLOW']

add_test_artifact(active, {
    'type': 'test_output',
    'path': 'docs/artifacts/[workflow]/test-red-output.txt',
    'description': 'Test FAILED: [function] raises NotImplementedError - assertion error line 42',
    'phase': 'phase5_tdd_red'
})
print('Artifact registered')
"
```

### 6. PO-Zusammenfassung ausgeben (PFLICHT)

Gib nach dem Artifact-Register immer diese Übersicht aus:

> **Tests geschrieben — was sie prüfen:**
>
> | AC | Was getestet wird | Status |
> |---|---|---|
> | AC-1: [AC-Text kurz] | [Was der Test konkret prüft, in Nutzerworten] | ❌ Fehlgeschlagen (erwartet) |
> | AC-2: [AC-Text kurz] | [Was der Test konkret prüft] | ❌ Fehlgeschlagen (erwartet) |
>
> Das ist korrekt so — die Tests schlagen fehl, weil das Feature noch nicht gebaut ist.
> Ich starte jetzt die Implementierung.

Kein User-Gate, keine Warteschleife. Direkt mit Phase 6 fortfahren.

## Artifact Requirements

Each artifact MUST:
- Be a **real file** (not placeholder)
- Have **minimum size** (proves non-empty)
- Include **description** of what it proves
- Show **failure evidence** (error, fail, assertion)

## RED Phase Checklist

Before proceeding to implementation:

- [ ] Tests written for all spec requirements
- [ ] All tests executed
- [ ] All tests FAIL (RED)
- [ ] At least 1 artifact registered
- [ ] Artifact shows failure evidence

## Next Step

After RED phase is complete:
> "TDD RED complete. [N] tests written, all failing as expected. Artifacts captured. Ready for `/implement`."

```bash
python3 .claude/hooks/workflow_state_multi.py phase phase6_implement
```

## Common Mistakes

❌ **Tests that pass** → Test is worthless, proves nothing
❌ **Mock everything** → Not testing real behavior
❌ **Placeholder artifacts** → Hook will block implementation
❌ **Skip to implement** → TDD enforcement hook will block you
