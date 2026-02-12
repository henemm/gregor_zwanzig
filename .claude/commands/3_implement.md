# Phase 3: Implementation

You are starting the **Implementation Phase**.

## Prerequisites

Check `.claude/workflow_state.json`:
- `current_phase` must be `spec_approved`
- `spec_approved` must be `true`

If not, the `workflow_gate` hook will block your edits!

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

## Step 2: Implement Core (Main Context = Opus)

With the context from Step 1, implement the core functionality:

1. **Follow the spec exactly** - No creative deviations
2. **Implementation order:**
   - Core functionality first
   - Integration second
3. **Validate after each file change** (syntax check)
4. **Document deviations** - If you must deviate from spec, note why

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

**Only launch Agent B if config/data changes are actually needed.**

## Step 4: Integrate & Verify

Back in main context:
1. Review agent outputs (tests, config)
2. Run quick syntax check on all changed files
3. Ensure everything fits together

## Step 5: Update Workflow State

```json
{
  "current_phase": "implemented",
  "implementation_done": true,
  "last_updated": "[ISO timestamp]"
}
```

## Next Step

> "Implementation abgeschlossen. Naechster Schritt: `/validate`"

**IMPORTANT:** Do NOT commit without running `/validate` first!
