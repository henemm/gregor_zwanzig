---
entity_id: bug_353_trend_forecast_horizon
type: module
created: 2026-05-26
updated: 2026-05-26
status: draft
version: "1.0"
tags: [weather, trend, openmeteo, forecast-horizon, bugfix]
---

# Bug #353: Mehrtages-Trend überschreitet Open-Meteo-Vorhersagehorizont

## Approval

- [ ] Approved

## Purpose

Der Mehrtages-Trend (`_build_stage_trend`) fragt Wetter für **jede** zukünftige Etappe ab.
Liegt eine Etappe mehr als ~15 Tage in der Zukunft, antwortet Open-Meteo mit HTTP 400
(`start_date out of allowed range`) — denn **kein** Open-Meteo-Modell reicht weiter als
`today+15` (empirisch bestätigt, endpoint-übergreifend). Folge bisher: verschwendeter
API-Call, ERROR-Rauschen in der Diagnose, kaputtes/leeres Trend-Segment. Dieser Fix
überspringt nicht-vorhersagbare Etappen **proaktiv vor dem Call** — kein Call, kein Fehler,
keine Trend-Zeile. Etappen innerhalb des Horizonts bleiben unverändert.

## Source

- **File:** `src/services/trip_report_scheduler.py`
- **Identifier:** `_build_stage_trend` (Trend-Schleife über `trip.get_future_stages`)
- **File:** `src/providers/openmeteo.py`
- **Identifier:** neue Konstante `OPENMETEO_MAX_FORECAST_DAYS` + reine Hilfsfunktion
  `is_within_forecast_horizon(stage_date, reference_date)`

> **Schicht:** Python-Backend (`src/services/`, `src/providers/`). Kein Frontend, kein Go.
> Bestätigt per grep: `_build_stage_trend` existiert nur in `src/services/trip_report_scheduler.py`.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `OpenMeteoProvider.fetch_forecast` | upstream | erzeugt den 400 bei fernem `start_date` |
| `_fetch_weather` (scheduler) | upstream | fängt heute jede Exception → `logger.error` + has_error-Placeholder (Rauschquelle) |
| `multi_day_trend` (Spec v3.0) | sibling | definiert den Trend-Algorithmus, der hier geschützt wird |
| `providers/call_log.py` | observability | Call-Counter (#338) — Nachweis „kein Call" |

## Implementation Details

```
# src/providers/openmeteo.py
# Empirisch (2026-05-25, echte Diagnose-Calls): /v1/meteofrance, /v1/dwd-icon, /v1/ecmwf,
# /v1/gfs erlauben start_date nur bis today+15; +16 → HTTP 400. Grenze ist modell-/
# endpoint-übergreifend identisch (Open-Meteo validiert vor dem Modell-Processing).
OPENMETEO_MAX_FORECAST_DAYS = 15

def is_within_forecast_horizon(stage_date: date, reference_date: date) -> bool:
    """True, wenn stage_date <= reference_date + OPENMETEO_MAX_FORECAST_DAYS.
    Reine Funktion, deterministisch testbar (keine API, keine Mocks)."""
    return (stage_date - reference_date).days <= OPENMETEO_MAX_FORECAST_DAYS

# src/services/trip_report_scheduler.py  — in _build_stage_trend, in der Etappen-Schleife:
today = date.today()
for stage in future_stages:
    if not is_within_forecast_horizon(stage.date, today):
        logger.debug(
            "Stage %s (%s) beyond Open-Meteo forecast horizon (today+%d), skipping trend",
            stage.id, stage.date, OPENMETEO_MAX_FORECAST_DAYS,
        )
        continue
    # ... unveränderter Fetch + Summary
```

## Expected Behavior

- **Input:** Trip mit zukünftigen Etappen, `target_date`, `tz`.
- **Output:** Trend-Liste nur für Etappen mit `stage.date <= today + 15`; fernere Etappen
  fehlen (kein Eintrag).
- **Side effects:** Für übersprungene Etappen **kein** Open-Meteo-Call und **kein**
  `logger.error`; höchstens ein `logger.debug`.

## Acceptance Criteria

- **AC-1:** Given ein Trip mit einer zukünftigen Etappe, deren Datum mehr als 15 Tage nach
  `date.today()` liegt / When `_build_stage_trend` läuft / Then enthält das Ergebnis **keine**
  Trend-Zeile für diese Etappe und der Open-Meteo-Call-Counter (`providers.call_log`) wird für
  sie **nicht** erhöht (kein API-Call abgesetzt)
  - Test: (populated after /tdd-red)

- **AC-2:** Given ein Trip mit einer zukünftigen Etappe innerhalb von 15 Tagen ab
  `date.today()` / When `_build_stage_trend` läuft / Then erscheint diese Etappe wie bisher mit
  Wetter-Summary im Trend-Ergebnis (Verhalten unverändert)
  - Test: `tests/tdd/test_bug_353_trend_horizon.py::TestNearStagesWithinHorizon`

- **AC-3:** Given eine Etappe wird wegen Horizont-Überschreitung übersprungen / When dies
  geschieht / Then wird **kein** `logger.error` ausgelöst (Diagnose-Rauschen beseitigt) —
  zulässig ist höchstens ein `logger.debug`
  - Test: (populated after /tdd-red)

- **AC-4:** Given die reine Funktion `is_within_forecast_horizon(stage_date, reference_date)` /
  When `stage_date == reference_date + 15 Tage` / Then liefert sie `True`; und When
  `stage_date == reference_date + 16 Tage` / Then liefert sie `False` (Grenze exakt `today+15`,
  empirisch bestätigt)
  - Test: (populated after /tdd-red)

- **AC-5:** Given der Hauptbericht-Pfad (`generate_trip_report` → `_fetch_weather`, fragt nur
  heute/morgen ab) / When ein Report gebaut wird / Then bleibt das `has_error`-Placeholder-
  Verhalten (WEATHER-04) vollständig unverändert — die Horizont-Prüfung greift ausschließlich
  in `_build_stage_trend`, nicht in `_fetch_weather` oder `fetch_forecast`
  - Test: `tests/tdd/test_bug_353_trend_horizon.py::TestGuardOnlyInTrendPath`

- **AC-6:** Given ein kurzer Trip, dessen Etappen alle innerhalb 15 Tagen liegen / When
  `_build_stage_trend` läuft / Then ist das Trend-Ergebnis byte-identisch zum Verhalten vor dem
  Fix (Backward-Compatibility, keine Regression für den Normalfall)
  - Test: `tests/tdd/test_bug_353_trend_horizon.py::TestBackwardCompatNoSkipForNearTrip`

## Known Limitations

- Etappen jenseits `today+15` bekommen **keine** Vorschau — das ist eine physikalische Grenze
  numerischer Wettervorhersage (kein Modell reicht weiter), kein behebbares Defizit. Sobald die
  Tour näher rückt, fällt die Etappe automatisch in den Horizont und erscheint im Trend.
- Die Grenze `OPENMETEO_MAX_FORECAST_DAYS = 15` ist konservativ gegen die empirische
  Open-Meteo-Obergrenze gesetzt. Sollte Open-Meteo den Horizont künftig ändern, ist nur die
  Konstante anzupassen.

## Test Strategy (KEINE Mocks — CLAUDE.md)

- **AC-4** direkt gegen die reine Funktion — vollständig deterministisch, ohne API.
- **AC-1/AC-2/AC-3/AC-6** als Integrationstest mit echten Trip-Objekten + `FixtureProvider`
  (#263, `GZ_TEST_FIXTURE_DIR`) statt Live-API; „kein Call" via `providers.call_log`-Counter
  (vgl. `tests/tdd/test_bug_338_openmeteo_call_counter.py`).
- **AC-5** durch Inspektion: Horizont-Logik existiert nur in `_build_stage_trend`; `_fetch_weather`
  bleibt unverändert (Diff-Review).
