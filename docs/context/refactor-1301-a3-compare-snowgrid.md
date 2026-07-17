# Context + Analysis: A3 — Schnee vom Landesdienst als Ergänzung (Epic #1301)

## Request Summary
Nach A2 holt der Vergleich (und der Trip) Wetter über openmeteo, das keine
Schneewerte liefert (`snow_depth_cm`/`swe_kgm2` = None). A3 ergänzt für Orte im
SNOWGRID-Abdeckungsgebiet (Alpen, lat 45–50 / lon 8–18) die Schneewerte über
`GeoSphereProvider.fetch_snowgrid` und füllt sie **fill-only** in die
openmeteo-Zeitreihe ein. **PO-Entscheid 2026-07-17: gemeinsamer Weg + Touren-Bonus**
— das Einfüllen sitzt am einzigen gemeinsamen Punkt aller Pfade
(`OpenMeteoProvider.fetch_forecast`), damit Vergleich UND Tour-Briefings Schnee sehen.

## Type
Refactor/Feature (gemeinsamer Datenpfad-Baustein). Full Process.

## Der gemeinsame Seam (belegt)
`OpenMeteoProvider.fetch_forecast` (`openmeteo.py:741`) ist der EINZIGE Punkt, den
alle vier Pfade durchlaufen:
- Trip-Report: `trip_report_scheduler.py:1105/1218` → `SegmentWeatherService.fetch_segment_weather` (`segment_weather.py:136`) → `fetch_forecast`
- Trip-Waypoint: `trip_forecast.py:156` → `fetch_forecast`
- Compare-Report: `comparison_engine.fetch_forecast_for_location` → `ForecastService.get_forecast` (`forecast.py:85`) → `fetch_forecast`
- Compare-/Trip-Alert (15-Min): `compare_location_weather_source.py:51` / `trip_alert.py:836` → `fetch_segment_weather` → `fetch_forecast`

## Kosten-Falle & neuer Schalter
Ein bedingungsloses Snow-Enrichment in `fetch_forecast` würde bei jedem
15-Minuten-Alarm-Check einen zusätzlichen SNOWGRID-Call auslösen (Bug #288-Klasse).
Der vorhandene `enrich_ensemble`-Schalter taugt NICHT als Diskriminator (der
Trip-Report nutzt ihn auch mit `False`). → **Neuer orthogonaler Schalter
`enrich_snow: bool = True`**; nur die zwei echten Alarm-Checks setzen ihn auf `False`.

### Klassifikation der Aufrufstellen
| Aufruf | Pfad | enrich_snow |
|--------|------|-------------|
| `trip_report_scheduler.py:1105/1218` | Trip-Briefing (rendert Schnee, SN-Token) | Default **True** (Bonus) |
| `forecast.py:85` (ComparePreview/Report) | Vergleichs-Mail | Default **True** (behebt A2-Regression) |
| `trip_forecast.py:156` | Waypoint-Forecast | Default **True** |
| `stage_weather.py:55` | Cockpit-Risiko (ThreadPool, kein Schnee-Render) | Default **True** (unkritisch) |
| `trip_alert.py:836` | 15-Min Trip-Alarm | **False** |
| `compare_location_weather_source.py:51` | 15-Min Compare-Alarm | **False** |

## Affected Files (with changes)
| File | Change | Description |
|------|--------|-------------|
| `src/providers/openmeteo.py` | MODIFY | `enrich_snow: bool = True` Param; Snow-Enrichment-Helper (bounds-gated, fail-soft, fill-only) vor Hauptrückgabe (:997) und Cross-Provider-Rückgabe (:887); Provenance in `meta.fallback_metrics` (non-clobber) |
| `src/providers/geosphere.py` | MODIFY | SNOWGRID-Bounds-Helper (`snowgrid_covers(lat, lon)`; lat 45–50 / lon 8–18) co-located mit `fetch_snowgrid` |
| `src/services/segment_weather.py` | MODIFY | `enrich_snow: bool = True` an `fetch_segment_weather`; an `fetch_forecast` (:136) durchreichen |
| `src/services/trip_alert.py` | MODIFY | :836 `enrich_snow=False` |
| `src/services/compare_location_weather_source.py` | MODIFY | :51 `enrich_snow=False` |
| `tests/tdd/test_a3_snowgrid_supplement.py` | CREATE | Kern-Tests (netzfrei): Alpen-Ort bekommt snow_depth via Snow-Enrichment (fill-only, non-clobber); Alarm-Check (enrich_snow=False) löst KEIN Snow-Enrichment aus; Nicht-Alpen-Ort unberührt |

## Technischer Ansatz
- **Fill-only-Stamp nach UV-Vorbild** (`openmeteo.py:903-920`): der SNOWGRID-Snapshot
  `(snow_depth_cm, swe_kgm2)` wird auf jeden Datenpunkt gestempelt, aber nur wenn das
  Feld dort None ist (kein Überschreiben von Bergfex/vorhandenen Werten).
  **Bewusste Abweichung von `merge_missing_fields` (A1):** dessen Vertrag ist ein
  ts×ts-Join; SNOWGRID ist ein Skalar-Snapshot. Das in-Funktion-Vorbild (UV-Merge)
  ist der passende, bereits etablierte Reuse — kein Nachbau.
- **fail-soft:** `fetch_snowgrid` ist HTTP-fehler-tolerant; das Enrichment kapselt
  zusätzlich `try/except`, damit jeder Fehler (Timeout etc.) die openmeteo-Daten
  unangetastet lässt („keine Lücke").
- **Provenance:** gefüllte Snow-Params werden `meta.fallback_metrics` angehängt; ein
  bestehender `fallback_reason` (`model_5xx`/`metric_gap`) wird NICHT überschrieben.
- **Cross-Provider-Rückgabe (:882-887):** Snow-Enrichment via Helper auch dort (der
  `enrich_snow`-Parameter wird NICHT in den Fremdprovider-Call durchgereicht —
  fremde Provider kennen den Param nicht; die Anreicherung passiert in openmeteo).

## Scope Assessment
- Files: 5 Quelle + 1 Test.
- Estimated LoC: ~130–200. Risiko, dass 250 gerissen wird → falls ja, PO-Override erfragen.
- Risk Level: MEDIUM–HIGH (berührt den Trip-Briefing-Datenpfad; neuer Param durch mehrere Schichten).

## Dependencies
- Nutzt: `GeoSphereProvider.fetch_snowgrid` (`geosphere.py:288`), UV-Merge-Muster.
- Konsumenten Snow: Trip-Renderer (SN-Token `builder.py:134`, `snow_depth_cm` DTO
  `trip_result.py:48/73`) — nur wenn Nutzer `snow_depth`-Metrik aktiv hat (`trip_report.py:214`).
  Compare-Extraktion (`comparison_engine.py:415-425`) liest snow_depth aus forecast.data.

## Open Questions / Known Limitations
- [x] Gemeinsamer Seam? → `fetch_forecast`, bestätigt.
- [x] Alarm-Kosten? → neuer `enrich_snow`-Schalter, nur 2 Alarm-Checks False.
- [ ] **Nur `snow_depth_cm`+`swe_kgm2`** kommen aus SNOWGRID; `snowfall_limit_m`
  (Schneefallgrenze) ist ein AROME-Feld, NICHT SNOWGRID — bleibt außerhalb A3.
- [ ] Pro-Etappe ein SNOWGRID-Call im Briefing (Region-gleich, ohne Cache) —
  akzeptiert für den ersten Wurf (Briefing läuft im Hintergrund; Cockpit parallel).
  Caching = mögliche spätere Optimierung.
- [x] `comparison_engine.py` braucht KEINE Änderung — die vorhandene Snow-Extraktion
  (415-425) greift automatisch, sobald forecast.data Schnee trägt.
