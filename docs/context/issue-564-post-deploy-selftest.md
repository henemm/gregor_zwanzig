# Context: Issue #564 — Post-Deploy-Selbsttest

## Request Summary

Nach jedem Prod-Deploy führt Claude selbstständig einen AC-Level-Selftest gegen Produktion durch, schreibt einen strukturierten Bericht (Pass/Fail pro AC) und schließt das Issue nur bei vollständigem PASS. Bei Fail: sofortige Rollback-Entscheidung ohne User-Interaktion.

## Related Files

| Datei | Relevanz |
|-------|----------|
| `.claude/commands/7-deploy.md` | **Hauptänderung**: Selftest-Schritt nach Prod-Deploy einfügen |
| `.claude/hooks/staging_gate.py` | Schreibt/prüft `e2e_verified.json` — Quelle der Staging-Findings |
| `.claude/e2e_verified.json` | Enthält `findings[]` (AC-PASS/FAIL vom Staging-Validator) |
| `.claude/agents/staging-validator.md` | Schreibt Staging-Findings — explizit nur für Staging, NICHT Prod |
| `.claude/validator.env` | Staging-Credentials + URL — darf NICHT für Prod-Login verwendet werden |
| `docs/artifacts/<workflow>/` | Zielordner für `prod-selftest.md` |
| `henemm-infra/scripts/deploy-gregor-prod.sh` | Aktuell nur HTTP-Smoke nach Deploy (`/` + `/trips/new`) |

## Existing Patterns

- **Staging-Gate**: `staging_gate.py --check` blockiert Prod-Deploy bis `e2e_verified.json` mit VERIFIED vorhanden
- **AC-Level Findings**: `e2e_verified.json` enthält `findings[]` mit `{ac, status, url, evidence}` aus Staging-Playwright
- **Prod-Smoke** (jetzt): Deploy-Script wartet auf HTTP 200/302 auf `/` und `/trips/new` — kein AC-Bezug
- **Issue-Close** (jetzt): `gh issue close` in `/7-deploy` läuft sofort nach Deploy, ohne AC-Verifikation

## Dependencies

- **Upstream**: `e2e_verified.json` (muss Findings aus Staging-Validator enthalten)
- **Upstream**: Aktiver Workflow mit `spec_file` (für AC-Definitionen)
- **Upstream**: `deploy-gregor-prod.sh` muss erfolgreich (Exit 0) gewesen sein
- **Downstream**: `gh issue close` — darf erst nach Selftest-PASS laufen

## Existing Specs

- `docs/features/scope.md` — Projektvision
- Kein bestehender Spec für "post-deploy self-test"

## Key Design Decision

**Kein Playwright gegen Production** — staging-validator sagt explizit: niemals gegen `gregor20.henemm.com` ohne `staging.`. Begründung: Real-Sessions, Real-Daten, Real-User betroffen.

Stattdessen **2-Stufen-Prod-Selftest**:
1. **Commit-Attestation**: `GET /api/health` → `commit`-Feld muss HEAD-SHA matchen (beweist: Code ist wirklich live)
2. **AC-Attestation**: Für jede AC aus `e2e_verified.json findings[]`:
   - Status `PASS` auf Staging → generiere HTTP-Smoke-Nachweis (GET der URL, kein Login)
   - Schreibe `{ac, staging_status, prod_evidence}` in Bericht
3. **Bericht**: `docs/artifacts/<workflow>/prod-selftest.md` — Markdown-Tabelle per AC

## Risks & Considerations

- **Kein Spec im Workflow**: Wenn `spec_file=null`, kann kein AC-Selftest laufen → Fallback: nur Commit-Attestation, Hinweis im Bericht
- **Selftest-Timeout**: Muss <60s laufen (nach Deploy schon 2+ Min gewartet)
- **Issue #563 (OPEN)**: Vereinfacht den Deploy-Flow (doppeltes Gate entfernen) — unabhängiger Scope, aber beide ändern `/7-deploy`. Achtung auf Konflikt beim Merge
- **Selftest schlägt fehl**: Prod ist live aber kaputt → Issue nicht schließen + Rollback-Snippet ausgeben
- **Bestehende Workflows ohne ACs**: Selftest liefert nur Commit-Attestation (nicht leer, aber reduziert)
