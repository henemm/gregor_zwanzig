---
entity_id: issue_131_alert_email_klarheit_tests
type: tests
created: 2026-05-13
updated: 2026-05-13
status: draft
version: "1.0"
tags: [tests, bug, email, alert, change-detection, issue-131]
parent: issue_131_alert_email_klarheit
phase: phase5_tdd_red
---

# Issue #131 — Alert-E-Mail klarer formatieren (Tests)

## Approval

- [x] Approved

## Purpose

Test-Manifest für die Implementierung aus
`docs/specs/modules/issue_131_alert_email_klarheit.md`. Jeder pytest-
Funktionsname mappt 1:1 auf eine Acceptance-Criterion der Parent-Spec.

Parent-Spec: `docs/specs/modules/issue_131_alert_email_klarheit.md` v1.0

## Source

- **File:** `tests/unit/test_issue_131_alert_klarheit.py` (NEU — RED-Tests
  für alle 9 ACs)

## Test Inventory

Test-Funktionsnamen führen den AC-Index, damit der Spec-Enforcement-Hook
sie auflösen kann.

| Test-Funktion | AC | Was geprüft wird |
|---|---|---|
| `test_ac1_detect_changes_attaches_segment_id` | AC-1 | `WeatherChangeDetectionService.detect_changes()` füllt `WeatherChange.segment_id` aus `new_data.segment.segment_id`. |
| `test_ac2_from_display_config_uses_enabled_not_alert_enabled` | AC-2 | `from_display_config()` baut Schwellwert für jede Metrik mit `enabled=True` (nicht mehr `alert_enabled`). |
| `test_ac3_fallback_to_trip_config_without_display_config` | AC-3 | `from_trip_config()` bleibt der Fallback-Pfad und liefert identische Schwellwerte wie vorher. |
| `test_ac4_format_metric_value_meters_thousands` | AC-4 | `format_metric_value("m", 12240.0) == "12.240 m"`. |
| `test_ac5_format_metric_value_percent_integer` | AC-5 | `format_metric_value("%", 63.0)` und signed-Variante. |
| `test_ac6_format_metric_value_celsius_and_mm_with_comma` | AC-6 | `°C` / `mm` mit Komma + 1 NK; signed liefert Unicode-Minus. |
| `test_ac7_format_change_line_with_segment_label` | AC-7 | Komplette Change-Zeile inkl. `Segment N (HH:MM–HH:MM)`-Präfix. |
| `test_ac8_two_segments_render_two_distinct_lines` | AC-8 | Zwei Sichtweite-Aenderungen in zwei Segmenten erzeugen zwei unterschiedliche Zeilen via `format_change_line()`. |
| `test_ac9_trip_report_legacy_change_block_removed` | AC-9 | Toter Renderer-Block in `src/formatters/trip_report.py` ist entfernt (kein `Wetteränderungen` mehr). |

## Implementation Details

Tests folgen dem No-Mocks-Pattern aus `tests/unit/test_change_detection.py`:
- Reale Dataclasses (`WeatherChange`, `SegmentWeatherData`,
  `UnifiedWeatherDisplayConfig`).
- Reale Modul-Imports (`format_metric_value`, `format_change_line`,
  `build_segment_label`).
- Keine `Mock()`, kein `patch()`, kein `MagicMock`.

In RED-Phase müssen Imports `format_metric_value`, `format_change_line`,
`build_segment_label` `ImportError` werfen — die Funktionen existieren noch
nicht. AC-9 prüft das produktive Quellfile direkt.

## Expected Behavior

- **Input:** Synthetische `SegmentWeatherData`-Objekte und
  `WeatherChange`-Instanzen.
- **Output:** Assertions auf Strings/Listen — kein I/O, keine Netzwerk-Calls.
- **Side effects:** Keine.

## Acceptance Criteria

- **AC-T1:** Given die Test-Datei existiert und die Implementierung fehlt /
  When `pytest tests/unit/test_issue_131_alert_klarheit.py -v` läuft /
  Then schlagen mindestens 7 der 9 Tests fehl (RED-Phase erfolgreich
  signalisiert). AC-3 darf grün sein, weil `from_trip_config()` bereits
  korrekt implementiert ist; AC-9 ist grün, sobald der tote Block fehlt
  (kann in RED rot oder grün sein, je nach aktuellem Stand).

- **AC-T2:** Given GREEN-Phase ist abgeschlossen /
  When derselbe pytest-Lauf ausgeführt wird /
  Then sind alle 9 Tests grün, ohne Mocks und ohne Netzwerk-I/O.

## Known Limitations

- Tests nutzen den realen `MetricCatalog` — wenn dort `default_change_threshold`
  für `visibility` geändert wird, schlägt AC-2 fehl. Bewusste Kopplung an
  echte Konfiguration.

## Changelog

- 2026-05-13: Initial — Test-Manifest für Issue #131.
