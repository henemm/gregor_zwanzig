---
entity_id: issue_697_telegram_on_demand_fetch_tests
type: tests
created: 2026-06-10
updated: 2026-06-10
status: approved
version: "1.0"
tags: [telegram, on-demand, fetch, snapshot, e2e, tdd]
---

# Tests — #697 On-demand Wetter-Fetch für Telegram-Abfragebefehle

## Approval

- [x] Approved (PO 'go' 2026-06-10)

## Purpose

TDD-Test-Inventar für den on-demand Wetter-Fetch wenn kein Snapshot vorhanden ist.
Modul-Spec: `docs/specs/modules/issue_697_telegram_on_demand_fetch.md`.

Alle Tests beweisen echtes Nutzerverhalten: kein Snapshot vorab anlegen,
on-demand Fetch muss selbst funktionieren. Keine Mocks.

## Test-Funktionen (Datei: `tests/tdd/test_issue_697_telegram_on_demand_fetch.py`)

| Test-Funktion | AC | Beweist |
|---------------|----|---------|
| `test_ac1_heute_without_snapshot_returns_weather` | AC-1 | `/heute` ohne Snapshot liefert echte Wetterdaten (°C/km/h/mm), kein Fehler-Text |
| `test_ac2_morgen_without_snapshot_returns_weather` | AC-2 | `/morgen` ohne Snapshot liefert echte Wetterdaten für morgen |
| `test_ac3_glance_without_snapshot_returns_both_days` | AC-3 | `/glance` ohne Snapshot liefert heute + morgen Wetterdaten |
| `test_ac4_loading_message_sent_before_weather` | AC-4 | Erster API-Call ist sendMessage mit ⏳, zweiter editMessageText mit Wetterdaten |
| `test_ac5_fresh_snapshot_used_directly` | AC-5 | Zweiter /heute-Aufruf nach erstem Fetch ist <1s (Cache-Hit) |
| `test_ac6_e2e_no_preseed_all_commands_return_weather` | AC-6 | E2E ohne Snapshot-Vorseedung: alle 7 Befehle liefern echte Wetterdaten |
