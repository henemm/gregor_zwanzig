---
entity_id: issue_655_telegram_callback_query_tests
type: tests
created: 2026-06-08
updated: 2026-06-08
status: implemented
version: "1.0"
tags: [tests, telegram, callback_query, navigation, epic-639, issue-655]
parent: issue_655_telegram_callback_query
phase: phase6_implementation
---

# Issue #655 — Telegram Hybrid-Navigation (Tests v1.0)

## Approval

- [x] Approved

## Purpose

Test-Manifest für Issue #655 (callback_query + editMessageText). Beweist aus
Nutzerperspektive: echter HTTP-POST gegen die reale FastAPI-App
(`/api/internal/telegram-webhook`) mit callback_query-Body; ausgehende Bot-API-Calls
an einem echten lokalen http.server-Socket beobachtet (Boundary-Capture via
`TELEGRAM_API_BASE`); echter `TripCommandProcessor`, echter Trip + Snapshot, echte
User-Auflösung. **Keine Mocks der Logik unter Test.**

Parent-Spec: `docs/specs/modules/issue_655_telegram_callback_query.md` v1.0

## Source

- **Files:**
  - `tests/tdd/test_issue_655_telegram_callback_query.py` (NEU — mock-frei)
- **Spec:** `docs/specs/modules/issue_655_telegram_callback_query.md` v1.0

## Test Inventory

| Test-Funktion | AC | Was geprüft wird |
|---------------|----|------------------|
| `ac1_tl_today_edits_message_to_timeline` | AC-1 | callback_query `tl_today` → editMessageText (gleiche chat_id+message_id) mit Timeline; reply_markup hat Zurück-Button (callback_data=glance); KEIN sendMessage. |
| `ac2_answer_callback_query_always_even_unknown` | AC-2 | Unbekanntes callback_data → answerCallbackQuery mit korrekter callback_query.id wird trotzdem aufgerufen; kein editMessageText. |
| `ac3_duplicate_callback_query_idempotent` | AC-3 | Identisches Update (gleiche update_id) zweimal → 1. status=ok, 2. status=duplicate; genau 1 editMessageText. |
| `ac4_drilldown_edits_with_back_to_timeline` | AC-4 | callback_query `dd_thunder_today` → editMessageText mit Drilldown; reply_markup hat Zurück-Button zur Timeline (callback_data=tl_today). |
| `ac5_multi_user_isolation_no_cross_leak` | AC-5 | Zwei echte Nutzer (alice chat=111, bob chat=222); Klick von alice → editMessageText an chat 111 mit alice's Trip-Name, niemals bob's; kein default-Fallback. |

## Expected RED-State (vor GREEN-Phase)

Alle Tests schlagen in Phase 5 fehl weil:
- `InboundTelegramReader._process_update` verarbeitet `callback_query` nicht (return False)
  → kein `_process_callback_query`, kein editMessageText/answerCallbackQuery.
- `TelegramOutput.edit_message_text` / `TelegramOutput.answer_callback_query` existieren nicht.
- Folge: der lokale Capture-Server empfängt keine editMessageText/answerCallbackQuery-Calls
  → Assertions schlagen fehl.

## Mock-Freiheit (CLAUDE.md)

- Echter HTTP-POST gegen reale `api.main.app` via TestClient.
- Ausgehende Telegram-Calls an echtem lokalen Socket (`http.server`) — kein Mock,
  nur Umlenkung des API-Hosts (`TELEGRAM_API_BASE`) = Boundary-Capture.
- AC-5: zwei echte `user.json`-Dateien + reale `lookup_user_by_telegram_chat_id`.
