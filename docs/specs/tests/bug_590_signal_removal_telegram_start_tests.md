---
entity_id: bug_590_signal_removal_telegram_start_tests
type: tests
created: 2026-06-04
updated: 2026-06-04
status: draft
version: "1.0"
tags: [tests, signal, telegram, removal, start-flow, bug-590]
parent: bug_590_kanal_settings
phase: phase5_tdd_red
---

# Bug #590 — Signal-Removal + Telegram /start-Flow Tests

## Approval

- [x] Approved

## Purpose

Test-Manifest für Bug #590.
Prüft: Signal vollständig entfernt, Telegram /start-Token-Flow korrekt implementiert.

Parent-Spec: `docs/specs/modules/bug_590_kanal_settings.md`.

## Source

- **Files:**
  - `tests/tdd/test_bug590_signal_removal_telegram_start.py` (NEU)
- **Spec:** `docs/specs/modules/bug_590_kanal_settings.md` v1.0

## Test Inventory

| Test-Funktion | AC | Was geprüft wird |
|---------------|----|-----------------|
| `test_settings_has_no_signal_phone_field` | AC-7 | Settings.model_fields enthält kein signal_phone |
| `test_settings_has_no_signal_api_key_field` | AC-7 | Settings.model_fields enthält kein signal_api_key |
| `test_settings_has_no_can_send_signal_method` | AC-7 | Settings hat keine can_send_signal()-Methode |
| `test_signal_output_module_does_not_exist` | AC-7 | src/outputs/signal.py ist gelöscht |
| `test_trip_report_config_has_no_send_signal` | AC-7 | TripReportConfig hat kein send_signal-Feld |
| `test_trip_subscription_has_no_send_signal` | AC-7 | CompareSubscription hat kein send_signal-Feld |
| `test_scheduler_imports_no_signal_output` | AC-7 | trip_report_scheduler.py referenziert kein SignalOutput |
| `test_inbound_telegram_reader_handles_start_command` | AC-3 | _process_start_command() existiert und gibt True zurück |
| `test_inbound_telegram_reader_dispatches_start_to_handler` | AC-3 | _process_update erkennt /start und ruft _process_start_command auf |
| `test_scheduler_send_report_ignores_signal_silently` | AC-7 | Settings ohne signal_phone initialisierbar, kein AttributeError |
| `test_compare_tabs_has_no_signal_channel_row` | AC-6 | CompareTabs.svelte enthält kein 'Signal' mehr |
| `test_compare_tabs_has_no_signal_in_channels_array` | AC-6 | CompareTabs.svelte enthält kein 'signal' im channels-Array |
| `test_step5_versand_has_no_signal_toggle` | AC-6 | Step5Versand.svelte enthält keinen Signal-Toggle mehr |
| `test_step5_versand_has_no_signal_channel_toggle` | AC-6 | Step5Versand.svelte enthält kein sendSignal mehr |

## Expected RED-State (vor GREEN-Phase)

| Test | Erwartung in Phase 5 (RED) | Begründung |
|------|---------------------------|-----------|
| `test_settings_has_no_signal_phone_field` | `AssertionError` | signal_phone existiert noch in Settings |
| `test_settings_has_no_signal_api_key_field` | `AssertionError` | signal_api_key existiert noch in Settings |
| `test_settings_has_no_can_send_signal_method` | `AssertionError` | can_send_signal() existiert noch |
| `test_signal_output_module_does_not_exist` | `AssertionError` | signal.py existiert noch |
| `test_trip_report_config_has_no_send_signal` | `AssertionError` | send_signal existiert noch in TripReportConfig |
| `test_trip_subscription_has_no_send_signal` | `AssertionError` | send_signal existiert noch in CompareSubscription |
| `test_scheduler_imports_no_signal_output` | `AssertionError` | SignalOutput noch referenziert |
| `test_inbound_telegram_reader_handles_start_command` | `AttributeError` | _process_start_command() existiert nicht |
| `test_inbound_telegram_reader_dispatches_start_to_handler` | `AssertionError` | _process_update ruft _process_start_command nicht auf |
| `test_scheduler_send_report_ignores_signal_silently` | `AssertionError` | signal_phone noch vorhanden |
