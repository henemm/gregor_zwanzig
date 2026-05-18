# Context: Issue #203 — Stage-Row Wetter-Summary + Risiko-Pill

## Request Summary
Jede Etappe in der Trip-Detail Stage-Liste soll eine Wetter-Summary (Emoji + Temp + Wind + Niederschlag) und eine farbige Risiko-Pill (grün/gelb/rot) anzeigen. Basis-Infrastruktur (Risk-Engine, Forecast-Provider) existiert bereits im Go-Backend.

## Architektur-Schlüsselfunde

### Was bereits existiert
- **Risk-Engine:** `internal/risk/engine.go` — `Assess(SegmentWeatherSummary) → RiskAssessment` mit `GetMaxRiskLevel()` → `low|moderate|high`
- **Wetter-Modell:** `internal/model/segment.go` — `SegmentWeatherSummary` mit allen nötigen Feldern (TempMinC, TempMaxC, WindMaxKmh, PrecipSumMm, DominantWmoCode, ThunderLevelMax, etc.)
- **Forecast-Provider:** `internal/provider/provider.go` + `openmeteo/` — `FetchForecast(lat, lon, hours) → *Timeseries`
- **Forecast-Model:** `internal/model/forecast.go` — `Timeseries{Timezone, Meta, Data []ForecastDataPoint}` (stündliche Daten)
- **Frontend weatherEmoji():** `frontend/src/lib/utils/weatherEmoji.ts` — bereits vorhanden
- **Frontend Pill-Komponente:** `frontend/src/lib/components/ui/pill/` — bereits vorhanden

### Was FEHLT
- **Go-Aggregation:** Keine `Timeseries → SegmentWeatherSummary` Funktion in Go (nur in Python `src/services/weather_metrics.py`)
- **Stage-Modell-Erweiterung:** `Stage` hat keine `weather_summary`- oder `risk`-Felder
- **Neuer API-Endpoint:** Kein `GET /api/trips/{id}/stages/weather` oder ähnliches
- **Frontend-Typen:** `Stage` in `types.ts` hat kein `weather_summary?` oder `risk?`

## Related Files

| Datei | Relevanz |
|-------|----------|
| `internal/model/trip.go` | `Stage` Struct (ID, Name, Date, Waypoints, StartTime) — zu erweitern |
| `internal/model/segment.go` | `SegmentWeatherSummary` — Template für Stage-Weather-Felder |
| `internal/model/forecast.go` | `Timeseries`, `ForecastDataPoint` — Rohdaten vom Provider |
| `internal/model/risk.go` | `RiskLevel`, `RiskAssessment` — Risiko-Ergebnis |
| `internal/risk/engine.go` | `Assess()`, `GetMaxRiskLevel()` — Risiko-Berechnung |
| `internal/risk/thresholds.go` | Wind/Gust/Precip/Cape Schwellen |
| `internal/handler/trip.go` | `TripHandler` — `GET /api/trips/{id}` |
| `internal/handler/forecast.go` | `ForecastHandler` — `GET /api/forecast` (Referenz-Pattern) |
| `internal/provider/provider.go` | `WeatherProvider` Interface |
| `cmd/server/main.go` | Route-Registration |
| `frontend/src/lib/components/trip-detail/StageDetailRow.svelte` | Hauptkomponente — Wetter + Pill hinzufügen |
| `frontend/src/lib/components/trip-detail/StageList.svelte` | Übergibt `stage` an StageDetailRow — muss stage-weather ergänzen |
| `frontend/src/lib/types.ts` | `Stage`, `Trip` Interfaces — zu erweitern |
| `frontend/src/lib/utils/weatherEmoji.ts` | `weatherEmoji()` — bereits vorhanden |
| `docs/specs/modules/epic_135_step4_left_column.md` | Basis-Spec (linke Spalte) |

## Architektur-Entscheidung: Neuer Endpoint vs. Erweiterung

**Empfehlung: Neuer Endpoint `GET /api/trips/{id}/stages/weather`**

Begründung:
- `GET /api/trips/{id}` ist heute ein reiner Persistence-Read (Load → Encode). Weather-Berechnung ist rechenintensiv (N API-Calls für N Stages)
- Separation of Concerns: Storage vs. Live-Computation
- Frontend kann Trip laden (schnell) und Weather asynchron nachladen (lazy)
- Platzhalter-UI möglich: Stage-Row zeigt Loading-Skeleton bis Wetter da ist

Endpoint-Design:
```
GET /api/trips/{id}/stages/weather
→ { stage_id: { weather_summary: WeatherSummary, risk: "green"|"yellow"|"red" } }
```

`WeatherSummary` (kompaktes Subset aus SegmentWeatherSummary):
```json
{
  "wmo_code": 61,
  "temp_min": 12.3,
  "temp_max": 21.0,
  "wind_max_kmh": 45.0,
  "precip_mm": 8.2,
  "is_day": 1
}
```

## Aggregations-Logik (neu in Go)

Funktion: `aggregateTimeseries(ts *Timeseries, stageDate string) SegmentWeatherSummary`

Schritt 1: Zeitreihen-Punkte filtern auf `stageDate` (UTC-Tag)
Schritt 2: Aggregieren:
- `TempMinC` = MIN aller T2mC
- `TempMaxC` = MAX aller T2mC
- `WindMaxKmh` = MAX aller Wind10mKmh
- `GustMaxKmh` = MAX aller GustKmh
- `PrecipSumMm` = SUM aller Precip1hMm
- `ThunderLevelMax` = höchster ThunderLevel
- `DominantWmoCode` = häufigster WMO-Code (oder höchster Schweregrad)
- `IsDay` = 1 wenn mindestens ein Punkt isDay=1 an diesem Tag

Schritt 3: `risk.Assess(summary)` → `GetMaxRiskLevel()` → Mapping:
- `low` → `"green"`
- `moderate` → `"yellow"`
- `high` → `"red"`

## Forecast-Koordinate pro Stage

Problem: Eine Etappe hat Waypoints mit Koordinaten. Welche Koordinate für den Forecast?

Ansatz: Mittelpunkt aller Waypoints (lat/lon Durchschnitt). Falls keine Waypoints: kein Forecast möglich → `null` zurückgeben.

## Umgang mit fehlenden Daten

Laut Issue: "Bei fehlenden Forecast-Daten (z.B. Stage in mehr als 7 Tagen) wird ein neutraler Platzhalter angezeigt"

- Stage ohne Datum: `null` → Frontend zeigt kein Wetter
- Stage-Datum > 7 Tage in der Zukunft: Forecast außerhalb Reichweite → `null`
- Stage ohne Waypoints: Kein Mittelpunkt berechenbar → `null`
- API-Fehler: `null` (Fail-soft, kein UI-Crash)

## Frontend-Erweiterungen

### types.ts
```typescript
export interface StageWeatherSummary {
  wmo_code?: number | null;
  temp_min?: number | null;
  temp_max?: number | null;
  wind_max_kmh?: number | null;
  precip_mm?: number | null;
  is_day?: number | null;
}
export type StageRisk = 'green' | 'yellow' | 'red';
export interface StageWeatherData {
  weather_summary: StageWeatherSummary | null;
  risk: StageRisk | null;
}
```

### StageList.svelte
- Neuer `stageWeather: Record<string, StageWeatherData>` Prop (oder selbst fetchen)
- Übergibt `weatherData={stageWeather[stage.id] ?? null}` an jede `StageDetailRow`

### StageDetailRow.svelte
- Neuer optionaler Prop `weatherData?: StageWeatherData | null`
- Zeigt unter dem stat-strip eine Wetter-Zeile: Emoji + Temp-Range + Wind + Niederschlag
- Zeigt eine Risiko-Pill rechts im Header neben Code-Pill

## Risiken

1. **Aggregation-Logik:** Muss korrekt implementiert werden (Min/Max/Sum/Dominant) — Python-Referenz in `src/services/weather_metrics.py` verfügbar
2. **Performance:** N Forecast-Calls für N Stages. OpenMeteo ist kostenfrei, aber Latenz. Caching empfohlen (existiert bereits: `internal/provider/openmeteo/cache.go`)
3. **Kein Forecast > 7 Tage:** OpenMeteo hat 16-Tage-Forecast — aber die letzten Tage sind weniger genau. Ab ~7 Tagen gelten als "grobe Orientierung"
4. **Frontend-Ladereihenfolge:** Trip-Load (schnell) + Stage-Weather-Load (async) → Skeleton nötig

## Existing Specs
- `docs/specs/modules/epic_135_step4_left_column.md` — Basis-Spec mit explizitem Verweis auf #203
