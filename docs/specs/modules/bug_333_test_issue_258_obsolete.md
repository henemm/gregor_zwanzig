---
entity_id: bug_333_test_issue_258_obsolete
type: bugfix
created: 2026-05-22
updated: 2026-05-22
status: draft
version: "1.0"
tags: [bugfix, tests, workflow, hooks, session-registry, symlink-deprecation, issue-333]
---

<!-- Issue #333 — Bug: tests/tdd/test_issue_258_hook_arch.py veraltet nach Symlink-Fallback-Deaktivierung -->

# Issue #333 — Bug-Fix: Tests an neue Hook-Architektur anpassen

## Approval

- [ ] Approved

## Zweck

`tests/tdd/test_issue_258_hook_arch.py` enthält 9 rote Tests, die das **alte** Symlink-basierte Verhalten von `workflow.py:_active_name()` prüfen. Commit `59bd925` (2026-05-22) hat den Symlink-Fallback bewusst deaktiviert — Production-Code ist korrekt, nur die Tests sind veraltet. Der Fix aktualisiert das Test-Setup auf die neue dreistufige Resolution-Reihenfolge (Session-Registry → `GZ_ACTIVE_WORKFLOW` → FATAL) und entfernt den ENV-Leak, der die Subprocess-Tests heute zusätzlich vergiftet. Production-Code wird **nicht** angefasst.

## Quelle / Source

**Geänderte Dateien:**
- `tests/tdd/test_issue_258_hook_arch.py` — Fixture-Hardening (delenv für drei Session-Vars), zwei neue Helper (`_subprocess_env`, `_activate`), 9 Test-Bodies angepasst, 1 Test inhaltlich umformuliert (AC-3-Drift), Modul-Docstring aktualisiert.

> **Schicht-Hinweis:** Reine Test-Schicht (`tests/tdd/`). Kein Frontend-, Go-API- oder Python-Backend-Code betroffen. Auch `workflow.py` selbst bleibt unangetastet — die getestete Architektur (`read_active_workflow_fast`, `_active_name`, `cmd_complete`, `cmd_cleanup`) ist in Production bereits seit Issue #258 + #325 etabliert.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `tests/tdd/test_issue_258_hook_arch.py` | Pytest-Modul | Die zu aktualisierende Test-Datei (17 Tests, 9 rot) |
| `.claude/hooks/workflow.py` | Python-Modul (read-only) | Liefert `_active_name()` mit Session-Registry → ENV → FATAL-Logik (workflow.py:328–385); `read_active_workflow_fast()` (Z. 402–411); `cmd_complete` (Z. 913–950) |
| `.claude/session_workflows.json` | JSON-Registry (read-only) | Mapping `session_id` → `workflow_name`; in fake_repo nicht relevant, weil Fixture die drei Session-Env-Vars `delenv`t |
| Commit `59bd925` | Git-Commit | Hat den Symlink-Fallback deaktiviert — Grund für den Test-Drift |

## Implementation Details

### 1. Fixture `fake_repo` — Session-Env-Vars isolieren

Aktuell (Z. 62–74):

```python
@pytest.fixture
def fake_repo(tmp_path, monkeypatch, hooks_on_path):
    repo = tmp_path / "repo"
    (repo / ".claude" / "workflows" / "_archive").mkdir(parents=True)
    (repo / ".claude" / "workflows" / "_log").mkdir(parents=True)
    subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
    monkeypatch.chdir(repo)
    return repo
```

Wird ergänzt um:

```python
@pytest.fixture
def fake_repo(tmp_path, monkeypatch, hooks_on_path):
    # Isolation gegen Shell-Leaks aus laufenden Workflows (Issue #333):
    # Drei Session-Vars müssen explizit aus der Test-Env verschwinden,
    # sonst sieht der subprocess-aufgerufene workflow.py die kontaminierten
    # Werte und triggert FATAL "set but no matching workflow file exists".
    for var in ("GZ_ACTIVE_WORKFLOW", "CLAUDE_CODE_SESSION_ID", "GZ_HOOK_SESSION_ID"):
        monkeypatch.delenv(var, raising=False)
    repo = tmp_path / "repo"
    # ... rest unchanged ...
```

### 2. Neuer Helper `_subprocess_env(active=None)`

```python
def _subprocess_env(active: str | None = None) -> dict:
    """Sauberes env-dict für subprocess-Aufrufe: keine Session-Leaks aus Shell.

    Optional setzt es GZ_ACTIVE_WORKFLOW auf einen im fake_repo existierenden
    Workflow, damit _active_name() im Subprocess auflöst statt FATAL zu triggern.
    """
    env = {k: v for k, v in os.environ.items()
           if k not in ("GZ_ACTIVE_WORKFLOW", "CLAUDE_CODE_SESSION_ID",
                        "GZ_HOOK_SESSION_ID")}
    if active is not None:
        env["GZ_ACTIVE_WORKFLOW"] = active
    return env
```

### 3. Neuer Helper `_activate(repo, name, monkeypatch)`

```python
def _activate(repo: Path, name: str, monkeypatch) -> None:
    """Markiere `name` als aktiven Workflow für In-Process-Tests.

    Setzt sowohl den (legacy) .active-Symlink als auch die heute autoritative
    Env-Var GZ_ACTIVE_WORKFLOW. Der Symlink bleibt, weil cmd_start/cmd_complete
    ihn in Production weiter pflegen — er ist nur kein Fallback mehr."""
    _set_active(repo, name)
    monkeypatch.setenv("GZ_ACTIVE_WORKFLOW", name)
```

### 4. Tests in `TestReadActiveWorkflowFast` (4 Tests)

- `test_returns_none_when_no_active_symlink` — bleibt **inhaltlich**. Fixture-Hardening sorgt dafür, dass kein ENV-Leak die Erwartung „result is None" stört. (Symlink wird in diesem Test gar nicht gesetzt; Funktion muss `None` returnen, wenn weder Registry noch ENV noch Symlink etwas zeigen.)

- `test_returns_name_and_data_when_active_exists` — ersetze `_set_active(fake_repo, name)` durch `_activate(fake_repo, name, monkeypatch)`. Rest unverändert. Erwartet weiterhin `(name, data)`-Tuple.

- `test_returns_none_when_active_symlink_dangling` — **inhaltlich umformuliert** zu `test_fatal_when_env_workflow_file_missing` (AC-3 Verhaltens-Drift):
  - Setup: `_create_workflow(repo, "ghost")`, `monkeypatch.setenv("GZ_ACTIVE_WORKFLOW", "ghost")`, dann `wf_path.unlink()` (JSON gelöscht, ENV zeigt weiterhin auf „ghost").
  - Erwartung: `pytest.raises(SystemExit)` beim Aufruf von `read_active_workflow_fast()`, capsys-stderr enthält `"FATAL"` und `"ghost"`.
  - Begründung im Docstring: „Symlink-Fallback ist deaktiviert (Commit 59bd925) — dangling state führt jetzt zu einem klaren FATAL exit 1 statt zu None. Dieser Test verifiziert die strengere Fail-Loud-Semantik."

- `test_no_filesystem_aggregation` — ersetze `_set_active` durch `_activate`; `monkeypatch.setattr(Path, "glob", explode_on_glob)` bleibt unverändert. Erwartet weiter `(name, data)` ohne `glob`-Aufruf.

### 5. Tests in `TestCmdCompleteOptionalName` (5 Tests)

Jeder `subprocess.run([...workflow.py, "complete", ...], ...)` wird auf:

```python
subprocess.run(
    [sys.executable, str(HOOKS_DIR / "workflow.py"), "complete", ...],
    capture_output=True, text=True, cwd=str(fake_repo),
    env=_subprocess_env(<aktiver Workflow im fake_repo, oder None>),
)
```

umgestellt. Konkret:

- `test_complete_without_arg_removes_symlink`:
  - 1. Sub-Run (`complete` ohne Arg): `env=_subprocess_env("wf-a")` (wf-a muss als aktiv aufgelöst werden).
  - 2. Sub-Run (`complete totally-unknown-wf`): `env=_subprocess_env(None)` (keine aktiv-ENV nötig, weil Code-Pfad über `_workflow_file(name).exists()` direkt zu `"ERROR: Workflow 'totally-unknown-wf' not found"` führt, ohne `_active_name()` zu treffen).

- `test_complete_with_active_name_removes_symlink`: `env=_subprocess_env("wf-dummy-active")`. Test verifiziert weiterhin, dass `complete wf-b` exit 0, `wf-b` archiviert, `.active` zeigt unverändert auf `wf-dummy-active`.

- `test_complete_with_other_name_keeps_symlink`: `env=_subprocess_env("wf-active")`.

- `test_complete_with_other_name_prints_warning`: `env=_subprocess_env("wf-active")`. Verifiziert weiterhin den WARN-Banner mit beiden Workflow-Namen.

- `test_complete_archives_workflow_json`: `env=_subprocess_env("wf-other-active")`. Verifiziert weiterhin Archive-Move + Sanity (aktiver Workflow nicht angefasst).

### 6. Modul-Docstring + Klassen-Docstrings

Aktuell (Z. 14–24):

```python
"""TDD-RED: Issue #258 — Hook-Architektur Fast-Path-Reader + cmd_cleanup.

ALLE Tests MÜSSEN aktuell FEHLSCHLAGEN, da:
- `read_active_workflow_fast()` in `workflow.py` noch nicht existiert
- ...
"""
```

Wird umformuliert zu:

```python
"""Regression-Guard: Issue #258 Hook-Architektur (Fast-Path + cmd_cleanup).

Spec:    docs/specs/modules/issue_258_hook_arch_fix.md (Original-Spec, #258)
Update:  docs/specs/modules/bug_333_test_issue_258_obsolete.md (Test-Refresh, #333)
Issue:   https://github.com/henemm/gregor_zwanzig/issues/258

Tests gegen 14 Acceptance Criteria, gruppiert in 4 Test-Klassen:

- TestReadActiveWorkflowFast    (AC-1, AC-2, AC-3)         — 4 Tests
- TestCmdCompleteOptionalName   (AC-6, AC-7, AC-8, AC-9)   — 6 Tests
- TestCmdCleanup                (AC-10 … AC-13)            — 5 Tests
- TestHotPathIntegration        (AC-4, AC-5)               — 2 Tests

Update 2026-05-22 (#333): Commit 59bd925 hat den Symlink-Fallback in
_active_name() deaktiviert — Tests setzen seitdem zusätzlich
GZ_ACTIVE_WORKFLOW (in-process via _activate(), subprocess via
_subprocess_env()). Test AC-3 wurde von "dangling → None" auf
"dangling/missing → FATAL exit 1" umformuliert (Verhaltens-Drift,
nicht Setup-Anpassung). Production-Code unverändert.

Keine Mocks (CLAUDE.md-Regel), echte Filesystem-Operationen via tmp_path,
echte subprocess-Calls für CLI-Tests.
"""
```

### 7. LoC-Budget

| Datei | Δ LoC | Zählt |
|-------|--------|-------|
| `tests/tdd/test_issue_258_hook_arch.py` | +~80 / -~30 = netto +~50 | ja |
| **Gesamt** | **~80 LoC bewegt, ~50 netto** | **< 250 LoC-Limit** |

## Expected Behavior

- **Input:** `uv run pytest tests/tdd/test_issue_258_hook_arch.py -v` ohne externe ENV-Vars **oder** mit beliebig gesetztem `GZ_ACTIVE_WORKFLOW=<irgendetwas>` aus der laufenden Shell.
- **Output:** Alle 17 Tests grün. Insbesondere die heutigen 9 roten Tests (4× `TestReadActiveWorkflowFast`, 5× `TestCmdCompleteOptionalName`) verifizieren jetzt die aktuelle Production-Logik statt der vor-#258 Symlink-Fallback-Logik.
- **Side effects:** Tests verändern weiterhin nur `tmp_path`-Verzeichnisse; Fixture isoliert Shell-Env-Leaks via `monkeypatch.delenv`.

## Acceptance Criteria

- **AC-1:** Given der aktive Workflow `bug_333_test_issue_258_obsolete` läuft (`GZ_ACTIVE_WORKFLOW` ist in der laufenden Shell gesetzt) / When `uv run pytest tests/tdd/test_issue_258_hook_arch.py -v` ausgeführt wird / Then sind alle 17 Tests grün (insbesondere die heutigen 9 Failures aus `TestReadActiveWorkflowFast` und `TestCmdCompleteOptionalName`)
  - Test: (populated after /4-tdd-red)

- **AC-2:** Given die Fixture `fake_repo` / When sie verwendet wird / Then sind `GZ_ACTIVE_WORKFLOW`, `CLAUDE_CODE_SESSION_ID` und `GZ_HOOK_SESSION_ID` im Test-Prozess garantiert nicht gesetzt (auch wenn die aufrufende Shell sie kontaminiert hat)
  - Test: (populated after /4-tdd-red)

- **AC-3:** Given ein Workflow `ghost` in der fake_repo-Sandbox, `GZ_ACTIVE_WORKFLOW=ghost` gesetzt, JSON-Datei nachträglich gelöscht / When `read_active_workflow_fast()` aufgerufen wird / Then triggert `_active_name()` ein `SystemExit(1)` mit `"FATAL"` und `"ghost"` auf stderr (dokumentiert den bewussten Verhaltens-Shift in #59bd925: dangling state → FATAL statt None)
  - Test: (populated after /4-tdd-red)

- **AC-4:** Given die fünf Subprocess-Tests in `TestCmdCompleteOptionalName` / When sie via `subprocess.run(..., env=_subprocess_env(<aktiver Workflow>))` ausgeführt werden / Then schlägt kein Test mehr mit `"set but no matching workflow file exists"` fehl (ENV-Leak aus laufender Shell ist isoliert)
  - Test: (populated after /4-tdd-red)

- **AC-5:** Given die Tests in `TestCmdCleanup` (5 Tests) und `TestHotPathIntegration` (2 Tests) waren bereits grün / When der Fix angewendet wird / Then bleiben sie grün — kein Regressions-Schaden an den 7 funktionierenden Tests
  - Test: (populated after /4-tdd-red)

- **AC-6:** Given `.claude/hooks/workflow.py` (Production-Code) / When der Fix angewendet wird / Then ist die Datei zeichengleich zur Pre-Fix-Version (`git diff .claude/hooks/workflow.py` ist leer) — der Fix beschränkt sich strikt auf die Test-Schicht
  - Test: (populated after /4-tdd-red)

## Known Limitations

- **Inhaltlicher Verhaltens-Shift bei AC-3:** Der Test verifiziert nicht mehr „dangling Symlink → graceful None", sondern „dangling/missing JSON bei gesetzter ENV → FATAL exit 1". Das ist die bewusste Production-Semantik seit Commit 59bd925 und wird im Test-Docstring + im Spec-Changelog dokumentiert.
- **Symlink-Lifecycle wird weiterhin getestet:** Auch wenn der Symlink kein Fallback mehr ist, pflegen `cmd_start` und `cmd_complete` ihn weiter. Die Assertions auf `.active.is_symlink()` und `.active.unlink()`-Verhalten bleiben deshalb in den Tests erhalten — sie verifizieren den Lifecycle, nicht die Resolution.

## Out of Scope

- Änderungen an `workflow.py:_active_name()`, `read_active_workflow_fast()`, `cmd_complete` oder `cmd_cleanup` (alle korrekt seit #258/#325)
- Erweiterung der `_subprocess_env` / `_activate` Helper außerhalb dieser Test-Datei (bei Bedarf später dedupliziert)
- Symlink-Cleanup-Migration (separate Aufräumarbeit; der Symlink ist deprecated-but-living)
- Migration der Tests von subprocess-Style auf In-Process-Imports (Subprocess-Style ist näher am echten Hook-Verhalten und bleibt)

## Changelog

- 2026-05-22: Initial spec erstellt. Behebt Test-Drift in `tests/tdd/test_issue_258_hook_arch.py` (9 von 17 Tests rot) nach Symlink-Fallback-Deaktivierung in Commit 59bd925. 1 Test-Datei, ~50 LoC netto, kein Production-Code.
