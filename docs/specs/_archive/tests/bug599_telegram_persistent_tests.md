---
entity_id: bug599_telegram_persistent_tests
type: tests
created: 2026-06-04
updated: 2026-06-04
status: draft
version: "1.0"
tags: [tests, telegram, persistent, singleton, bug-599]
parent: bug599_telegram_persistent
phase: phase5_tdd_red
---

# Bug #599 — Telegram Persistent Offset + Token-Store + Bot-Bestätigung Tests

## Approval

- [x] Approved

## Purpose

Test-Manifest für Bug #599.
Prüft: Modul-Singleton in scheduler.py, Offset-Persistenz, Bot-Bestätigungsnachricht.

Parent-Spec: `docs/specs/modules/bug599_telegram_persistent.md`.

## Source

- **Files:**
  - `tests/tdd/test_bug599_telegram_persistent.py` (NEU)
- **Spec:** `docs/specs/modules/bug599_telegram_persistent.md` v1.0

## Test Inventory

| Test-Funktion | AC | Was geprüft wird |
|---------------|----|-----------------|
| `test_scheduler_has_module_level_telegram_reader` | AC-1 | `_telegram_reader` existiert auf Modulebene in scheduler |
| `test_trigger_reuses_reader_instance` | AC-2 | Offset bleibt erhalten (nicht auf 0 zurückgesetzt) |
| `test_no_new_reader_instance_on_each_call` | AC-1 | Objektidentität — keine neue Instanz pro Aufruf |
| `test_process_start_command_sends_confirmation_on_success` | AC-3 | TelegramOutput.send() mit "verbunden" bei HTTP 200 |
| `test_process_start_command_no_confirmation_on_failure` | AC-3 | Kein "verbunden" bei HTTP 422 |

## Expected RED-State (vor GREEN-Phase)

| Test | Erwartung in Phase 5 (RED) | Begründung |
|------|---------------------------|-----------|
| `test_scheduler_has_module_level_telegram_reader` | `AssertionError` | `_telegram_reader` existiert noch nicht auf Modulebene |
| `test_trigger_reuses_reader_instance` | `AssertionError` | neues Objekt bei jedem Aufruf → Offset=0 |
| `test_no_new_reader_instance_on_each_call` | `AssertionError` | verschiedene Instanzen, nicht dieselbe |
| `test_process_start_command_sends_confirmation_on_success` | `AssertionError` | TelegramOutput.send() wird nicht aufgerufen |
| `test_process_start_command_no_confirmation_on_failure` | pass | negativer Test, bereits korrekt |
