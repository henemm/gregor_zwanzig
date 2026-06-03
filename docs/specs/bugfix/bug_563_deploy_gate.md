---
entity_id: bug_563_deploy_gate
type: bugfix
created: 2026-06-02
updated: 2026-06-02
status: draft
version: "1.0"
tags: [workflow, infra, deploy, gates]
---

# Bug #563: Deploy-Gate doppelt

## Approval

- [ ] Approved

## Purpose

Behebt die redundante Doppel-Aktion am Workflow-Ende: Bisher musste der PO `/7-deploy` eintippen und danach nochmal `go` sagen — zwei Aktionen für eine Entscheidung. Nach dem Fix läuft der Deploy-Prozess automatisch nach dem Commit weiter, der PO sagt nur noch einmal `go` beim Tech-Lead-Brief.

Gleichzeitig werden zwei falsche Angaben in der CLAUDE.md-Workflow-Tabelle korrigiert: Phase 3 zeigt `'approved'` statt dem tatsächlich erkannten `'go'`; Phase 8 zeigt `'ja' sagen` statt `'go'`.

## Source

- **Files:**
  - `.claude/commands/6-validate.md` — Step 5 (Zeilen 159–176): Übergabe-Abschnitt wird durch inline Deploy-Ablauf ersetzt
  - `CLAUDE.md` — Workflow-Tabelle Zeilen 19 und 24: falsche Keywords korrigieren

## Estimated Scope

- **LoC:** ~30 (reine Textänderung in Markdown-Dateien, kein Logik-Code)
- **Files:** 2
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `.claude/commands/7-deploy.md` | Referenz (unverändert) | Liefert den Deploy-Ablauf, der in 6-validate.md inline übernommen wird |
| `workflow_state_updater.py` | keine Änderung | Erkennt `go` bereits korrekt — Hook bleibt unverändert |

## Implementation Details

**Änderung 1 — `6-validate.md` Step 5:**

Aktuell (Zeilen 159–176):
```markdown
## Step 5: Commit & Übergabe an Deploy

After successful validation:

1. **Commit & Push** the changes
2. **Dem User mitteilen:** Validierung abgeschlossen — bereit für Deploy
3. **NICHT** "Fertig und live" oder "abgeschlossen" sagen — das passiert erst nach Prod-Deploy
4. **Nächster Schritt:** `/7-deploy` — dort wird auf Staging gewartet, ...

**Das Issue bleibt offen bis `/7-deploy` abgeschlossen ist.**
```

Neu (Zeilen 159–):
```markdown
## Step 5: Commit, Push & Deploy

After successful validation, commit and push — dann direkt weiter mit dem Deploy (NICHT auf `/7-deploy` warten):

1. **Commit & Push** the changes
2. **Staging-Deploy sofort triggern** (nicht auf Cron warten):
   bash /home/hem/henemm-infra/scripts/auto-deploy-gregor-staging.sh
3. **Auf Staging warten** (max. 5×30s, bis /api/health den neuen Commit zeigt)
4. **E2E ausführen** via `/e2e-verify` — kein Weitergehen bis VERIFIED
5. **Tech-Lead-Brief ausgeben** (erst nach E2E VERIFIED — gleiche Vorlage wie in /7-deploy)
6. **Auf 'go' warten** — dann Prod-Deploy
7. **Prod-Deploy:** bash /home/hem/henemm-infra/scripts/deploy-gregor-prod.sh
8. **Post-Deploy-Smoke** und Issue schließen

NICHT "Fertig und live" sagen, bis Schritt 8 abgeschlossen ist.
```

**Änderung 2 — `CLAUDE.md` Zeile 19 (Phase 3):**

Aktuell:
```
| 3 | `/3-write-spec` | Spezifikation erstellen | **Pflicht: ACs auf Deutsch freigeben** ('approved') |
```

Neu:
```
| 3 | `/3-write-spec` | Spezifikation erstellen | **Pflicht: ACs auf Deutsch freigeben** ('go') |
```

**Änderung 3 — `CLAUDE.md` Zeile 24 (Phase 8):**

Aktuell:
```
| 8 | `/7-deploy` | Deployment | **Pflicht: Tech-Lead-Brief lesen + 'ja' sagen** |
```

Neu:
```
| 8 | — | Deployment (automatisch via `/6-validate`) | **Pflicht: Tech-Lead-Brief lesen + 'go' sagen** |
```

## Expected Behavior

- **Input:** PO führt `/6-validate` nach erfolgter Implementierung aus
- **Output:** Nach Commit+Push läuft der Deploy-Prozess automatisch: Staging → E2E → Tech-Lead-Brief → Pause → `go` → Prod → Issue-Schließung
- **Side effects:** `/7-deploy` bleibt unverändert als eigenständiger Befehl für manuelle Out-of-Band-Deploys erhalten

## Acceptance Criteria

**AC-1:** Given `/6-validate` wurde ausgeführt und alle Validierungen sind bestanden / When Step 5 erreicht wird / Then startet der Deploy-Prozess automatisch (Staging-Trigger, Warte-Loop, E2E) ohne dass der PO einen Befehl eintippen muss.

**AC-2:** Given der Deploy-Prozess läuft in Step 5 von `/6-validate` / When E2E auf Staging VERIFIED ist / Then erscheint der Tech-Lead-Brief und Claude wartet auf `go` — danach läuft Prod-Deploy und Issue-Schließung automatisch durch.

**AC-3:** Given `CLAUDE.md` Workflow-Tabelle Phase 3 / When der PO-Eingriff gelesen wird / Then steht dort `('go')` — nicht `('approved')`.

**AC-4:** Given `CLAUDE.md` Workflow-Tabelle Phase 8 / When der PO-Eingriff gelesen wird / Then steht dort `'go' sagen` (nicht `'ja' sagen`) und die Command-Spalte zeigt `—` statt `/7-deploy`.

**AC-5:** Given `/7-deploy` wird als eigenständiger Befehl aufgerufen / When der Befehl ausgeführt wird / Then läuft der vollständige Deploy-Ablauf wie bisher (Staging → E2E → Brief → `go` → Prod).

## Known Limitations

- Docs-only-Ausnahme (aus CLAUDE.md) gilt weiterhin: Bei Workflows mit ausschließlich Doku-Änderungen kann der PO den Deploy-Schritt überspringen — dies wird durch bestehende Logik in 7-deploy geregelt und muss in Step 5 sinngemäß übernommen werden.

## Changelog

- 2026-06-02: Initial spec created (Issue #563)
