# Phase 3: Write Specification

You are in **Phase 3 - Specification Writing**.

## Prerequisites

- Analysis completed (`phase2_analyse`)
- Context document exists with affected files list

Check current workflow:
```bash
python3 .claude/hooks/workflow_state_multi.py status
```

## Your Tasks

### Step 1: Gather Context

Collect from the current conversation:
- **Feature name** from workflow state
- **Analysis results** from Phase 2 (affected files, dependencies, strategy)
- **User requirements** from the original request

### Step 2: Create Spec via Agent

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

### Step 3: Validate Spec via Agent

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

### Step 4: Update Workflow State

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

### Step 5: Present to User

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
