---
entity_id: bug_338_openmeteo_call_counter_tests
type: tests
created: 2026-05-22
updated: 2026-05-22
status: draft
version: "1.0"
tags: [tests, observability, open-meteo, api-limit, diagnostics, issue-338]
parent: bug_338_openmeteo_call_counter
phase: phase5_tdd_red
---

# Issue #338 — Open-Meteo Abruf-Zaehler (Tests)

## Approval

- [x] Approved

## Purpose

Test-Manifest fuer den Diagnose-Zaehler aus
`docs/specs/modules/bug_338_openmeteo_call_counter.md`. Jeder pytest-Test mappt
1:1 auf ein Acceptance Criterion der Parent-Spec.

Parent-Spec: `docs/specs/modules/bug_338_openmeteo_call_counter.md` v1.0

## Source

- **File:** `tests/tdd/test_bug_338_openmeteo_call_counter.py` (NEU — Tests fuer
  JSONL-Logging, Quellen-Bestimmung via Stack, Fail-Soft-Verhalten und
  Auswertungs-Skript)

## Test Inventory

### Python (`tests/tdd/test_bug_338_openmeteo_call_counter.py`)

| Test-Funktion | AC | Was geprueft wird |
|---|---|---|
| `test_ac1_fetch_forecast_appends_one_jsonl_line` | AC-1 | Echter `fetch_forecast()`-Aufruf (200 oder 429) haengt genau eine JSONL-Zeile mit `ts`, `endpoint` (host+path ohne Query), `status`, `source` an. |
| `test_ac2_alarm_path_sets_source_alarm` | AC-2 | Abruf aus echtem Alarm-Pfad `TripAlertService._fetch_fresh_weather` liefert `source == "alarm"`. |
| `test_ac2_trend_path_sets_source_trend` | AC-2 | Abruf aus echtem Mehrtages-Trend-Pfad `TripReportSchedulerService._build_stage_trend` liefert `source == "trend"`. |
| `test_ac2_preview_path_sets_source_vorschau` | AC-2 (F002) | Abruf aus echtem Vorschau-Pfad `PreviewService.render_email_preview` (Trip henning/5f534011) liefert `source == "vorschau"` und NICHT `"briefing"`. |
| `test_ac3_unwritable_log_target_is_swallowed` | AC-3 | Nicht-beschreibbares Diagnose-Ziel (Pfad unter einer Datei): `_log_api_call` schluckt den Fehler, `fetch_forecast` laeuft unveraendert weiter (kein Logging-Crash). |
| `test_ac4_analyze_script_breaks_down_by_source_endpoint_hour` | AC-4 | `scripts/analyze_openmeteo_calls.py` schluesselt eine befuellte JSONL nach `source`, `endpoint` und Stunde auf inkl. Status-Quote. |

## Implementation Details

Tests folgen dem No-Mocks-Pattern des Projekts:
- Echte `OpenMeteoProvider`-, `TripAlertService`- und
  `TripReportSchedulerService`-Aufrufpfade
- `TripReportSchedulerService`/`TripAlertService` minimal via `__new__()`
- JSONL-Pfad-Isolation via `DIAGNOSTICS_PATH`-Umkonfiguration auf `tmp_path`
  (Konfiguration, kein Mock)
- AC-3 nutzt ein echtes nicht-beschreibbares Ziel (Pfad unter einer Datei)
- Keine `Mock()`, `patch()`, `MagicMock`

In RED-Phase schlagen alle Tests fehl, weil `DIAGNOSTICS_PATH`,
`_log_api_call`, `_resolve_call_source` und `scripts/analyze_openmeteo_calls.py`
noch nicht existieren.

## Expected Behavior

- **Input:** Echte Innsbruck-Koordinaten; minimale Trip/Stage/Segment-Objekte;
  vorbereitete JSONL-Fixture.
- **Output:** Assertions ueber JSONL-Zeilen-Felder, `source`-Werte, Fail-Soft
  und Skript-Ausgabe.
- **Side effects:** Echte OpenMeteo-Requests (429 erlaubt, da Limit erschoepft);
  Schreibvorgaenge ausschliesslich in `tmp_path`.

## Acceptance Criteria

- **AC-T1:** Given die Test-Datei existiert und Implementierung fehlt /
  When `pytest tests/tdd/test_bug_338_openmeteo_call_counter.py -v` laeuft /
  Then schlagen alle 5 Tests fehl (RED-Phase erfolgreich).

- **AC-T2:** Given GREEN-Phase abgeschlossen /
  When `pytest tests/tdd/test_bug_338_openmeteo_call_counter.py -v` ausgefuehrt /
  Then alle 5 Tests gruen, keine Mocks.

## Known Limitations

- AC-1/AC-2/AC-3-Tests machen echte Wetter-API-Calls (429 ist hier ein
  valider, erwuenschter Pfad — der Zaehler muss auch 429 protokollieren).
- Quellen-Heuristik ist stack-basiert; bei unerwarteten Aufrufpfaden moeglich
  `source == "unbekannt"` (akzeptiert, eigenes Signal).

## Changelog

- 2026-05-22: Initial — Test-Manifest fuer Issue #338 (Open-Meteo Abruf-Zaehler).
