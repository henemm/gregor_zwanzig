---
entity_id: issue_651_telegram_query_glance_tests
type: tests
created: 2026-06-07
updated: 2026-06-07
status: approved
version: "1.0"
tags: [telegram, query, glance, epic-639, tdd]
---

# Tests — #651 Telegram-Abfrage-Befehle (`/s /h /m /hg`) + Tier-1-Glance

## Approval

- [x] Approved (PO 'go' 2026-06-07)

## Purpose

TDD-Test-Inventar für die lesenden Telegram-Abfrage-Befehle und die Tier-1-Glance.
Modul-Spec: `docs/specs/modules/issue_651_telegram_query_glance.md`.

Alle Tests beweisen Nutzerverhalten über **echte Datei-I/O** (Trip + Snapshot über
eine `tmp_path`-Umlenkung von `app.loader.get_data_dir`) — **keine** Mocks, keine
Dateiinhalt-Checks auf Quellcode.

## Test-Funktionen (Datei: `tests/tdd/test_issue_651_telegram_query_glance.py`)

| Test-Funktion | AC | Beweist |
|---------------|----|---------|
| `test_ac1_glance_lists_today_and_tomorrow_with_buttons` | AC-1 | `### query: glance` nennt heute- und morgen-Werte und liefert `reply_markup` mit beiden Timeline-Buttons. |
| `test_ac2_query_does_not_mutate_trip` | AC-2 | Kein `command_log.json`, Etappendaten unverändert nach der Abfrage. |
| `test_ac3_heute_only_today` | AC-3 | `### query: heute` enthält nur heutige Werte, nicht die morgigen. |
| `test_ac3_morgen_only_tomorrow` | AC-3 | `### query: morgen` enthält nur morgige Werte, nicht die heutigen. |
| `test_ac4_heute_gewitter_focus` | AC-4 | `### query: heute_gewitter` nennt das Gewitter-Level für heute fokussiert. |
| `test_ac6_no_snapshot_hint_with_buttons` | AC-6 | Ohne Snapshot kommt ein Hinweistext (kein leerer Body) und `reply_markup` bleibt gesetzt. |
| `test_ac5_shortcut_mapping` | AC-5 | `_parse_command` mappt `/s /h /m /hg` auf die Query-Keys. |
| `test_ac5_mutating_path_still_parses` | AC-5 | Der bestehende verändernde Pfad (`ruhetag 2`) bleibt unverändert. |

## Acceptance Criteria (Verweis)

Siehe Modul-Spec AC-1…AC-6. Dieser Test-Spec dient der `spec_enforcement`-Registrierung
der obigen Test-Entitäten und ist mit der Modul-Spec freigegeben.
