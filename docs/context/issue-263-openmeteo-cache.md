# Context: Issue #263 — OpenMeteo-Anfragen in E2E-Tests cachen

## Request Summary

E2E-Tests (Playwright) schlagen fehl, wenn das kostenlose OpenMeteo-Tageslimit erschöpft ist. Ziel: statische JSON-Fixtures, die bei gesetzter Env-Var statt der echten API verwendet werden — kein Einfluss auf Production.

## Architektur (Ist-Stand)

```
cmd/server/main.go
  → openmeteo.NewProvider(cfg)     ← echte HTTP-Calls
  → compare.New(store, omProvider) ← Engine nimmt WeatherProvider-Interface
  → handler.CompareRunHandler(engine)
```

`provider.WeatherProvider` ist bereits ein Interface (`internal/provider/provider.go`):
```go
type WeatherProvider interface {
    FetchForecast(lat, lon float64, hours int) (*model.Timeseries, error)
}
```

Der `compare.Engine` akzeptiert schon `nil` als Provider (liefert dann leere Summaries). Die Unit-Tests in `internal/handler/compare_run_test.go` nutzen `nil` oder einen `errorProvider`-Stub — sie rufen die echte API nie auf.

## Betroffene Dateien

| Datei | Relevanz |
|-------|----------|
| `internal/provider/provider.go` | WeatherProvider-Interface |
| `internal/provider/openmeteo/provider.go` | Echte HTTP-Implementierung |
| `internal/compare/engine.go` | Nutzt WeatherProvider-Interface |
| `cmd/server/main.go` | Wiring: OpenMeteoProvider → Engine |
| `internal/config/config.go` | Config via `envconfig "GZ_..."` |
| `frontend/e2e/compare-main-stage.spec.ts` | Betroffene E2E-Tests (AC-1–AC-6) |
| `fixtures/providers/` | Bestehende Fixture-Ablage (met, mosmix, nowcastmix) |

## Vorhandene Patterns

- **Fixture-Ablage:** `fixtures/providers/*.json` — Python-Fixtures. Go braucht eigenes Verzeichnis.
- **Interface-Pluggabilität:** `compare.Engine` nimmt schon beliebige `WeatherProvider`-Impl.
- **Config-Pattern:** `envconfig:"GZ_..."` in `internal/config/config.go` — neues Feld `TestFixtureDir string` wird dort ergänzt.
- **Kein Mock-Paket:** Projekt-Konvention verbietet `testing.Mock` — echte Structs sind Pflicht.

## Lösungsdesign

**Option A (empfohlen): FixtureProvider** — neues Go-Paket `internal/provider/fixture/`

```go
// FetchForecast gibt normalisierte Timeseries aus einer JSON-Datei zurück.
// Matching: Closest-Coord aus fixture-registry.json (L1-Norm lat+lon).
func (p *FixtureProvider) FetchForecast(lat, lon float64, hours int) (*model.Timeseries, error)
```

Aktivierung in `main.go`:
```go
if cfg.TestFixtureDir != "" {
    omProvider = fixture.NewProvider(cfg.TestFixtureDir)
} else {
    omProvider = openmeteo.NewProvider(...)
}
```

Fixture-Dateien: `fixtures/openmeteo/<id>.json` — Inhalt ist `model.Timeseries` (normalisiertes Format, nicht Raw-API).

**Option B: Lokaler HTTP-Mock-Server** — zu komplex, braucht extra Go-Binary, keine Fixtures-Wiederverwendung.

## Test-Locations

| ID | Name | Lat | Lon |
|----|------|-----|-----|
| `innsbruck` | Innsbruck | 47.2692 | 11.4041 |
| `stubai` | Stubai (Neustift) | 47.1015 | 11.2958 |
| `zillertal` | Zillertal (Mayrhofen) | 47.2190 | 11.8767 |

## Fixture-Refresh-Script

`scripts/refresh-openmeteo-fixtures.sh` — ruft echte API für die 3 Test-Locations, speichert normalisiert nach `fixtures/openmeteo/`. Wird wöchentlich via Cron ausgeführt.

## Dependencies

- **Upstream:** `model.Timeseries`, `model.ForecastDataPoint`
- **Downstream:** `compare.Engine`, `compare_run_test.go`, E2E-Tests

## Risiken

1. Fixture-Daten veralten → Refresh-Cron nötig (wöchentlich)
2. Fixture-Koordinaten-Matching muss tolerant genug sein (Staging-Locations haben leicht andere Coords als Fixture-Locations)
3. E2E-Testumgebung muss `GZ_TEST_FIXTURE_DIR` kennen → `playwright.config.ts` oder `.env.test`
