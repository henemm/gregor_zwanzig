---
entity_id: issue_203_stage_weather_risk
type: module
created: 2026-05-18
updated: 2026-05-18
status: draft
version: "1.0"
parent_spec: epic_135_step4_left_column
issues: [203]
tags: [backend, go, frontend, sveltekit, svelte5, trip-detail, weather, risk, issue-203]
---

# Issue #203 — Stage-Row Wetter-Summary + Risiko-Pill

## Approval

- [ ] Approved

## Purpose

Erweitert die Trip-Detail Stage-Liste (`StageDetailRow`) um eine kompakte Wetter-Summary (Wetter-Emoji + Temperatur-Range + Wind + Niederschlag) und eine farbige Risiko-Pill (grün/gelb/rot) pro Etappe. Die Wetterdaten werden asynchron über einen neuen separaten Endpoint `GET /api/trips/{id}/stages/weather` nachgeladen, damit der initiale Trip-Load nicht durch externe API-Calls verlangsamt wird.

## Source

- **NEU:** `internal/model/stage_weather.go` — DTOs: `StageWeatherSummary`, `StageWeatherResult`, `StagesWeatherResponse`
- **NEU:** `internal/handler/stage_weather.go` — Handler + package-private Aggregations-Logik
- **NEU:** `internal/handler/stage_weather_test.go` — Go-Tests für Handler und Aggregation
- **EDIT:** `cmd/server/main.go` — Route-Registration `GET /api/trips/{id}/stages/weather`
- **EDIT:** `frontend/src/lib/types.ts` — Neue Typen `StageWeatherSummary`, `StageWeatherResult`, `StagesWeatherResponse`
- **EDIT:** `frontend/src/lib/components/trip-detail/StageList.svelte` — Async-Fetch nach Trip-Load + Prop-Weitergabe
- **EDIT:** `frontend/src/lib/components/trip-detail/StageDetailRow.svelte` — Wetter-Zeile + Risiko-Pill UI
- **Identifier:** `StagesWeatherHandler`, `aggregateForecasts`, `StageWeatherSummary`, `StageWeatherResult`, `StagesWeatherResponse`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `internal/model/stage_weather.go` (`StageWeatherSummary`, `StageWeatherResult`, `StagesWeatherResponse`) | NEU | DTOs für API-Response: Weather-Felder + Risk-String pro Stage |
| `internal/model/` (`Trip`, `Stage`, `Waypoint`) | bestehend | Datenmodell: `Stage.id`, `Stage.date`, `Stage.waypoints`, `Waypoint.lat`, `Waypoint.lon` |
| `internal/provider/` (`FetchForecast`) | bestehend | Externe API-Calls für Wetterdaten pro Koordinate; liefert Forecast-Punkte |
| `internal/model/segment.go` (`SegmentWeatherSummary`) | bestehend | Aggregiertes Wetter-Modell; wird von `aggregateForecasts` (NEU, in `stage_weather.go`) befüllt und von `risk.Assess` konsumiert |
| `internal/risk/` (`Assess`, `GetMaxRiskLevel`) | bestehend | Berechnet Risiko-Level aus `SegmentWeatherSummary`; liefert `low`, `moderate`, `high` |
| `internal/store/` (`GetTrip`) | bestehend | Lädt Trip inkl. Stages + Waypoints aus Persistenz |
| `cmd/server/main.go` | bestehend (EDIT) | Route-Registration; `omProvider` wird an Handler übergeben |
| `frontend/src/lib/types.ts` (`Trip`, `Stage`) | bestehend (EDIT) | Bestehende Typen; neue Wetter-Typen ergänzen ohne Änderung vorhandener Felder |
| `frontend/src/lib/components/trip-detail/StageList.svelte` | bestehend (EDIT) | Async-Fetch nach Trip-Load; `stageWeather`-State; Prop `weatherData` an `StageDetailRow` |
| `frontend/src/lib/components/trip-detail/StageDetailRow.svelte` | bestehend (EDIT) | Neuer optionaler Prop `weatherData`; Wetter-Zeile + Risiko-Pill als UI-Erweiterung |
| `frontend/src/lib/components/ui/pill/Pill.svelte` | bestehend | Risiko-Pill mit `tone="success"`, `tone="warning"`, `tone="danger"` |
| `frontend/src/app.css` (Tokens) | bestehend | `--g-success`, `--g-warning`, `--g-danger` für Risiko-Pill-Farben |

## Implementation Details

### §1 Datenmodell `internal/model/stage_weather.go`

```go
package model

// StageWeatherSummary — kompaktes Subset aus SegmentWeatherSummary für die API-Response
type StageWeatherSummary struct {
    TempMinC    *float64 `json:"temp_min_c"`
    TempMaxC    *float64 `json:"temp_max_c"`
    WindMaxKmh  *float64 `json:"wind_max_kmh"`
    PrecipMm    *float64 `json:"precip_mm"`
    WmoCode     *int     `json:"wmo_code"`
    IsDay       *int     `json:"is_day"`
}

// StageWeatherResult — Weather + Risk für eine Stage
type StageWeatherResult struct {
    WeatherSummary *StageWeatherSummary `json:"weather_summary"`
    Risk           *string              `json:"risk"` // "green", "yellow", "red" — null wenn kein Forecast
}

// StagesWeatherResponse — Response für GET /api/trips/{id}/stages/weather
type StagesWeatherResponse struct {
    Results map[string]*StageWeatherResult `json:"results"` // stage_id → result
}
```

### §2 Handler `internal/handler/stage_weather.go`

**Route:** `GET /api/trips/{id}/stages/weather`

**Request-Verarbeitung:**

1. Trip-ID aus URL-Parameter extrahieren; Trip via `store.GetTrip(id)` laden.
2. Trip nicht gefunden → HTTP 404.
3. `results := make(map[string]*StageWeatherResult)` initialisieren.
4. Alle Stages parallel verarbeiten via `sync.WaitGroup` + Mutex auf `results`.

**Pro Stage (goroutine):**

1. Stage ohne `date` (leer oder null) → `results[stageId] = null`; weiter.
2. Stage ohne Waypoints (`len(stage.Waypoints) == 0`) → `results[stageId] = null`; weiter.
3. Koordinate berechnen: Mittelpunkt aller Waypoints (`avgLat = sum(lat)/n`, `avgLon = sum(lon)/n`).
4. `FetchForecast(lat, lon, hours=168)` aufrufen (7 Tage Lookahead).
5. API-Fehler → `results[stageId] = null`; weiter (Fail-soft, keine 5xx für einzelne Stage).
6. `aggregateForecasts(forecastPoints, stageDate)` → `*SegmentWeatherSummary`.
7. Keine Datenpunkte für den Tag → `results[stageId] = null`; weiter.
8. `risk.Assess(summary)` → `GetMaxRiskLevel()` aufrufen.
9. Risk-Mapping: `low` → `"green"`, `moderate` → `"yellow"`, `high` → `"red"`.
10. `StageWeatherSummary` aus `SegmentWeatherSummary` extrahieren (nur die 6 Frontend-relevanten Felder).
11. `results[stageId] = &StageWeatherResult{WeatherSummary: summary, Risk: &riskStr}`.

**Response:** HTTP 200, JSON `StagesWeatherResponse`.

**package-private Aggregations-Logik `aggregateForecasts`:**

Zeitfilter: Nur Forecast-Punkte des UTC-Tages von `stageDate` (00:00–23:59 UTC).

| Feld | Aggregation |
|------|------------|
| `TempMinC` | MIN(T2mC) |
| `TempMaxC` | MAX(T2mC) |
| `WindMaxKmh` | MAX(Wind10mKmh) |
| `GustMaxKmh` | MAX(GustKmh) |
| `PrecipSumMm` | SUM(Precip1hMm) |
| `ThunderLevelMax` | MAX nach Ordnung NONE < MED < HIGH |
| `VisibilityMinM` | MIN(VisibilityM) |
| `WindChillMinC` | MIN(WindChillC) |
| `PopMaxPct` | MAX(PopPct) |
| `CapeMaxJkg` | MAX(CapeJkg) |
| `DominantWmoCode` | WMO-Code mit höchstem Schweregrad (Ranking: Gewitter > Regen > Schnee > Nebel > Bewölkt > Klar) |
| `IsDay` | 1 wenn mindestens ein Datenpunkt IsDay=1 an dem Tag |

### §3 Route-Registration `cmd/server/main.go`

```go
r.Get("/api/trips/{id}/stages/weather", handler.StagesWeatherHandler(s, omProvider))
```

Zwei Zeilen (Import + Route); keine weiteren Änderungen an `main.go`.

### §4 Frontend-Typen `frontend/src/lib/types.ts`

```typescript
export interface StageWeatherSummary {
    temp_min_c?: number | null;
    temp_max_c?: number | null;
    wind_max_kmh?: number | null;
    precip_mm?: number | null;
    wmo_code?: number | null;
    is_day?: number | null;
}

export interface StageWeatherResult {
    weather_summary: StageWeatherSummary | null;
    risk: 'green' | 'yellow' | 'red' | null;
}

export interface StagesWeatherResponse {
    results: Record<string, StageWeatherResult | null>;
}
```

Bestehende Typen (`Trip`, `Stage`, `Waypoint` etc.) bleiben unverändert.

### §5 `StageList.svelte` — Async-Fetch + Prop-Weitergabe

```typescript
import type { StagesWeatherResponse, StageWeatherResult } from '$lib/types';

let stageWeather: Record<string, StageWeatherResult | null> = $state({});

$effect(() => {
    if (!trip?.id) return;
    fetch(`/api/trips/${trip.id}/stages/weather`)
        .then(r => r.ok ? r.json() as Promise<StagesWeatherResponse> : null)
        .then(data => { if (data) stageWeather = data.results; })
        .catch(() => {}); // Fail-soft: keine Wetterdaten → UI bleibt ohne Wetter-Elemente
});
```

Jeder `StageDetailRow` erhält den neuen Prop:

```svelte
<StageDetailRow
  ...bestehende Props...
  weatherData={stageWeather[stage.id] ?? null}
/>
```

### §6 `StageDetailRow.svelte` — Wetter-Zeile + Risiko-Pill

**Neuer optionaler Prop:**

```typescript
import type { StageWeatherResult } from '$lib/types';
import Pill from '$lib/components/ui/pill/Pill.svelte';

interface Props {
  ...bestehende Props...
  weatherData?: StageWeatherResult | null;
}
let { ..., weatherData = null }: Props = $props();
```

**Wetter-Emoji-Helper (package-local):**

```typescript
function weatherEmoji(wmoCode: number | null | undefined, isDay: number | null | undefined): string {
    // WMO-Code Mapping:
    // 0–1 → isDay ? '☀️' : '🌙'
    // 2–3 → '⛅'
    // 45–48 → '🌫️'
    // 51–67 → '🌧️'
    // 71–77 → '❄️'
    // 80–82 → '🌦️'
    // 95–99 → '⛈️'
    // Fallback → '🌡️'
}
```

**Risiko-Mapping:**

```typescript
const riskTone = $derived(
    weatherData?.risk === 'green' ? 'success' :
    weatherData?.risk === 'yellow' ? 'warning' :
    weatherData?.risk === 'red' ? 'danger' : null
);

const riskLabel = $derived(
    weatherData?.risk === 'green' ? 'Gering' :
    weatherData?.risk === 'yellow' ? 'Mittel' :
    weatherData?.risk === 'red' ? 'Hoch' : null
);
```

**Template-Erweiterung** (unterhalb des bestehenden `stat-strip`):

```svelte
{#if weatherData?.weather_summary}
  {@const ws = weatherData.weather_summary}
  <div class="weather-strip" data-testid="trip-stage-row-weather-{stage.id}">
    <span>{weatherEmoji(ws.wmo_code, ws.is_day)}</span>
    {#if ws.temp_min_c != null && ws.temp_max_c != null}
      <span>{Math.round(ws.temp_min_c)}–{Math.round(ws.temp_max_c)} °C</span>
    {/if}
    {#if ws.wind_max_kmh != null}
      <span>Wind {Math.round(ws.wind_max_kmh)} km/h</span>
    {/if}
    {#if ws.precip_mm != null && ws.precip_mm > 0}
      <span>💧 {ws.precip_mm.toFixed(1)} mm</span>
    {/if}
  </div>
{/if}

{#if riskTone && riskLabel}
  <Pill tone={riskTone} data-testid="trip-stage-row-risk-{stage.id}">
    {riskLabel}
  </Pill>
{/if}
```

**Risiko-Pill-Position:** Innerhalb des `<header>`-Bereichs der Card, rechts neben der bestehenden Code-Pill. Erfordert `header`-Container auf `justify-between` oder ähnliches Flex-Layout.

### §7 Datei-Liste

| Art | Datei | Zweck | LoC |
|-----|-------|-------|-----|
| NEU | `internal/model/stage_weather.go` | DTOs für API-Response | ~30 |
| NEU | `internal/handler/stage_weather.go` | Handler + Aggregations-Logik | ~150 |
| NEU | `internal/handler/stage_weather_test.go` | Go-Tests | ~80 |
| EDIT | `cmd/server/main.go` | +2 LoC Route-Registration | +2 |
| EDIT | `frontend/src/lib/types.ts` | +25 LoC neue Typen | +25 |
| EDIT | `frontend/src/lib/components/trip-detail/StageList.svelte` | +30 LoC Fetch + Prop | +30 |
| EDIT | `frontend/src/lib/components/trip-detail/StageDetailRow.svelte` | +50 LoC Wetter-UI + Risiko-Pill | +50 |
| **Summe** | | | **~367 LoC** |

**LoC-Override erforderlich vor Phase 6:** `workflow.py set-field loc_limit_override 400 --name issue_203_stage_weather_risk`

## Expected Behavior

- **Input:** `GET /api/trips/{id}/stages/weather` — Trip-ID als URL-Parameter; kein Request-Body.
- **Output:**
  - HTTP 200 + JSON `StagesWeatherResponse` mit `results`-Map: jede Stage-ID → `StageWeatherResult | null`.
  - `StageWeatherResult.weather_summary` enthält `temp_min_c`, `temp_max_c`, `wind_max_kmh`, `precip_mm`, `wmo_code`, `is_day` (alle nullable).
  - `StageWeatherResult.risk` ist einer aus `"green"`, `"yellow"`, `"red"` oder `null`.
  - Stage ohne Datum oder Waypoints sowie API-Fehler pro Stage → `results[stageId] = null` (kein 5xx, andere Stages weiter verarbeitet).
  - Trip nicht gefunden → HTTP 404.
  - Frontend: `StageDetailRow` zeigt Wetter-Zeile (`data-testid="trip-stage-row-weather-{stageId}"`) und Risiko-Pill (`data-testid="trip-stage-row-risk-{stageId}"`) nur wenn `weatherData` vorhanden und nicht null.
  - Frontend: Ohne Wetterdaten (`weatherData === null`) keine leeren Elemente, kein Runtime-Error.
- **Side effects:**
  - Backend: Externe API-Calls (`FetchForecast`) pro Stage mit Waypoints; Anzahl paralleler Calls = Anzahl qualifizierter Stages.
  - Frontend: Ein `fetch()`-Call nach Trip-Load pro geöffneter Trip-Detail-Seite; kein Polling.

## Acceptance Criteria

- **AC-1:** Given ein Trip mit einer Etappe mit Datum und mindestens einem Waypoint, when `GET /api/trips/{id}/stages/weather` aufgerufen wird, then enthält die Response für diese Stage-ID eine `weather_summary` mit den Feldern `temp_min_c`, `temp_max_c`, `wind_max_kmh`, `precip_mm`, `wmo_code`, `is_day` sowie ein `risk` aus `{"green","yellow","red"}`.
  - Test: (populated after /tdd-red)

- **AC-2:** Given eine Stage ohne Waypoints (`waypoints` leer oder nicht vorhanden), when `GET /api/trips/{id}/stages/weather` aufgerufen wird, then ist `results[stageId]` null — kein 5xx, kein Crash, andere Stages in derselben Response werden korrekt berechnet.
  - Test: (populated after /tdd-red)

- **AC-3:** Given eine Stage ohne Datum (leerer String oder null), when der Endpoint aufgerufen wird, then ist `results[stageId]` null — kein 5xx.
  - Test: (populated after /tdd-red)

- **AC-4:** Given ein nicht-existierender Trip (unbekannte ID), when `GET /api/trips/{id}/stages/weather` aufgerufen wird, then antwortet der Server mit HTTP 404.
  - Test: (populated after /tdd-red)

- **AC-5:** Given ein Trip mit drei Etappen (alle mit Datum und Waypoints), when der Endpoint aufgerufen wird, then enthält `results` Einträge für alle drei Stage-IDs — Fehler einer einzelnen Stage (simuliert via API-Fehler) führt zu `null` für diese Stage, nicht zum Abbruch der gesamten Response.
  - Test: (populated after /tdd-red)

- **AC-6:** Given eine Stage mit Wetterdaten (`weather_summary` vorhanden, `risk` gesetzt), when die Trip-Detail-Seite geöffnet wird und der Fetch abgeschlossen ist, then zeigt `StageDetailRow` ein Element `data-testid="trip-stage-row-weather-{stageId}"` mit Emoji, Temperatur-Range, Wind-Wert sowie ein Element `data-testid="trip-stage-row-risk-{stageId}"` mit dem korrekten Risiko-Label.
  - Test: (populated after /tdd-red)

- **AC-7:** Given eine Stage ohne verfügbare Wetterdaten (`weatherData === null`), when die Trip-Detail-Seite geöffnet wird, then rendert `StageDetailRow` weder `data-testid="trip-stage-row-weather-{stageId}"` noch `data-testid="trip-stage-row-risk-{stageId}"` — keine leeren Container, kein Runtime-Error, kein "undefined" im DOM.
  - Test: (populated after /tdd-red)

- **AC-8:** Given Wetterdaten mit `risk: "red"` (z.B. Wind > 70 km/h), when die Risiko-Pill gerendert wird, then hat sie `tone="danger"` und zeigt den Text "Hoch". Bei `risk: "yellow"`: `tone="warning"` + "Mittel". Bei `risk: "green"`: `tone="success"` + "Gering".
  - Test: (populated after /tdd-red)

## Known Limitations

- **Koordinaten-Genauigkeit:** Der Mittelpunkt aller Waypoints einer Stage wird als repräsentative Koordinate für den Forecast verwendet. Bei sehr langen Stages mit großem Höhengefälle kann dies zu ungenauen Wetterdaten führen. Eine segmentbasierte Mehrfach-Abfrage ist nicht in Scope.
- **Kein Caching:** Jeder Seitenaufruf löst neue `FetchForecast`-Calls aus. Bei Trips mit vielen Stages kann das zu merklicher Ladezeit führen. Caching ist ein separates Feature.
- **Stages außerhalb des 7-Tage-Fensters:** `FetchForecast` liefert 168 Stunden; Stages mit Datum > 7 Tage in der Zukunft erhalten `null`. Keine Fehlermeldung — stille Null.
- **WMO-Code-Mapping im Frontend:** Das Emoji-Mapping in `weatherEmoji()` deckt die gängigsten WMO-Codes ab; seltene Codes (z.B. 56–57 Gefrierender Nieselregen) fallen auf den Fallback `'🌡️'`.
- **Risiko-Pill-Position:** Die Pill wird im `<header>` der Card rechts neben der Code-Pill platziert. Bei sehr langen Stage-Namen kann es zu Überlappungen kommen; kein Wrapping-Schutz im Scope.

## Changelog

- 2026-05-18: Initial spec — Issue #203 (Stage-Row Wetter-Summary + Risiko-Pill). Neuer Backend-Endpoint `GET /api/trips/{id}/stages/weather` mit paralleler Stage-Verarbeitung (sync.WaitGroup), Aggregations-Logik für tagesbasierte Wetter-Zusammenfassung, Risk-Mapping low/moderate/high → green/yellow/red. Neue DTOs `StageWeatherSummary`, `StageWeatherResult`, `StagesWeatherResponse`. Frontend: Async-Fetch in `StageList.svelte` nach Trip-Load; `StageDetailRow.svelte` erweitert um Wetter-Zeile (Emoji + Temp-Range + Wind + Niederschlag) und Risiko-Pill mit tone success/warning/danger. Fail-soft auf allen Ebenen: Stage ohne Datum/Waypoints und API-Fehler pro Stage liefern null, kein 5xx. 8 Acceptance Criteria im AC-N-Format.
