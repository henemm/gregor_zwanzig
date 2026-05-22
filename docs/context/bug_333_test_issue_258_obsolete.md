# Context: Bug #333 — `test_issue_258_hook_arch.py` veraltet nach Symlink-Fallback-Deaktivierung

## Request Summary

9 von 17 Tests in `tests/tdd/test_issue_258_hook_arch.py` sind rot, weil sie auf der **alten** Hook-Architektur basieren (Symlink `.active` als autoritative Quelle des aktiven Workflows). Commit `59bd925` (2026-05-22) hat den Symlink-Fallback in `workflow.py:_active_name()` bewusst deaktiviert — Tests sind veraltet, nicht der Production-Code. Sie müssen auf die neue Resolution-Reihenfolge (Session-Registry > `GZ_ACTIVE_WORKFLOW` > FATAL) aktualisiert werden.

## Related Files

| File | Relevance |
|------|-----------|
| `tests/tdd/test_issue_258_hook_arch.py` | Die zu aktualisierende Test-Datei (627 Zeilen, 17 Tests, 9 rot) |
| `.claude/hooks/workflow.py` | `_active_name()` + `read_active_workflow_fast()` + `cmd_complete` + `cmd_cleanup` — die geprüfte Production-Logik |
| `.claude/hooks/tdd_enforcement.py` | Z. 246–247: nutzt bereits `read_active_workflow_fast` (AC-4, bereits grün) |
| `.claude/hooks/workflow_gate.py` | Z. 32/41/94/100: nutzt bereits `read_active_workflow_fast` (AC-5, bereits grün) |
| `docs/specs/modules/issue_258_hook_arch_fix.md` | Ursprungs-Spec mit 14 ACs — diente als Grundlage für die Tests |
| `docs/context/issue-258-hot-path-hooks.md` | Damaliger Kontext zur Hook-Architektur-Umstellung |

## Existing Patterns

### Aktuelle Resolution-Reihenfolge in `_active_name()` (workflow.py:328–385)

1. **Session-ID-Registry** (höchste Priorität) — `GZ_HOOK_SESSION_ID`/`CLAUDE_CODE_SESSION_ID` → `session_workflows.json` Lookup (Issue #325, eingeführt mit `f905a67`/`3798e44`)
2. **`GZ_ACTIVE_WORKFLOW` ENV-Var** — wenn gesetzt aber ungültig → FATAL exit 1
3. **`.active`-Symlink** — wenn vorhanden ohne ENV-Var → FATAL exit 1 mit Anweisung „export GZ_ACTIVE_WORKFLOW=…"
4. **Legacy single-file state** — nur wenn v3-Dir leer

### Was die Tests in `test_issue_258_hook_arch.py` *heute* tun

- Fixture `fake_repo` legt nur `.claude/workflows/`-Layout an, **setzt weder ENV noch Session-Registry**.
- Helper `_set_active(repo, name)` legt nur den `.active`-Symlink an.
- Konsequenz: `read_active_workflow_fast()` (oder die Subprocess-Variante) findet keine ENV-Var → FATAL exit 1, weil der Symlink-Fallback aus ist.
- Zusätzlich: pytest-Subprocesses *erben* `GZ_ACTIVE_WORKFLOW` aus der laufenden Shell — was bei aktivem Workflow zu „set but no matching workflow file exists" FATAL führt, weil die `tmp_path`-Sandbox den Namen nicht kennt.

### Was die Tests *sollen*

Test-Setup-Pattern (neu):
- Workflow-File anlegen wie gehabt.
- Zusätzlich `monkeypatch.setenv("GZ_ACTIVE_WORKFLOW", name)` setzen (für In-Process-Tests).
- Für Subprocess-Tests: `env=os.environ \| {"GZ_ACTIVE_WORKFLOW": name, ...}` durchreichen UND `CLAUDE_CODE_SESSION_ID`/`GZ_HOOK_SESSION_ID` leeren, damit die Session-Registry den fake_repo-Workflow nicht überlagert.
- `_set_active()` kann bleiben, weil `cmd_start`/`cmd_complete` den Symlink weiterhin setzen/entfernen — er ist nur kein Fallback mehr.

### Tests, die unverändert grün laufen (Referenzpattern)

- `TestCmdCleanup` (5 Tests) — `cmd_cleanup` iteriert direkt über `_sweep_candidates()`, ruft kein `_active_name()`.
- `TestHotPathIntegration` (2 Tests) — prüft nur Source-Code via `inspect.getsource`/`read_text`.

## Dependencies

- **Upstream:** Tests prüfen Verhalten von `workflow.py` (`_active_name`, `read_active_workflow_fast`, `cmd_complete`, `cmd_cleanup`).
- **Downstream:** Keine. Nur Tests, kein Production-Code abhängig davon.

## Existing Specs

- `docs/specs/modules/issue_258_hook_arch_fix.md` — Original-Spec mit 14 ACs, die Tests waren der RED-Phasen-Beweis.
- `docs/specs/modules/issue_325_session_id_registry.md` (falls vorhanden) — Hintergrund zur Session-Registry, die Symlink-Pattern ersetzt hat.

## Risks & Considerations

1. **ENV-Var-Lecks zwischen Tests** — pytest erbt die laufende Shell-Umgebung. Wir müssen `monkeypatch.delenv("GZ_ACTIVE_WORKFLOW", raising=False)` in der `fake_repo`-Fixture aufnehmen, sonst kontaminiert ein aktiver Workflow den Test. Ebenso `CLAUDE_CODE_SESSION_ID`/`GZ_HOOK_SESSION_ID`.
2. **Subprocess-env** — `subprocess.run(..., env=...)` muss explizit gebaut werden, sonst erbt der Subprocess die kontaminierte Shell-Umgebung. Pattern: `env = {k: v for k, v in os.environ.items() if k not in ("GZ_ACTIVE_WORKFLOW", "CLAUDE_CODE_SESSION_ID", "GZ_HOOK_SESSION_ID")} | {"GZ_ACTIVE_WORKFLOW": name}`.
3. **`test_returns_none_when_active_symlink_dangling` (AC-3)** — heute erwartet Test `None`-Return bei dangling Symlink. Mit neuer Logik: ENV gesetzt + File fehlt → FATAL exit 1. Test muss umformuliert werden: „dangling state → klares FATAL statt None" (Verhalten ist *bewusst* strenger geworden).
4. **`test_complete_without_arg_removes_symlink` Sub-Lauf 2** — der zweite Sub-Lauf (`complete totally-unknown-wf`) erwartet die Issue-#258-Fehlermeldung. Das funktioniert heute schon: `cmd_complete(["totally-unknown-wf"])` returnt `ERROR: Workflow '...' not found` (Z. 919). Aber der ENV-Var-Leak (Subprocess erbt `GZ_ACTIVE_WORKFLOW=...` von Shell) ist der Show-Stopper.
5. **Keine Production-Änderungen nötig** — `workflow.py` ist korrekt, alle 14 ACs aus #258 sind in Production erfüllt. Nur die Tests testen das alte Pre-#258-Verhalten + treffen den neuen FATAL-Guard.
6. **Bewahrte Aussagekraft** — Tests sollen die *aktuelle* Production-Logik weiter scharf prüfen (insb. Symlink-Cleanup in `cmd_complete`, AC-7/AC-8 Warning-Verhalten), nicht nur „grün hinmogeln".

## Anti-Pattern (verboten)

- `.skip` oder `xfail` als Quick-Fix — Tests sollen das *neue* Verhalten verifizieren, nicht ignoriert werden.
- Tests komplett löschen — sie decken kritische Pfade (`cmd_complete` Sub-Cases) ab.
- Test-Code so umbauen, dass er nur noch die alte Codeline ausführt (z. B. `_set_active` weglassen und nur ENV setzen) — der Symlink-Lifecycle ist weiterhin Production-Code (cmd_start/cmd_complete setzen/entfernen ihn) und sollte verifiziert bleiben.

## Implementations-Strategie (Phase 2 Analyse)

### Schritte

1. **Fixture `fake_repo` härten** — `monkeypatch.delenv` für `GZ_ACTIVE_WORKFLOW`, `CLAUDE_CODE_SESSION_ID`, `GZ_HOOK_SESSION_ID` (`raising=False`), sodass Shell-Leaks die Tests nicht kontaminieren.

2. **Helper `_subprocess_env(active=None)`** — baut sauberes env-dict aus `os.environ` ohne die drei Session-Vars und setzt `GZ_ACTIVE_WORKFLOW` optional. Alle Subprocess-Tests nutzen `env=_subprocess_env(...)`.

3. **Helper `_activate(repo, name, monkeypatch)`** — Convenience-Wrapper: `_set_active(repo, name)` + `monkeypatch.setenv("GZ_ACTIVE_WORKFLOW", name)`. Für In-Process-Tests in `TestReadActiveWorkflowFast`.

4. **`TestReadActiveWorkflowFast` (4 Tests):**
   - `test_returns_none_when_no_active_symlink` — bleibt inhaltlich; Fixture-Hardening verhindert ENV-Leak.
   - `test_returns_name_and_data_when_active_exists` — `_set_active` → `_activate`.
   - `test_returns_none_when_active_symlink_dangling` — **inhaltlich umformulieren** auf „ENV gesetzt + JSON gelöscht → FATAL exit 1" via `pytest.raises(SystemExit)`. Umbenennen zu `test_fatal_when_env_workflow_missing`.
   - `test_no_filesystem_aggregation` — `_set_active` → `_activate`; `monkeypatch.setattr(Path, "glob", explode)` bleibt.

5. **`TestCmdCompleteOptionalName` (5 Tests):**
   - Jeder `subprocess.run(...)` bekommt `env=_subprocess_env(<aktiver Workflow im fake_repo>)`.
   - In `test_complete_without_arg_removes_symlink`: erster Sub-Run mit `env=_subprocess_env("wf-a")`, zweiter Sub-Run mit `env=_subprocess_env(None)` (kein aktiver Workflow, weil wf-a archiviert + Symlink weg — Code-Pfad geht über args-Branch direkt zu ERROR vor `_active_name()`).
   - Restliche 4 Tests: ENV jeweils auf den im Fixture aktiven Workflow setzen.

6. **Modul-Docstring updaten** — „RED-Pflicht" entfernen, durch „Regression-Guard für Symlink-Deaktivierung (Commit 59bd925)" ersetzen.

### Verzicht

- Keine `spec-writer`-Delegation — 70 LoC Test-Refresh, kein neues Verhalten.
- Keine Production-Änderungen — `workflow.py` ist korrekt.
- Kein neuer Helper außerhalb der Test-Datei.

### Scope

- 1 Datei: `tests/tdd/test_issue_258_hook_arch.py`
- ~70 LoC Netto (innerhalb 250-Limit)
- 0 Production-Files
