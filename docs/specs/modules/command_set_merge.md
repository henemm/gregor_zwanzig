---
entity_id: command_set_merge
type: module
created: 2026-02-12
updated: 2026-02-12
status: active
version: "1.0"
tags: [commands, agents, workflow, openspec, upstream, merge]
---

# Command Set Merge (Upstream Dash-Commands + Agent-Orchestrierung)

## Approval

- [x] Approved (2026-02-12)

## Purpose

Merge two parallel command sets (.claude/commands/) by deleting redundant underscore files (1_analyse.md, 2_write-spec.md, 3_implement.md) and porting their agent orchestration patterns (Task subagent syntax with model selection) into the canonical upstream dash files (2-analyse.md, 3-write-spec.md, 5-implement.md). Maintains enhanced agent definitions and workflow state system while adopting the official OpenSpec framework structure.

## Source

- **Files (DELETE):**
  - `.claude/commands/1_analyse.md`
  - `.claude/commands/2_write-spec.md`
  - `.claude/commands/3_implement.md`

- **Files (MODIFY):**
  - `.claude/commands/2-analyse.md`
  - `.claude/commands/3-write-spec.md`
  - `.claude/commands/5-implement.md`
  - `.claude/commands/6-validate.md` (verify only)

- **Files (NO CHANGE):**
  - Upstream: 0-reset.md, 1-context.md, 4-tdd-red.md, 7-deploy.md, workflow.md, feature.md, user-story.md, bug.md, add-artifact.md, README.md
  - Enhanced agents: spec-writer.md, spec-validator.md, docs-updater.md, bug-intake.md

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| agent_orchestration | module | Defines Task() subagent syntax and model selection patterns |
| workflow_state_multi.py | hook | Manages workflow state transitions |
| workflow_gate.py | hook | Enforces workflow phase prerequisites |
| spec_enforcement.py | hook | Validates specs exist before implementation |
| .claude/agents/*.md | agents | Enhanced with input contracts and structured outputs |

## Implementation Details

### Phase A: Port Agent Orchestration to 2-analyse.md

**FROM:** `1_analyse.md` (lines 1-92)

**TO:** `2-analyse.md` (replace sections after "## Your Tasks")

**CHANGES:**

1. **Replace Section "1. Deep Analysis"** with:

```markdown
## Step 1: Determine Type

Is this a **Bug** or a **Feature**?

- **Bug** → Run bug-intake agent first (see Step 2b)
- **Feature** → Skip to Step 2a

## Step 2a: Parallel Codebase Research (Features)

Launch **3 Explore agents in parallel** (all Haiku for speed):

```
Task(subagent_type="Explore", model="haiku", prompt="...")
```

**Agent 1 - Affected Files:**
> Search the codebase for files related to [FEATURE]. Find all files that would need changes. Look for existing implementations, patterns, and code conventions used in similar areas. Report: file paths, key functions/classes, current behavior.

**Agent 2 - Existing Specs:**
> Search docs/specs/ for any specifications related to [FEATURE]. Also check docs/features/ and docs/reference/ for related documentation. Report: relevant spec paths, their status (draft/active), and any constraints they define.

**Agent 3 - Dependencies & Imports:**
> Trace the dependency chain for [AFFECTED AREA]. What modules import what? What external APIs are called? What data files are read? Report: dependency graph, external dependencies, data flow.

**IMPORTANT:** Launch all 3 agents in a SINGLE message (parallel execution).

## Step 2b: Bug Investigation

Launch **bug-intake agent** instead:

```
Task(subagent_type="bug-intake", model="haiku", prompt="
  Symptom: [USER'S BUG DESCRIPTION]
  Investigate root cause autonomously.
")
```

The bug-intake agent will spawn its own 3 parallel Explore/haiku sub-agents for investigation (Error Trail, Recent Changes, State & Config). See `.claude/agents/bug-intake.md` for details.

## Step 3: Strategic Assessment

After all research agents return, launch a **Plan agent** (Sonnet for quality):

```
Task(subagent_type="Plan", model="sonnet", prompt="
  Based on this analysis for [FEATURE]:

  [PASTE RESULTS FROM STEP 2]

  Create an implementation strategy:
  1. What architectural approach is best? Why?
  2. What is the implementation order?
  3. What are the risks?
  4. How many files need changes? (flag if >4-5)
  5. Estimated LoC changes? (flag if >250)
")
```
```

2. **Replace Section "2. Document Analysis"** with:

```markdown
## Step 4: Present to User

Synthesize all results into:

1. **Understanding Checklist** - Bullet points of what you understood
2. **One clear recommendation** - Not multiple options
3. **Scope estimate** - Files and LoC (flag if exceeding limits)
4. **Risks** - Only if significant
```

3. **Replace Section "3. Update Workflow State"** with:

```markdown
## Step 5: Update Workflow State

After user confirms understanding:

Update workflow state via hook:
```bash
python3 .claude/hooks/workflow_state_multi.py phase phase3_spec
```

Also update context document at `docs/context/[workflow-name].md`:

```markdown
## Analysis

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| src/auth.py | MODIFY | Add OAuth provider |
| src/config.py | MODIFY | Add OAuth settings |
| tests/test_auth.py | CREATE | New test file |

### Scope Assessment
- Files: [N]
- Estimated LoC: +[N]/-[N]
- Risk Level: LOW/MEDIUM/HIGH

### Technical Approach
[How we'll implement this]

### Open Questions
- [ ] Question 1?
- [ ] Question 2?
```
```

4. **Keep Section "## Next Step"** unchanged (already correct)

### Phase B: Port Agent Orchestration to 3-write-spec.md

**FROM:** `2_write-spec.md` (lines 1-78)

**TO:** `3-write-spec.md` (replace sections after "## Your Tasks")

**CHANGES:**

1. **Replace Section "1. Create Specification"** with:

```markdown
## Step 1: Gather Context

Collect from the current conversation:
- **Feature name** from workflow state
- **Analysis results** from Phase 2 (affected files, dependencies, strategy)
- **User requirements** from the original request

## Step 2: Create Spec via Agent

Launch a **general-purpose agent** (Sonnet for writing quality):

```
Task(subagent_type="general-purpose", model="sonnet", prompt="
  You are a spec writer. Follow the instructions in .claude/agents/spec-writer.md exactly.

  INPUT:
  - Feature Name: [NAME]
  - Analysis Summary: [PASTE ANALYSIS]
  - Affected Files: [LIST]
  - Dependencies: [LIST]

  Read the template from docs/specs/_template.md first.
  Read existing specs in docs/specs/ to match style.
  Create the spec file. Return the file path when done.
")
```

## Step 3: Validate Spec via Agent

After the spec is created, launch a **spec-validator agent** (Haiku for speed):

```
Task(subagent_type="spec-validator", model="haiku", prompt="
  Validate the spec at: [SPEC_PATH]
  Follow the validation rules in .claude/agents/spec-validator.md.
  Return VALID or INVALID with details.
")
```

**If INVALID:**
1. Fix the issues yourself (in main context)
2. Re-run spec-validator/haiku to verify the fix
3. Max 2 validation loops. If still INVALID after 2 attempts, present issues to user.

**If VALID:** Proceed to Step 4.

## Step 4: Update Workflow State

```bash
# Update spec file path in workflow
python3 -c "
import sys; sys.path.insert(0, '.claude/hooks')
from workflow_state_multi import load_state, save_state
state = load_state()
active = state.get('active_workflow')
if active:
    state['workflows'][active]['spec_file'] = 'docs/specs/[category]/[entity].md'
    save_state(state)
"

# Advance to spec_written phase
python3 .claude/hooks/workflow_state_multi.py phase phase3_spec
```

## Step 5: Present to User

Show the spec content to the user and ask:
> "Spec erstellt: `[path]`. Bitte pruefen und mit 'approved' oder 'freigabe' bestaetigen."

**IMPORTANT:** Do NOT implement until the user explicitly approves!

## After Approval

When user approves:
1. `workflow_state_updater` hook detects approval phrase
2. State advances to `phase4_approved`
3. Next: `/tdd-red` to write failing tests

**IMPORTANT:**
- Do NOT implement until approved
- Do NOT skip TDD RED phase after approval
```

2. **Delete Section "2. Update Workflow State"** (already merged into Step 4 above)

3. **Delete Section "## Next Step"** (already merged into Step 5 above)

### Phase C: Port Agent Orchestration to 5-implement.md

**FROM:** `3_implement.md` (lines 1-93)

**TO:** `5-implement.md` (replace sections after "## Your Tasks")

**CHANGES:**

1. **Insert after "## Prerequisites" and before "## Your Tasks":**

```markdown
## Step 1: Load Context via Agent

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
```

2. **Replace Section "### 2. Read the Spec"** with:

```markdown
## Step 2: Implement Core (Main Context = Opus)

With the context from Step 1, implement the core functionality:

1. **Follow the spec exactly** - No creative deviations
2. **Implementation order:**
   - Core functionality first
   - Integration second
3. **Validate after each file change** (syntax check)
4. **Document deviations** - If you must deviate from spec, note why
```

3. **Replace Section "### 3. Implement - Make Tests GREEN"** with:

```markdown
## Step 3: Parallel Side Tasks

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
```

4. **Replace Section "### 4. Run Tests - MUST BE GREEN"** with:

```markdown
## Step 4: Integrate & Verify

Back in main context:
1. Review agent outputs (tests, config)
2. Run quick syntax check on all changed files
3. Ensure everything fits together
4. Run tests to verify GREEN status:

```bash
pytest tests/test_[feature].py -v
```

**Expected:** All tests PASS.
```

5. **Replace Section "### 5. Capture GREEN Artifacts"** with:

```markdown
## Step 5: Update Workflow State

Capture test artifacts:

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
```

6. **Delete Section "### 6. Update Workflow State"** (merged into Step 5 above)

7. **Keep Sections "## Implementation Constraints" and "## Next Step"** unchanged

### Phase D: Verify 6-validate.md

**ACTION:** Verify that `6-validate.md` already has agent orchestration patterns matching our style.

**EXPECTED CONTENT CHECK:**

1. Step 1 should have 4 parallel Task() calls with model selection:
   - `Task(subagent_type="Bash", model="haiku", ...)`
   - `Task(subagent_type="spec-validator", model="haiku", ...)`
   - `Task(subagent_type="Explore", model="haiku", ...)`
   - `Task(subagent_type="general-purpose", model="haiku", ...)`

2. Step 2b should have auto-fix with:
   - `Task(subagent_type="general-purpose", model="sonnet", ...)`

3. Step 3 should have docs update with:
   - `Task(subagent_type="docs-updater", model="sonnet", ...)`

**IF MISSING:** Add the agent orchestration syntax matching the pattern from underscore files.

**IF PRESENT:** No changes needed.

### Phase E: Delete Redundant Files

**ACTION:** Delete 3 underscore command files after verification that dash files contain all orchestration logic.

```bash
rm .claude/commands/1_analyse.md
rm .claude/commands/2_write-spec.md
rm .claude/commands/3_implement.md
```

**VERIFICATION BEFORE DELETE:**
1. Confirm 2-analyse.md has bug/feature routing + 3 parallel Explore agents + Plan agent
2. Confirm 3-write-spec.md has spec-writer + spec-validator + auto-fix loop
3. Confirm 5-implement.md has Explore context loading + parallel test/config agents

### Phase F: Update README.md

**ACTION:** Update `.claude/commands/README.md` to remove references to underscore commands.

**CHANGES:**

1. **Line 24** - DELETE this line:
   ```markdown
   **Alternative naming:**
   - `/1_analyse`, `/2_write-spec`, `/3_implement`, `/4_validate`, `/5_e2e-test`
   ```

2. **Table in "Workflow Commands (Sequential)"** - Already correct (uses dash names)

3. **No other changes needed** - README already documents dash commands as primary

## Architecture

```
BEFORE (Dual System):
├── Upstream Dash Commands (2-analyse.md, 3-write-spec.md, 5-implement.md)
│   └── No agent orchestration, basic workflow instructions
└── Project Underscore Commands (1_analyse.md, 2_write-spec.md, 3_implement.md)
    └── Has Task() subagent syntax + model selection

AFTER (Merged System):
├── Enhanced Dash Commands (2-analyse.md, 3-write-spec.md, 5-implement.md)
│   └── Upstream structure + Project agent orchestration patterns
├── Enhanced Agents (.claude/agents/*.md)
│   └── Input contracts + structured outputs (unchanged)
└── Workflow State System
    └── workflow_state_multi.py + hooks (unchanged)
```

## Expected Behavior

### Input
- Developer runs workflow commands: `/analyse`, `/write-spec`, `/implement`, `/validate`
- Commands now follow OpenSpec framework naming (dash, not underscore)

### Output
- Same agent orchestration behavior as before (parallel Tasks, model selection)
- Same workflow state transitions
- Same hook enforcement
- Cleaner command set (no duplication)

### Side Effects
- 3 underscore command files deleted
- 4 dash command files enhanced with agent orchestration
- README.md cleaned up (no more "alternative naming")
- No changes to workflow behavior (functionally identical)

## Known Limitations

- Manual verification required that all orchestration patterns are correctly ported
- No automated migration test (must rely on visual diff + testing)
- Agent definition files (.claude/agents/*.md) not changed (assumes they're already correct)
- No rollback mechanism if merge introduces bugs

## Validation Checklist

Before marking spec as approved:

- [ ] Read all 3 underscore files completely
- [ ] Read all 3 target dash files completely
- [ ] Identify exact sections to port (line numbers)
- [ ] Verify agent orchestration syntax matches (Task(), model=, subagent_type=)
- [ ] Verify workflow state hook calls are consistent
- [ ] Verify no functionality is lost in merge
- [ ] Test one complete workflow cycle (/analyse → /write-spec → /implement → /validate)

## Changelog

- 2026-02-12: Implementation complete, marked as active
- 2026-02-12: Initial spec created for command set merge
