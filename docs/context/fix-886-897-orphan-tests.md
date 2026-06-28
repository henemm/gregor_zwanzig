# Context: fix-886-897-orphan-tests

## Request Summary
Bündel #886 + #897 — Bereinigung zweier Test-Altlasten aus der Plugin-Migration (Commit 33da201c, 2026-06-22). Reine Test-/Tooling-Ebene, kein Produktionscode.

## Befund pro Issue

### #886 — bereits behoben (verifiziert)
`tests/tdd/test_issue_811_renderer_gate.py::test_pass_with_both_evidences` und `::test_record_matrix_writes_hash`.
- Issue forderte: Subprozess-Env mit `OPENSPEC_ACTIVE_WORKFLOW` explizit setzen (statt Ambient-Env zu erben).
- **Bereits eingespielt durch Commit `4c2de0a3` (fix(#894))**: `_run_gate` (Z. 89–98) und der Commit-Test (Z. 325–338) setzen `env["OPENSPEC_ACTIVE_WORKFLOW"]=_WF_NAME` und übergeben `env=env`.
- **Verifikation gegen origin/main-Basis (HEAD f9275fd3): beide Tests grün (`..`).**
- Konsequenz: kein Code nötig, Issue als erledigt schließen.

### #897 — verwaister Test, entfernen
`tests/tdd/test_bug_380_approval_injection.py` (14 Tests).
- Test ruft `.claude/hooks/workflow_state_updater.py` als Subprozess auf (Z. 30, 65–86) und schreibt in `.claude/session_workflows.json` (`_bind`, Z. 87–88).
- **Beide existieren seit 33da201c (Plugin-Migration) nicht mehr.** Verifikation: alle 14 Tests `FAILED` mit `can't open file '.../workflow_state_updater.py': No such file or directory`.
- Der getestete Mechanismus (separater Updater-Hook + Session-Registry) ist vollständig durch `phase_listener.py` (UserPromptSubmit) ersetzt — siehe #892, #893, #894.

## Bug-380-Schutz heute (strukturell garantiert)
Bug-380-Sorge: injizierter Agent-/Task-Text darf keine Spec-/GREEN-Freigabe auslösen.
- Freigabe-Stichworte werden heute NUR in `phase_listener.py` ausgewertet, das ausschließlich am Hook-Ereignis **UserPromptSubmit** hängt.
- `hook_utils.get_user_message()` (Z. 48–60) liest ausschließlich das `prompt`-Feld des UserPromptSubmit-Payloads = echte Nutzer-Eingabe.
- Injizierter Text (Agent-Output, Task-Notifications, system-reminder) kommt NICHT als UserPromptSubmit an → erreicht den Hook nie.
- Zusätzlich phasengebunden: Spec-Approval nur in `phase3_spec`, GREEN nur in `phase6_implement`/`phase6b_adversary`.
- **Ergebnis:** Der Schutz, den der alte Test inhaltlich nachstellte, ist heute durch die Architektur (Hook-Event) sichergestellt. Kein Ersatztest nötig.

## Related Files
| Datei | Relevanz |
|------|-----------|
| tests/tdd/test_bug_380_approval_injection.py | Verwaist — wird entfernt (#897) |
| tests/tdd/test_issue_811_renderer_gate.py | #886 bereits grün — unverändert |
| .claude/hooks/phase_listener.py | Heutiger Freigabe-Mechanismus (UserPromptSubmit) |
| .claude/hooks/hook_utils.py | get_user_message liest nur prompt-Feld |

## Verwandte Vorgänge
- #893, #894: gleiche Orphan-Klasse aus 33da201c bereits bereinigt (Session-Binding-/Registry-Tests).
- #892: Stichwort-Steuerung über phase_listener wiederhergestellt.

## Risiken & Erwägungen
- Risiko minimal: Löschen eines Tests, der nicht ausführbar ist (fehlende Datei). Keine Produktverhalten-Änderung.
- Einzige inhaltliche Prüfung (Bug-380-Schutz) oben abgeschlossen: strukturell erhalten.
