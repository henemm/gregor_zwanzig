---
entity_id: wintersport_profile_consolidation_tests
type: tests
created: 2026-04-28
updated: 2026-04-28
status: draft
version: "1.0"
tags: [tests, output, pipeline, refactor, epic-render-pipeline, wintersport]
parent: wintersport_profile_consolidation
phase: β4
---

# Wintersport Profile Consolidation Tests

## Approval

- [ ] Approved

## Purpose

Test-Manifest für die β4 Wintersport-Profile-Konsolidierung. Jeder Eintrag mappt einen
pytest-Funktionsnamen (ohne `test_`-Präfix) auf das beobachtete Verhalten.

Parent-Modul-Spec: `docs/specs/modules/wintersport_profile_consolidation.md`.

## Source

- **Files:**
  - `tests/unit/test_trip_result_adapter.py` (NEU — Adapter-Unit-Tests)
  - `tests/unit/test_renderers_text_report.py` (NEU — Long-Report-Renderer-Tests)
  - `tests/golden/text_report/test_text_report_golden.py` (NEU — Long-Report-Golden)
  - `tests/integration/test_cli_wintersport.py` (NEU — CLI-Pipeline-Integration)
  - `tests/golden/sms/test_sms_golden.py::test_golden_arlberg_winter_morning` (vorhanden — bleibt unverändert grün)
  - `tests/test_formatters.py` (zu STREICHEN — `TestWintersportFormatter`-Klasse komplett)
- **Spec:** `docs/specs/modules/wintersport_profile_consolidation.md` v1.0

## Test Inventory

### Adapter-Unit-Tests (`tests/unit/test_trip_result_adapter.py`)

Spec §5.1, §A1, §A4. Adapter `_trip_result_to_normalized` und Helper.

| Test | Asserts |
|---|---|
| `adapter_produces_normalized_forecast` | `_trip_result_to_normalized(result)` liefert `NormalizedForecast`; `days[0]` enthält `temp_min_c`, `temp_max_c`, `wind_chill_c`, `snow_depth_cm`, `snow_new_24h_cm`, `snowfall_limit_m` aus `summary` befüllt |
| `adapter_handles_all_none_summary` | Summary mit allen `AggregatedValue.value=None` → `DailyForecast`-Defaults, kein Exception |
| `adapter_pure_function` | Zwei Aufrufe mit identischem `result` → bit-identische `NormalizedForecast` (Determinismus) |
| `adapter_avalanche_level_is_none` | `AggregatedSummary` enthält kein Avalanche-Feld → `daily.avalanche_level is None` (out-of-scope, dokumentiert) |
| `adapter_hourly_samples_anchor_at_hour_12` | `summary.wind.value=45` → `daily.wind_hourly == (HourlyValue(12, 45),)` (Default-Anker, Spec §5.1) |
| `waypoint_to_detail_extracts_id_name_elevation_timewindow` | `_waypoint_to_detail(wf)` liefert `WaypointDetail` mit `id`, `name`, `elevation_m`, `time_window` |
| `summary_to_rows_formats_temperature_range` | `_summary_to_rows(summary)` produziert Zeile `("Temperatur", "-15.0 bis -5.0°C (Gipfel)")` für temp_min=-15 (source=Gipfel), temp_max=-5 (source=Start) |
| `summary_to_rows_omits_none_fields` | `summary.snow_depth.value=None` → keine "Schneehöhe"-Zeile in der Ausgabe |
| `wintersport_default_config_enables_av_wc_sn_sn24_sfl` | `_wintersport_default_config()` liefert `MetricSpec`-Liste mit Symbolen `AV`, `WC`, `SN`, `SN24+`, `SFL` und allen `enabled=True` |

### Long-Report-Renderer-Tests (`tests/unit/test_renderers_text_report.py`)

Spec §A4, §A5. `render_text_report` als pure Function.

| Test | Asserts |
|---|---|
| `renders_header_summary_waypoints` | Output enthält Trip-Name (UPPERCASE), `start_date` als String, `report_type` als Titel, "ZUSAMMENFASSUNG", "WEGPUNKT-DETAILS" |
| `renders_avalanche_block_when_regions_present` | `avalanche_regions=("AT-7",)` → Output enthält "LAWINENREGIONEN" und "AT-7" |
| `omits_avalanche_block_when_regions_empty` | `avalanche_regions=()` → Output enthält **kein** "LAWINENREGIONEN" |
| `renders_token_line_from_token_line_arg` | `token_line` mit Wintersport-Tokens → Output enthält die Token-Zeile (z.B. `Stubaier:` Stage-Prefix); Position oben oder unten ist Implementation-Detail, Test prüft nur Vorhandensein |
| `is_pure_function` | Zwei Aufrufe mit identischen Inputs → bit-identische Strings (`==`) |
| `is_profile_agnostic` | Aufruf mit `token_line` aus `profile="standard"` (keine Wintersport-Tokens) liefert konsistenten Output ohne Wintersport-Sektion — Renderer fragt nicht nach `profile` |
| `omits_summary_rows_when_empty` | `summary_rows=[]` → "ZUSAMMENFASSUNG" Header existiert, Body-Sektion ist leer (kein Crash) |
| `omits_waypoint_details_when_empty` | `waypoint_details=[]` → "WEGPUNKT-DETAILS" Header existiert, Body leer |

### Long-Report-Golden (`tests/golden/text_report/test_text_report_golden.py`)

Spec §A4. Bit-identischer Golden-Vergleich für einen Referenz-Trip.

| Test | Asserts |
|---|---|
| `golden_stubaier_skitour_evening` | `render_text_report(token_line, …)` für Stubaier-Skitour-Fixture (analog `tests/test_formatters.py::TestWintersportFormatter._create_simple_result`) liefert Output bit-identisch zu `tests/golden/text_report/stubaier-skitour-evening.txt`. Golden-Datei wird in Phase 5/6 vom Developer-Agent aus dem implementierten Renderer eingefroren — nicht aus altem `WintersportFormatter.format()`-Output kopiert. |

### CLI-Integration-Tests (`tests/integration/test_cli_wintersport.py`)

Spec §A3, §A4. End-to-end durch die CLI-Bahnen `--compact` und Long-Report.

| Test | Asserts |
|---|---|
| `cli_compact_uses_pipeline` | CLI-Aufruf mit `--trip <wintersport-fixture> --compact` produziert Output mit Stage-Prefix `Stubaier:`, enthält Wintersport-Tokens (`AV…`, `WC…`, `SN…`, `SN24+…`, `SFL…` falls Fixture-Daten verfügbar), Länge ≤160, **niemals** Legacy-Form `T-15/-5` (das alte `format_compact()`-Format) |
| `cli_long_report_contains_all_sections` | CLI-Aufruf ohne `--compact` produziert Output mit "ZUSAMMENFASSUNG", "WEGPUNKT-DETAILS"; bei `avalanche_regions` zusätzlich "LAWINENREGIONEN"; Trip-Name in UPPERCASE; Token-Zeile sichtbar |
| `cli_no_wintersport_formatter_import` | `grep -r "from formatters.wintersport" src tests` liefert null Treffer (Adversary-Test, prüft Big-Bang-Streichung §A1) |
| `cli_long_report_subject_unchanged` | Subject im Long-Report-Pfad bleibt `f"GZ {report_type.title()} - {trip.name}"` (wie heute) |

### Bestehender Golden bleibt grün (`tests/golden/sms/test_sms_golden.py`)

| Test | Asserts |
|---|---|
| `test_golden_arlberg_winter_morning` (vorhanden) | **Unverändert grün** — direkter `build_token_line(profile="wintersport")`-Pfad bleibt von β4 unberührt |

### Streichungen (Big-Bang)

`tests/test_formatters.py::TestWintersportFormatter` wird in Phase 6/GREEN-Schritt 5
**komplett gestrichen**. Datei wird leer oder ganz gelöscht. Folgende Tests entfallen:

- `test_format_basic`
- `test_format_includes_trip_name`
- `test_format_includes_summary`
- `test_format_includes_waypoints`
- `test_format_includes_avalanche_regions`
- `test_format_shows_warnings`
- `test_format_compact`
- `test_format_compact_includes_key_values`
- `test_format_report_type`

Ihre Inhalte sind in den oben gelisteten Renderer-Unit-Tests + CLI-Integration-Tests
abgedeckt (Trip-Name, Summary, Waypoints, Avalanche-Regions, Compact-Format,
Report-Type).

## Expected Behavior

- **Phase 5 RED:** Alle in §"Test Inventory" gelisteten **neuen** Tests (≈22) müssen
  fehlschlagen, weil:
  - `src/output/adapters/trip_result.py` existiert nicht (`ImportError`).
  - `src/output/renderers/text_report/` existiert nicht (`ImportError`).
  - `tests/golden/text_report/stubaier-skitour-evening.txt` existiert nicht
    (`FileNotFoundError`).
  - CLI-Pfad importiert noch `WintersportFormatter` — Integration-Tests scheitern an
    Format-Assertions.
- **Phase 6 GREEN:** Alle ≈22 neuen Tests grün; bestehende β1-Goldens
  (`arlberg-winter-morning`) unverändert grün; β2-Subject-Tests unverändert grün; β3-
  Renderer-Tests unverändert grün; `tests/test_formatters.py::TestWintersportFormatter`
  ist gelöscht.
- **Adversary-Phase 6b:** Implementation-Validator-Agent prüft:
  - `grep -r WintersportFormatter src tests` → null Treffer.
  - Adapter mit Edge-Case-Inputs (alle-None, sehr große Werte, leere Wegpunkte) bricht
    nicht.
  - Long-Report-Renderer mit ungültigen `report_type`-Werten verhält sich definiert
    (entweder Default-Behaviour oder klarer `ValueError`).

## Known Limitations

- HTML-Volltext-Goldens sind kein Bestandteil von β4 (Long-Report ist Plain-ASCII, kein
  HTML).
- Property-Tests (Hypothesis) sind kein Bestandteil von β4.
- Provider-seitige `avalanche_level`-Befüllung ist out-of-scope; der Adapter setzt
  `None` (siehe Spec §13). `AV`-Token-Coverage erfolgt über synthetische Fixtures
  (analog β1).

## Changelog

- 2026-04-28: Initial test manifest for β4 wintersport profile consolidation
  (TDD RED). Manifest deckt Adapter (`_trip_result_to_normalized`), neuen Renderer
  (`render_text_report`), CLI-Integration und Big-Bang-Streichung der
  `TestWintersportFormatter`-Klasse ab.
