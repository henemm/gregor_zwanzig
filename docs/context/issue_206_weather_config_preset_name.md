# Context: Issue #206 — Trip.weather_config.preset_name

## Request Summary

`WeatherMetricsPreviewCard` leitet den Preset-Namen aktuell aus `trip.aggregation.profile` ab (Notlösung aus Epic #135 Step 5). Issue #206 führt `Trip.weather_config.preset_name` als echtes Datenfeld ein, damit die Card den Namen direkt anzeigt — ohne Ableitung. Migration für Bestands-Trips.

## Related Files

| Datei | Relevanz |
|-------|----------|
| `internal/model/trip.go` | Go-Modell: `Trip.WeatherConfig map[string]interface{}` — kein typisiertes `preset_name`, aber JSON-Blob trägt beliebige Felder |
| `internal/handler/trip.go` | PATCH-Handler: `weatherConfig` wird als opakes Map gespeichert, kein Schema-Enforcement |
| `internal/handler/weather_config.go` | `PUT /api/trips/{id}/weather-config` → setzt `trip.DisplayConfig` (NICHT `WeatherConfig`!) |
| `src/app/models.py` | Python-DTO: `UnifiedWeatherDisplayConfig` — kein `preset_name` Feld vorhanden |
| `src/app/loader.py` | Serialisierung + Migration `_parse_display_config`, `_migrate_weather_config`, `_trip_to_dict` |
| `frontend/src/lib/types.ts` | TS-Typen: `WeatherConfig { metrics?: WeatherConfigMetric[] }` — kein `preset_name` |
| `frontend/src/lib/utils/rightColumn.ts` | `getPresetLabel()` leitet Label aus `trip.aggregation?.profile` ab — muss `preset_name` bevorzugen |
| `frontend/src/lib/components/trip-detail/WeatherMetricsPreviewCard.svelte` | Zeigt `presetLabel = getPresetLabel(trip)` — nutzt nach Fix automatisch `preset_name` |
| `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte` | Template-Select speichert aktuell nur `metrics`, NICHT den Template-Namen als `preset_name` |

## Existing Patterns

- **Go API:** `WeatherConfig` und `DisplayConfig` sind beide `map[string]interface{}` — kein typisiertes Schema, akzeptiert jedes JSON ohne Code-Änderung am Backend
- **WeatherMetricsTab speichert nach `DisplayConfig`:** `PUT /api/trips/{id}/weather-config` → `PutTripWeatherConfigHandler` → `trip.DisplayConfig` (Python: `display_config`, nicht `weather_config`)
- **Python Migration-Muster:** `_migrate_weather_config()` in `loader.py` — liest altes Feld, schreibt neues. Gleiches Muster für `preset_name`-Initialisierung aus `activity_profile` nötig
- **Kein Schema-Enforcement im Go-Layer:** `preset_name` in `DisplayConfig` einfach mitschicken, Go speichert es transparent

## Kritischer Befund: WeatherConfig vs. DisplayConfig

Das Issue spricht von `Trip.weather_config.preset_name`, aber der WeatherMetricsTab speichert über `PutTripWeatherConfigHandler` nach **`trip.DisplayConfig`** (nicht `WeatherConfig`). Frontend-Typen lesen `trip.weather_config?.metrics`. **Entscheidung für Analyse:** `preset_name` muss in `display_config` leben, weil das der Ort ist, wo die aktivierten Metriken auch gespeichert werden und den der WeatherMetricsTab schreibt.

## Dependencies

- **Upstream:** `trip.aggregation.profile` (Fallback für Migration)
- **Downstream:** `WeatherMetricsPreviewCard.svelte` (liest Label), `WeatherMetricsTab.svelte` (schreibt beim Speichern), Python-Serializer in `loader.py`

## Existing Specs

- `docs/specs/modules/weather_config.md` v2.3 — beschreibt `UnifiedWeatherDisplayConfig`, kein `preset_name` Feld

## Risks & Considerations

- **Schema-Drift Go vs. Python:** Go speichert als Blob transparent, Python braucht explizites Feld + Serialisierung
- **Migration:** Bestands-Trips haben kein `preset_name` → beim Laden aus `aggregation.profile` ableiten
- **WeatherMetricsTab:** Muss beim Speichern den gewählten Template-Namen als `preset_name` mitschicken (oder leer bei "— Eigene Auswahl —")
- **Kein Datenverlust-Risiko:** `display_config` ist ein JSON-Blob — neues Feld additiv, ältere Reads ignorieren es

## Scope Abgrenzung (Issue #206 vs. Folge-Issues)

| In Scope | Out of Scope |
|----------|--------------|
| `preset_name` als optionales Feld in `display_config` | Vollständige Preset-Verwaltung (speichern eigener Presets) |
| Migration: Bestands-Trip bekommt `preset_name` aus `activity_profile` | `preset_id` für persistierte Presets |
| WeatherMetricsTab schreibt `preset_name` beim Speichern | Neues Template-Management-UI |
| Frontend-Card liest `preset_name` direkt | |
