---
entity_id: session_singleton_guard_tests
type: tests
created: 2026-05-25
updated: 2026-05-25
status: draft
version: "1.0"
tags: [tests, hooks, infrastructure, workflow, session-isolation]
parent: session_singleton_guard
phase: phase5_tdd_red
---

# Session-Singleton-Guard (Tests)

## Approval

- [x] Approved

## Purpose

Test-Manifest fuer den Session-Singleton-Waechter aus
`docs/specs/modules/session_singleton_guard.md`. Jeder pytest-Test mappt 1:1 auf
ein Acceptance Criterion (AC-1..AC-7) der Parent-Spec.

Parent-Spec: `docs/specs/modules/session_singleton_guard.md` v1.0

## Source

- **File:** `tests/tdd/test_session_singleton_guard.py` (NEU) — echte
  tmpdir-basierte Tests. Der reale Hook wird als Subprozess aufgerufen
  (`subprocess.run([sys.executable, hook_path, "guard"], ...)`), Registry-Dateien
  werden mit echten Werten vorab geschrieben. KEINE Mocks.

## Test Inventory

| Test-Funktion | AC | Was geprueft wird |
|---|---|---|
| `test_ac1_sole_owner_allowed` | AC-1 | Sitzung A registriert sich und schickt einen Tool-Aufruf ueber `guard` -> exit 0 (alleiniger Inhaber). |
| `test_ac2_younger_session_blocked` | AC-2 | Aelterer lebender Inhaber A vorhanden; juengere Sitzung B sendet Edit-Aufruf -> exit 2 mit deutscher gz-workspace-Anleitung. |
| `test_ac3_rescue_path_pure_allowed` | AC-3 | Blockierte Sitzung B schickt einen reinen `gz-workspace`-Bash-Aufruf -> exit 0 (Rettungsweg offen). |
| `test_ac3_rescue_path_chained_blocked` | AC-3 | Verkettetes Kommando (`gz-workspace ... ; rm ...`) bleibt blockiert -> exit 2. |
| `test_ac4_different_repos_both_allowed` | AC-4 | Zwei Sitzungen in verschiedenen git-Toplevels -> beide exit 0 (kein Repo-uebergreifender Block). |
| `test_ac5_no_own_entry_allowed` | AC-5 | Sitzung ohne eigenen Registry-Eintrag (Bestands-Sitzung) -> immer exit 0. |
| `test_ac6_failsafe_broken_input_allowed` | AC-6 | Leerer Payload, kaputtes JSON, fehlendes/leeres cwd -> exit 0, kein Traceback nach aussen (Fail-safe, parametrisiert). |
| `test_ac7_dead_owner_reaped` | AC-7 | Toter Inhaber A (PID nicht in /proc und last_seen aelter als STALE_SECONDS) -> verbliebene Sitzung B wird Inhaber (exit 0), A's Eintrag aufgeraeumt. |

### Adversary-Regressionen (F001–F003)

| Test-Funktion | Finding | Was geprueft wird |
|---|---|---|
| `test_f001_reregister_preserves_ownership` | F001 | Re-Register (z.B. nach /clear) bewahrt `started_at` des rechtmaessigen Inhabers; A bleibt Inhaber (exit 0), B bleibt blockiert (exit 2) — keine Selbst-Aussperrung. |
| `test_f002_block_message_command_is_allowed` | F002 | Das in der Block-Meldung vorgeschlagene Rettungs-Kommando (`bash .claude/tools/gz-workspace new mein-feature`) liefert bei einer Nicht-Inhaber-Sitzung exit 0; die Meldung enthaelt keine spitzen Klammern `<`/`>`. |
| `test_f003_session_id_path_traversal_contained` | F003 | Eine `../`-haltige session_id wird vor der Pfadbildung sanitisiert (register UND guard gleich), bleibt INNERHALB des Hash-Unterordners; dieselbe Sitzung findet sich als Inhaber (exit 0), eine zweite wird blockiert (exit 2). |

## Implementation Details

Tests folgen dem No-Mocks-Pattern des Projekts:
- Echter Hook-Aufruf als Subprozess (`sys.executable` + Hook-Pfad + Modus).
- Pro Test ein echtes `git init` unter `tmp_path`, damit
  `git rev-parse --show-toplevel` die Repo-Wurzel aufloest.
- Ownership/Zeit wird ueber vorab geschriebene Registry-Dateien gesteuert
  (`started_at`, `last_seen`, `pid`), nicht ueber Mocks.
- `GZ_SESSION_STALE_SECONDS` wird per Subprozess-`env` gesetzt, wo noetig.
- Keine `Mock()`, `patch()`, `MagicMock`.

In der RED-Phase schlagen alle Tests fehl, weil
`.claude/hooks/session_singleton_guard.py` noch nicht existiert (Subprozess
liefert non-zero / "No such file").

## Expected Behavior

- **Input:** stdin-Payload (`session_id`, `cwd`, `tool_name`, `tool_input`) je Test.
- **Output:** Assertions ueber den Subprozess-`returncode` (0=erlaubt, 2=blockiert)
  sowie die deutsche stderr-Meldung im Block-Fall.
- **Side effects:** Anlegen/Aktualisieren/Aufraeumen von Registry-Dateien
  ausschliesslich unter `tmp_path/.claude/.session-locks/`.

## Acceptance Criteria

- **AC-T1:** Given die Test-Datei existiert und der Hook fehlt /
  When `pytest tests/tdd/test_session_singleton_guard.py -v` laeuft /
  Then schlagen alle Tests fehl (RED-Phase erfolgreich).

- **AC-T2:** Given GREEN-Phase abgeschlossen /
  When `pytest tests/tdd/test_session_singleton_guard.py -v` ausgefuehrt /
  Then sind alle Tests gruen, ohne Mocks.

## Known Limitations

- PID-Liveness nutzt `/proc` (Linux); die Tests laufen in der Ubuntu-Server-Umgebung.
- AC-2/AC-3/AC-7 verwenden `os.getpid()` als garantiert lebende PID und eine
  rueckwaerts gesuchte freie PID als garantiert tote PID.

## Changelog

- 2026-05-25: Initial — Test-Manifest fuer Session-Singleton-Guard (AC-1..AC-7).
