# Mini-Spec: #894 — Verwaiste Session-Registry aufräumen

## Kontext

Seit der Plugin-3.4.0-Migration (`33da201c`, 2026-06-22) schreibt **niemand** mehr
`.claude/session_workflows.json` — der frühere Schreiber `workflow_state_updater.py`
wurde gelöscht (#893). Einziger verbliebener Leser im Hauptrepo ist
`.claude/hooks/renderer_mail_gate.py` (Funktion `_active_workflow_name`, Z. 116–140),
der über `GZ_HOOK_SESSION_ID`/`CLAUDE_CODE_SESSION_ID` in die Registry schaut und
sonst auf `OPENSPEC_ACTIVE_WORKFLOW` zurückfällt. Der Registry-Lookup trifft
praktisch nie → toter Pfad. Alle Schwester-Gates nutzen längst den zentralen
Resolver `hook_utils.resolve_active_workflow()` / `get_active_workflow_name()`.

## Was ändert sich

- `renderer_mail_gate.py`: Funktion `_active_workflow_name()` entfällt; der Aufrufer
  nutzt `hook_utils.get_active_workflow_name()` (zentraler Resolver, identisch zu
  allen anderen Gates). Der Registry-Lookup über `session_workflows.json` und die
  `GZ_HOOK_SESSION_ID`/`CLAUDE_CODE_SESSION_ID`-Logik werden gelöscht.
- `.claude/session_workflows.json` (394 Zeilen Altdaten) wird gelöscht, da nach dem
  obigen Schritt kein Leser mehr darauf zugreift.

## Was darf sich nicht ändern

- **Verhalten des Gates bei aktivem Workflow:** Bei gesetztem
  `OPENSPEC_ACTIVE_WORKFLOW` muss der Resolver denselben Workflow-Namen liefern wie
  bisher (war ohnehin der reale Fall — der Env-Fallback griff praktisch immer).
- **Block-/No-op-Logik:** Matrix-Hash-Prüfung, Validator-Log-Freshness, Exit-Codes
  (0 = erlaubt/no-op, 2 = blockiert) bleiben unverändert.
- **Keine Mail-Inhalts-Datei** wird angefasst (`src/output/renderers/email/*`,
  `src/formatters/*`, `src/outputs/email.py`) → das #811-Renderer-Commit-Gate wird
  durch diese Änderung nicht ausgelöst.

## Manuelle Test-Schritte

1. `python3 -c "import ast; ast.parse(open('.claude/hooks/renderer_mail_gate.py').read())"` → Syntax ok.
2. Bei gesetztem `OPENSPEC_ACTIVE_WORKFLOW=fix-894-orphan-session-registry` das Gate
   im Hook-Modus aufrufen (ohne gestagte Mail-Datei) → Exit 0 (no-op).
3. `grep -rn "session_workflows" .claude/hooks/*.py` → keine Treffer mehr im Hauptrepo.
4. `test ! -e .claude/session_workflows.json` → Datei gelöscht.

## Inline-Test (wird während Implementierung geschrieben)

- [ ] Test: `renderer_mail_gate` resolved den aktiven Workflow-Namen über
      `hook_utils.get_active_workflow_name()` (Env `OPENSPEC_ACTIVE_WORKFLOW` gesetzt
      → korrekter Name; nicht gesetzt → leer), und referenziert
      `session_workflows.json` nicht mehr.
