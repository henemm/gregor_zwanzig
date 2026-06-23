---
entity_id: fix_853_842_837_tooling_gates
type: bugfix
created: 2026-06-23
updated: 2026-06-23
status: draft
version: "1.0"
tags: [tooling, hooks, workflow, gates, prod-selftest]
---

<!-- Issues #853, #842, #837 — Tooling-Gate Bundle -->

# Fix #853/#842/#837 — Tooling-Gate Bundle

## Approval

- [ ] Approved

## Purpose

Drei Tooling-Gate-Schwachstellen beseitigen: (1) das `override`-Keyword im UserPromptSubmit-Pfad als lokalen Fallback registrieren, damit es auch ohne Plugin funktioniert; (2) den prod_selftest Commit-Check von Strict-Equality auf Ancestor-Check umstellen, damit parallele Deploys nicht fälschlicherweise blockiert werden; (3) Issue #842 (Rebase-Check) als erledigt schließen — der Check existiert seit Commit `3020ff7` in `bash_gate.py`.

## Source

- **File:** `.claude/settings.json` (UserPromptSubmit-Fallback-Eintrag)
- **File:** `.claude/hooks/prod_selftest.py` (Ancestor-Check, Zeilen 425–445)
- **Identifier:** `prod_selftest.py::_run` (Commit-Attestation-Block)

## Estimated Scope

- **LoC:** ~23 (settings.json +8, prod_selftest.py +15)
- **Files:** 2
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `.claude/hooks/phase_listener.py` | intern | Wertet `override`-Keyword aus und schreibt Override-Token; wird neu in settings.json registriert |
| `subprocess` stdlib | stdlib | Bereits in `prod_selftest.py` importiert; wird für `git merge-base --is-ancestor` verwendet |
| `bash_gate.py` Plugin-Commit `3020ff7` | intern | Enthält Rebase-Check für Issue #842 — kein Code-Fix nötig |

## Implementation Details

### Fix #853 — UserPromptSubmit-Fallback in settings.json

Das Plugin (`/home/hem/agent-os-openspec`, Version 3.4.0) registriert `phase_listener.py` bereits über `hooks/hooks.json`. Das lokale `.claude/settings.json` hat jedoch keinen `UserPromptSubmit`-Eintrag. Falls das Plugin nicht geladen wird, bleibt das `override`-Keyword wirkungslos.

Lösung: Denselben Eintrag zusätzlich in `.claude/settings.json` registrieren. `phase_listener.py` ist idempotent — ein Doppelaufruf überschreibt das Token ohne Seiteneffekt.

Einfügen nach dem bestehenden `"PostToolUse"`-Block in `.claude/settings.json`:

```json
"UserPromptSubmit": [
  {
    "hooks": [
      {
        "type": "command",
        "command": "python3 \"${CLAUDE_PROJECT_DIR}/.claude/hooks/phase_listener.py\"",
        "timeout": 5
      }
    ]
  }
]
```

### Fix #837 — Ancestor-Check in prod_selftest.py

Aktuelle Zeilen ca. 430–441 (Strict-Equality-Block):

```python
head = _head_sha()
verified_commit = verified.get("verified_commit", "")

if head != verified_commit:
    _log(f"FAIL: Commit-Mismatch — HEAD={head[:8]} vs verified={verified_commit[:8]}", ...)
    _write_report(report_path, _render_fail_commit_mismatch(workflow, head, verified_commit))
    return 1
```

Bei parallelen Deploys pusht Session B nach Session A: HEAD ≠ verified_commit, obwohl der verifizierte Code korrekt im Ancestry von HEAD liegt. Das führt zu fälschlichem FAIL.

Ersatz durch Ancestor-Check:

```python
head = _head_sha()
verified_commit = verified.get("verified_commit", "")

if head != verified_commit:
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", verified_commit, head],
        cwd=str(_root), capture_output=True
    )
    if ancestor.returncode != 0:
        _log(f"FAIL: Commit-Mismatch — HEAD={head[:8]} vs verified={verified_commit[:8]}", ...)
        _write_report(report_path, _render_fail_commit_mismatch(workflow, head, verified_commit))
        return 1
    _log(f"PASS (Ancestor): verified_commit={verified_commit[:8]} ist Ancestor von HEAD={head[:8]}", ...)
```

`subprocess` ist in `prod_selftest.py` bereits importiert — kein neuer Import nötig.

### Issue #842 — Kein Code-Fix

`bash_gate.py` enthält den Rebase-Check (`git merge-base --is-ancestor`) bereits seit Commit `3020ff7`. Aktion: Issue schließen, kein Source-Code-Edit.

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `.claude/settings.json` | MODIFY | UserPromptSubmit-Block für phase_listener.py hinzufügen |
| `.claude/hooks/prod_selftest.py` | MODIFY | Strict-Equality durch Ancestor-Check ersetzen (Zeilen 425–445) |

### Estimated Changes

- Files: 2
- LoC: +23 / -6

## Acceptance Criteria

- **AC-1:** Given das Plugin `agent-os-openspec` ist nicht geladen / When der User das Keyword `override` tippt / Then schreibt der lokale UserPromptSubmit-Hook in settings.json einen gültigen Override-Token nach `.claude/user_override_token.json`

- **AC-2:** Given `e2e_verified.json` hat einen `verified_commit` der ein Ancestor von HEAD ist / When `prod_selftest.py` ausgeführt wird / Then ist der Exit-Code 0 und das Log enthält den Text `PASS (Ancestor)`

- **AC-3:** Given `e2e_verified.json` hat einen `verified_commit` der KEIN Ancestor von HEAD ist / When `prod_selftest.py` ausgeführt wird / Then ist der Exit-Code 1 und das Log enthält `FAIL: Commit-Mismatch`

- **AC-4:** Given ein aktiver Workflow und der Branch liegt mindestens 1 Commit hinter origin/main / When ein `git commit` Befehl ausgeführt wird / Then blockt `bash_gate.py` den Commit mit der Meldung `BLOCKED — Branch ist` und fordert zum Rebase auf

## Test Plan

| AC | Test | Kommando |
|----|------|----------|
| AC-1 | `phase_listener.py` direkt mit `override`-Input aufrufen, Token-Datei prüfen | `echo '{"message":"override"}' \| python3 .claude/hooks/phase_listener.py` |
| AC-2 | `prod_selftest.py` mit Ancestor-Commit als `verified_commit` testen | `python3 .claude/hooks/prod_selftest.py` (nach Vorbereitungs-Setup in Test) |
| AC-3 | `prod_selftest.py` mit Nicht-Ancestor-Commit testen → Exit 1 | Unit-Test mit mockem `e2e_verified.json` |
| AC-4 | `git commit` mit Branch hinter origin/main versuchen → Block prüfen | Manuell in Test-Worktree |

## Expected Behavior

- **Input:** `.claude/settings.json` ohne UserPromptSubmit-Eintrag; `prod_selftest.py` mit Strict-Equality-Commit-Check
- **Output:** `.claude/settings.json` enthält redundanten UserPromptSubmit-Hook als Plugin-Fallback; `prod_selftest.py` akzeptiert Ancestor-Commits als PASS
- **Side effects:** `phase_listener.py` läuft bei Plugin-Load ggf. zweimal (idempotent, kein Bug); `prod_selftest.py` loggt `PASS (Ancestor)` statt FAIL bei parallelen Deploys

## Known Limitations

- Der UserPromptSubmit-Doppeleintrag (Plugin + settings.json) erzeugt zwei Hook-Aufrufe pro Prompt wenn das Plugin geladen ist. `phase_listener.py` ist idempotent — kein funktionaler Unterschied, aber minimal erhöhte Hook-Latenz (~10ms, vernachlässigbar).
- Der Ancestor-Check via `git merge-base --is-ancestor` schlägt fehl wenn `.git` nicht erreichbar ist (z.B. außerhalb des Repos). `prod_selftest.py` läuft ausschließlich im Repo-Kontext — dieser Fall ist praktisch ausgeschlossen.

## Changelog

- 2026-06-23: Initial spec erstellt — Issues #853, #842, #837
