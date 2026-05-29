# Context: Issue #454 — Compare-Engine Backend (Wetter N Orte × Profil-Scoring)

## Request Summary

Ein neuer oder erweiterter `POST /api/compare/run`-Endpoint, der für N ausgewählte Locations Wetterdaten parallel abruft, nach Aktivitätsprofil gewichtet und ein Score-Ranking mit drei Antwort-Blöcken (`ranking`, `matrix`, `stunden_verlauf`) zurückgibt. Sub-Issue von Epic #246.

---

## Kritischer Befund: Endpoint existiert bereits

Die gesamte Compare-Engine wurde in Issue #250 implementiert und ist live:

| Datei | Status |
|-------|--------|
| `internal/compare/engine.go` | Implementiert — paralleles Fetch (sync.WaitGroup), Aggregation, Cache-Integration |
| `internal/compare/scoring.go` | Implementiert — 4 Profile mit gewichteten metricSpec-Einträgen, ScoreRow, WinnerTags |
| `internal/compare/cache.go` | Implementiert — 15-Min TTL-Cache, Key: location_id × date × profile |
| `internal/compare/types.go` | Implementiert — CompareRequest, CompareResult, CompareRow, CompareWinner, ActivityProfile |
| `internal/handler/compare_run.go` | Implementiert — HTTP-Handler mit Validierung |
| `internal/handler/compare_run_test.go` | 8 Tests, alle grün |
| `cmd/server/main.go` | Route `POST /api/compare/run` registriert |

### Delta: Was #454 gegenüber dem Bestehenden neu braucht

| Bereich | Bestand (Issue #250) | Ziel (Issue #454) |
|---------|---------------------|-------------------|
| Request: Datum | `date: "YYYY-MM-DD"` (einzelner Tag) | `date_from` + `date_to` (Datumsbereich) |
| Request: Stunden | fehlt | `hour_from: int`, `hour_to: int` |
| Response: Ranking | `rows: [{location_id, score, rank, metrics: SegmentWeatherSummary}]` | `ranking: [{location_id, name, score, tags: [{type, label}]}]` |
| Response: Metriken | `metrics: SegmentWeatherSummary` (Go-Struct) | `matrix: [{location_id, metrics: {key: value}}]` (flat dict) |
| Response: Stunden | `hourly: {location_id: [ForecastDataPoint]}` (map + raw DP) | `stunden_verlauf: [{location_id, hours: [{hour, values}]}]` |
| Winner-Tags | `tags: []string` (einfache Labels) | `tags: [{type, label}]` (typisiert) |

---

## Related Files

| Datei | Relevanz |
|-------|----------|
| `internal/compare/engine.go` | Core-Orchestrierung — wird erweitert (date_from/to, hour_from/to) |
| `internal/compare/types.go` | DTOs — CompareRequest + CompareResult Format ändert sich |
| `internal/compare/scoring.go` | Scoring — bleibt weitgehend unverändert |
| `internal/compare/cache.go` | Cache-Key muss date_from/to + hour_from/to aufnehmen |
| `internal/handler/compare_run.go` | HTTP-Handler — neue Request-Validierung |
| `internal/handler/compare_run_test.go` | Bestehende Tests — müssen kompatibel bleiben |
| `internal/model/location.go` | Location-Struct — enthält `Name`, `Lat`, `Lon`, `ActivityProfile` |
| `internal/store/store.go` | `LoadLocation(id)`, `WithUser(userId)` — unchanged |
| `internal/provider/openmeteo/provider.go` | `FetchForecast(lat, lon, hours)` — unchanged |
| `internal/model/segment.go` | `SegmentWeatherSummary` — Basis für Aggregation, bleibt |
| `cmd/server/main.go` | Route bereits registriert, Engine-Init bleibt |
| `docs/specs/modules/issue_250_compare_engine.md` | Alter Spec — #454 ist Erweiterung davon |

---

## Existing Patterns

- **Parallel-Fetch:** `sync.WaitGroup` + `sync.Mutex` in `engine.go:Run()` — identisches Pattern bleibt für Multi-Date
- **Cache-Key-Struct:** `cacheKey{LocationID, Date, Profile}` — muss um `DateFrom`, `DateTo`, `HourFrom`, `HourTo` erweitert werden
- **Partial-Result:** Locations, die nicht ladbar sind, werden still gedroppt — bleibt
- **Profil-Validierung:** `IsValidProfile(p)` in `types.go` — bleibt
- **Date-Validierung:** `time.Parse("2006-01-02", req.Date)` — wird auf DateFrom/DateTo ausgeweitet
- **Aggregation pro Tag:** `aggregateByDate(points, dateStr)` in `engine.go` — wird auf Datumsbereich ausgeweitet
- **Top-3 Hourly:** Stundenwerte nur für Top-3 Locations — bleibt, anderes Format

---

## Dependencies

**Upstream (wird verwendet):**
- `internal/provider`: `FetchForecast(lat, lon, hours int) (*Timeseries, error)` — braucht ggf. mehr Stunden für Datumsbereich
- `internal/store`: `LoadLocation(id string) (*Location, error)` via `WithUser()`
- `internal/model`: `SegmentWeatherSummary`, `ForecastDataPoint`, `Location`

**Downstream (verwendet den Endpoint):**
- `#453` — Locations-Verwaltung Frontend (Rail) → konsumiert `ranking` für Score-Badges
- `#455` — Compare-Hauptbühne Frontend → konsumiert `ranking` + `matrix` + `stunden_verlauf`
- `#456` — Auto-Briefings → triggert denselben Endpoint
- `#457` — Compare-E-Mail → konsumiert Engine-Output als Basis

---

## Existing Specs

- `docs/specs/modules/issue_250_compare_engine.md` — Implementierter Vorgänger, vollständig
- `docs/specs/modules/issue_132_compare_activity_profiles.md` — Profil-Integration Frontend
- `docs/specs/modules/issue_366_compare_score_recalibration.md` — Score-Schwellen-Kalibrierung
- `docs/specs/modules/issue_362_score_toggle.md` — Score-Member-Toggle per Location

---

---

## Analyse-Ergebnisse (Phase 2)

### Architektur-Entscheidung: Breaking Change auf demselben Endpoint

- Frontend ruft `POST /api/compare/run` **noch nicht auf** (nur ein Kommentar in `types.ts`) — Breaking Change ist sicher
- Alte Komponenten (HourlyMatrix, CompareMatrix, RecommendationBanner) aus #251 werden durch #455 ersetzt → kein aktiver Konsument des alten Formats

### Antworten auf offene Fragen

| Frage | Antwort |
|-------|---------|
| Multi-Day-Aggregation | Eine `SegmentWeatherSummary` über den gesamten Bereich: TempMin=min aller Tage, PrecipSum=sum, SunnyHours=sum, WindMax=max etc. |
| `matrix`-Keys | `SegmentWeatherSummary` JSON-Feldnamen (`temp_max_c`, `wind_max_kmh`, `precip_sum_mm`, `sunny_hours_h`, ...) via `json.Marshal` → `map[string]any` |
| `stunden_verlauf` pro Stunde | Subset: `hour`, `t2m_c`, `wind10m_kmh`, `gust_kmh`, `precip_1h_mm`, `cloud_total_pct`, `thunder_level`, `visibility_m` |
| Tag-Typen | machine-readable: `"best_snow"`, `"best_sun"`, `"low_wind"`, `"low_rain"`, `"good_visibility"`, `"low_thunder"`, `"best_temp"` |
| `hour_from`/`hour_to` | UTC (System-Standard; Ortszeit würde Timezone-Lookup erfordern) |
| Trip-Pipeline-Adapter | Bereits erfüllt — `model.Location` hat `Lat`/`Lon` als Pflichtfelder, Engine arbeitet nur damit |
| Provider-Stunden | Dynamisch: `hours = ceil((dateTo - now) × 24) + 24`; Limit: date_to max heute+10 (240h) |

### Implementierungsplan

**Reihenfolge der Dateien:**

| # | Datei | Änderung | Delta-LoC |
|---|-------|----------|-----------|
| 1 | `internal/compare/types.go` | CompareRequest + CompareResult vollständig neu | +50 |
| 2 | `internal/compare/cache.go` | cacheKey: DateFrom/DateTo/HourFrom/HourTo statt Date | +5 |
| 3 | `internal/compare/engine.go` | `aggregateByDateRange`, `filterByDateRange`, neue Result-Konstruktion | +80 |
| 4 | `internal/compare/scoring.go` | `WinnerTagsTyped` + `typeFor()` | +20 |
| 5 | `internal/handler/compare_run.go` | Neue Validierung für date_from/date_to/hour_from/hour_to | +20 |
| 6 | `internal/handler/compare_run_test.go` | Test-Migration + neue Testfälle | +40 |
| **Σ** | **5 Produktionsdateien + 1 Test** | | **~215 LoC** |

**Kein LoC-Override nötig** (215 < 250-Limit).

### Risiken

1. **FetchForecast-Limit:** Bei `date_to > heute+10` → Handler gibt 400 zurück ("date_range_too_large")
2. **Test-Migration:** 8 bestehende Tests kompilieren nicht mehr (gewollt, kontrolliert)
3. **SunnyHours summiert:** Über 7 Tage = 7× Tageswert — konzeptionell korrekt, da Score-Normalisierung relativ ist

---

## Offene Fragen für Phase 2 (ursprünglich, gelöst)

1. **Rückwärtskompatibilität:** Gibt es noch aktive Frontend-Komponenten, die das alte `rows`/`winner`/`hourly`-Format konsumieren? Falls ja: neues Format als Ergänzung oder Ersatz?
2. **Multi-Day-Aggregation:** `date_from` + `date_to` → aggregieren über alle Tage (Durchschnitt) oder bestes-Tag-Ranking zurückgeben?
3. **`matrix`-Format:** Welche konkreten Keys hat `{key: value}`? (`temp_max_c`, `precip_sum_mm`, ...)?
4. **`stunden_verlauf`-Format:** Was enthält `values` pro Stunde? Subset der ForecastDataPoint-Felder?
5. **Tag-Typen:** Was sind gültige `type`-Werte in `tags: [{type, label}]`?
6. **`hour_from`/`hour_to`:** Lokale Ortszeit oder UTC?
7. **Trip-Pipeline-Adapter:** Issue erwähnt "bare Coordinates ohne Stage/Waypoints" — ist das ein zweiter Request-Typ oder nur intern?
8. **Provider-Stunden-Tiefe:** `FetchForecast(lat, lon, 72)` reicht für 3 Tage. Bei date_to > heute+3 → andere Anforderung?

---

## Risks & Considerations

- **Breaking Change:** Änderung des Response-Formats bricht die bestehenden 8 Tests und potenziell laufende Frontend-Komponenten
- **Cache-Key-Änderung:** Alter Cache-Key (`LocationID × Date × Profile`) wird inkompatibel → Cache-Einträge veralten sofort nach Deploy
- **Multi-Day-Performance:** Für Datumsbereich >3 Tage: `FetchForecast` muss mit mehr als 72h parametriert werden (Open-Meteo-Grenze: heute+15 Tage)
- **Backward Compatibility:** Alte Spec-Tests referenzieren `CompareResult.Rows` / `CompareResult.Winner` — müssen mitgeführt oder migriert werden
