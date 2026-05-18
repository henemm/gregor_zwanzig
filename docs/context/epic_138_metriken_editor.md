# Context: Epic 138 — Wetter-Metriken-Editor

## Request Summary

User möchte einen vollständigen Wetter-Metriken-Editor im "Wetter-Metriken"-Tab der Trip-Detail-Ansicht. User wählt aus 26 Metriken (5 Gruppen), welche ins Briefing kommen — mit 7 Presets und pro-Metrik Roh/Indikator-Toggle für 12 Metriken mit Skala-Mapping.

## Related Files

| File | Relevanz |
|------|----------|
| `src/app/metric_catalog.py` | Single Source of Truth: 26 MetricDefinitions, 7 WEATHER_TEMPLATES, `has_friendly_format` Property |
| `src/app/models.py:455–525` | `MetricConfig` (metric_id, enabled, use_friendly_format), `UnifiedWeatherDisplayConfig` |
| `src/app/loader.py:292,566,692,900` | Serialisierung von `use_friendly_format` ↔ JSON |
| `internal/handler/weather_config.go` | `GET/PUT /api/trips/{id}/weather-config` — vollständig implementiert |
| `cmd/server/main.go:97–98` | Proxy-Routen für weather-config |
| `api/routers/config.py` | `GET /metrics` (Katalog) + `GET /templates` (Templates) |
| `frontend/src/lib/components/WeatherConfigDialog.svelte` | Dialog-Variante: enable/disable + Templates. KEIN use_friendly_format-Toggle. |
| `frontend/src/lib/components/edit/EditWeatherSection.svelte` | Inline-Variante (Wizard): Template-Select + Checkboxen + keine Roh/Indikator-Toggle |
| `frontend/src/lib/components/trip-detail/TripTabs.svelte` | "weather"-Tab ist definiert, zeigt nur Platzhalter-Text |
| `frontend/src/routes/trips/[id]/+page.svelte` | Trip-Detail-Seite — rendert TripTabs |

## Existing Patterns

- **WeatherConfigDialog** (Dialog-Variante, für Locations/Subscriptions): Lädt `/api/metrics` + `/api/templates`, zeigt Checkboxen gruppiert nach Kategorie, Template-Select, speichert via `onsave`-Callback.
- **EditWeatherSection** (Inline-Variante, Wizard): Gleiches Muster als Inline-Komponente ohne Dialog-Wrapper. Bindet `displayConfig` bidirektional.
- **Backend:** `GET /api/trips/{id}/weather-config` → `trip.DisplayConfig` als JSON. `PUT` schreibt zurück. Identisch für Locations und Subscriptions.
- **MetricConfig.use_friendly_format:** Im Backend serialisiert/deserialisiert, vom Renderer ausgewertet. Im Frontend bisher NICHT exponiert.

## Was bereits existiert (kein Re-Implementieren!)

- 26 Metriken im MetricCatalog ✓
- 7 Templates in `WEATHER_TEMPLATES` ✓
- `GET/PUT /api/trips/{id}/weather-config` Endpoints ✓
- `WeatherConfigDialog` mit Template-Select + Checkboxen ✓
- `MetricConfig.use_friendly_format` im Backend + Loader ✓

## Was fehlt (Epic 6 Scope)

1. **WeatherMetricsTab-Komponente** — ersetzt Platzhalter-Text im "weather"-Tab von `TripTabs.svelte`
2. **Roh/Indikator-Toggle** pro Metrik im Editor (für die 12 Metriken mit `has_friendly_format=True`)
3. **`use_friendly_format` im Save-Payload** — `WeatherConfigDialog.handleSave()` schreibt aktuell nur `{metric_id, enabled}` — `use_friendly_format` fehlt

## Metriken mit Indikator-Format (12 Stück)

Die folgenden MetricDefinitions haben `friendly_label != ""` (d.h. `has_friendly_format = True`):

| metric_id | friendly_label | Indikator-Beispiel |
|-----------|---------------|-------------------|
| wind_direction | N/S/W/E | Windrichtung als Himmelsrichtung |
| cloud_total | ☀️⛅☁️ | Bewölkungs-Emoji |
| cloud_low | ☀️⛅☁️ | Tiefe Wolken Emoji |
| cloud_mid | ☀️⛅☁️ | Mittelhohe Wolken Emoji |
| cloud_high | ☀️⛅☁️ | Hohe Wolken Emoji |
| visibility | good/fog | Sichtweite als Text |
| sunshine | ☀️🌙☁️ | Sonnenschein als Emoji |
| thunder | ⚡ | Gewitterlevel als Symbol |
| cape | 🟢🟡🔴 | CAPE-Energie als Farb-Dot |
| temperature | (kein friendly_label) | — |
| wind_chill | (kein friendly_label) | — |
| humidity | (kein friendly_label) | — |

*(exakte Liste aus metric_catalog.py — nur die mit non-empty friendly_label zählen)*

## API-Kontrakt: Save-Payload

Aktuell schreibt `WeatherConfigDialog`:
```json
{ "metrics": [{"metric_id": "temperature", "enabled": true}] }
```

Soll nach Epic 6 schreiben:
```json
{ "metrics": [{"metric_id": "temperature", "enabled": true, "use_friendly_format": true}] }
```

Der Loader (`src/app/loader.py:292`) liest `use_friendly_format` bereits korrekt, Default `True`.

## Dependencies

- **Upstream:** `GET /api/metrics`, `GET /api/templates`, `GET /api/trips/{id}/weather-config`
- **Downstream:** Trip-Report-Formatter liest `use_friendly_format` aus der gespeicherten Config

## Risks & Considerations

- `WeatherConfigDialog` wird für Locations/Subscriptions und durch EditWeatherSection für den Wizard verwendet — Änderungen am Save-Payload müssen rückwärtskompatibel sein (Loader hat Default `True`, also unkritisch)
- Der Tab-Content-Bereich existiert als Platzhalter — neue Komponente muss dort eingehängt werden
- 12 Metriken mit Indikator vs. 14 ohne — UX muss klar unterscheiden (Toggle nur anzeigen wenn relevant)
- Datenverlust-Schutz: Beim Speichern MUSS Read-Modify-Write erfolgen (nicht nur metrics-Array überschreiben)
