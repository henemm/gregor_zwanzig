# Phase 1: Analyse

You are starting the **Analysis Phase** for a new feature or change.

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

The bug-intake agent will spawn its own Explore sub-agents for investigation.

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

## Step 4: Present to User

Synthesize all results into:

1. **Understanding Checklist** - Bullet points of what you understood
2. **One clear recommendation** - Not multiple options
3. **Scope estimate** - Files and LoC (flag if exceeding limits)
4. **Risks** - Only if significant

## Step 5: Update Workflow State

After user confirms understanding:

Update `.claude/workflow_state.json`:
```json
{
  "current_phase": "analyse_done",
  "feature_name": "[Feature Name]",
  "spec_file": null,
  "spec_approved": false,
  "last_updated": "[ISO timestamp]"
}
```

## Next Step

> "Analyse abgeschlossen. Naechster Schritt: `/write-spec`"

**IMPORTANT:** Do NOT start implementation without `/write-spec`!
