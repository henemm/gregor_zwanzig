# Context: Bug #563 — Deploy-Gate doppelt

## Request Summary

Nach `/6-validate` muss der PO `/7-deploy` eintippen UND danach nochmal `go` sagen — zwei Aktionen für eine Entscheidung. Der Fix: `/6-validate` startet den Deploy-Prozess automatisch nach Commit+Push, der PO sagt nur noch einmal `go` beim Tech-Lead-Brief.

## Related Files

| File | Relevance |
|------|-----------|
| `.claude/commands/6-validate.md` | **Hauptänderung** — Step 5 endet aktuell mit "Nächster Schritt: /7-deploy"; muss stattdessen den Deploy-Flow inline ausführen |
| `.claude/commands/7-deploy.md` | Enthält den vollständigen Deploy-Ablauf (Staging → E2E → Brief → `go` → Prod); bleibt als eigenständiger Befehl für Out-of-Band-Deploys erhalten |
| `docs/features/openspec_workflow.md` | Dokumentiert die 8 Phasen; Phase 8 = Deploy; Beschreibung muss angepasst werden |
| `CLAUDE.md` (Workflow-Tabelle, Zeile 24) | Zeigt aktuell: Phase 8 = `/7-deploy`; nach Fix: automatisch nach Phase 7 |

## Existing Patterns

- **3 PO-Gates im Workflow:** Nach Analyse (`go`), nach ACs (`go`), vor Prod-Deploy (`go`) — laut Issue-Beschreibung das Ziel
- **`/7-deploy` Ablauf:** Schritt 1 Staging triggern → Schritt 2 warten → Schritt 3 E2E (`/e2e-verify`) → Schritt 4 Tech-Lead-Brief → `go` → Schritt 5 Prod-Deploy → Schritt 6 Smoke → Schritt 7 Issue schließen
- **`/6-validate` Step 5** (aktuell): Commit+Push → "Nächster Schritt: `/7-deploy`" — übergibt Kontrolle zurück an User
- **Docs-only Ausnahme:** Bei reinen Doku-Änderungen entfällt Staging-Validierung und Prod-Deploy (aus CLAUDE.md)

## Dependencies

- **Upstream:** `/6-validate` wird nach Adversary-VERIFIED aus `/5-implement` aufgerufen
- **Downstream:** Deploy-Flow in `/7-deploy` ist der nächste Schritt nach Validation
- **Phase-State:** `phase7_validate` → `phase8_complete` — kein neuer Phasen-Übergang nötig, da Deploy schon in Phase 8 war

## Risks & Considerations

- **`/7-deploy` bleibt erhalten** — für manuelle Deploys (z.B. Hotfix außerhalb Workflow, Docs-Deploy)
- **Docs-only Ausnahme:** Die Bedingung "kein Deploy bei reinen Doku-Änderungen" muss in Step 5 von `/6-validate` berücksichtigt werden (wie bisher schon in CLAUDE.md dokumentiert)
- **Scope:** Nur `.claude/commands/6-validate.md` (Step 5) und ggf. `docs/features/openspec_workflow.md` (Beschreibung Phase 8) — kein Python-Code, keine Hooks
- **CLAUDE.md:** Phase-8-Zeile in der Workflow-Tabelle sollte aktualisiert werden (kein expliziter `/7-deploy`-Befehl mehr nötig)
