---
entity_id: issue_521_staging_validator
type: module
created: 2026-06-01
updated: 2026-06-01
status: draft
version: "1.0"
tags: [workflow, hooks, e2e, staging, deployment-pipeline, qa, gate, issue-521]
---

<!-- Issue #521 — Staging Validator Agent: UI-Acceptance-Criteria gegen Live-Staging prüfen -->

# Issue #521 — Staging Validator Agent

## Approval

- [ ] Approved

## Purpose

Der Staging Validator Agent ist eine neue QA-Schicht zwischen `git push` und Prod-Deploy. Er loggt sich in die Staging-Umgebung ein, liest die Acceptance Criteria der aktiven Spec und prüft jeden UI-AC durch reale Playwright-Interaktion gegen `https://staging.gregor20.henemm.com`. Das ist das UI-Äquivalent zum Adversary Agent (der Code-Logik bricht) — der Staging Validator bricht die laufende App. `staging_gate.py` schreibt das Ergebnis als maschinenlesbares Artefakt; `deploy-gregor-prod.sh` liest es und blockiert Deploys wenn die Verifikation fehlt oder fehlschlug.

## Source

- **File:** `.claude/agents/staging-validator.md` (NEU — Agent-Protokoll)
- **File:** `.claude/hooks/staging_gate.py` (NEU, ~105 LoC — Gate-Logik, Mode A + B)
- **File:** `.claude/e2e_verified.json` (EXTEND — neue Felder `verified_commit`, `staging_verdict`, `findings[]`)
- **File:** `.claude/commands/e2e-verify.md` (UPDATE — delegiert an neuen Agent)
- **File:** `henemm-infra/scripts/deploy-gregor-prod.sh` (MODIFY — Gate-Check nach `git reset --hard`, separates Repo)
- **File:** `CLAUDE.md` (UPDATE — E2E-Sektion referenziert neuen Agent)

> **Schicht-Hinweis:** Primär Workflow-/Tooling-Schicht (`.claude/`). `deploy-gregor-prod.sh` liegt in `henemm-infra` — Änderung dort via MQ-Nachricht an `infra` koordinieren oder direkt im `henemm-infra`-Repo committen.

## Estimated Scope

- **LoC:** ~105 (staging_gate.py) + ~80 (staging-validator.md Agent-Protokoll) + ~20 (deploy-gregor-prod.sh Patch)
- **Files:** 6 (2 neu, 4 geändert; deploy-gregor-prod.sh in externem Repo)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `.claude/hooks/workflow.py` | intern | Liest `GZ_ACTIVE_WORKFLOW`, liest `spec_file` aus Workflow-JSON |
| `.claude/workflows/<name>.json` | intern | Enthält `spec_file`-Pfad und `scope` des aktiven Workflows |
| `.claude/validator.env` | Konfiguration | `GZ_VALIDATOR_USER`, `GZ_VALIDATOR_PASS`, `GZ_VALIDATION_URL` — Staging-Credentials |
| `playwright` (Python) | externe Lib | Playwright-Browser-Automatisierung für Login und AC-Navigation |
| `subprocess.check_output(["git", "rev-parse", "HEAD"])` | stdlib | HEAD-SHA für `verified_commit`-Feld |
| `datetime.datetime.utcnow()` | stdlib | `verified_at`-Timestamp in e2e_verified.json |
| `.claude/e2e_verified.json` | Artefakt | Canonical-Path (gitignored), von Gate und Deploy-Script gelesen |
| `henemm-infra/scripts/deploy-gregor-prod.sh` | extern | Bestehender Deploy-Workflow, bekommt Gate-Check-Aufruf hinzu |
| `subprocess` + `git diff HEAD~1 HEAD` | stdlib | `_detect_committed_scope()` inline in staging_gate.py — docs-only-Erkennung für Gate-Bypass |

## Implementation Details

### Architektur-Überblick

```
staging-validator.md (Agent-Protokoll)
    ↓ aufgerufen via /e2e-verify
staging_gate.py --write-verdict VERDICT --findings-json PATH
    ↓ schreibt
.claude/e2e_verified.json  (gitignored, bleibt bei git reset --hard erhalten)
    ↓ gelesen von
deploy-gregor-prod.sh  --check  (in henemm-infra)
```

### staging_gate.py — Mode A: Verdict schreiben

Aufgerufen vom Agent nach Abschluss der Playwright-Checks:

```python
python3 .claude/hooks/staging_gate.py \
    --write-verdict "VERIFIED: alle 5 ACs grün" \
    --findings-json /tmp/findings_<ts>.json
```

Schreibt in `.claude/e2e_verified.json`:

```json
{
  "verified_commit": "<git rev-parse HEAD>",
  "staging_verdict":  "VERIFIED: alle 5 ACs grün",
  "findings": [...],
  "verified_at": "2026-06-01T12:34:56Z",
  "scope": "frontend"
}
```

Exit-Code: 0 bei `VERIFIED`/`AMBIGUOUS`, 1 bei `BROKEN`.
Datei wird nur bei Exit 0 geschrieben — kein BROKEN-Artefakt (verhindert stilles Durchlaufen).

### staging_gate.py — Mode B: Gate-Check

Aufgerufen von `deploy-gregor-prod.sh`:

```python
python3 "$REPO_DIR/.claude/hooks/staging_gate.py" --check
```

Prüfungen in dieser Reihenfolge:
1. `GZ_SKIP_E2E_GATE=1` → warnendes Log-Entry + Exit 0 (kein stiller Bypass)
2. `_detect_committed_scope()` liefert `docs-only` → Exit 0 (kein Gate)
3. `e2e_verified.json` nicht vorhanden → Fehlermeldung + Exit 1
4. `verified_commit != git rev-parse HEAD` → Fehlermeldung + Exit 1
5. `staging_verdict` beginnt nicht mit `VERIFIED` → Fehlermeldung + Exit 1
6. `verified_at` älter als 24 h → Fehlermeldung + Exit 1
7. Alle Checks ok → "Staging-Gate: OK" + Exit 0

### staging-validator.md — Agent-Protokoll (Sequenz)

```
Step 1: GZ_ACTIVE_WORKFLOW laden → spec_file aus .claude/workflows/$name.json lesen
Step 2: AC-Parsing — alle **AC-N:** Einträge aus ## Acceptance Criteria der Spec extrahieren
Step 3: Smoke-Check — GET $GZ_VALIDATION_URL/api/health muss 200 zurückgeben
Step 4: Playwright-Login
        POST /api/auth/login {username, password}
        Selektoren: input[name="username"], input[name="password"], button[type="submit"]
        Assert: Redirect auf /  (Status 200, URL endet nicht auf /login)
Step 5: Pro AC-Eintrag:
        - Zur relevanten URL navigieren
        - DOM-Assertions (sichtbare Elemente, Text-Content, aria-Attribute)
        - Screenshot als Artefakt
        - Finding erstellen: {ac: "AC-N", status: PASS|FAIL, url: "URL:AC-N", evidence: "..."}
Step 6: Verdict ableiten:
        Alle PASS → VERIFIED
        Mindestens ein FAIL → BROKEN
        Assertions technisch nicht auswertbar → AMBIGUOUS
Step 7: staging_gate.py --write-verdict aufrufen
Step 8: Report im Adversary-Format ausgeben:
        F001 | Severity: CRITICAL | URL:AC-N | Beschreibung
```

### deploy-gregor-prod.sh — Gate-Patch (henemm-infra)

Nach `git reset --hard origin/main`, vor dem Go-Build (~20 Zeilen):

```bash
REPO_DIR="/home/hem/gregor_zwanzig"
if python3 "$REPO_DIR/.claude/hooks/staging_gate.py" --check; then
  echo "Staging-Gate: OK"
else
  echo "FEHLER: Staging-Gate blockiert Deploy."
  echo "  /e2e-verify auf Staging ausführen, dann erneut deployen."
  echo "  Notfall-Override: GZ_SKIP_E2E_GATE=1 bash deploy-gregor-prod.sh"
  exit 1
fi
```

### e2e_verified.json — erweitertes Schema

Neue Pflichtfelder zusätzlich zu bestehenden (`scope`, `timestamp`, ...):

| Feld | Typ | Beschreibung |
|------|-----|-------------|
| `verified_commit` | string | `git rev-parse HEAD` zum Zeitpunkt der Verifikation |
| `staging_verdict` | string | `"VERIFIED: ..."` / `"BROKEN: ..."` / `"AMBIGUOUS: ..."` |
| `findings` | array | Pro-AC-Ergebnis-Objekte `{ac, status, url, evidence}` |

Bestehende Felder bleiben erhalten (backward-compatible).

## Expected Behavior

- **Input:** Aktiver Workflow mit Frontend-Scope, gepushter Commit auf `origin/main`, Staging-Auto-Deploy abgeschlossen
- **Output:** `.claude/e2e_verified.json` mit `verified_commit` (HEAD-SHA), `staging_verdict: "VERIFIED: ..."`, und strukturierten Findings pro AC; Playwright-Screenshots als Artefakte
- **Side effects:** `deploy-gregor-prod.sh` liest `e2e_verified.json` und bricht ab wenn `verified_commit != HEAD` oder `staging_verdict != VERIFIED*`; `GZ_SKIP_E2E_GATE=1` ermöglicht Notfall-Bypass mit Warn-Eintrag im Deploy-Log

## Acceptance Criteria

**AC-1:** Given ein Workflow mit Frontend-Scope, When der Staging Validator Agent aufgerufen wird, Then loggt er sich in Staging ein (POST /api/auth/login, Cookies gesetzt), navigiert zur relevanten UI und prüft jedes UI-AC aus der Spec durch DOM-Assertions mit Playwright.
- Test: (populated after /tdd-red)

**AC-2:** Given erfolgreiche Verifikation aller ACs, When der Agent fertig ist, Then enthält `e2e_verified.json` die Felder `verified_commit` (aktueller HEAD-SHA), `staging_verdict` beginnend mit `"VERIFIED"`, und strukturierte Findings pro AC mit `{ac, status, url, evidence}`.
- Test: (populated after /tdd-red)

**AC-3:** Given `e2e_verified.json` zeigt auf einen anderen Commit als HEAD (veraltete Verifikation), When `deploy-gregor-prod.sh` läuft, Then bricht das Script mit einer klaren Fehlermeldung ab und empfiehlt `/e2e-verify` auszuführen.
- Test: (populated after /tdd-red)

**AC-4:** Given `staging_verdict` ist nicht `"VERIFIED*"` (fehlt, `BROKEN` oder `AMBIGUOUS`), When `deploy-gregor-prod.sh` bei einem Non-docs-Scope läuft, Then bricht das Script ab — kein Deploy ohne gültige Verifikation.
- Test: (populated after /tdd-red)

**AC-5:** Given `GZ_SKIP_E2E_GATE=1`, When `deploy-gregor-prod.sh` läuft, Then deployt es ohne Gate-Block, schreibt aber einen Warn-Eintrag ins Deploy-Log (keine stille Umgehung).
- Test: (populated after /tdd-red)

**AC-6:** Given der Staging Validator findet mindestens ein AC nicht erfüllt (DOM-Assertion schlägt fehl), Then liefert er `BROKEN` mit strukturiertem Finding im Adversary-Format (`F001 | Severity | URL:AC-N | Beschreibung`) und schreibt kein `VERIFIED`-Artefakt in `e2e_verified.json`.
- Test: (populated after /tdd-red)

**AC-7:** Given ein Workflow mit `scope == "docs-only"` (nur `.md`/`docs/`/`.claude/`-Änderungen committed), When `deploy-gregor-prod.sh` läuft, Then ist der Staging Validator nicht Pflicht — `staging_gate.py --check` gibt Exit 0 ohne Fehlermeldung.
- Test: (populated after /tdd-red)

## Known Limitations

- Der Staging Validator prüft nur ACs mit beobachtbaren DOM-Zuständen (sichtbare Elemente, Text, aria). Backend-only-ACs (z.B. Datenbank-Felder, E-Mail-Inhalt) liegen außerhalb seines Scope — dafür bleibt der bestehende `email_spec_validator.py`.
- Playwright-Login über `POST /api/auth/login` setzt voraus, dass kein 2FA auf dem Staging-Validator-Account aktiv ist.
- `findings[]`-Schema ist forward-compatible, aber nicht migriert: bestehende `e2e_verified.json`-Dateien ohne `findings`-Feld werden von `--check` ignoriert (nur `verified_commit` und `staging_verdict` sind Gate-relevant).
- Der 24-h-TTL in Mode B bedeutet: bei langer Debugging-Session nach /e2e-verify kann das Gate ablaufen; dann erneut `/e2e-verify` ausführen.
- `deploy-gregor-prod.sh` liegt in `henemm-infra` (separates Repo) — der Gate-Patch muss dort separat committed und deployed werden, bevor das Gate scharf ist.

## Changelog

- 2026-06-01: Initial spec (Issue #521) — Staging Validator Agent als UI-QA-Schicht zwischen push und Prod-Deploy; staging_gate.py Mode A+B; erweitertes e2e_verified.json-Schema; deploy-gregor-prod.sh Gate-Patch
