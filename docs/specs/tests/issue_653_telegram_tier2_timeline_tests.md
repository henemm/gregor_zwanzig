---
entity_id: issue_653_telegram_tier2_timeline_tests
type: tests
created: 2026-06-07
updated: 2026-06-07
status: approved
version: "1.0"
tags: [telegram, query, timeline, tier2, epic-639, tdd]
---

# Tests — #653 Telegram Tier-2 vertikale Timeline je Etappe

## Approval

- [x] Approved (PO 'go' 2026-06-07)

## Purpose

TDD-Test-Inventar für die vertikale Timeline-Ausgabe (Tier-2).
Modul-Spec: `docs/specs/modules/issue_653_telegram_tier2_timeline.md`.

Alle Tests beweisen Nutzerverhalten über **echte Datei-I/O** (Trip + Snapshot über
eine `tmp_path`-Umlenkung von `app.loader.get_data_dir`) — **keine** Mocks, keine
Dateiinhalt-Checks auf Quellcode.

## Test-Funktionen (Datei: `tests/tdd/test_issue_653_telegram_tier2_timeline.py`)

| Test-Funktion | AC | Beweist |
|---------------|----|---------|
| `test_ac1_timeline_lists_waypoints_today` | AC-1 | `### query: timeline_heute` listet pro Wegpunkt Ankunftszeit (10:00/12:00) + Werte, mehrzeilig, nur heute (kein Morgen-Wert). |
| `test_ac2_critical_metric_drilldown_and_back_buttons` | AC-2 | Kritische Metrik (Gewitter HIGH) → Drilldown-Button `dd_thunder_today` plus genau ein „Zurück"-Button (`callback_data: glance`). |
| `test_ac3_timeline_does_not_mutate_trip` | AC-3 | Kein `command_log.json`, Etappendaten unverändert nach der Abfrage. |
| `test_ac4_timeline_morgen_only_tomorrow` | AC-4 | `### query: timeline_morgen` enthält nur morgige Werte, nicht die heutigen. |
| `test_ac5_shortcut_mapping` | AC-5 | `_parse_command` mappt `/th /tm` auf `timeline_heute`/`timeline_morgen`. |
| `test_ac5_mutating_path_still_parses` | AC-5 | Der bestehende verändernde Pfad (`ruhetag 2`) bleibt unverändert. |
| `test_ac6_no_snapshot_hint_with_back_button` | AC-6 | Ohne Snapshot kommt ein Hinweistext (kein leerer Body) und der „Zurück"-Button bleibt gesetzt. |
| `test_ac6_snapshot_but_no_stage_today` | AC-6 | Snapshot ohne heutiges Segment → „Keine Etappe geplant", kein Crash, „Zurück"-Button. |

## Acceptance Criteria (Verweis)

Siehe Modul-Spec AC-1…AC-6. Dieser Test-Spec dient der `spec_enforcement`-Registrierung
der obigen Test-Entitäten und ist mit der Modul-Spec freigegeben.
