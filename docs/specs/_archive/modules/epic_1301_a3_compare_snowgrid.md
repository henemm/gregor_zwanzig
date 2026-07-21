---
entity_id: epic_1301_a3_compare_snowgrid
type: module
created: 2026-07-17
updated: 2026-07-17
status: draft
version: "1.0"
tags: [compare, trip, provider, snow, snowgrid, refactor, epic-1301]
---

# A3 — Schnee vom Landesdienst als Ergänzung (gemeinsamer Weg + Touren-Bonus)

## Approval

- [x] Approved (PO 2026-07-17, „Lgtm")

## Purpose

Nach A2 holen Vergleich und Trip Wetter über openmeteo, das keine Schneewerte
liefert. A3 ergänzt für Orte im SNOWGRID-Abdeckungsgebiet (Alpen) die Werte
`snow_depth_cm` und `swe_kgm2` über `GeoSphereProvider.fetch_snowgrid` und füllt
sie **fill-only** in die openmeteo-Zeitreihe ein — am **gemeinsamen** Punkt
`OpenMeteoProvider.fetch_forecast`, damit Vergleichs-Mail **und** Tour-Briefings
Schnee zeigen (PO-Entscheid 2026-07-17: gemeinsamer Weg + Touren-Bonus). Der
15-Minuten-Alarm-Check bleibt über einen neuen Schalter `enrich_snow=False` von
dem zusätzlichen Abruf ausgenommen (Bug #288-Klasse).

## Source

- **File:** `src/providers/openmeteo.py` — `OpenMeteoProvider.fetch_forecast`
- **File:** `src/providers/geosphere.py` — SNOWGRID-Bounds-Helper + `fetch_snowgrid`
- **File:** `src/services/segment_weather.py` — `fetch_segment_weather`
- **File:** `src/services/trip_alert.py`, `src/services/compare_location_weather_source.py`

Python-Core / Domain-Backend (`src/providers/`, `src/services/`).

## Estimated Scope

- **LoC:** ~130–200 (Quelle + Tests). Falls >250 → PO-Override erfragen.
- **Files:** 5 Quelle + 1 Test.
- **Effort:** medium.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `GeoSphereProvider.fetch_snowgrid` (`geosphere.py:288`) | uses | SNOWGRID-Snapshot `(snow_depth_cm, swe_kgm2)`, fail-soft |
| UV-Merge-Muster (`openmeteo.py:903-920`) | pattern | Fill-only-Stamp per Timestamp — Vorbild |
| `fetch_forecast` Konsumenten | dependents | Trip-Report, Compare-Report, Alert-Checks |

## Implementation Details

```
1. geosphere.py — Bounds-Helper (co-located mit fetch_snowgrid):
   SNOWGRID_BOUNDS = {min_lat:45.0, max_lat:50.0, min_lon:8.0, max_lon:18.0}
   def snowgrid_covers(lat, lon) -> bool  (inklusive Grenzen)

2. openmeteo.py — fetch_forecast:
   - Signatur: ... enrich_ensemble: bool = True, enrich_snow: bool = True
   - Reine Gating-Funktion (modul- oder methodenlokal, testbar):
       _should_enrich_snow(enrich_snow, lat, lon) -> bool
         = enrich_snow and geosphere.snowgrid_covers(lat, lon)
   - Reine Stamp-Funktion (fill-only, testbar):
       _stamp_snow(timeseries, snow_depth_cm, swe_kgm2) -> list[str]
         setzt dp.snow_depth_cm / dp.swe_kgm2 NUR wenn dort None; gibt die
         tatsächlich gefüllten Param-Namen zurück (["snow_depth","swe_tot"]).
   - Enrichment-Aufruf (best-effort, try/except Exception → no-op):
       if _should_enrich_snow(enrich_snow, lat, lon):
           try:
               sd, swe = GeoSphereProvider().fetch_snowgrid(lat, lon)  # lazy import
               if sd is not None or swe is not None:
                   filled = _stamp_snow(timeseries, sd, swe)
                   if filled:
                       meta.fallback_metrics = sorted(set(meta.fallback_metrics or []) | set(filled))
                       if meta.fallback_reason is None:
                           meta.fallback_reason = "snow_geosphere"
           except Exception: pass
   - Platzierung: unmittelbar vor der Hauptrückgabe (:997) UND vor der
     Cross-Provider-Rückgabe (:887). enrich_snow wird NICHT in den
     Fremdprovider-Call (:882) durchgereicht (fremde Provider kennen den Param
     nicht) — die Anreicherung passiert danach in openmeteo.

3. segment_weather.py:
   - fetch_segment_weather(..., enrich_ensemble=..., enrich_snow: bool = True)
   - an fetch_forecast (:136) durchreichen: enrich_snow=enrich_snow.

4. Alarm-Checks auf False (die zwei echten 15-Min-Pfade):
   - trip_alert.py:836          → enrich_snow=False
   - compare_location_weather_source.py:51 → enrich_snow=False

Keine Änderung an comparison_engine.py — die Snow-Extraktion (415-425) greift
automatisch, sobald forecast.data Schneewerte trägt.
```

## Expected Behavior

- **Input:** Standort mit Koordinaten; Aufruf über den gemeinsamen `fetch_forecast`.
- **Output:** Für Alpen-Orte (SNOWGRID-Bounds) mit `enrich_snow=True` tragen die
  Datenpunkte `snow_depth_cm`/`swe_kgm2` aus SNOWGRID (fill-only, kein Überschreiben);
  Herkunft in `meta.fallback_metrics`. Nicht-Alpen-Orte und `enrich_snow=False`
  unverändert (kein SNOWGRID-Call).
- **Side effects:** ein zusätzlicher SNOWGRID-HTTP-Call pro `fetch_forecast` in den
  Report-/Display-Pfaden für Alpen-Orte; fail-soft.

## Known Limitations (Teil der Freigabe)

1. **Nur `snow_depth_cm` + `swe_kgm2`** aus SNOWGRID. `snowfall_limit_m`
   (Schneefallgrenze) ist ein AROME-Feld, nicht SNOWGRID — außerhalb A3.
2. **Ein SNOWGRID-Call pro Etappe/Ort** im Briefing (kein Cache); Region-gleich,
   für den ersten Wurf akzeptiert (Briefing läuft im Hintergrund, Cockpit parallel).
3. **Touren-Bonus opt-in:** Schnee erscheint im Trip-Briefing nur, wenn der Nutzer
   die Metrik `snow_depth` aktiviert hat (bestehendes Verhalten `trip_report.py:214`).

## Acceptance Criteria

- **AC-1:** Given eine openmeteo-Zeitreihe, deren Datenpunkte `snow_depth_cm=None`
  haben / When `_stamp_snow(ts, 42.0, 120.0)` läuft / Then tragen alle Datenpunkte
  `snow_depth_cm=42.0` und `swe_kgm2=120.0`, und die Rückgabe listet die gefüllten
  Params.
  - Test: Kern, netzfrei, reine Funktion. Zusätzlich: ein Datenpunkt mit bereits
    gesetztem `snow_depth_cm=10.0` wird NICHT überschrieben (fill-only).

- **AC-2:** Given die Gating-Logik / When `_should_enrich_snow(enrich_snow, lat, lon)`
  aufgerufen wird / Then liefert sie True nur für `enrich_snow=True` UND Koordinaten
  in den SNOWGRID-Bounds (Alpen); False bei `enrich_snow=False` oder außerhalb (z. B.
  Mallorca 39.7/2.6).
  - Test: Kern, netzfrei; Innsbruck+True→True, Innsbruck+False→False, Mallorca+True→False,
    Grenzen (45.0/8.0 und 50.0/18.0) inklusiv.

- **AC-3:** Given ein Alpen-Ort über den gemeinsamen `fetch_forecast` mit Default
  `enrich_snow=True` / When echtes SNOWGRID Schnee liefert / Then trägt das Ergebnis
  `snow_depth_cm` (aus SNOWGRID) und `meta.fallback_metrics` enthält den Snow-Param;
  ein bereits gesetzter `fallback_reason` (`model_5xx`/`metric_gap`) wird NICHT
  überschrieben.
  - Test: `live`-markiert (echter GeoSphere+openmeteo-Call).

- **AC-4:** Given der 15-Minuten-Alarm-Check (`compare_location_weather_source.fetch`
  bzw. `trip_alert`) / When er läuft / Then ruft er `fetch_forecast`/`fetch_segment_weather`
  mit `enrich_snow=False` — kein zusätzlicher SNOWGRID-Call.
  - Test: Kern, netzfrei — die Aufrufstellen übergeben `enrich_snow=False` (belegbar
    über die Gating-Funktion: `_should_enrich_snow(False, 47.3, 11.4) is False`), bzw.
    ein `live`/Integrationstest zeigt kein Snow-Enrichment im Alert-Pfad.

- **AC-5:** Given der Trip-Briefing-Pfad (Alpen-Etappe, Metrik `snow_depth` aktiv) /
  When das Briefing erzeugt wird / Then trägt die Etappe SNOWGRID-Schnee (Bonus).
  - Test: `live`/Integration — Trip-Segment über `fetch_segment_weather` (Default
    enrich_snow=True) für Alpen-Koordinaten liefert `snow_depth_cm != None`.

## Regression Protection

- Nicht-Alpen-Orte: kein SNOWGRID-Call, kein Verhaltenswandel.
- Bestehende WEATHER-05b / metric_gap-Provenance bleibt unangetastet (non-clobber).
- A2-Kern-Test (`test_a2_compare_openmeteo_metrics.py`) bleibt grün.

## Out of Scope

- `snowfall_limit_m` (AROME) · SNOWGRID-Caching · Anheben forecast_hours (A4) · Renderer/UI.
