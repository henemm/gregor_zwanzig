---
entity_id: issue_360_signal_channel_renderer_tests
type: tests
created: 2026-05-24
updated: 2026-05-24
status: draft
version: "1.0"
tags: [tests, output, signal, telegram, channel-renderer, issue-360, epic-331]
parent: issue_360_signal_channel_renderer
phase: phase5_tdd_red
---

# Issue #360 — Kanal-bewusster Renderer für Signal/Telegram (Tests)

## Approval

- [x] Approved

## Purpose

Test-Manifest für den kanal-bewussten Renderer aus
`docs/specs/modules/issue_360_signal_channel_renderer.md`. Jeder pytest-Test
mappt 1:1 auf ein Acceptance Criterion der Parent-Spec (AC-1..AC-8).

Parent-Spec: `docs/specs/modules/issue_360_signal_channel_renderer.md` v1.0

## Source

- **File:** `tests/tdd/test_issue_360_channel_renderer.py` (NEU — RED-Phase-Tests
  für `render_for_channel()`, `render_narrow()`, das erweiterte Datenmodell
  (`MetricConfig.bucket/.order`, `TripReport.signal_text/.telegram_text`) und die
  Legacy-Migration im Loader).

## Test Inventory

### Python (`tests/tdd/test_issue_360_channel_renderer.py`)

| Test-Funktion | AC | Was geprüft wird |
|---|---|---|
| `test_ac1_signal_five_primary_all_in_table` | AC-1 | Signal mit 5 primary-Metriken: alle in `table_columns`, `detail_metrics == []`, `demoted_count == 0`. |
| `test_ac2_signal_nine_primary_caps_at_five` | AC-2 | Signal mit 9 primary-Metriken: `table_columns` genau 5 (Zeit + 5 = 6 Spalten), `detail_metrics` die übrigen 4, `demoted_count == 4`. |
| `test_ac3_email_no_limit_keeps_all_primary` | AC-3 | Email mit demselben dc (9 primary): alle 9 in `table_columns`, `demoted_count == 0` (kein Limit). |
| `test_ac4_sms_pushes_everything_to_detail` | AC-4 | SMS mit demselben dc: `table_columns == []`, alle Werte flach in `detail_metrics`. |
| `test_ac5_render_narrow_signal_line_width_and_detail_trailer` | AC-5 | `render_narrow("signal", … 9 primary)`: jede Body-Zeile ≤26 Zeichen, Body endet mit `·`-getrennter Detail-Zeile. |
| `test_ac6_format_email_populates_signal_text` | AC-6 | `TripReportFormatter.format_email(...)` mit echtem Segment-Fixture: `report.signal_text` gesetzt und ungleich `report.email_plain` (reiner Formatter-Test, kein Netzversand). |
| `test_ac7_legacy_roundtrip_assigns_bucket_order_without_diff` | AC-7 | Legacy-Trip-JSON ohne `bucket`/`order`: nach load→save→load haben alle `MetricConfig` gültige `bucket`/`order`, kein anderes Feld geändert (Roundtrip ohne Daten-Diff). |
| `test_ac7b_partial_migration_keeps_active_metric_primary` | AC-7 (F002) | Teil-migrierte Trip-JSON: `temperature` explizit `bucket=primary`, `wind`/`precipitation` (beide enabled) ohne `bucket`/`order` → erben `primary` via `auto_distribute` (nicht still `secondary`) und landen in der Signal-Tabelle. |
| `test_ac8_order_determines_column_sequence` | AC-8 | dc mit gesetzter `order`: `render_for_channel` liefert `table_columns` in genau dieser Reihenfolge. |

## Implementation Details

Tests folgen dem No-Mocks-Pattern des Projekts:
- Reine Datenstrukturen (`UnifiedWeatherDisplayConfig`/`MetricConfig`) +
  echte Funktionsaufrufe der (noch zu bauenden) pure functions.
- `SegmentWeatherData`-Builder übernommen aus
  `tests/tdd/test_reports_pro_typ.py` (echte `NormalizedTimeseries`).
- Roundtrip-Test übernimmt das save/load-Muster aus
  `tests/integration/test_config_persistence.py`, schreibt aber in `tmp_path`.
- Keine `Mock()`, `patch()`, `MagicMock`.

In RED-Phase schlagen alle Tests fehl, weil `channel_layout.py`/`narrow.py`,
die Felder `MetricConfig.bucket/.order`, `TripReport.signal_text/.telegram_text`
und die Loader-Migration noch nicht existieren (ImportError/AttributeError).

## Expected Behavior

- **Input:** `UnifiedWeatherDisplayConfig` mit gesetzten `bucket`/`order`;
  minimales `SegmentWeatherData`-Fixture; Legacy-Trip-JSON ohne neue Felder.
- **Output:** Assertions über `ChannelLayout`-Felder, Narrow-Body-Zeilenbreite,
  `TripReport.signal_text` und den Migrations-Roundtrip.
- **Side effects:** Schreibvorgänge ausschließlich in `tmp_path`. Kein Netz.

## Acceptance Criteria

- **AC-T1:** Given die Test-Datei existiert und Implementierung fehlt /
  When `pytest tests/tdd/test_issue_360_channel_renderer.py -v` läuft /
  Then schlagen alle 8 Tests fehl (RED-Phase erfolgreich).

- **AC-T2:** Given GREEN-Phase abgeschlossen /
  When `pytest tests/tdd/test_issue_360_channel_renderer.py -v` ausgeführt /
  Then alle 8 Tests grün, keine Mocks.

## Known Limitations

- Der Narrow-Renderer-Test (AC-5) prüft die Zeilenbreite anhand eines
  vorgebauten `seg_tables`-Row-Dicts, um vom konkreten Spaltenformat des
  Formatters unabhängig zu bleiben.

## Changelog

- 2026-05-24: Initial — Test-Manifest für Issue #360 (Signal/Telegram Renderer).
