# Phase 2: Analyse

You are in **Phase 2 - Analysis** of the workflow.

## Prerequisites

- Context gathered (`/context` completed, or combined with analysis)
- Active workflow exists

Check current workflow:
```bash
python3 .claude/hooks/workflow_state_multi.py status
```

## Your Tasks

### Step 1: Determine Type

Is this a **Bug** or a **Feature**?

- **Bug** → Run bug-intake agent first (see Step 2b)
- **Feature** → Skip to Step 2a

### Step 2a: Parallel Codebase Research (Features)

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

### Step 2b: Bug Investigation

Launch **bug-intake agent** instead:

```
Task(subagent_type="bug-intake", model="haiku", prompt="
  Symptom: [USER'S BUG DESCRIPTION]
  Investigate root cause autonomously.
")
```

The bug-intake agent will spawn its own 3 parallel Explore/haiku sub-agents for investigation (Error Trail, Recent Changes, State & Config). See `.claude/agents/bug-intake.md` for details.

### Step 3: Strategic Assessment

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

### Step 4: Present to User

Synthesize all results into:

1. **Understanding Checklist** - Bullet points of what you understood
2. **One clear recommendation** - Not multiple options
3. **Scope estimate** - Files and LoC (flag if exceeding limits)
4. **Risks** - Only if significant

### Step 5: Document & Update Workflow State

Update or create `docs/context/[workflow-name].md` with analysis results.

```bash
python3 .claude/hooks/workflow_state_multi.py phase phase3_spec
```

## Next Step

When analysis is complete:
> "Analysis complete. Scope: [N] files, ~[N] LoC. Next: `/write-spec` to create the specification."

If you have open questions, ask the user before proceeding.

**IMPORTANT:** Do NOT start implementation. Analysis → Spec → Approve → TDD RED → Implement.
