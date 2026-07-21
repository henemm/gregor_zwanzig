---
entity_id: issue_654_telegram_thunder_drilldown_tests
type: tests
created: 2026-06-08
updated: 2026-06-08
status: draft
version: "2.0"
tags: [tests, telegram, drilldown, thunder, epic-639, issue-654]
parent: telegram_tier3_drilldown
phase: phase5_tdd_red
---

# Issue #654 — Telegram Tier-3 Drilldown (Tests v2.0)

## Approval

- [x] Approved

## Purpose

Test-Manifest für Issue #654 v2.0 (stündlicher Drilldown-Inhalt hinter #651-Buttons).
Testet `TripCommandProcessor.process()` direkt über `InboundMessage` — kein Reader,
kein Netz, keine Mocks.

Parent-Spec: `docs/specs/modules/telegram_tier3_drilldown.md` v2.0

## Source

- **Files:**
  - `tests/tdd/test_issue_654_telegram_thunder_drilldown.py` (NEU — mock-frei)
- **Spec:** `docs/specs/modules/telegram_tier3_drilldown.md` v2.0

## Test Inventory

| Test-Funktion | AC | Was geprüft wird |
|---------------|----|------------------|
| `ac1_dd_thunder_today_returns_hourly_list` | AC-1 | Echter Snapshot; `### query: dd_thunder_today`; ≥6 HH:MM-Zeilen mit Stufen-Labels im result.confirmation_body. |
| `ac2_dd_thunder_today_reply_markup_has_zurueck_button` | AC-2 | result.reply_markup.inline_keyboard enthält Button mit text „Zurück" und callback_data „tl_today". |
| `ac3_dd_thunder_today_no_snapshot_returns_empty_state` | AC-3 | Trip ohne Snapshot → success=False, Leerzustand-Text im body, kein Crash. |
| `ac4_dd_wind_body_contains_kmh_and_precip_contains_mm` | AC-4 | `dd_wind_today` → body enthält „km/h"; `dd_precip_today` → body enthält „mm". |
| `ac1_dd_thunder_direct_key_also_works` | AC-1 | Direkter Key `### dd_thunder_today` (ohne `query:`) → gleiche stündliche Liste. |

## Expected RED-State (vor GREEN-Phase)

Alle Tests schlagen in Phase 5 fehl weil:
- `_DRILLDOWN_PATTERN` nicht existiert
- `_handle_drilldown()` nicht existiert
- `process()` kennt Drilldown-Tokens nicht → landet im „Unbekannter Befehl"-Zweig
