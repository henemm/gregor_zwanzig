# Kontext: fix-2873-deploy-sidebar (#2873)

## Request Summary

PO-Meldung 2026-11-09: Die Workflow-Seitenleiste (Plan-Ansicht des Plugins agent-os-openspec)
zeigte nach Phase 8 „▶ Deploy (nicht eingerichtet)“ und zugleich „Nächster: /70-deploy #N“.
Ziel: Der Deploy-Stand ist immer eindeutig (offen → läuft → fertig / fehlgeschlagen), und
`/70-deploy` wird nur vorgeschlagen, solange der Deploy wirklich offen ist.

## Ist-Stand mit Plugin 4.28.1 (geprüft 2026-11-27)

- `openspec.yaml` hat weiterhin **keinen `deploy:`-Block** (Top-Level-Schlüssel: project,
  workflow, protected_paths, always_allowed, strict_code_gate, specs, claude_md, modules,
  agents, spec_validation, scope_guard, bash_gate, hooks, herdr).
- `workflow.py deploy_mode()` → `unconfigured`; `_plan_deploy_mode()` bildet das seit #550 auf
  `off` ab. Folge heute: Der Plan zeigt **gar keine Deploy-Zeile**, und der Endzustand meldet
  „#N ist fertig (und ausgeliefert)“, obwohl der Prod-Deploy noch aussteht. Der Widerspruch
  aus der Meldung ist dem Wortlaut nach verschwunden, der Kern (Leiste kennt den Prod-Deploy
  nicht) besteht.
- Weder `.claude/commands/70-deploy.md` noch Projekt-Hooks/Skripte setzen
  `workflow.py ship-status …` oder `workflow.py deploy-status …` (grep ohne Treffer).

## Relevante Plugin-Mechanik (nur lesen, Plugin wird nicht geändert)

- `deploy_mode()` (workflow.py ~4666): `configured`, wenn `deploy.command` UND `deploy.verify`
  gesetzt; `off` bei `deploy.enabled: false`.
- `deploy_autonomous()` (~4903): `deploy.autonomous: true` → Endzustand „⏳ Claude deployt #N“
  statt „❗ Du: /70-deploy“ (passt zu CLAUDE.md: Deploy läuft ohne Halt).
- `render_plan` (~761–793): Deploy-Zeile nur bei `configured`; sie wird erst „aktiv“, wenn
  Phase 8 erreicht **und** `ship_status` done/skipped ist (`ship_final`).
- `_plan_deploy_line` (~836): `○ Deploy` / `▶ Deploy (offen)` / `▶ Deploy (läuft)` /
  `✔ Deploy` / `✘ Deploy (fehlgeschlagen)`.
- `phase8_complete` setzt `ship_status: open` (#612). Ohne `ship-status done` bleibt die
  Auslieferung (Push/PR/Merge) als offen stehen → Deploy-Zeile käme nie über „○“ hinaus.
  **Daher muss `/70-deploy` auch `ship-status` führen**, sonst bleibt das Ziel unerreicht.
- `cmd_deploy_status` / `cmd_ship_status`: rein informativ, keine Gate-Wirkung; `--note` für
  Fehlergrund.
- `deploy.command`/`verify`/`rollback` werden vom Plugin nur angezeigt (`deploy-config`), nicht
  ausgeführt; das Projekt ersetzt `/70-deploy` durch `.claude/commands/70-deploy.md`.

## Related Files

- `openspec.yaml` — `deploy:`-Block ergänzen (command, verify, rollback, autonomous).
- `.claude/commands/70-deploy.md` — Statusaufrufe an den Schrittgrenzen:
  Schritt 1 (Push/PR/Merge) → `ship-status running` / `done` / `failed`;
  Schritt 4 → `deploy-status running`; nach Selftest-Exit 0 bzw. Server-Status `success`
  → `deploy-status done`; Hard-Gate-Abbruch (Staging BROKEN, Selftest ≠ 0, Status
  `failure`) → `deploy-status failed --note …`.
- Doku-Ausnahme „reine Doku-/Werkzeug-Änderung“ (Schritt 2–4 entfallen): dann
  `deploy-status done --note "nur Doku/Werkzeug, kein Prod-Deploy nötig"` (sonst bliebe „offen“).

## Existing Patterns

- Zwei Deploy-Wege: auf dem Server direkt (`deploy-gregor-prod.sh` + `prod_selftest.py`),
  außerhalb (iMac/Mac/Cloud) Warten auf Commit-Status `deploy/prod` (Pull-Deploy, ADR-0129).
  Beide Wege müssen dieselben Statusübergänge setzen.

## Dependencies / Dependents

- Abhängig: Plugin agent-os-openspec ≥ 4.x (`ship-status`, `deploy-status`, `deploy.autonomous`).
- Wer liest `openspec.yaml`: alle Plugin-Hooks über `config_loader`. Ein neuer Top-Level-Block
  `deploy:` ändert keine Gate-Regel (nur Anzeige/Endzustand), Risiko für Gates gering;
  YAML-Syntax muss aber valide bleiben (sonst fallen alle Hooks auf Defaults).
- Mögliche Hook-Sperre beim Editieren von `openspec.yaml` (Gate-Config-Schutz) — prüfen.

## Existing Specs

- Keine Modul-Spec für Workflow-Tooling im Projekt; Mechanik in Plugin-Issues #510, #550, #612.

## Risks

- YAML-Fehler in `openspec.yaml` legt alle Hooks lahm → nach Edit mit `deploy-config` und
  `python3 -c yaml.safe_load` prüfen.
- `deploy.command` darf nicht so verstanden werden, dass ein Plugin-Pfad ihn auf dem Mac
  ausführt — Plugin führt ihn nicht aus (nur Anzeige); Wert dokumentiert den Server-Weg.
- Test: Verhalten über echte `workflow.py`-Aufrufe (render/endstate) gegen das Projekt-Config
  prüfen, kein Mock.

## Analysis

**Type:** Bugfix (Anzeige-/Statusfehler im Workflow-Tooling, kein Produktcode).

### Affected Files

| Datei | Change | Grund |
|---|---|---|
| `openspec.yaml` | MODIFY | `deploy:`-Block: `command` (Server-Deploy-Skript), `verify` (`prod_selftest.py`), `rollback` (Verweis Playbook), `autonomous: true` |
| `.claude/commands/70-deploy.md` | MODIFY | Plugin-Pfad-Auflösung für `workflow.py`; Statusaufrufe `ship-status running/done/failed` um Schritt 1, `deploy-status running/done/failed` um Schritt 2–4b (Server- und Nicht-Server-Weg), Doku-Ausnahme → `deploy-status done --note …`; Reihenfolge: Status `done` VOR `write-log`/`finish` |
| `tests/tdd/test_issue_2873_deploy_sidebar.py` | CREATE | Verhaltenstests über echtes Plugin-`workflow.py` (skip, wenn Plugin fehlt, wie `tests/unit/test_secret_output_gate.py`) + ein `# doc-compliance-test` für die Statusaufrufe in `70-deploy.md` |

### Scope / Risk

- ~15 Zeilen YAML/Markdown + ~90 Zeilen Test; 3 Dateien. Risiko niedrig-mittel: YAML-Validität
  von `openspec.yaml` ist kritisch (alle Hooks lesen sie). Keine Gate-Regel ändert sich;
  `deploy.*` wirkt nur auf Plan-Anzeige und Endzustand (`endstate`).
- `ship.py` des Plugins setzt `ship-status` selbst, wird im Projekt aber nicht genutzt
  (Projekt-`70-deploy` pusht/merged von Hand) → Statusaufrufe explizit in die Anleitung.

### Technical Approach

1. `openspec.yaml` um `deploy:` ergänzen (Werte als Strings; Plugin führt sie nicht aus).
2. `70-deploy.md`: Setup-Block mit `$WF` (gleiche Auflösung wie Plugin-Skills); an jeder
   Schrittgrenze den Status setzen; Hard-Gate-Abbruch → `failed --note <Befund>`.
3. Tests (Nutzersicht = was die Leiste/der Endzustand zeigt), in temp-Projektkopie mit der
   echten `openspec.yaml`:
   - `deploy-config` → `DEPLOY_CONFIGURED=yes`, `autonomous: true`.
   - Workflow in Phase 8, `ship_status` done, kein `deploy_status` → Plan enthält
     „▶ Deploy  (offen)“, nicht „nicht eingerichtet“; Endzustand ⏳ statt ❗ `/70-deploy`.
   - `deploy_status` running/done/failed → „(läuft)“ / „✔ Deploy“ / „✘ Deploy (fehlgeschlagen)“;
     bei done keine `/70-deploy`-Empfehlung.
   - doc-compliance: `70-deploy.md` enthält `deploy-status running|done|failed` und
     `ship-status running|done|failed`.
   RED-Nachweis: Ohne `deploy:`-Block fehlt die Deploy-Zeile / `DEPLOY_CONFIGURED=no`.

### Dependencies

Plugin agent-os-openspec ≥ 4.28 (`ship-status`, `deploy-status`, `_plan_deploy_mode`).

### Open Questions

Keine — technische Umsetzung; die Produktentscheidung (autonomer Deploy) steht in CLAUDE.md.
