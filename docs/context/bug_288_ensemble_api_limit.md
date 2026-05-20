# Context: Bug #288 — Ensemble-API-Limit erschöpft durch Alert-Checks

## Request Summary

Die Ensemble-API (`ensemble-api.open-meteo.com`) wird bei jedem Alert-Check-Lauf (alle 30 Min, 13 Etappen) mitabgerufen, obwohl die Konfidenz-Information nur für tägliche Reports gebraucht wird. Das kostenlose Tageslimit (ca. 50 Calls?) wird täglich bereits um ~04:27 Uhr erschöpft, danach schlagen alle Wetterdaten-Abrufe bis Mitternacht fehl.

## Related Files

| File | Relevanz |
|------|----------|
| `src/providers/openmeteo.py` | `fetch_forecast()` (Z. 660+) ruft `_fetch_ensemble_spread()` (Z. 452+) immer auf — hier muss das Flag rein |
| `src/services/trip_alert.py` | `_fetch_fresh_weather()` ruft `SegmentWeatherService.fetch_segment_weather()` auf — hier Flag auf `False` setzen |
| `src/services/segment_weather.py` | `fetch_segment_weather()` (Z. 71+) ruft `provider.fetch_forecast()` auf — Durchgangspunkt für das Flag |
| `src/providers/base.py` | `fetch_forecast()` Protokoll-Definition (Z. 40+) — Signatur muss angepasst werden |

## Existing Patterns

- Ensemble-Fetch ist bereits "best-effort" (bei Fehler leeres Dict `{}` zurück, kein Raise — Z. 484–486)
- `ENSEMBLE_TIMEOUT = 15.0` (kürzer als `TIMEOUT = 30.0`) — bereits als latenz-kritisch markiert
- UV-Daten werden nur bei `start and end` abgerufen (Z. 741) — ähnliches Conditional-Pattern wie der geplante Ensemble-Guard

## Call Chain (Alert-Check-Pfad)

```
Scheduler (alle 30 Min)
  → TripAlertService.check_all_trips()
  → TripAlertService.check_and_send_alerts(trip, cached)
  → TripAlertService._fetch_fresh_weather(cached)
  → SegmentWeatherService.fetch_segment_weather(segment)   [13x pro Trip]
  → OpenMeteoProvider.fetch_forecast(location, start, end)
  → OpenMeteoProvider._fetch_ensemble_spread(...)          ← HIER 13x täglich × 48 Läufe = 624 Calls
```

## Call Chain (Report-Pfad)

```
Scheduler (morgens/abends)
  → TripReportScheduler / CLI
  → SegmentWeatherService.fetch_segment_weather(segment)
  → OpenMeteoProvider.fetch_forecast(location, start, end)
  → OpenMeteoProvider._fetch_ensemble_spread(...)          ← hier soll es bleiben
```

## Geplante Lösung (laut Issue)

`fetch_forecast()` bekommt `enrich_ensemble: bool = True`. Im Alert-Check-Pfad wird es auf `False` gesetzt. Da das Flag von `SegmentWeatherService.fetch_segment_weather()` und `providers.base.fetch_forecast()` durchgereicht wird, müssen drei Stellen angepasst werden:

1. `base.py` — `fetch_forecast()` Signatur erweitern
2. `openmeteo.py` — `fetch_forecast()` Flag auswerten, `_fetch_ensemble_spread()` nur wenn `True`
3. `segment_weather.py` — `fetch_segment_weather()` Flag annehmen + weiterreichen
4. `trip_alert.py` — `fetch_segment_weather(enrich_ensemble=False)` übergeben

## Dependencies

- Upstream: `httpx` Client (in `OpenMeteoProvider.__init__`)
- Downstream: `TripReportFormatter`, `EmailOutput` — nutzen `confidence_pct`, `spread_t2m_k`, `spread_precip_mm` aus `ForecastDataPoint` — bleiben `None` bei Alert-Calls (bestehende Logik schon `None`-sicher)

## Existing Specs

- Kein Spec bisher für diesen Bug (neu erstellen: `docs/specs/modules/bug_288_ensemble_api_limit.md`)
- Verwandt: `docs/specs/modules/forecast_confidence.md` (Issue #121)

## Risks & Considerations

- **Base-Protokoll-Änderung:** `fetch_forecast()` in `base.py` ist ein `Protocol` — Signatur-Erweiterung mit `enrich_ensemble: bool = True` ist backward-compatible (Default=True)
- **Andere Provider:** Nur `OpenMeteoProvider` implementiert Ensemble — alle anderen Provider ignorieren das Flag (kein Ensemble-Support)
- **Konfidenz-Felder bleiben None:** Bei Alert-Checks werden `confidence_pct`, `spread_t2m_k`, `spread_precip_mm` `None` — das ist bereits der aktuelle Fallback-Wert, kein Regressionspotenzial
- **Kein Cache:** `service._cache.clear()` in `_fetch_fresh_weather()` vor jedem Segment-Fetch — Flag hat keinen Cache-Einfluss
