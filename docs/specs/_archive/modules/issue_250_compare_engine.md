---
entity_id: issue_250_compare_engine
type: module
created: 2026-05-19
updated: 2026-05-19
status: draft
version: "1.0"
issue: 250
tags: [compare, go, engine, scoring, cache, goroutines, api]
---

# Issue #250 — Compare-Engine Backend: POST /api/compare/run

## Approval

- [ ] Approved

## Purpose

Implementiert einen neuen Go-nativen Endpoint `POST /api/compare/run`, der Wetterdaten für N Locations parallel via Goroutines abruft, sie nach einem von vier Aktivitätsprofilen gewichtet bewertet und ein sortiertes Ranking als JSON-Response zurückgibt. Der Endpoint ersetzt die bestehende sequenzielle Python-Delegation (`GET /api/compare`) für die Compare-Engine-Logik, ohne den bestehenden Python-Proxy-Endpoint zu verändern, und bedient den Compare-Screen im Frontend (Issue #249).

## Source

- **NEU:** `internal/compare/engine.go` — Core-Orchestrierung: paralleler Forecast-Fetch, Aggregation, Scoring-Aufruf, Cache-Integration
- **NEU:** `internal/compare/scoring.go` — Profil-gewichtetes Scoring (config-getrieben, 4 Profile)
- **NEU:** `internal/compare/cache.go` — 15-Minuten In-Memory-Cache mit Key `location_id × date × profile`
- **NEU:** `internal/compare/types.go` — DTOs: `CompareRequest`, `CompareResult`, `CompareRow`, `CompareWinner`, `ActivityProfile`
- **NEU:** `internal/handler/compare_run.go` — HTTP-Handler für `POST /api/compare/run`
- **NEU:** `internal/handler/compare_run_test.go` — Integrationstests (keine Mocks, echte OpenMeteo-Calls)
- **EDIT:** `cmd/server/main.go` — Route `r.Post("/api/compare/run", ...)` registrieren (1 Zeile)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `OpenMeteoProvider.FetchForecast(lat, lon, hours)` (`internal/provider/openmeteo/provider.go`) | intern | Liefert `*model.Timeseries` für eine Location; wird parallel pro Location aufgerufen |
| `aggregateForecasts(points []model.ForecastDataPoint, date time.Time)` (`internal/handler/stage_weather.go`) | intern | Aggregiert ForecastDataPoints für ein Datum zu Metriken; wird für jede Location adaptiert übernommen |
| `store.LoadLocation(userID, locationID string)` (`internal/store/store.go`) | intern | Lädt Location-Struct (Lat, Lon, ElevationM) aus JSON; benötigt Auth-Kontext via `WithUser()` |
| `model.SegmentWeatherSummary` (`internal/model/segment.go`) | intern | Basis-DTO für aggregierte Metriken (Temperatur, Wind, Regen, Schnee, UV, etc.) |
| `model.ForecastDataPoint` / `model.Timeseries` (`internal/model/forecast.go`) | intern | Rohdaten-Structs aus OpenMeteo-Provider |
| `model.Location` (`internal/model/location.go`) | intern | Location-Struct mit Lat/Lon/ElevationM; enthält seit Issue #247 auch Timezone, DataSource, CreatedAt |
| `sync.WaitGroup` + `sync.Mutex` (Go-Stdlib) | extern | Goroutine-Koordination; Pattern identisch zu `StagesWeatherHandler` in `stage_weather.go:26–45` |
| Auth-Middleware / `WithUser()` | intern | Handler-Request muss User-Context tragen, damit `store.LoadLocation()` den richtigen Datenpfad bestimmt |

## Implementation Details

### §1 `internal/compare/types.go` — DTOs

```go
type ActivityProfile string

const (
    ProfileWintersport    ActivityProfile = "WINTERSPORT"
    ProfileAlpineTouring  ActivityProfile = "ALPINE_TOURING"
    ProfileSummerTrekking ActivityProfile = "SUMMER_TREKKING"
    ProfileAllgemein      ActivityProfile = "ALLGEMEIN"
)

type CompareRequest struct {
    LocationIDs []string        `json:"location_ids"`  // normierte IDs (kebab-case)
    Date        string          `json:"date"`           // "YYYY-MM-DD"
    Profile     ActivityProfile `json:"profile"`
}

type CompareRow struct {
    LocationID string                 `json:"location_id"`
    Score      int                    `json:"score"`   // 0–100
    Rank       int                    `json:"rank"`    // 1 = bester
    Metrics    model.SegmentWeatherSummary `json:"metrics"`
}

type CompareWinner struct {
    LocationID string   `json:"location_id"`
    Tags       []string `json:"tags"`  // z.B. ["Wenig Regen", "Gute Sicht"]
}

type CompareResult struct {
    Rows   []CompareRow                      `json:"rows"`
    Winner CompareWinner                     `json:"winner"`
    Hourly map[string][]model.ForecastDataPoint `json:"hourly"` // Top-3 LocationIDs → Stundenwerte
}
```

### §2 `internal/compare/scoring.go` — Profil-Gewichtungen (config-getrieben)

Gewichtungen als Package-Level-Konstanten, nicht hartcodiert in Scoring-Logik. Vier Profile:

| Profil | Metrik | Gewicht |
|--------|--------|---------|
| WINTERSPORT | Schnee cm | 0.30 |
| WINTERSPORT | Neuschnee | 0.25 |
| WINTERSPORT | Sonnenstunden | 0.20 |
| WINTERSPORT | Wind/Böen | 0.15 |
| WINTERSPORT | Wolkenlage | 0.10 |
| ALPINE_TOURING | Lawinenstufe | 0.35 |
| ALPINE_TOURING | Neuschnee | 0.25 |
| ALPINE_TOURING | Sicht | 0.20 |
| ALPINE_TOURING | Wind | 0.20 |
| SUMMER_TREKKING | Regen | 0.30 |
| SUMMER_TREKKING | Gewitterwahrscheinlichkeit | 0.25 |
| SUMMER_TREKKING | Wind | 0.20 |
| SUMMER_TREKKING | UV | 0.15 |
| SUMMER_TREKKING | Sicht | 0.10 |
| ALLGEMEIN | Temperatur | 0.25 |
| ALLGEMEIN | Wind | 0.25 |
| ALLGEMEIN | Regen | 0.25 |
| ALLGEMEIN | Sicht | 0.25 |

**Score-Normalisierung:** Relativ — der beste Wert pro Metrik über alle verglichenen Locations erhält 100%, alle anderen werden proportional skaliert. Bei negativen Metriken (Regen, Wind) wird die Location mit dem niedrigsten Wert als 100% gewertet.

**Lawinenstufe (ALPINE_TOURING):** Kein Feld in `ForecastDataPoint`. Wird als `0` (neutraler Wert) behandelt — der Gewichtungsanteil von 35% fällt damit gleichmäßig auf alle Locations und beeinflusst das Ranking nicht. Kein Fehler, kein Log-Warning; dieser Placeholder ist in `Known Limitations` dokumentiert.

**Tags für Winner:** Aus den Top-2 Metriken mit dem höchsten Gewicht werden lesbare Strings generiert, z.B. `"Wenig Regen"`, `"Gute Sicht"`, `"Viel Schnee"`. Pro Metrik gibt es eine feste Tag-Map in einer Package-Konstante.

**Signaturen:**

```go
// ScoreRow berechnet den Gesamt-Score einer Location für ein Profil.
// allMetrics enthält die aggregierten Metriken aller verglichenen Locations (für Normalisierung).
func ScoreRow(loc model.SegmentWeatherSummary, profile ActivityProfile, allMetrics []model.SegmentWeatherSummary) int

// WinnerTags gibt 2–3 beschreibende Tags für die Gewinner-Location zurück.
func WinnerTags(winner model.SegmentWeatherSummary, profile ActivityProfile) []string
```

### §3 `internal/compare/cache.go` — 15-Min In-Memory-Cache

```go
type cacheKey struct {
    LocationID string
    Date       string  // "YYYY-MM-DD"
    Profile    ActivityProfile
}

type cachedEntry struct {
    result    CompareRow
    expiresAt time.Time
}
```

- `sync.RWMutex` für Thread-Safety
- `Get(key cacheKey) (CompareRow, bool)` — gibt Eintrag zurück wenn `time.Now().Before(entry.expiresAt)`
- `Set(key cacheKey, row CompareRow)` — setzt TTL auf `time.Now().Add(15 * time.Minute)`
- Kein Eviction-Mechanismus über TTL hinaus — Cache wächst linear mit Anzahl Location × Date × Profile-Kombinationen; bei diesem Use-Case unkritisch

### §4 `internal/compare/engine.go` — Core-Orchestrierung

**Run(ctx, userID, req CompareRequest) (CompareResult, error):**

1. Für jede `location_id` in `req.LocationIDs` parallel (Goroutine + WaitGroup):
   a. Cache-Lookup mit Key `{location_id, date, profile}` — bei Hit: cached Row verwenden, kein Fetch
   b. Cache-Miss: `store.LoadLocation(userID, locationID)` → Lat/Lon/ElevationM
   c. `provider.FetchForecast(lat, lon, 72)` → `*model.Timeseries`
   d. `aggregateForecasts(timeseries.Points, parsedDate)` → `model.SegmentWeatherSummary`
   e. Ergebnis in `results` map schreiben (Mutex)
2. Nach WaitGroup.Wait(): Alle `SegmentWeatherSummary` zusammen an `ScoreRow()` übergeben (Normalisierung braucht alle Werte gleichzeitig)
3. `CompareRow` für jede Location aufbauen: `{LocationID, Score, Metrics}`
4. `rows` nach `Score` absteigend sortieren, `Rank` von 1 aufwärts vergeben
5. `Winner` = `rows[0]`, `Tags` via `WinnerTags()`
6. `Hourly`: für Top-3 LocationIDs die rohen Stundenwerte aus dem gecachten Timeseries-Ergebnis extrahieren (Zwischenpuffer in der Goroutine mitführen)
7. Cache-Set für alle neuen Rows (nur neu abgerufene, nicht bereits gecachte)
8. `CompareResult{Rows, Winner, Hourly}` zurückgeben

**Fehlerbehandlung:** Wenn eine Location nicht ladbar ist oder der Provider-Call fehlschlägt, wird diese Location aus dem Ergebnis ausgelassen (Partial-Result). Der Response-Body enthält die erfolgreichen Rows; kein 500-Fehler bei Einzel-Fehlern.

### §5 `internal/handler/compare_run.go` — HTTP-Handler

```go
func CompareRunHandler(engine *compare.Engine) http.HandlerFunc {
    return func(w http.ResponseWriter, r *http.Request) {
        // 1. JSON-Decode CompareRequest
        // 2. Validierung: len(location_ids) >= 2, profile valide, date parsebar
        // 3. userID aus Auth-Kontext (WithUser)
        // 4. engine.Run(r.Context(), userID, req)
        // 5. JSON-Encode CompareResult → 200
        // Fehler: 400 bei Validierungsfehler, 500 bei engine-Fehler
    }
}
```

### §6 `cmd/server/main.go` — Route registrieren

Einzige Änderung: Eine Zeile nach dem bestehenden `r.Get("/api/compare", ...)`:

```go
r.Post("/api/compare/run", handler.CompareRunHandler(compareEngine))
```

`compareEngine` wird als Package-Level-Singleton instanziiert (analog zu anderen Handler-Initialisierungen in `main.go`).

### §7 LoC-Schätzung

| Datei | Inhalt | LoC |
|-------|--------|-----|
| `internal/compare/types.go` | DTOs, Profil-Enum | ~40 |
| `internal/compare/cache.go` | TTL-Cache, Get/Set | ~45 |
| `internal/compare/scoring.go` | Gewichtungen + ScoreRow + WinnerTags | ~80 |
| `internal/compare/engine.go` | Run-Funktion + Goroutines | ~90 |
| `internal/handler/compare_run.go` | HTTP-Handler | ~40 |
| `internal/handler/compare_run_test.go` | 4 Integrationstests | ~80 |
| `cmd/server/main.go` | +1 Zeile Route | +1 |
| **Summe** | | **~376 LoC** |

LoC-Limit-Override auf 400 setzen vor Implementierungsstart: `workflow.py set-field loc_limit_override 400`

## Expected Behavior

- **Input:** `POST /api/compare/run` mit Body `{ "location_ids": ["loc-a", "loc-b"], "date": "2026-06-15", "profile": "SUMMER_TREKKING" }`. Mindestens 2 LocationIDs. Authentifizierter Request (Auth-Middleware muss aktiv sein).
- **Output:** `CompareResult` als JSON mit `rows` (sortiert nach Score absteigend, Rank ab 1), `winner` (LocationID + Tags), `hourly` (Stundenwerte für Top-3 Locations). HTTP 200.
- **Side effects:**
  - Neue Forecast-Calls werden für 15 Minuten im In-Memory-Cache gecacht (Key: location_id × date × profile).
  - Bestehender `GET /api/compare`-Endpoint bleibt unverändert.
  - Keine Schreiboperationen auf dem Dateisystem.
  - Bei Partial-Failure (eine Location nicht ladbar): Response enthält die übrigen Locations, kein Fehler-Status.

## Acceptance Criteria

**AC-1:** Given zwei valide Location-IDs mit gespeicherten JSON-Dateien und ein gültiges Datum / When `POST /api/compare/run` mit `profile: "ALLGEMEIN"` aufgerufen wird / Then enthält die Response `rows` mit genau zwei Einträgen, beide mit `score` zwischen 0 und 100, und `rank` 1 und 2; der Eintrag mit dem höheren Score hat `rank: 1`.
  - Test: (populated after /tdd-red)

**AC-2:** Given derselbe Request wie AC-1 wird zweimal innerhalb von 15 Minuten gestellt / When der zweite Request eintrifft / Then ist die Antwortzeit des zweiten Requests deutlich kürzer als die des ersten (Cache-Hit) und der `score`-Wert ist identisch.
  - Test: (populated after /tdd-red)

**AC-3:** Given ein Request mit `profile: "SUMMER_TREKKING"` und zwei Locations / When die Engine den Winner bestimmt / Then enthält `winner.tags` mindestens einen nicht-leeren String, und `winner.location_id` entspricht der Location mit `rank: 1` in `rows`.
  - Test: (populated after /tdd-red)

**AC-4:** Given eine Location-ID, die nicht im Store des authentifizierten Users existiert / When `POST /api/compare/run` mit dieser und einer gültigen Location-ID aufgerufen wird / Then enthält die Response nur die ladbare Location in `rows` (Partial-Result), kein 500-Fehler.
  - Test: (populated after /tdd-red)

**AC-5:** Given ein Request mit weniger als 2 Location-IDs oder einem unbekannten Profil-Wert / When der Handler die Validierung durchführt / Then antwortet der Endpoint mit HTTP 400 und einer lesbaren Fehlermeldung; kein Fetch wird gestartet.
  - Test: (populated after /tdd-red)

**AC-6:** Given `profile: "ALPINE_TOURING"` / When die Engine die Scores berechnet / Then verursacht das fehlende Lawinenstufe-Feld (`ForecastDataPoint` hat kein avalanche-Feld) keinen Fehler; alle Locations erhalten denselben Lawinenstufe-Beitrag (0), und das Ranking basiert auf den verbleibenden Metriken (Neuschnee, Sicht, Wind).
  - Test: (populated after /tdd-red)

## Known Limitations

- **Lawinenstufe (ALPINE_TOURING):** OpenMeteo liefert keine Lawinenstufe. Der 35%-Gewichtungsanteil dieses Profils wird mit Wert 0 für alle Locations befüllt — das Ranking für ALPINE_TOURING basiert effektiv nur auf Neuschnee (25%), Sicht (20%) und Wind (20%). Eine externe Lawinendaten-Quelle (z.B. LAWIS) ist nicht im Scope dieser Spec.
- **Normalisierung bei gleichem Wetter:** Wenn alle verglichenen Locations identische Werte für eine Metrik haben, erhalten alle denselben Teilscore (100%) — kein Informationsgewinn aus dieser Metrik. Der Gesamt-Score kann bei gleichem Wetter überall bei 100 liegen, was inhaltlich korrekt, aber für den Nutzer möglicherweise verwirrend ist.
- **Cache-Eviction:** Der In-Memory-Cache hat keine Größenbeschränkung und keinen expliziten Eviction-Mechanismus. Bei sehr vielen unterschiedlichen Location × Date × Profile-Kombinationen wächst der Cache. Im normalen Betrieb (wenige Dutzend Locations) ist das unkritisch; für einen produktiven Scale-Out wäre eine Cache-Größenbeschränkung oder ein LRU-Mechanismus nötig.
- **Hourly nur Top-3:** Stundenwerte werden nur für die drei am besten bewerteten Locations zurückgegeben. Wenn weniger als 3 Locations verglichen werden, enthält `hourly` entsprechend weniger Einträge.
- **Auth-Kontext zwingend:** Der Endpoint setzt eine funktionierende Auth-Middleware voraus. Ohne gesetzten User-Kontext schlägt `store.LoadLocation()` fehl und alle Locations werden als Partial-Failure behandelt — die Response enthält dann leere `rows`.

## Changelog

- 2026-05-19: Initial spec — Issue #250. Go-nativer Compare-Engine-Endpoint mit Goroutines, 15-Min-Cache, 4 Aktivitätsprofilen, config-getriebenen Scoring-Gewichtungen, Partial-Result-Handling. ~376 LoC, LoC-Override auf 400 erforderlich.
