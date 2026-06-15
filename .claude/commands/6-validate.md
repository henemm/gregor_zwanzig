# Phase 7: Validation

You are starting the **Validation Phase**.

## Wiedereinstieg via Issue-Nummer (nach `/clear`)

**Wurde dieser Befehl als `/6-validate #<N>` aufgerufen** (typisch nach einem `/clear`)? Dann löse zuerst den Workflow von der Platte auf — der komplette State überlebt jeden `/clear`/Worktree:

```bash
ISSUE=574   # die übergebene Nummer (ohne #)
python3 - "$ISSUE" <<'PY'
import sys, json, glob, re, os
issue = sys.argv[1].lstrip('#')
pat = re.compile(rf'(^|[-_]){re.escape(issue)}([-_]|$)')
hits = []
for f in glob.glob('.claude/workflows/*.json'):
    name = os.path.basename(f)[:-5]
    if pat.search(name):
        d = json.load(open(f))
        hits.append((name, d.get('current_phase'), d.get('spec_approved'), d.get('adversary_verdict')))
if not hits:
    print(f'KEIN laufender Workflow fuer #{issue} (evtl. abgeschlossen -> .claude/workflows/_archive/).')
else:
    for name, ph, spec, verd in hits:
        print(f'GEFUNDEN: {name} | Phase={ph} | Spec={spec} | Verdict={verd}')
    print('\nexport GZ_ACTIVE_WORKFLOW=' + hits[0][0])
PY
```

Setze `GZ_ACTIVE_WORKFLOW=<name>`, fasse dem User in 2 Sätzen den Stand zusammen (Phase, Verdict) und fahre dann mit den Prerequisites fort.

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
aber schließe es noch **nicht** — das passiert erst nach Prod-Deploy in Step 5.

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

## Step 5: Commit, Push & Deploy

**Docs-only-Ausnahme:** Wenn der Commit ausschließlich `.md`-Dateien, `docs/`, `.claude/`-Inhalte oder `.gitignore` ändert (kein Code in `src/`, `api/`, `internal/`, `frontend/`, `cmd/`), entfallen Schritte 2–8. In diesem Fall nach dem Push fertig — kein Staging-Deploy, kein E2E, kein Prod-Deploy nötig.

### Schritt 1: Commit & Push

Commit und Push auf `main`.

### Schritt 2: Staging aktuell machen

**Keine Ankündigung "ich warte X Minuten". Sofort ausführen:**

```bash
EXPECTED=$(git rev-parse HEAD)
STAGING=$(curl -s https://staging.gregor20.henemm.com/api/health | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('commit','?'))" 2>/dev/null)
echo "Staging: ${STAGING:0:7} | Erwartet: ${EXPECTED:0:7}"
if [ "${STAGING:0:7}" != "${EXPECTED:0:7}" ]; then
  echo "→ Deploy triggern..."
  bash /home/hem/henemm-infra/scripts/auto-deploy-gregor-staging.sh
  for i in 1 2 3 4 5; do
    sleep 30
    STAGING=$(curl -s https://staging.gregor20.henemm.com/api/health | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('commit','?'))" 2>/dev/null)
    echo "Versuch $i: ${STAGING:0:7}"
    [ "${STAGING:0:7}" = "${EXPECTED:0:7}" ] && echo "✓ Staging aktuell" && break
  done
else
  echo "✓ Staging bereits aktuell"
fi
```

### Schritt 3: E2E gegen Staging ausführen

Rufe `/e2e-verify` auf. **Kein Weitergehen bis Verdict = VERIFIED.**

- Bei VERIFIED → Schritt 5
- Bei BROKEN → Fehler beheben, neu pushen, Schritt 2 wiederholen
- Bei AMBIGUOUS → Findings prüfen, ggf. weitermachen mit Begründung

### Schritt 5: Tech-Lead-Brief ausgeben (nach E2E VERIFIED)

**Was wurde gebaut:** [1-2 Sätze aus Nutzerperspektive]

**Staging validiert:** [staging_verdict] — [verified_at]

**Tests:** [N] bestanden, 0 fehlgeschlagen

**Risiko:** niedrig / mittel / hoch — [1 Satz Begründung]

**Empfehlung:** Deploy auf Production.

Sage **'go'** um zu deployen.

### Schritt 6: Prod-Deploy (nach 'go')

```bash
git branch --show-current      # muss "main" sein
git status --porcelain         # muss leer sein
bash /home/hem/henemm-infra/scripts/deploy-gregor-prod.sh
```

### Schritt 7: Post-Deploy-Smoke

```bash
curl https://gregor20.henemm.com/api/health
```

### Schritt 8: Issue schließen

```bash
gh issue close <ISSUE_NR> --comment "Fertig und live — $(git rev-parse --short HEAD) auf Production."
```

**NICHT früher "Fertig und live" sagen.**

**Das Issue bleibt offen bis Schritt 8 abgeschlossen ist.**

## On Failure

If validation fails and auto-fix didn't work:
1. Do NOT commit
2. Report specific failures to user
3. Go back to implementation: run `/implement` again
