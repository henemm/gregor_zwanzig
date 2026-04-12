# Context: Go Project Structure + Config + JSON Store (M1c)

## Request Summary
Go-Projektstruktur aufbauen (`internal/`, `cmd/server/`), Config-System mit `envconfig` (GZ_ Prefix), und JSON Store der bestehende `data/users/` Dateien lesen kann. Fundament fuer alle CRUD-Endpoints.

## Related Files
| File | Relevance |
|------|-----------|
| cmd/gregor-api/main.go | Bestehender Go-Proxy, wird zu cmd/server/ umstrukturiert |
| cmd/gregor-api/main_test.go | Bestehende Tests, muessen angepasst werden |
| src/app/config.py | Python Config mit GZ_ Env-Prefix (Referenz) |
| src/app/loader.py | Python JSON Store (819 LOC) — Format-Referenz |
| src/app/models.py | Python DTOs (585 LOC) — Go Structs ableiten |
| data/users/default/locations/*.json | Location JSON Format |
| data/users/default/trips/*.json | Trip JSON Format |
| data/users/default/compare_subscriptions.json | Subscription Format |
| docs/project/migration-plan-go-sveltekit.md | Gesamtplan, Zielstruktur |

## Existing Patterns

### Config (Python)
- Pydantic BaseSettings mit `GZ_` Prefix
- Env-Vars: GZ_LATITUDE, GZ_LONGITUDE, GZ_PROVIDER, GZ_SMTP_HOST, etc.
- Fallback zu `.env` Datei, dann Defaults

### JSON Store (Python)
- Verzeichnisstruktur: `data/users/{user_id}/locations/`, `trips/`, `weather_snapshots/`
- Ein JSON pro Entity (Location, Trip)
- ID = Dateiname (ohne .json)
- Optionale Felder werden weggelassen (nicht null gesetzt)
- Legacy-Migration: alte `weather_config` → neue `display_config`

### Datenformate
- **Location:** id, name, lat, lon, elevation_m (opt), region (opt), activity_profile (opt), display_config (opt)
- **Trip:** id, name, stages[{id, name, date, waypoints[{id, name, lat, lon, elevation_m, time_window}]}]
- **Time Formats:** ISO "09:00:00" fuer start_time, "HH:MM-HH:MM" fuer time_window
- **Enums:** Strings ("wintersport", "daily_evening")

## Dependencies
- Upstream: `github.com/go-chi/chi/v5`, `github.com/kelseyhightower/envconfig` (neu)
- Downstream: Alle zukuenftigen M2-M4 Endpoints bauen auf Config + Store auf

## Existing Specs
- `docs/specs/modules/go_proxy_binary.md` — M1b (abgeschlossen)

## Risks & Considerations
- JSON Store muss bestehende Dateien **ohne Modifikation** lesen
- Legacy-Felder (weather_config vs display_config) muessen beide unterstuetzt werden
- Unicode in Dateinamen (hochfügen.json, mühlbach.json) — Go's os.ReadDir handelt das
- Optional nesting: omitempty in Go Struct Tags muss korrekt gesetzt sein
- Scope-Risiko: Nur Lese-Store fuer M1c, CRUD kommt spaeter
