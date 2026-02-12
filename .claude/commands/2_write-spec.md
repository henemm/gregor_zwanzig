# Phase 2: Write Specification

You are starting the **Spec Writing Phase**.

## Prerequisites

Check `.claude/workflow_state.json`:
- `current_phase` must be `analyse_done`

If not, tell the user to run `/analyse` first.

## Step 1: Gather Context

Collect from the current conversation:
- **Feature name** from workflow state
- **Analysis results** from Phase 1 (affected files, dependencies, strategy)
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

**If INVALID:** Fix the issues yourself (in main context), then re-validate.
**If VALID:** Proceed to Step 4.

## Step 4: Update Workflow State

```json
{
  "current_phase": "spec_written",
  "feature_name": "[Feature Name]",
  "spec_file": "docs/specs/[category]/[entity_id].md",
  "spec_approved": false,
  "last_updated": "[ISO timestamp]"
}
```

## Step 5: Present to User

Show the spec content to the user and ask:
> "Spec erstellt: `[path]`. Bitte pruefen und mit 'approved' oder 'freigabe' bestaetigen."

**IMPORTANT:** Do NOT implement until the user explicitly approves!

The `workflow_state_updater` hook will automatically detect approval phrases.
