---
entity_id: issue_381_guard_message_tests
type: tests
created: 2026-05-25
updated: 2026-05-25
status: draft
version: "1.0"
tags: [tests, hooks, infrastructure, session, worktree, dx]
parent: issue_381_guard_message
phase: phase5_tdd_red
---

# Issue 381 — Selbsterklärende Block-Meldung (Tests)

## Approval

- [x] Approved

## Purpose

Test-Manifest für `docs/specs/modules/issue_381_guard_message.md`. Der Test prüft
1:1 die Acceptance Criteria der Parent-Spec (AC-1 + AC-2).

Parent-Spec: `docs/specs/modules/issue_381_guard_message.md` v1.0

## Source

- **File:** `tests/tdd/test_session_singleton_guard.py` (Ergänzung) — KEINE Mocks.
  Der Test fährt den echten Hook als Subprozess (`_run_hook`) mit echten
  temporären Registry-Einträgen (`tmp_path`, `_write_entry`) und liest die echte
  Block-Meldung von stderr.

## Test Inventory

| Test-Funktion | AC | Was geprüft wird |
|---|---|---|
| `test_issue381_block_message_directs_direct_enterworktree` | AC-1, AC-2 | Block-Meldung einer geblockten Zweit-Sitzung enthält den Hinweis, `EnterWorktree` **direkt** aufzurufen (`direkt`) und KEINEN `ToolSearch`-Vorlauf zu versuchen (`toolsearch`). Bestehende Garantien bleiben grün: `enterworktree` + `gz-workspace` weiterhin genannt, keine `<`/`>`-Platzhalter (F002). Exit-Code bleibt 2. |

## Known Limitations

- Prüft den Wortlaut der Meldung, nicht den darunterliegenden Harness-Umstand,
  dass `EnterWorktree` ein deferred tool ist (siehe Parent-Spec „Known Limitations").

## Changelog

- 2026-05-25: Initial test manifest (Issue #381)
