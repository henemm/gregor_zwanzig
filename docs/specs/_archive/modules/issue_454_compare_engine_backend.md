---
entity_id: issue_454_compare_engine_backend
type: module
created: 2026-05-29
updated: 2026-05-29
status: draft
version: "1.0"
issue: 454
tags: [compare, go, engine, scoring, cache, goroutines, api, date-range, hourly, epic-246]
---

# Issue #454 — Orts-Vergleich · Compare-Engine Backend (Multi-Day, Datums-/Stunden-Fenster)

## Approval

- [ ] Approved

## Purpose

Erweitert die bestehende Compare-Engine (`internal/compare/`) von einem Einzeldatum-Abfrage-Modell auf ein konfigurierbares Datums- und Stunden-Fenster: Der Endpoint `POST /api/compare/run` nimmt ab sofort `date_from`/`date_to` (Multi-Day) und `hour_from`/`hour_to` (Tagesfenster in UTC) entgegen, aggregiert die Forecast-Daten über den gesamten Bereich und liefert ein neu strukturiertes Response-Format mit `ranking`, `matrix` und `stunden_verlauf`. Die Änderung ist ein Breaking Change auf demselben Endpoint ohne Versionierung — das Frontend ruft den Endpoint noch nicht auf, sodass kein bestehender Client bricht.

> **Schicht-Zuordnung:** Ausschließlich Go-API (`internal/`, `api/`). Kein Frontend-Change in diesem Issue.

## Source

- **UPDATE** `internal/compare/types.go` — `CompareRequest` (date → date_from/date_to/hour_from/hour_to) + `CompareResult` (rows/winner/hourly → ranking/matrix/stunden_verlauf) + neue DTOs (`CompareTag`, `RankingEntry`, `MatrixEntry`, `StundenVerlaufHour`, `StundenVerlaufEntry`); alte Typen `CompareRow`, `CompareWinner` werden entfernt
- **UPDATE** `internal/compare/cache.go` — `cacheKey`-Struct: `Date string` → `DateFrom`, `DateTo string` + `HourFrom`, `HourTo int`
- **UPDATE** `internal/compare/engine.go` — neue Funktion `aggregateByDateRange()`, Multi-Day-Merge-Logik, `filterByDateRange()`, `stunden_verlauf`-Konstruktion über alle N Locations
- **UPDATE** `internal/compare/scoring.go` — neue Funktion `WinnerTagsTyped()` → `[]CompareTag` (ersetzt `WinnerTags()` → `[]string`); neue Hilfsfunktion `typeFor(metricKey) string`
- **UPDATE** `internal/handler/compare_run.go` — erweiterte Validierungslogik für 7 neue Fehlerfälle
- **UPDATE** `internal/handler/compare_run_test.go` — 8 bestehende Tests migriert auf neues Request-/Response-Format + 5 neue Testfälle

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `Engine.Run()` (`internal/compare/engine.go`) | intern | Bestehende Orchestrierung (paralleler Fetch via sync.WaitGroup) — wird um `aggregateByDateRange()` erweitert |
| `aggregateByDate()` (`internal/compare/engine.go`) | intern | Bestehende Einzel-Tag-Aggregation; wird intern von `aggregateByDateRange()` pro Kalendertag aufgerufen |
| `ScoreRow()` (`internal/compare/scoring.go`) | intern | Profil-gewichtetes Scoring; bleibt unverändert, da `SegmentWeatherSummary` als Input-DTO erhalten bleibt |
| `WinnerTags()` (`internal/compare/scoring.go`) | intern | Wird durch `WinnerTagsTyped()` ersetzt; im selben Commit entfernt |
| `model.SegmentWeatherSummary` (`internal/model/segment.go`) | intern | Aggregations-DTO; bleibt Basis für `matrix`-Block und Scoring-Input |
| `model.ForecastDataPoint` / `model.Timeseries` (`internal/model/forecast.go`) | intern | Rohdaten aus OpenMeteo; Basis für `stunden_verlauf`-Filterung nach UTC-Stunde |
| `model.Location` (`internal/model/location.go`) | intern | Liefert Name, Lat/Lon/ElevationM für `ranking`-Block und Forecast-Fetch |
| `store.LoadLocation(userID, locationID)` (`internal/store/store.go`) | intern | Lädt Location-Struct mit Auth-Kontext; unverändert |
| `OpenMeteoProvider.FetchForecast(lat, lon, hours)` (`internal/provider/openmeteo/provider.go`) | intern | Einzelner Forecast-Abruf pro Location; `hours`-Parameter wird dynamisch aus `date_to`-Abstand berechnet |
| `sync.WaitGroup` + `sync.Mutex` (Go-Stdlib) | extern | Goroutine-Koordination; Muster identisch zu bisheriger Engine-Implementierung |
| `time` (Go-Stdlib) | extern | Datum-Parsing (`time.Parse("2006-01-02", ...)`), UTC-Stunden-Filterung, `today+9`-Grenze |
| Auth-Middleware / `WithUser()` | intern | Request muss User-Context tragen; unverändert |

## Implementation Details

### §1 `internal/compare/types.go` — neue DTOs

Alte Typen `CompareRow` und `CompareWinner` werden vollständig entfernt. Neue Typen:

```go
// Request (date wird durch date_from/date_to/hour_from/hour_to ersetzt)
type CompareRequest struct {
    LocationIDs []string        `json:"location_ids"`
    DateFrom    string          `json:"date_from"`   // "YYYY-MM-DD"
    DateTo      string          `json:"date_to"`     // "YYYY-MM-DD", >= DateFrom
    HourFrom    int             `json:"hour_from"`   // 0-23, UTC
    HourTo      int             `json:"hour_to"`     // 0-23, UTC, >= HourFrom
    Profile     ActivityProfile `json:"profile"`
}

// Response-Blöcke (ersetzen CompareResult{rows, winner, hourly})
type CompareTag struct {
    Type  string `json:"type"`   // machine-readable, z.B. "low_rain", "best_sun"
    Label string `json:"label"`  // human-readable, z.B. "Wenig Regen"
}

type RankingEntry struct {
    LocationID string       `json:"location_id"`
    Name       string       `json:"name"`
    Score      int          `json:"score"`  // 0-100
    Tags       []CompareTag `json:"tags"`
}

type MatrixEntry struct {
    LocationID string         `json:"location_id"`
    Metrics    map[string]any `json:"metrics"`  // SegmentWeatherSummary-Felder als flat dict
}

type StundenVerlaufHour struct {
    Hour   string         `json:"hour"`    // zweistellig UTC, z.B. "08"
    Values map[string]any `json:"values"`  // t2m_c, wind10m_kmh, gust_kmh, precip_1h_mm,
                                           // cloud_total_pct, thunder_level, visibility_m
}

type StundenVerlaufEntry struct {
    LocationID string               `json:"location_id"`
    Hours      []StundenVerlaufHour `json:"hours"`
}

type CompareResult struct {
    Ranking        []RankingEntry        `json:"ranking"`
    Matrix         []MatrixEntry         `json:"matrix"`
    StundenVerlauf []StundenVerlaufEntry `json:"stunden_verlauf"`
}
```

`ActivityProfile` und die vier Profil-Konstanten bleiben unverändert.

### §2 `internal/compare/cache.go` — erweiterter Cache-Key

```go
type cacheKey struct {
    LocationID string
    DateFrom   string
    DateTo     string
    HourFrom   int
    HourTo     int
    Profile    ActivityProfile
}
```

`cachedEntry` bleibt: `{summary *model.SegmentWeatherSummary, hourly []model.ForecastDataPoint, storedAt time.Time}`. Bestehende in-memory Einträge mit dem alten Key-Schema werden beim nächsten Prozessstart automatisch invalidiert (kein persistentes State).

### §3 `internal/compare/engine.go` — Multi-Day-Aggregation

**Neue Funktion `filterByDateRange(points []model.ForecastDataPoint, dateFrom, dateTo string, hourFrom, hourTo int) []model.ForecastDataPoint`:**
- Iteriert alle Punkte, behält nur jene, bei denen `date(pt.Time.UTC())` in `[dateFrom..dateTo]` liegt UND `pt.Time.UTC().Hour()` in `[hourFrom..hourTo]`.

**Neue Funktion `aggregateByDateRange(points []model.ForecastDataPoint, dateFrom, dateTo string, hourFrom, hourTo int) *model.SegmentWeatherSummary`:**
1. Berechne alle Kalendertage `d` von `dateFrom` bis `dateTo` (inklusiv).
2. Für jeden Tag `d`: filtere `points` auf `date == d && hour ∈ [hourFrom..hourTo]`, rufe bestehende `aggregateByDate(filteredPoints)` auf.
3. Merge aller Tages-Aggregate zu einem `SegmentWeatherSummary`:
   - `TempMinC` = min aller Tages-TempMinC
   - `TempMaxC` = max aller Tages-TempMaxC
   - `WindMaxKmh` = max aller Tages-WindMaxKmh
   - `GustMaxKmh` = max aller Tages-GustMaxKmh
   - `PrecipSumMm` = Summe aller Tages-PrecipSumMm
   - `SunnyHoursH` = Summe aller Tages-SunnyHoursH
   - `CloudAvgPct` = gewichteter Durchschnitt (Gewicht = Anzahl Punkte pro Tag)
   - `ThunderLevel` = max Severity über alle Tage
   - `VisibilityMinM` = min aller Tages-VisibilityMinM
   - `SnowDepthCm` = letzter Wert im Bereich (Zustand, nicht Summe)
   - `SnowNewSumCm` = Summe aller Tages-SnowNewSumCm

**Angepasste `Engine.Run()` (Zusammenfassung der Änderungen):**
- Cache-Lookup mit neuem Key-Schema (`DateFrom`/`DateTo`/`HourFrom`/`HourTo`).
- `hours`-Parameter für `FetchForecast`: `int(date_to_time.Sub(now).Hours()) + 48` (Puffer), maximal 240h. Berechnung nach `date_to`-Parsing.
- Statt `aggregateByDate` → `aggregateByDateRange` aufrufen.
- `stunden_verlauf`-Block: alle N Locations (nicht nur Top-3), Punkte via `filterByDateRange` gefiltert, pro Punkt nur die 7 Felder: `t2m_c`, `wind10m_kmh`, `gust_kmh`, `precip_1h_mm`, `cloud_total_pct`, `thunder_level`, `visibility_m`; `hour`-Key ist `fmt.Sprintf("%02d", pt.Time.UTC().Hour())`.
- `ranking`-Block: `Location.Name` aus `store.LoadLocation()` in `RankingEntry.Name` übernehmen.
- `matrix`-Block: `SegmentWeatherSummary`-Felder als `map[string]any` serialisiert (Feldnamen snake_case).
- `winner`-Bestimmung: `ranking[0]`, Tags via `WinnerTagsTyped()`.

### §4 `internal/compare/scoring.go` — WinnerTagsTyped

```go
// typeFor gibt den machine-readable Tag-Typ für einen metricKey zurück.
func typeFor(k metricKey) string {
    switch k {
    case metricSnowDepth, metricSnowNew:  return "best_snow"
    case metricSunnyHours:               return "best_sun"
    case metricWindMax:                  return "low_wind"
    case metricPrecipSum:                return "low_rain"
    case metricVisibilityMin:            return "good_visibility"
    case metricThunderProxy:             return "low_thunder"
    case metricTempMax:                  return "best_temp"
    case metricCloudAvg:                 return "clear_sky"
    case metricAvalancheLevel:           return "low_avalanche"
    case metricUvIndexMax:               return "moderate_uv"
    }
    return "best_score"
}

// WinnerTagsTyped ersetzt WinnerTags() und gibt []CompareTag statt []string zurück.
// Die Label-Strings bleiben identisch zur bisherigen WinnerTags-Implementierung.
func WinnerTagsTyped(winner model.SegmentWeatherSummary, profile ActivityProfile) []CompareTag
```

`WinnerTags()` (→ `[]string`) wird im selben Commit entfernt. Die Profil-Gewichtungen und Normalisierungslogik in `ScoreRow()` bleiben unverändert.

### §5 `internal/handler/compare_run.go` — Validierungslogik

Validierungsreihenfolge und 400-Fehlerfälle:

| Bedingung | HTTP 400 `error`-Feld |
|-----------|----------------------|
| `len(location_ids) < 2` | `"too_few_locations"` |
| `date_from` nicht parsebar als `"YYYY-MM-DD"` | `"invalid_date_from"` |
| `date_to` nicht parsebar als `"YYYY-MM-DD"` | `"invalid_date_to"` |
| `date_from > date_to` | `"invalid_date_range"` |
| `date_to > heute+9` (max 240h OpenMeteo-Limit) | `"date_range_too_large"` |
| `hour_from < 0 || hour_from > 23` | `"invalid_hour_from"` |
| `hour_to < 0 || hour_to > 23` | `"invalid_hour_to"` |
| `hour_from > hour_to` | `"invalid_hour_range"` |
| `profile` nicht in `validProfiles` | `"invalid_profile"` |

Response-Body bei 400: `{"error": "<code>", "message": "<lesbare Beschreibung>"}`.

### §6 `internal/handler/compare_run_test.go` — Testmigration + neue Fälle

**Migration bestehender 8 Tests:**
- Request-Body: `"date"` → `"date_from"/"date_to"`, `"hour_from": 0`, `"hour_to": 23`
- Response-Assertions: `result.Rows` → `result.Ranking`, `result.Winner` → `result.Ranking[0].Tags`

**5 neue Testfälle:**
1. `date_from > date_to` → HTTP 400, `error: "invalid_date_range"`
2. `date_to > heute+9` → HTTP 400, `error: "date_range_too_large"`
3. `hour_from > hour_to` → HTTP 400, `error: "invalid_hour_range"`
4. Multi-Day: `date_from="2026-06-15"`, `date_to="2026-06-17"`, `hour_from=8`, `hour_to=16` → `ranking` mit 2 Einträgen, beide `score ∈ [0, 100]`
5. `stunden_verlauf` enthält nur Datenpunkte mit UTC-Stunde in `[hour_from..hour_to]`

Alle Tests verwenden echte OpenMeteo-API-Calls — keine Mocks.

### §7 LoC-Schätzung

| Datei | Änderung | Delta-LoC |
|-------|----------|-----------|
| `internal/compare/types.go` | DTOs vollständig ersetzt | +50 |
| `internal/compare/cache.go` | cacheKey-Felder erweitert | +5 |
| `internal/compare/engine.go` | aggregateByDateRange, filterByDateRange, neue Result-Konstruktion | +80 |
| `internal/compare/scoring.go` | WinnerTagsTyped + typeFor | +20 |
| `internal/handler/compare_run.go` | Neue Validierungslogik | +20 |
| `internal/handler/compare_run_test.go` | 8 Tests migriert + 5 neue | +40 |
| **Summe** | | **~215 LoC** |

LoC-Override vor Implementierungsstart: `workflow.py set-field loc_limit_override 250`

## Expected Behavior

- **Input:** `POST /api/compare/run` mit Body `{ "location_ids": ["uuid-a", "uuid-b"], "date_from": "2026-06-15", "date_to": "2026-06-17", "hour_from": 8, "hour_to": 16, "profile": "SUMMER_TREKKING" }`. Mindestens 2 Location-UUIDs. Authentifizierter Request (Auth-Middleware aktiv). `date_to` maximal `heute+9`.
- **Output:** `CompareResult` als JSON mit:
  - `ranking`: alle N Locations absteigend nach Score sortiert; jeder Eintrag mit `location_id`, `name`, `score` (0-100) und `tags` (aus `WinnerTagsTyped`, nur für `ranking[0]` nicht-leer)
  - `matrix`: alle N Locations mit `metrics` als flat `map[string]any` (SegmentWeatherSummary-Felder)
  - `stunden_verlauf`: alle N Locations, gefilterte Stundenpunkte mit 7 Feldern pro Stunde
  - HTTP 200
- **Side effects:**
  - Neue Forecast-Calls werden für 15 Minuten im In-Memory-Cache gecacht (Key: location_id × date_from × date_to × hour_from × hour_to × profile).
  - Kein Write auf das Dateisystem.
  - Bei Partial-Failure einer einzelnen Location: übrige Locations im Response, kein 500-Fehler.
  - Der alte `GET /api/compare`-Endpoint bleibt unverändert.

## Acceptance Criteria

**AC-1:** Given 2 valide Location-IDs, `date_from = date_to = heute`, `hour_from = 0`, `hour_to = 23`, `profile = "ALLGEMEIN"` / When `POST /api/compare/run` aufgerufen wird / Then enthält die Response `ranking` mit genau 2 Einträgen, jeder mit `score` ∈ [0, 100] und nicht-leerem `name`-Feld; der Eintrag mit dem höheren Score steht an Position 0.

**AC-2:** Given identischer Request mit `profile = "WINTERSPORT"` und danach `profile = "SUMMER_TREKKING"` bei gleichen Locations und Datumsangaben / When `POST /api/compare/run` zweimal aufgerufen wird / Then können sich `ranking`-Reihenfolge und `matrix`-Metriken-Gewichtung zwischen den Aufrufen unterscheiden (Profil-abhängige Scoring-Logik).

**AC-3:** Given N Locations werden parallel abgerufen (Goroutine-Implementierung) / When `POST /api/compare/run` mit 3 Locations aufgerufen wird / Then ist die gemessene Antwortzeit höchstens doppelt so hoch wie ein Einzelabruf (kein sequenzieller Fetch).

**AC-4:** Given derselbe Request (`location_ids`, `date_from`, `date_to`, `hour_from`, `hour_to`, `profile`) wird innerhalb von 15 Minuten zweimal gestellt / When der zweite Request eintrifft / Then liefert er identische `ranking`-Scores und ist messbar schneller als der erste Aufruf (Cache-Hit, kein OpenMeteo-Fetch).

**AC-5:** Given `date_from = "2026-06-17"`, `date_to = "2026-06-15"` (`date_from > date_to`) / When `POST /api/compare/run` aufgerufen wird / Then antwortet der Endpoint mit HTTP 400 und `{"error": "invalid_date_range", ...}`.

**AC-6:** Given `date_to` ist mehr als 9 Tage in der Zukunft (`> heute+9`) / When `POST /api/compare/run` aufgerufen wird / Then antwortet der Endpoint mit HTTP 400 und `{"error": "date_range_too_large", ...}`.

**AC-7:** Given `hour_from = 8`, `hour_to = 16`, `date_from = date_to = valides Datum` / When `POST /api/compare/run` aufgerufen wird / Then enthält jede Location in `stunden_verlauf` ausschließlich Datenpunkte mit UTC-Stunde `h`, für die gilt: `8 ≤ h ≤ 16`; Punkte außerhalb dieses Fensters sind nicht enthalten.

## Known Limitations

- **Lawinenstufe (ALPINE_TOURING):** `ForecastDataPoint` enthält kein Lawinenstufe-Feld. Der 35%-Gewichtungsanteil dieses Profils wird weiterhin mit Wert 0 behandelt — das Ranking basiert effektiv auf Neuschnee, Sicht und Wind. Unverändert gegenüber Issue #250.
- **`stunden_verlauf` bei Multi-Day:** Bei mehreren Tagen kann `stunden_verlauf` eine große Anzahl an Datenpunkten enthalten (z.B. 3 Tage × 9 Stunden × N Locations). Keine Paginierung oder Komprimierung in diesem Issue.
- **`matrix`-Felder nicht typisiert:** `metrics` ist `map[string]any` — das Frontend muss die Feldnamen kennen und selbst casten. Ein typisiertes DTO wäre robuster, ist aber out of scope.
- **Cache ohne Größenbeschränkung:** Der In-Memory-Cache wächst linear mit der Anzahl einzigartiger Anfrage-Kombinationen. Im normalen Betrieb (wenige Dutzend Locations, begrenzter Datums-Bereich) unkritisch.
- **`date_to > heute+9`-Limit:** OpenMeteo liefert keine Forecast-Daten über 240h hinaus. Anfragen mit größerem Bereich werden mit 400 abgewiesen. Langzeitplanung über 9 Tage ist damit nicht möglich.

## Changelog

- 2026-05-29: Initial spec — Issue #454. Breaking-Change-Erweiterung der Compare-Engine: date_from/date_to/hour_from/hour_to statt date, Multi-Day-Aggregation, neues Response-Format (ranking/matrix/stunden_verlauf), WinnerTagsTyped. ~215 Delta-LoC, LoC-Override auf 250 erforderlich. Sub-Issue von Epic #246.
