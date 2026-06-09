---
entity_id: issue_671_bot_menu_autoset_tests
type: tests
created: 2026-06-09
updated: 2026-06-09
status: draft
version: "1.0"
tags: [tests, telegram, bot-menu, startup, e2e, issue-671]
parent: issue_671_bot_menu_autoset
phase: phase5_tdd_red
---

# Issue #671 — Bot-Menü Auto-Set + Live-E2E (Tests v1.0)

## Approval

- [x] Approved (2026-06-09, PO — „go, mit echtem Live-E2E gegen den Bot")

## Purpose

Test-Manifest für die echte Behebung von #671. Beweist mock-frei: (1) der
FastAPI-Startup setzt das Bot-Menü idempotent aus `BOT_COMMANDS` (am echten
http.server-Socket erfasst), (2) fail-soft ohne Bot-Token, (3) ein echter
Live-E2E gegen die Telegram-Bot-API (`setMyCommands`→`getMyCommands`, gated),
(4) `prod_selftest.check_bot_menu` fängt eine Menü-Regression im Deploy-Gate.

Parent-Spec: `docs/specs/modules/issue_671_bot_menu_autoset.md` v1.0

## Source

- **Files:**
  - `tests/tdd/test_issue_671_bot_menu_autoset.py` (NEU — mock-frei)
- **Spec:** `docs/specs/modules/issue_671_bot_menu_autoset.md` v1.0

## Test Inventory

| Test-Funktion | AC | Was geprüft wird |
|---------------|----|------------------|
| `ac1_startup_sets_bot_menu_from_bot_commands` | AC-1 | FastAPI-Startup (Lifespan, Token gesetzt) → genau ein setMyCommands-Call mit commands == BOT_COMMANDS, am echten Socket erfasst. |
| `ac2_no_token_no_call_no_crash` | AC-2 | Startup-Helper mit leerem Token (chat_id gesetzt) → kein setMyCommands, keine Exception (fail-soft). |
| `ac2_token_without_chatid_still_sets_menu` | AC-2 | Gegenprobe: Token gesetzt, chat_id leer → Menü wird trotzdem gesetzt (nur Token zählt). |
| `ac3_live_set_then_get_matches_bot_commands` | AC-3 | Echter Live-E2E (gated GZ_TELEGRAM_BOT_TOKEN): set_my_commands → get_my_commands == BOT_COMMANDS (gleiche Namen/Reihenfolge). |
| `ac4_selftest_check_bot_menu_pass_fail_skip` | AC-4 | `prod_selftest.check_bot_menu` → PASS bei Live-Match, FAIL bei Abweichung (alter briefing/wetter-Stand), SKIPPED ohne Token. |

## Expected RED-State (vor GREEN-Phase)

- **AC-1** rot: `api/main.py` hat keinen Lifespan-/Startup-Hook → kein setMyCommands
  beim Start → `len(sets) == 0 != 1`.
- **AC-2** rot: `api.main._init_telegram_bot_menu` existiert nicht → ImportError.
- **AC-4** rot: `prod_selftest.check_bot_menu` existiert nicht → `hasattr` False.
- **AC-3** läuft nur gated (Staging-Token in der Validierungsphase); ohne Token skip.

## Changelog

- 2026-06-09: Initial test manifest (Issue #671 echte Behebung).
