---
entity_id: issue_570_telegram_bot_tests
type: tests
created: 2026-06-03
updated: 2026-06-03
status: draft
version: "1.0"
tags: [tests, telegram, inbound, bot, issue-570]
parent: inbound_telegram_reader
phase: phase5_tdd_red
---

# Issue #570 — Inbound Telegram Reader Tests

## Approval

- [x] Approved

## Purpose

Test-Manifest für den Inbound Telegram Reader (Issue #570).
Mappt pytest-Funktionsnamen auf die Acceptance Criteria der Parent-Spec.

Parent-Spec: `docs/specs/_archive/modules/inbound_telegram_reader.md`.

## Source

- **Files:**
  - `tests/tdd/test_inbound_telegram_reader.py` (NEU)
- **Spec:** `docs/specs/_archive/modules/inbound_telegram_reader.md` v1.0

## Test Inventory

| Test-Funktion | AC | Was geprüft wird |
|---------------|----|-----------------|
| `poll_returns_zero_without_credentials` | AC-7 | poll_and_process() gibt 0 zurück wenn kein Token/Chat-ID |
| `find_active_trip_today_overlap` | AC-2 | Trip mit heutigem Datum-Overlap wird automatisch gewählt |
| `find_active_trip_next_future` | AC-3 | Nächster zukünftiger Trip wenn kein aktueller aktiv |
| `find_active_trip_no_trips_returns_none` | AC-4 | None wenn kein Trip vorhanden |
| `parse_command_ruhetag_no_value` | — | Parser: 'ruhetag' → ('ruhetag', None) |
| `parse_command_ruhetag_with_value` | — | Parser: 'ruhetag 2' → ('ruhetag', '2') |
| `parse_command_startdatum` | — | Parser: 'startdatum 2026-07-15' → ('startdatum', '2026-07-15') |
| `parse_command_case_insensitive` | — | Parser: 'Ruhetag' → ('ruhetag', None) |
| `parse_command_unknown_returns_none_key` | AC-8 | Unbekannter Befehl → (None, None) |
| `parse_command_ignores_extra_lines` | — | Nur erste Zeile wird geparst |
| `inbound_message_channel_is_telegram` | — | InboundMessage.channel='telegram' wird an Processor übergeben |
| `hilfe_command_in_processor` | AC-5 | 'hilfe' Befehl gibt alle Befehle zurück |
| `status_command_in_processor` | AC-6 | 'status' Befehl gibt Etappen-Übersicht zurück |

## Expected RED-State (vor GREEN-Phase)

| Test | Erwartung in Phase 5 (RED) | Begründung |
|------|---------------------------|-----------|
| `poll_returns_zero_without_credentials` | `ImportError` | `inbound_telegram_reader` existiert nicht |
| `find_active_trip_today_overlap` | `ImportError` | Modul existiert nicht |
| `find_active_trip_next_future` | `ImportError` | Modul existiert nicht |
| `find_active_trip_no_trips_returns_none` | `ImportError` | Modul existiert nicht |
| `parse_command_ruhetag_no_value` | `ImportError` | Modul existiert nicht |
| `parse_command_ruhetag_with_value` | `ImportError` | Modul existiert nicht |
| `parse_command_startdatum` | `ImportError` | Modul existiert nicht |
| `parse_command_case_insensitive` | `ImportError` | Modul existiert nicht |
| `parse_command_unknown_returns_none_key` | `ImportError` | Modul existiert nicht |
| `parse_command_ignores_extra_lines` | `ImportError` | Modul existiert nicht |
| `inbound_message_channel_is_telegram` | `ImportError` | Modul existiert nicht |
| `hilfe_command_in_processor` | `AssertionError` | `_VALID_COMMANDS` enthält 'hilfe' nicht |
| `status_command_in_processor` | `AssertionError` | `_VALID_COMMANDS` enthält 'status' nicht |
