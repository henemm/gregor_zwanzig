---
entity_id: bug_332_approval_hook_session_id_tests
type: tests
created: 2026-05-22
updated: 2026-05-22
status: draft
version: "1.0"
tags: [tests, bugfix, workflow, tooling, hooks, session-registry, issue-332]
parent: bug_332_approval_hook_session_id
phase: phase5_tdd_red
---

# Bug #332 — Approval-Hook Session-Routing: Test-Manifest

## Approval

- [x] Approved

## Zweck

Test-Manifest für `docs/specs/modules/bug_332_approval_hook_session_id.md`.
Jeder pytest-Test mappt auf ein Acceptance Criterion der Parent-Spec und ruft
den echten `workflow_state_updater.py`-Hook via `subprocess.run` mit isoliertem
tmp-Repo auf. Keine Mocks.

Parent-Spec: `docs/specs/modules/bug_332_approval_hook_session_id.md` v1.0

## Source

- **File:** `tests/tdd/test_workflow_state_updater_session_routing.py` (NEU)

## Test Inventory

| Test-Funktion | AC | Was geprüft wird |
|---|---|---|
| `test_ac1_session_a_approval_only_advances_workflow_a` | AC-1 | Mit zwei registrierten Sessions A+B: `approved` aus `sid-a` schiebt nur Workflow A nach `phase4_approved`, B bleibt unverändert |
| `test_ac2_session_b_approval_only_advances_workflow_b` | AC-2 | Symmetrische Variante: `approved` aus `sid-b` schiebt nur Workflow B |
| `test_ac3_single_session_fallback_via_env_var` | AC-3 | Ohne `session_id`-Feld im Payload und ohne Registry-Eintrag: `GZ_ACTIVE_WORKFLOW`-Env-var als Fallback funktioniert weiterhin |
| `test_ac4_session_registry_wins_over_env_var` | AC-4 | Session-Registry hat Vorrang vor `GZ_ACTIVE_WORKFLOW`-Env-var (kein Verwechseln durch alte Env-Werte) |

## Test-Ausführung

```bash
# RED-Phase (vor Implementation — alle 4 Tests sollen FAIL sein)
uv run pytest tests/tdd/test_workflow_state_updater_session_routing.py -v

# GREEN-Phase (nach Implementation — alle 4 PASS)
uv run pytest tests/tdd/test_workflow_state_updater_session_routing.py -v
```

## Expected RED-State (vor GREEN-Phase)

| Test | Erwartetes Ergebnis | Grund |
|------|---------------------|-------|
| `test_ac1_session_a_approval_only_advances_workflow_a` | FAIL | Hook ignoriert `session_id`, fällt auf zuletzt-aktiven Workflow zurück |
| `test_ac2_session_b_approval_only_advances_workflow_b` | FAIL | Gleiches Symptom, symmetrisch |
| `test_ac3_single_session_fallback_via_env_var` | PASS oder FAIL | Single-Session-Fallback funktioniert evtl. zufällig — soll im GREEN-Lauf garantiert passen |
| `test_ac4_session_registry_wins_over_env_var` | FAIL | Hook respektiert die Registry nicht; Env-var-Decoy gewinnt fälschlich |

Mindestens 3 von 4 Tests müssen FAIL liefern — das ist der RED-Beweis.

## Test-Design-Hinweise

- **Isoliertes Test-Repo:** Jeder Test setzt `tmp_path` mit `.git/`-Marker und `.claude/workflows/`-Subdir auf. Hook arbeitet via `cwd=str(tmp_path)` gegen dieses isolierte Repo, nicht gegen das echte Production-Repo.
- **Subprocess-Aufruf:** Hook wird via `subprocess.run([sys.executable, HOOK_PATH], input=json.dumps(payload), env=env, cwd=tmp_path)` aufgerufen — das ist das gleiche Aufruf-Muster wie in Claude-Code selbst (stdin-JSON-Payload).
- **Env-Scrubbing:** Pro Test werden `GZ_ACTIVE_WORKFLOW`, `GZ_HOOK_SESSION_ID`, `CLAUDE_CODE_SESSION_ID`, `CLAUDE_USER_PROMPT`, `CLAUDE_TOOL_INPUT` aus der Host-Env entfernt, damit der Host-Workflow-State nicht ins Test-Environment leakt.

## Changelog

- 2026-05-22: Initial test manifest erstellt für Bug #332 (Approval-Hook Session-Routing).
