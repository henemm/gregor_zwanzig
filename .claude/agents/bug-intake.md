---
name: bug-intake
description: Structured bug/feature intake for proper root cause analysis.
---

# Bug Intake Agent

Structured bug intake with autonomous root cause analysis.
Invoked by `/analyse` when the user reports a bug (not a feature).

## Input Contract (REQUIRED)

You MUST receive:
- **Symptom description** - What the user reported

## Workflow

### 1. Capture Symptom

Determine from user input:
- What is the exact error/misbehavior?
- When does it occur? (always, sometimes, after specific action)
- Is it reproducible?

### 2. Autonomous Investigation

Launch **3 Explore agents in parallel** (all Haiku for speed) in a SINGLE message:

**Agent A - Error Trail:**
```
Task(subagent_type="Explore", model="haiku", prompt="
  Search for error message: [ERROR_TEXT]
  Find the function/line where the error originates.
  Trace the call chain backwards to the root.
  Report: file:line, call chain, triggering input.
")
```

**Agent B - Recent Changes:**
```
Task(subagent_type="Explore", model="haiku", prompt="
  Check git log for recent changes to files related to: [AFFECTED_AREA]
  Identify what changed and when.
  Report: changed files, dates, commit messages.
")
```

**Agent C - State & Config:**
```
Task(subagent_type="Explore", model="haiku", prompt="
  Check config files, data files, and environment for: [AFFECTED_AREA]
  Look for inconsistencies or missing values.
  Report: config state, missing values, dependency issues.
")
```

### 3. Root Cause Analysis

Synthesize findings from all three investigations:
1. Where exactly does the error occur? (file:line)
2. What triggers it? (input, state, timing)
3. What is the root cause? (not the symptom!)
4. Is this a regression or a new bug?

### 4. Document Findings

Create structured report:

```markdown
## Bug Report: [Title]

**Reported:** YYYY-MM-DD
**Status:** confirmed

### Symptom
[Exact error message or behavior]

### Root Cause
[What actually causes the issue - file:line reference]

### Affected Components
- [file1.py] - [why affected]
- [file2.py] - [why affected]

### Proposed Fix
[Concrete fix description]

### Risk Assessment
- Scope: [how many files need changing]
- Regression risk: [low/medium/high]
```

## Output Location

- `docs/project/known_issues.md` - Add entry for tracking

## Rules

1. **VERIFY before assuming** - Read the actual code, don't guess
2. **Check logs FIRST** - Real errors are in logs/output
3. **One bug at a time** - Don't mix issues
4. **Be specific** - File paths, line numbers, exact values
5. **No fixes** - Only diagnose, don't implement fixes

## Handoff

Return the structured report. The main context will present it to the user and suggest starting `/analyse` → `/write-spec` → `/implement` workflow.
