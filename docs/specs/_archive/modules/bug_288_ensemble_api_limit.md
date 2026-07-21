---
entity_id: bug_288_ensemble_api_limit
type: bugfix
created: 2026-05-20
updated: 2026-05-20
status: draft
version: "1.0"
tags: [bugfix, ensemble, api-limit, open-meteo, alert-check, trip-report, issue-288]
---

<!-- Issue #288 — Ensemble-API: 624 Calls/Tag erschöpfen kostenloses Limit; Ensemble auf 1 Call/Report + 0 Calls/Alert-Check reduzieren -->

# Issue #288 — Bug-Fix: Ensemble-API nur 1x täglich abrufen, nicht bei jedem Alert-Check

## Approval

- [ ] Approved

## Zweck

Die Ensemble-API (`ensemble-api.open-meteo.com`) wird aktuell bei jedem Alert-Check (alle 30 Minuten × 13 Segmente) aufgerufen, was zu 624 API-Calls pro Tag führt. Das kostenlose Tageslimit wird dadurch täglich um ca. 04:27 Uhr erschöpft, wonach alle Wetterdaten-Abrufe bis Mitternacht fehlschlagen. Der Fix reduziert Ensemble-Calls auf exakt 1 Call pro Report-Lauf (für den letzten Wegpunkt der letzten Etappe) und 0 Calls bei Alert-Checks, indem ein `enrich_ensemble`-Flag durch den gesamten Provider- und Service-Stack propagiert wird.

## Quelle / Source

**Geänderte Dateien:**

- `src/providers/base.py` — Protocol-Signatur `fetch_forecast()` um Parameter `enrich_ensemble: bool = True` erweitern
- `src/providers/openmeteo.py` — Flag auswerten: bei `False` wird `_fetch_ensemble_spread()` nicht aufgerufen; `confidence_pct = None`
- `src/providers/geosphere.py` — Parameter `enrich_ensemble: bool = True` annehmen, ignorieren (kein Ensemble-Support)
- `src/services/segment_weather.py` — Flag von Caller entgegennehmen und an `fetch_forecast()` durchreichen
- `src/services/trip_alert.py` — `fetch_segment_weather()` mit `enrich_ensemble=False` aufrufen
- `src/services/trip_report_scheduler.py` — `_fetch_weather()` und `_fetch_night_weather()` mit `enrich_ensemble=False`; neue Methode `_enrich_ensemble_for_trip()` für den einmaligen Post-Fetch-Ensemble-Call

**Neue Test-Datei:**

- `tests/tdd/test_bug_288_ensemble_api_limit.py`

> **Schicht-Hinweis:** Alle Änderungen liegen ausschließlich im Python-Backend-Layer (`src/providers/`, `src/services/`). Frontend und Go-API sind nicht betroffen.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/providers/base.py` | Python-Protocol | Definiert `fetch_forecast()`-Signatur, die alle Provider implementieren müssen |
| `src/providers/openmeteo.py` | Python-Klasse | Implementiert `fetch_forecast()` und ruft `_fetch_ensemble_spread()` intern auf |
| `src/providers/geosphere.py` | Python-Klasse | Implementiert `fetch_forecast()` ohne Ensemble-Support; muss Parameter akzeptieren |
| `src/services/segment_weather.py` | Python-Service | Vermittelt zwischen Scheduler/Alert und Provider; propagiert Flag |
| `src/services/trip_alert.py` | Python-Service | Führt Alert-Checks durch; darf keine Ensemble-Calls auslösen |
| `src/services/trip_report_scheduler.py` | Python-Service | Führt Report-Fetches durch; ruft Ensemble einmalig nach Segment-Fetches auf |
| `src/app/trip.py` | Python-Datenmodell | Stellt `Stage.last_waypoint` Property bereit (lat, lon, elevation_m) |
| `ForecastDataPoint` | Python-Dataclass | Hält `.confidence_pct`, `.spread_t2m_k`, `.spread_precip_mm` für Propagation |
| `SegmentWeatherSummary` | Python-Dataclass | Hält `.confidence_pct_min`; ist nicht frozen, kann nachträglich gesetzt werden |

## Implementation Details

### 1. `src/providers/base.py` — Protocol-Signatur erweitern

```python
# Vorher:
def fetch_forecast(self, location: Location, start: date, end: date) -> ForecastResult: ...

# Nachher:
def fetch_forecast(
    self, location: Location, start: date, end: date,
    enrich_ensemble: bool = True
) -> ForecastResult: ...
```

Default `True` stellt backward-compatibility für alle bestehenden direkten Aufrufer sicher.

### 2. `src/providers/openmeteo.py` — Flag auswerten

Im Body von `fetch_forecast()` den bestehenden `_fetch_ensemble_spread()`-Aufruf mit dem Flag absichern:

```python
if enrich_ensemble:
    ensemble_data = self._fetch_ensemble_spread(location, start, end)
    # bestehende Confidence-Berechnung läuft wie bisher
else:
    # confidence_pct bleibt None auf allen DataPoints
    pass
```

Kein weiterer Umbau — die Timestamp-Normalisierung (tz-aware/naive, analog Zeilen 770–787) bleibt im bestehenden Ensemble-Pfad unverändert.

### 3. `src/providers/geosphere.py` — Parameter annehmen, ignorieren

```python
def fetch_forecast(
    self, location: Location, start: date, end: date,
    enrich_ensemble: bool = True  # ignoriert, kein Ensemble-Support
) -> ForecastResult: ...
```

Kein Funktionslogik-Umbau, nur Signatur-Anpassung.

### 4. `src/services/segment_weather.py` — Flag durchreichen

`fetch_segment_weather()` erhält neuen Parameter `enrich_ensemble: bool = True` und übergibt ihn an den Provider-Aufruf:

```python
def fetch_segment_weather(
    ..., enrich_ensemble: bool = True
) -> SegmentWeatherSummary:
    result = provider.fetch_forecast(..., enrich_ensemble=enrich_ensemble)
    ...
```

### 5. `src/services/trip_alert.py` — 0 Ensemble-Calls

Aufruf `fetch_segment_weather()` mit explizitem `enrich_ensemble=False`:

```python
summary = fetch_segment_weather(..., enrich_ensemble=False)
```

Alerts zeigen keine Confidence-Daten, daher ist `confidence_pct=None` auf allen DataPoints akzeptabel.

### 6. `src/services/trip_report_scheduler.py` — 1 Ensemble-Call pro Report

**6a. `_fetch_weather()` und `_fetch_night_weather()` — ohne Ensemble:**

```python
summary = fetch_segment_weather(..., enrich_ensemble=False)
```

Beide Methoden bekommen `enrich_ensemble=False`, da Ensemble danach separat und einmalig ergänzt wird.

**6b. Neue Methode `_enrich_ensemble_for_trip()`:**

```python
def _enrich_ensemble_for_trip(self, trip: Trip, weather_data: dict) -> None:
    # 1. Letzten Wegpunkt der letzten Etappe ermitteln
    last_wp = trip.stages[-1].last_waypoint  # hat lat, lon, elevation_m

    # 2. Zeitraum: Report-Startdatum bis Report-Enddatum
    # (identisch mit dem Fetch-Zeitraum des gesamten Reports)

    # 3. Einmaliger Ensemble-API-Call
    ensemble_data = self._provider._fetch_ensemble_spread(
        location=last_wp, start=start_date, end=end_date
    )

    # 4. confidence_pct pro Zeitstempel berechnen
    # (analog zu bestehender Logik in openmeteo.py)
    confidence_by_ts = compute_confidence_pct(ensemble_data)

    # 5. Confidence-Werte auf alle DataPoints aller Segmente propagieren
    for segment_summary in weather_data.values():
        for dp in segment_summary.data_points:
            ts_key = normalize_ts(dp.timestamp)  # tz-aware/naive analog Zeilen 770-787
            dp.confidence_pct = confidence_by_ts.get(ts_key)
            dp.spread_t2m_k = ensemble_data.spread_t2m_k.get(ts_key)
            dp.spread_precip_mm = ensemble_data.spread_precip_mm.get(ts_key)

        # 6. confidence_pct_min nachträglich neu setzen
        # (SegmentWeatherSummary ist nicht frozen)
        valid = [dp.confidence_pct for dp in segment_summary.data_points
                 if dp.confidence_pct is not None]
        segment_summary.confidence_pct_min = min(valid) if valid else None
```

**6c. Aufruf-Reihenfolge im Report-Run:**

```python
weather_data = self._fetch_weather(trip, ...)       # N Segment-Fetches, kein Ensemble
self._enrich_ensemble_for_trip(trip, weather_data)  # 1 Ensemble-Call, danach Propagation
```

### 7. LoC-Budget

| Datei | Δ LoC | Zählt |
|-------|--------|-------|
| `src/providers/base.py` | +3 | ja |
| `src/providers/openmeteo.py` | +8 | ja |
| `src/providers/geosphere.py` | +3 | ja |
| `src/services/segment_weather.py` | +5 | ja |
| `src/services/trip_alert.py` | +2 | ja |
| `src/services/trip_report_scheduler.py` | ~55 | ja |
| `tests/tdd/test_bug_288_ensemble_api_limit.py` | ~80 | ja |
| **Gesamt (zählend)** | **~156** | **< 250 LoC-Limit** |

## Expected Behavior

- **Input:** Bestehende Trip-Report- und Alert-Check-Flows ohne Änderungen am Aufrufer
- **Output:**
  - Alert-Check: 0 Ensemble-API-Calls; `confidence_pct=None` auf allen DataPoints (akzeptabel, Alerts zeigen keine Confidence)
  - Report-Run: Genau 1 Ensemble-API-Call für den letzten Wegpunkt der letzten Etappe; `confidence_pct` auf allen DataPoints aller Segmente befüllt; E-Mail-Hint und SMS-C-Token funktionieren unverändert
- **Side effects:**
  - Alle anderen direkten Aufrufer von `fetch_forecast()` sind durch `enrich_ensemble=True` als Default unverändert (backward-compatible)
  - `_build_stage_trend()` ruft `_fetch_weather()` auf und erhält korrekt `enrich_ensemble=False` automatisch durch die Änderung an `_fetch_weather()`
  - Bei einetappigen Trips: `trip.stages[-1]` ist identisch mit `trip.stages[0]`; Logik funktioniert korrekt

## Acceptance Criteria

- **AC-1:** Given ein laufender Alert-Check für einen Trip mit N Segmenten / When `trip_alert._fetch_fresh_weather()` aufgerufen wird / Then wird `ensemble-api.open-meteo.com` nicht aufgerufen und alle zurückgegebenen DataPoints haben `confidence_pct=None`
  - Test: (populated after /tdd-red)

- **AC-2:** Given ein Report-Run (Morgen- oder Abend-Briefing) für einen Trip mit N Etappen / When der vollständige Fetch-Zyklus abgeschlossen ist / Then wurde `ensemble-api.open-meteo.com` genau einmal aufgerufen, für den letzten Waypoint der letzten Etappe (`trip.stages[-1].last_waypoint`)
  - Test: (populated after /tdd-red)

- **AC-3:** Given ein Report-Run mit erfolgreichem Ensemble-Call / When E-Mail und SMS gerendert werden / Then erscheint `build_confidence_hint()` im E-Mail-Body (wenn Confidence < 60 %) und der SMS-C-Token ist `C+`, `C~` oder `C?` entsprechend dem berechneten `confidence_pct_min`
  - Test: (populated after /tdd-red)

- **AC-4:** Given ein direkter Aufruf von `fetch_forecast()` ohne `enrich_ensemble`-Argument / When der Aufruf ausgeführt wird / Then verhält sich der Code identisch zu vor dem Fix (Default `True`; Ensemble wird abgerufen wie bisher)
  - Test: (populated after /tdd-red)

- **AC-5:** Given ein Trip mit genau einer Etappe / When `_enrich_ensemble_for_trip()` aufgerufen wird / Then wird `trip.stages[-1].last_waypoint` korrekt aufgelöst (kein IndexError, kein falscher Waypoint); Ensemble-Daten werden auf den einzigen Segment-Summary propagiert
  - Test: (populated after /tdd-red)

## Known Limitations

- **Confidence-Granularität reduziert:** Ein einziger Ensemble-Call für den letzten Wegpunkt repräsentiert nicht die meteorologische Variabilität entlang der gesamten Route. Für Touren mit starken Höhenunterschieden oder mehreren Klimazonen kann die Confidence-Aussage unscharf sein. Dies ist ein bewusster Trade-off gegen das API-Limit-Problem.
- **`_fetch_ensemble_spread()` ist private Methode:** `_enrich_ensemble_for_trip()` greift direkt auf `self._provider._fetch_ensemble_spread()` zu. Wenn der Provider kein Ensemble unterstützt (z.B. Geosphere), muss dieser Aufruf mit einem `hasattr`-Guard abgesichert werden.
- **Propagation basiert auf Timestamp-Matching:** Ensemble-Daten und Segment-DataPoints müssen kompatible Timestamps haben. Timezone-Handling muss analog zur bestehenden Normalisierung in `openmeteo.py:770-787` erfolgen; Abweichungen führen zu `None`-Confidence.

## Out of Scope

- Caching von Ensemble-Daten über mehrere Report-Läufe hinweg (wäre Optimierung für spätere Issue)
- Ensemble-Support für Geosphere-Provider
- Anpassung der Confidence-Logik im Frontend oder in der E-Mail-Template-Struktur
- Erhöhung des API-Limits durch kostenpflichtige Open-Meteo-Subscription

## Changelog

- 2026-05-20: Initial spec erstellt. Reduziert Ensemble-API-Calls von 624/Tag auf 1/Report + 0/Alert-Check via `enrich_ensemble`-Flag durch Provider- und Service-Stack. Betrifft 6 Python-Dateien in `src/providers/` und `src/services/`.
