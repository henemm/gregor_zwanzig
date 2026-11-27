---
entity_id: workflow_deploy_status
type: bugfix
created: 2026-11-27
updated: 2026-11-27
status: draft
version: "1.0"
workflow: fix-2873-deploy-sidebar
tags: [workflow, tooling, deploy, issue-2873]
---

# Deploy-Stand in der Workflow-Seitenleiste (Issue #2873)

## Approval

- [ ] Approved

## Purpose

Die Workflow-Seitenleiste (Plan-Ansicht des Plugins agent-os-openspec) soll den Stand des Prod-Deploys immer eindeutig zeigen (offen, läuft, fertig, fehlgeschlagen). `/70-deploy` wird nur noch vorgeschlagen, solange der Deploy wirklich offen ist. Heute kennt die Leiste den Prod-Deploy nicht: Es gibt keinen `deploy:`-Block, und die Projekt-Anleitung setzt keinen Status.

## Source

- **File:** `openspec.yaml`, `.claude/commands/70-deploy.md`
- **Identifier:** Block `deploy:` (Projekt-Einstellung); Statusaufrufe `workflow.py ship-status` und `workflow.py deploy-status` in der Anleitung

> Schicht-Hinweis: reines Workflow-Tooling (Projekt-Konfiguration und Anleitung). Kein Frontend, keine Go-API, kein Python-Core. Plugin-Code (`workflow.py`) wird nicht geändert, nur gelesen und aufgerufen.
> Trip/Ortsvergleich-Teilung, Mandantentrennung, Kanäle: nicht betroffen (keine Nutzerdaten, kein Briefing-/Alarm-Inhalt).

## Estimated Scope

- **LoC:** ~15 Zeilen YAML/Markdown, ~90 Zeilen Test
- **Files:** 3
- **Effort:** low

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `openspec.yaml` | MODIFY | `deploy:`-Block: `command`, `verify`, `rollback`, `autonomous: true` |
| `.claude/commands/70-deploy.md` | MODIFY | Pfadauflösung für `workflow.py`; `ship-status` und `deploy-status` an den Schrittgrenzen (Server- und Nicht-Server-Weg), vor `write-log`/`finish` |
| `tests/tdd/test_issue_2873_deploy_sidebar.py` | CREATE | Echte `workflow.py`-Aufrufe (subprocess) gegen Temp-Kopie mit der echten `openspec.yaml`; `# doc-compliance-test` für die Anleitungsaufrufe |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| Plugin agent-os-openspec >= 4.28 (`workflow.py`) | external tool | `deploy-config`, `ship-status`, `deploy-status`, Plan-Ansicht, Endzustand |
| `deploy.autonomous` / `deploy_mode()` | Plugin-Mechanik | Endzustand "Claude deployt #N"; Deploy-Zeile nur bei `configured` |
| `/home/hem/henemm-infra/scripts/deploy-gregor-prod.sh` (Infra-Repo, nur auf dem Server), `.claude/hooks/prod_selftest.py` | Projekt-Skripte | Werte für `deploy.command` und `deploy.verify` (werden nur angezeigt, nicht vom Plugin ausgeführt) |
| `docs/reference/operations_playbook.md` | Doku | Ziel des `deploy.rollback`-Verweises |
| `tests/unit/test_secret_output_gate.py` | Testmuster | Skip, wenn Plugin nicht installiert |

## Implementation Details

1. `openspec.yaml`: neuer Top-Level-Block `deploy:` mit `command` (`bash /home/hem/henemm-infra/scripts/deploy-gregor-prod.sh`), `verify` (`python3 .claude/hooks/prod_selftest.py`), `rollback` (Verweis auf operations_playbook), `autonomous: true`. Werte sind Strings; das Plugin führt sie nicht aus, der Block wirkt nur auf Plan-Anzeige und Endzustand. Keine Gate-Regel ändert sich. Die Datei muss gültiges YAML bleiben (alle Hooks lesen sie).
2. `.claude/commands/70-deploy.md`: Setup-Block, der `workflow.py` im Plugin auflöst (`workflow.py` liegt im Plugin, nicht in `.claude/hooks`; gleiche Pfadauflösung wie die Plugin-Skills). Statusaufrufe:
   - `ship-status`: `running` vor dem Push, `done` nach dem Merge, `failed` bei CI rot oder Merge unmöglich.
   - `deploy-status`: `running` beim Start des Prod-Deploys (Server-Weg) bzw. beim Warten auf den Commit-Status `deploy/prod` (Nicht-Server-Weg); `done` nach Selftest-Exit 0 bzw. Server-Status `success`; `failed --note <Befund>` bei Staging BROKEN, Selftest-Exit != 0 oder Server-Status `failure`.
   - Doku-Ausnahme (Schritt 2 bis 4 entfallen): `deploy-status done --note "nur Doku/Werkzeug, kein Prod-Deploy nötig"`.
   - Reihenfolge: Status `done`/`failed` immer vor `write-log` und `finish`.
3. Test: Temp-Projektkopie mit der echten `openspec.yaml`, Workflow-Zustand in Phase 8, dann echte Aufrufe von `deploy-config`, Plan-Ansicht und Endzustand; Skip, wenn Plugin fehlt.

## Expected Behavior

- **Input:** Workflow-Zustand (Phase, `ship_status`, `deploy_status`) und Projekt-Einstellung `deploy:`
- **Output:** Deploy-Zeile der Seitenleiste (`○ Deploy`, `▶ Deploy (offen)`, `▶ Deploy (läuft)`, `✔ Deploy`, `✘ Deploy (fehlgeschlagen)`) und Endzustandszeile (`⏳ Claude deployt #N` statt `❗ Du: /70-deploy`)
- **Side effects:** keine; Status ist rein informativ, ohne Gate-Wirkung

## Acceptance Criteria

- **AC-1:** Given die Projekt-Einstellung `openspec.yaml` enthält den `deploy:`-Block / When `workflow.py deploy-config` gegen das Projekt läuft / Then meldet die Ausgabe `DEPLOY_CONFIGURED=yes` und `autonomous: true`, mit dem Server-Deploy-Skript als command, `prod_selftest.py` als verify und einem Verweis auf operations_playbook als rollback.
  - Test: echter `deploy-config`-Aufruf gegen eine Temp-Kopie mit der echten `openspec.yaml` zeigt eingerichtet und autonom.

- **AC-2:** Given ein Workflow in Phase 8, die Auslieferung (Merge) ist fertig und der Deploy noch nicht gestartet / When die Seitenleiste gerendert wird / Then steht dort `▶ Deploy (offen)` und an keiner Stelle `nicht eingerichtet`.
  - Test: Plan-Ansicht für Phase 8 mit `ship_status: done` und ohne `deploy_status` enthält die offene Deploy-Zeile.

- **AC-3:** Given derselbe Zustand wie in AC-2 (Deploy offen) bei autonomem Deploy / When die Endzustandszeile berechnet wird / Then lautet sie `⏳ Claude deployt #N` und fordert den PO nicht mit `❗ /70-deploy` zum Handeln auf.
  - Test: Endzustand-Aufruf zeigt das Wartezeichen und enthält keine PO-Aufforderung.

- **AC-4:** Given `deploy-status` steht auf `running`, `done` oder `failed` / When die Seitenleiste gerendert wird / Then zeigt sie `▶ Deploy (läuft)`, `✔ Deploy` bzw. `✘ Deploy (fehlgeschlagen)`, und bei `done` wird `/70-deploy` nicht mehr als nächster Schritt vorgeschlagen.
  - Test: drei echte Plan-Aufrufe je Status; beim Status `done` fehlt die `/70-deploy`-Empfehlung im Endzustand.

- **AC-5:** Given die Projekt-Anleitung `/70-deploy` / When ein Deploy auf dem Server oder von einem Nicht-Server-Rechner durchgeführt wird / Then setzt sie `ship-status` (`running` vor dem Push, `done` nach dem Merge, `failed` bei CI rot oder Merge unmöglich) und `deploy-status` (`running` beim Start bzw. Warten auf den Server-Status, `done` nach Selftest-Exit 0 bzw. Server-Status `success`, `failed --note` bei Staging BROKEN, Selftest-Exit != 0 oder Server-Status `failure`).
  - Test: `# doc-compliance-test`: Anleitung enthält auf beiden Wegen alle genannten `ship-status`- und `deploy-status`-Aufrufe samt `--note` bei `failed`.

- **AC-6:** Given eine reine Doku-/Werkzeug-Änderung, bei der Staging und Prod-Deploy entfallen / When `/70-deploy` abgeschlossen wird / Then steht `deploy-status done` mit Notiz, und `write-log` bzw. `finish` folgen erst nach dem Status, sodass die Leiste nicht auf `offen` hängen bleibt.
  - Test: `# doc-compliance-test`: Doku-Ausnahme enthält `deploy-status done --note`, und in der Anleitung steht der Status vor `write-log`/`finish`; die Pfadauflösung für `workflow.py` im Plugin ist vorhanden.

- **AC-7:** Given der neue `deploy:`-Block in `openspec.yaml` / When die Datei geparst wird und die Plugin-Aufrufe laufen / Then bleibt sie gültiges YAML, alle bisherigen Top-Level-Schlüssel sind erhalten, und keine Gate-Regel (Sperren, Scope, Phasen) verhält sich anders.
  - Test: `yaml.safe_load` liefert alle vorherigen Schlüssel plus `deploy`; die Plugin-Aufrufe gegen die Temp-Kopie laufen ohne Fehler durch.

## Scope

- **Drin:** `deploy:`-Block in `openspec.yaml`; Statusaufrufe `ship-status`/`deploy-status` samt Plugin-Pfadauflösung in `.claude/commands/70-deploy.md`; ein neuer Testfile.
- **Nicht drin:** Plugin-Code (`workflow.py`, Plan-Rendering), Deploy-Skripte selbst, Pull-Deploy-Timer, Produktcode.

## Test Plan

- `tests/tdd/test_issue_2873_deploy_sidebar.py` (Kern-Schicht, ohne Netz): Temp-Projektkopie mit der echten `openspec.yaml`; echte Aufrufe des installierten Plugin-`workflow.py` per subprocess (`deploy-config`, Plan-Ansicht, `endstate`) für Phase 8 mit `ship_status: done` und `deploy_status` leer/`running`/`done`/`failed` (AC-1 bis AC-4, AC-7).
- Doc-compliance-Teil (`# doc-compliance-test`) für die Anleitungsaufrufe (AC-5, AC-6).
- RED-Nachweis: vor der Änderung meldet `deploy-config` `DEPLOY_CONFIGURED=no`, die Deploy-Zeile fehlt, die Anleitung enthält keine Statusaufrufe.
- Skip, wenn das Plugin nicht installiert ist.

## Definition of Done

- Alle ACs durch den Testfile grün belegt; vorher rot nachgewiesen.
- `openspec.yaml` parst fehlerfrei; bestehende Gate-Tests, die `openspec.yaml` lesen, bleiben grün.
- Adversary-Verdict VERIFIED inkl. Mutations-Gegenprobe.
- PR mit allen CI-Checks grün gemergt; Issue #2873 mit Ergebnis-Kommentar geschlossen.

## Known Limitations

- Das Plugin führt `deploy.command`, `verify` und `rollback` nicht aus; sie dienen nur der Anzeige. Der Statuswechsel hängt an den Aufrufen in der Projekt-Anleitung.
- Das Plugin-eigene `ship.py` wird im Projekt nicht genutzt, daher setzt die Anleitung `ship-status` selbst.
- Tests werden übersprungen, wenn das Plugin nicht installiert ist (z. B. in CI ohne Plugin).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Konfigurations- und Anleitungsergänzung im Rahmen der bestehenden Entscheidung "Deploy läuft autonom" (CLAUDE.md, ADR-0129 Pull-Deploy); keine neue Entscheidungsfläche.

## Changelog

- 2026-11-27: Initial spec created (Issue #2873)
