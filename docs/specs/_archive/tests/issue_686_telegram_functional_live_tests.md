---
entity_id: issue_686_telegram_functional_live_tests_tests
type: tests
created: 2026-06-09
updated: 2026-06-09
status: draft
version: "1.0"
tags: [tests, telegram, e2e, live-test, fixture, issue-686]
parent: issue_686_telegram_functional_live_tests
phase: phase5_tdd_red
---

# Issue #686 — Funktionale Telegram-Live-Tests (Tests v1.0)

## Approval

- [x] Approved (2026-06-09, PO — „go")

## Purpose

Test-Manifest für #686. Beweist mock-frei: (1) der Fixture-Helper stellt idempotent
einen Staging-Test-User mit aktivem Trip sicher, (2) `send()` liefert die `message_id`,
(3) jeder der 7 Menü-Befehle erzeugt sinnvollen Inhalt, (4) jede Antwort wird real
zugestellt + wieder gelöscht, (5) `/e2e-verify` blockt bei übersprungenem Telegram-Live-Test.

Parent-Spec: `docs/specs/modules/issue_686_telegram_functional_live_tests.md` v1.0

## Source

- **Files:**
  - `tests/tdd/test_issue_686_telegram_functional_live.py` (NEU — mock-frei)
  - `tests/tdd/_telegram_live_fixture.py` (NEU — Fixture-Helper)
- **Spec:** `docs/specs/modules/issue_686_telegram_functional_live_tests.md` v1.0

## Test Inventory

| Test-Funktion | AC | Was geprüft wird |
|---------------|----|------------------|
| `ac1_fixture_ensures_user_with_active_trip` | AC-1 | Fixture-Helper legt in tmp-data_dir einen User mit `telegram_chat_id == GZ_TELEGRAM_TEST_CHAT_ID` + aktivem Trip an; `lookup_user_by_telegram_chat_id` findet ihn, `_find_active_trip` ≠ None; zweiter Aufruf idempotent. |
| `ac2_send_returns_message_id` | AC-2 | `TelegramOutput.send` gegen lokalen Socket (liefert message_id) gibt die int-`message_id` zurück, nicht None; Fehler-Status → None. |
| `ac3_all_seven_commands_produce_meaningful_content` | AC-3 | Für alle 7 Befehle: echte Pipeline gegen Fixture → `confirmation_body` nicht leer, kein „Unbekannter Befehl", kein „Kein aktiver Trip". |
| `ac4_live_delivery_and_cleanup` | AC-4 | Gated (Token+Test-Chat-ID): jede der 7 Antworten real an Test-Chat gesendet → message_id ≠ None → `delete_message` ok=True. Echte Telegram-API. |
| `ac5_e2e_verify_blocks_on_skipped_telegram` | AC-5 | `e2e_telegram_live.py`: Telegram-Scope ohne Test-Chat-ID → Exit ≠ 0 (Nicht-bestanden), nicht stilles SKIPPED-als-grün. |
| `ac5_write_verdict_blocks_telegram_scope_without_chat_id` | AC-5 | Echtes Close-Gate: `staging_gate.write_verdict` gegen ein echtes tmp-git-Repo mit Telegram-Commit (HEAD~1..HEAD) → OHNE `GZ_TELEGRAM_TEST_CHAT_ID` Rückgabe 1 UND kein `out.json` (Verdict verweigert); MIT Test-Chat-ID Rückgabe 0 UND `out.json` geschrieben. Mock-frei (echtes git, monkeypatch nur ENV + REPO_DIR). |

## Expected RED-State (vor GREEN-Phase)

- **AC-1/AC-3** rot: `tests/tdd/_telegram_live_fixture.py` existiert nicht → ImportError.
- **AC-2** rot: `send()` gibt aktuell `None` zurück → `assert mid is not None` schlägt fehl.
- **AC-4** rot/gated: ohne Token+Chat-ID SKIPPED; mit gesetzter Umgebung in der
  Validierungsphase MUSS er real laufen (kein stilles Skip — AC-5 erzwingt das).
- **AC-5** rot: `.claude/hooks/e2e_telegram_live.py` existiert nicht → ImportError/fehlt.

## Changelog

- 2026-06-09: Initial test manifest (Issue #686).
- 2026-06-09: AC-5 um echten Close-Gate-Test ergänzt (`ac5_write_verdict_blocks_telegram_scope_without_chat_id`) — beweist mock-frei, dass `staging_gate.write_verdict` bei Telegram-Scope ohne Test-Chat-ID das Verdict verweigert.
