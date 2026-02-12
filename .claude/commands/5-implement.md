# Phase 6: Implementation (TDD GREEN)

You are in **Phase 6 - Implementation / TDD GREEN Phase**.

## Purpose

Write the **minimal code** to make failing tests pass. No more, no less.

## Prerequisites

- Spec approved (`phase4_approved`)
- TDD RED complete (`phase5_tdd_red`)
- Test artifacts registered showing failures

Check status:
```bash
python3 .claude/hooks/workflow_state_multi.py status
```

**If TDD RED artifacts are missing, the `tdd_enforcement` hook will BLOCK your edits!**

## Your Tasks

### 1. Verify RED Phase Complete

```bash
python3 -c "
import sys; sys.path.insert(0, '.claude/hooks')
from workflow_state_multi import get_active_workflow

w = get_active_workflow()
if w:
    artifacts = [a for a in w.get('test_artifacts', []) if a.get('phase') == 'phase5_tdd_red']
    print(f'RED artifacts: {len(artifacts)}')
    for a in artifacts:
        print(f'  - {a[\"type\"]}: {a[\"description\"][:50]}...')
"
```

### 2. Load Context via Agent

Launch an **Explore agent** (Haiku for speed) to prepare implementation context:

```
Task(subagent_type="Explore", model="haiku", prompt="
  Prepare implementation context for: [FEATURE_NAME]

  1. Read the approved spec at: [SPEC_PATH]
  2. Read all files listed in the spec's Source and Dependencies
  3. Analyze code patterns: imports, naming, error handling style
  4. Report back:
     - Spec summary (key requirements)
     - Code conventions found in target files
     - Import patterns to follow
     - Any existing tests in the same area
")
```

### 3. Implement Core (Main Context = Opus)

With the context from Step 2, implement the core functionality:

1. **Follow the spec exactly** - No creative deviations
2. **Implementation order:**
   - Core functionality first
   - Integration second
3. **Validate after each file change** (syntax check)
4. **Document deviations** - If you must deviate from spec, note why

**TDD GREEN Rules:**
- Only write code that makes a test pass
- Don't add features not covered by tests
- Don't optimize prematurely
- Don't refactor yet

### 4. Parallel Side Tasks

After core is done, launch **parallel agents** for independent work:

```
# Agent A: Write tests (Sonnet for code quality)
Task(subagent_type="general-purpose", model="sonnet", prompt="
  Write tests for: [FEATURE_NAME]
  Spec: [SPEC_PATH]
  Core implementation: [SUMMARY OF WHAT WAS IMPLEMENTED]

  RULES from CLAUDE.md:
  - NO mocks! No Mock(), patch(), MagicMock
  - Real integration tests only
  - Place tests in tests/ directory
  - Use uv run pytest conventions
")

# Agent B: Update config/data if needed (Haiku for simple tasks)
Task(subagent_type="general-purpose", model="haiku", prompt="
  Update config/data files for: [FEATURE_NAME]
  Changes needed: [SPECIFIC CHANGES]
  Files: [data/*.json, config.ini, etc.]
")
```

**Decision for Agent B:** Check the spec's Implementation Details section for config/data changes. Only launch Agent B if the spec explicitly mentions config, data, or environment changes.

### 5. Integrate & Verify

Back in main context:
1. Review agent outputs (tests, config)
2. Run quick syntax check on all changed files
3. Ensure everything fits together
4. Run tests to verify GREEN status:

```bash
pytest tests/test_[feature].py -v
```

**Expected:** All tests PASS.

### 6. Capture Artifacts & Update State

```bash
pytest tests/ -v > docs/artifacts/[workflow]/test-green-output.txt 2>&1

python3 -c "
import sys; sys.path.insert(0, '.claude/hooks')
from workflow_state_multi import add_test_artifact, load_state

state = load_state()
active = state['active_workflow']

add_test_artifact(active, {
    'type': 'test_output',
    'path': 'docs/artifacts/[workflow]/test-green-output.txt',
    'description': 'All tests PASSED: 5 passed in 0.3s',
    'phase': 'phase6_implement'
})
"
```

Update workflow phase:

```bash
python3 .claude/hooks/workflow_state_multi.py phase phase7_validate
```

## Implementation Constraints

Follow scoping limits:
- **Max 4-5 files** per change
- **Max +/-250 LoC** total
- **Functions ≤50 LoC**
- **No side effects** outside spec scope

## Next Step

After implementation:
> "Implementation complete. All [N] tests pass. Ready for `/validate` for manual testing."

## Common Mistakes

❌ **Adding unrequested features** → Scope creep
❌ **Skipping tests** → Not TDD
❌ **Large functions** → Hard to test/maintain
❌ **Not running tests** → Might still be RED
