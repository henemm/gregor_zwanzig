---
entity_id: issue_672_telegram_e2e_pipeline_tests
type: tests
created: 2026-06-08
updated: 2026-06-08
status: implemented
version: "1.0"
tags: [tests, telegram, e2e, pipeline, epic-639, issue-672]
parent: issue_672_telegram_e2e_pipeline
phase: phase6_implementation
---

# Issue #672 — Telegram E2E-Pipeline-Tests (Tests v1.0)

## Approval

- [x] Approved (2026-06-08, PO)

## Purpose

Test-Manifest für Issue #672 (E2E-Pipeline-Tests + Fix #671). Beweist aus
Nutzerperspektive: echter HTTP-POST gegen die reale FastAPI-App
(`/api/internal/telegram-webhook`) mit Text-Message-Body; ausgehende Bot-API-Calls
an einem echten lokalen http.server-Socket beobachtet (Boundary-Capture via
`TELEGRAM_API_BASE`); echter `TripCommandProcessor`, echter Trip + Snapshot, echte
User-Auflösung. **Keine Mocks der Logik unter Test.**

Parent-Spec: `docs/specs/modules/issue_672_telegram_e2e_pipeline.md` v1.0

## Source

- **Files:**
  - `tests/tdd/test_e2e_telegram_pipeline.py` (NEU — mock-frei)
- **Spec:** `docs/specs/modules/issue_672_telegram_e2e_pipeline.md` v1.0

## Test Inventory

| Test-Funktion | AC | Was geprüft wird |
|---------------|----|------------------|
| `ac1_glance_text_command_sends_message_with_buttons` | AC-1 | Text `/s` → genau ein sendMessage mit Glance-Inhalt (heute + morgen) und reply_markup.inline_keyboard ≥1 Button; kein editMessageText. |
| `ac2_timeline_text_command_sends_message_with_drilldown_button` | AC-2 | Text `/th` → sendMessage mit Timeline-Inhalt und ≥1 Button (dd_* oder tl_/glance). |
| `ac3_every_bot_menu_command_is_supported` | AC-3 | Jeder BOT_COMMANDS-Eintrag mit `/` → sendMessage NICHT mit "Unbekannter Befehl" (behebt #671; rot vor Fix, grün nach Fix). |
| `ac4_glance_buttons_callback_data_all_handled` | AC-4 | Alle callback_data aus Glance-Antwort → `_callback_to_body` ≠ None (kein toter Button). |
| `ac5_live_staging_bot_smoke` | AC-5 | Live-Bot-Smoke (gated: GZ_TELEGRAM_BOT_TOKEN + GZ_TELEGRAM_TEST_CHAT_ID); getMe + sendMessage + editMessageText + deleteMessage je ok=True. |

## Expected RED-State (vor GREEN-Phase)

AC-3 schlägt fehl weil:
- `BOT_COMMANDS` in `outputs/telegram.py` enthält `briefing` und `wetter`, die
  `_SHORTCUT_MAP` in `inbound_telegram_reader.py` nicht kennt → Webhook antwortet
  mit "Unbekannter Befehl" für diese Befehle.
- AC-1, AC-2, AC-4 grün (Pipeline funktioniert bereits — Charakterisierung).
- AC-5 skip (keine Env).

## Mock-Freiheit (CLAUDE.md)

- Echter HTTP-POST gegen reale `api.main.app` via TestClient.
- Ausgehende Telegram-Calls an echtem lokalen Socket (`http.server`) — kein Mock,
  nur Umlenkung des API-Hosts (`TELEGRAM_API_BASE`) = Boundary-Capture.
- AC-5: echte Bot-API via httpx, kein Mock.
