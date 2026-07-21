---
entity_id: issue_434_per_report_layouts_tests
type: tests
created: 2026-05-29
updated: 2026-05-29
status: draft
version: "1.0"
tags: [tests, backend, data-model, per-report, channel-layouts, issue-434]
parent: issue_434_per_report_layouts
phase: phase5_tdd_red
---

# Issue #434 — Per-Report-Layout-Overrides (Tests)

## Approval

- [x] Approved

## Purpose

Test-Manifest für `docs/specs/modules/issue_434_per_report_layouts.md`. Jeder pytest-Test mappt 1:1 auf ein Acceptance Criterion der Parent-Spec (AC-1..AC-7).

Parent-Spec: `docs/specs/modules/issue_434_per_report_layouts.md` v1.0

## Source

- **File:** `tests/tdd/test_issue_434_per_report_layouts.py` (NEU — RED-Phase-Tests für `UnifiedWeatherDisplayConfig.per_report_layouts`, die erweiterte `get_metrics_for_channel()`-Kaskade, den `_parse_display_config()`-Zweig für `channel_layouts_per_report`, den Serialisierungs-Fix in `_trip_to_dict()` und den Email-Renderer-Fix in `trip_report.py:73`).

## Test Inventory

### Python (`tests/tdd/test_issue_434_per_report_layouts.py`)

| Test-Funktion | AC | Was geprüft wird |
|---|---|---|
| `test_ac1_loader_reads_channel_layouts_per_report` | AC-1 | Trip-JSON mit `channel_layouts_per_report` → `dc.per_report_layouts` ist nicht None, enthält pro report_type + channel eine korrekt typisierte `MetricConfig`-Liste. |
| `test_ac2_legacy_trip_has_no_per_report_layouts` | AC-2 | Alter Trip ohne `channel_layouts_per_report` → `dc.per_report_layouts is None` und `get_metrics_for_channel("email", ...)` verhält sich wie vor diesem PR (kein Regressions-Verhalten). |
| `test_ac3_per_report_wins_over_per_channel` | AC-3 | per_report_layouts["morning"]["email"] und per_channel_layouts["email"] beide gesetzt → `get_metrics_for_channel("email", "morning")` liefert die per_report-Liste, nicht die per_channel-Liste. |
| `test_ac4_no_per_report_falls_back_to_per_channel` | AC-4 | per_report_layouts hat keinen telegram-Eintrag → `get_metrics_for_channel("telegram", "morning")` fällt korrekt auf globale Liste zurück. |
| `test_ac5_empty_per_report_no_fallback` | AC-5 | `per_report_layouts["evening"]["email"] == []` → `get_metrics_for_channel("email", "evening")` liefert leere Liste, kein Fallback. |
| `test_ac6_roundtrip_per_channel_and_per_report_layouts` | AC-6 | Trip mit `per_channel_layouts` und `per_report_layouts` → `_trip_to_dict()` schreibt beide Felder zurück → `_parse_display_config()` liefert bit-identischen Zustand (Roundtrip-Garantie). |
| `test_ac7_trip_report_uses_get_metrics_for_channel` | AC-7 | Strukturtest: `trip_report.py.format_email()` enthält `get_metrics_for_channel`-Aufruf (nicht `get_metrics_for_report_type`). |
| `test_ac7_trip_report_does_not_bypass_channel_logic` | AC-7 | Strukturtest: `trip_report.py.format_email()` enthält keinen direkten `get_metrics_for_report_type`-Aufruf mehr. |

## Implementation Details

Tests folgen dem No-Mocks-Pattern des Projekts (CLAUDE.md: KEINE MOCKED TESTS):

- Reine Datenstrukturen (`UnifiedWeatherDisplayConfig` / `MetricConfig`) + echte Aufrufe der (noch zu bauenden) Methoden.
- Test-Fixtures als JSON-Dicts in Helper-Funktionen (`_legacy_trip_data`, `_per_report_trip_data`, `_per_report_empty_evening_data`).
- Echter Aufruf von `_parse_display_config()` aus `src/app/loader.py` — kein `Mock()`, kein `patch()`, kein `MagicMock`.
- AC-7: Source-Inspektion via `inspect.getsource()` — prüft Verhaltenspfad ohne vollständige Email-Pipeline-Ausführung.

## RED-Phase-Erwartung

- AC-1, AC-3, AC-4, AC-5: **AttributeError** beim Zugriff auf `dc.per_report_layouts` — Feld existiert noch nicht.
- AC-2: **AttributeError** beim Aufruf von `get_metrics_for_channel()` mit dem neuen Fallback-Verhalten.
- AC-6: **AssertionError** — `_trip_to_dict()` schreibt `channel_layouts` und `channel_layouts_per_report` noch nicht zurück.
- AC-7/AC-7b: **AssertionError** — `trip_report.py:73` ruft derzeit `get_metrics_for_report_type()` auf, nicht `get_metrics_for_channel()`.

## Expected Behavior

- **Input:** verschiedene `display_config`-Dicts mit/ohne `channel_layouts_per_report`.
- **Output:** `UnifiedWeatherDisplayConfig`-Instanzen mit erwarteten `per_report_layouts`-Werten, korrekte Kaskaden-Ergebnisse aus `get_metrics_for_channel`.
- **Side effects:** Keine I/O, keine DB-Writes (außer AC-6 nutzt `_trip_to_dict` auf einem In-Memory-Trip-Objekt).

## Acceptance Criteria

**AC-T1:** Given der Test-Lauf `pytest tests/tdd/test_issue_434_per_report_layouts.py -v` /
When alle 8 Test-Funktionen in der RED-Phase ausgeführt werden /
Then schlagen alle 8 Tests mit AttributeError oder AssertionError fehl.

**AC-T2:** Given die GREEN-Phase ist abgeschlossen (Implementation von `per_report_layouts` + erweitertes `get_metrics_for_channel` + Serialisierungs-Fix + Email-Renderer-Fix) /
When derselbe pytest-Lauf wiederholt wird /
Then sind alle 8 Tests grün und der `pytest`-Exit-Code ist 0.

## Known Limitations

- AC-7 wird als Strukturtest (`inspect.getsource`) implementiert, nicht als End-to-End-Render-Pipeline — volle Email-Pipeline-Tests liegen in `tests/integration/`.
- TypeScript-Typen (`ChannelLayoutsPerReport` Interface) werden nicht durch pytest abgedeckt — separater `tsc --noEmit`-Lauf.

## Changelog

- 2026-05-29: Initial test manifest für Issue #434.
