# Context: M3c Weather Table (SvelteKit)

## Request Summary
Weather-Tabelle als SvelteKit-Page: Forecast-Daten pro Trip/Location als stündliche Tabelle anzeigen. Nutzt den bestehenden Go Forecast-Endpoint.

## Related Files
| File | Relevance |
|------|-----------|
| `internal/handler/forecast.go` | Go API: GET /api/forecast?lat=X&lon=X&hours=N |
| `internal/model/forecast.go` | ForecastDataPoint (31 Felder), Timeseries, ForecastMeta |
| `internal/provider/openmeteo/provider.go` | Regionale Modell-Auswahl, Fallback-Logik |
| `src/web/pages/compare.py` | NiceGUI Compare (1828 LOC) — Referenz fuer Tabellen-Format |
| `src/services/weather_metrics.py` | HourlyCell, Emoji-Logik, Aggregation |
| `frontend/src/lib/types.ts` | Forecast-Types fehlen noch |
| `docs/reference/api_contract.md` | Feld-Konventionen (*_c, *_kmh, *_mm etc.) |

## Existing Patterns
- M3a/M3b: Server-side Load, shadcn Table, API Proxy
- Compare.py: Stündliche Tabelle mit Emoji, Temp, Precip, Wind, Gust, Windrichtung
- HourlyCell: symbol, temp_c, precip_symbol, precip_amount, wind_kmh, gust_kmh, wind_dir

## Dependencies
- **Upstream:** Go Forecast Endpoint (lat, lon, hours), Trip/Location data
- **Downstream:** Spaeter Compare-Page, Subscriptions

## Key Decision
Der Forecast-Endpoint nimmt lat/lon/hours — NICHT trip_id. Fuer eine Trip-Tabelle muss das Frontend:
1. Trip laden (stages -> waypoints -> lat/lon)
2. Pro Waypoint einen Forecast holen
3. Ergebnisse in einer Tabelle darstellen

Alternative: Nur Location-Forecast (einfacher — ein lat/lon Paar).

## Risks
- Viele API-Calls bei Trips mit vielen Waypoints
- Forecast-Response hat 31 Felder — welche anzeigen?
- Keine Forecast-TypeScript-Types vorhanden
