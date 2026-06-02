# Phase 7: Validation

You are starting the **Validation Phase**.

## Prerequisites

Check workflow status:
```bash
python3 .claude/hooks/workflow_state_multi.py status
```

- `current_phase` must be `phase7_validate` (or `phase6b_adversary` completed)
- Adversary Dialog must be **VERIFIED** or **AMBIGUOUS** (with user OK)

### External Validator Prerequisite

**Du MUSST pruefen, dass der External Validator Report existiert und von einer ANDEREN Session stammt:**

```bash
# Pruefe ob Report existiert
ls docs/artifacts/*/validator-report.md 2>/dev/null

# Pruefe Verdict im Report
grep -E "^## Verdict:" docs/artifacts/*/validator-report.md
```

**Wenn kein Report existiert:** Zurueck zu `/implement` Step 9 — User muss externe Validator-Session starten.
**Akzeptierte Verdicts:** **VERIFIED** oder **AMBIGUOUS** (mit User-OK nach Pruefung der Findings).
**BROKEN:** Zurueck zu `/implement` Step 3 zum Fixen.

## Step 1: Parallel Validation (4 agents)

Launch **all 4 agents in a SINGLE message** (parallel execution):

### Agent 1: Tests & Syntax (Bash/Haiku)

```
Task(subagent_type="Bash", model="haiku", prompt="
  Run validation for the Gregor Zwanzig project:

  1. Run: python3 .claude/validate.py
  2. Run: uv run pytest -v
  3. Report: Which tests passed, which failed, any syntax errors
")
```

### Agent 2: Spec Compliance (spec-validator/Haiku)

```
Task(subagent_type="spec-validator", model="haiku", prompt="
  Validate the spec at: [SPEC_PATH]
  Follow the validation rules in .claude/agents/spec-validator.md.
  Return VALID or INVALID with details.
")
```

### Agent 3: Regression Check (Explore/Haiku)

```
Task(subagent_type="Explore", model="haiku", prompt="
  Regression check for: [FEATURE_NAME]

  1. Check git diff to see ALL changed files
  2. For each changed file: are there changes OUTSIDE the scope of [FEATURE]?
  3. Check if any imports or interfaces changed that could break other modules
  4. Report: any unintended side effects found
")
```

### Agent 4: Scope Review (general-purpose/Haiku)

```
Task(subagent_type="general-purpose", model="haiku", prompt="
  Scope review for: [FEATURE_NAME]

  Check against CLAUDE.md limits:
  1. How many files were changed? (max 4-5)
  2. Total LoC changed? (max +-250)
  3. Any functions >50 LoC?
  4. Any drive-by refactoring outside scope?

  Report: PASS or FAIL with details.
")
```

## Step 2: Evaluate Results

Compile a validation checklist:

- [ ] Tests & syntax pass (Agent 1)
- [ ] Spec compliance valid (Agent 2)
- [ ] No regressions (Agent 3)
- [ ] Scope limits respected (Agent 4)

### If ALL pass → Step 3
### If ANY fail → Step 2b

## Step 2b: Auto-Fix (one attempt)

If tests failed, launch a **general-purpose agent** (Sonnet) for one fix attempt:

```
Task(subagent_type="general-purpose", model="sonnet", prompt="
  Test failure auto-fix for: [FEATURE_NAME]

  FAILURE:
  [PASTE ERROR OUTPUT FROM AGENT 1]

  SPEC:
  [SPEC_PATH]

  Fix the issue. Rules:
  - Only fix the failing test/code, nothing else
  - Stay within scope of the feature
  - Run uv run pytest after fixing to verify
  - If you cannot fix it in one attempt, report what you found
")
```

After auto-fix: Re-run Agent 1 (Bash) to verify. If still failing, report to user.

## Step 3: Documentation Update

If all validations pass, launch **docs-updater** (Haiku — sufficient for markdown updates):

```
Task(subagent_type="docs-updater", model="haiku", prompt="
  Follow the instructions in .claude/agents/docs-updater.md.

  INPUT:
  - Changed files: [LIST FROM GIT DIFF]
  - Feature summary: [1-2 SENTENCES]
  - Spec file: [SPEC_PATH]

  Update all relevant documentation.
")
```

## Step 3b: Issue-Kommentar (GitHub)

Kommentiere den Fortschritt im GitHub Issue (Commit-SHA + kurze Zusammenfassung),
aber schließe es noch **nicht** — das passiert erst nach Prod-Deploy in `/7-deploy`.

```bash
gh issue comment <ISSUE_NR> --body "Implementiert & validiert — Commit $(git rev-parse --short HEAD). Staging-Deploy läuft, Prod-Deploy folgt."
```

Die frühere Datei `ACTIVE-roadmap.md` ist seit 2026-05-02 stillgelegt (Issue #114)
— kein Roadmap-Update-Schritt mehr nötig.

## Step 4: Present Results

Show the user:

1. **Validation Checklist** - All checks with pass/fail
2. **Auto-fix results** - If any fixes were attempted
3. **Docs updated** - What documentation was changed

## Step 5: Commit & Übergabe an Deploy

After successful validation:

1. **Commit & Push** the changes
2. **Dem User mitteilen:** Validierung abgeschlossen — bereit für Deploy
3. **NICHT** "Fertig und live" oder "abgeschlossen" sagen — das passiert erst nach Prod-Deploy
4. **Nächster Schritt:** `/7-deploy` — dort wird auf Staging gewartet, E2E-Verifikation durchgeführt, Prod deployed und dann erst das Issue geschlossen

**Das Issue bleibt offen bis `/7-deploy` abgeschlossen ist.**

## On Failure

If validation fails and auto-fix didn't work:
1. Do NOT commit
2. Report specific failures to user
3. Go back to implementation: run `/implement` again
