# Context: Issue #251 — Compare-Hauptbühne (Frontend)

## Request Summary

Die Compare-Seite soll von der alten Python-API (GET /api/compare) auf die neue Go-Engine (POST /api/compare/run) umgestellt werden. Gleichzeitig wird die UI strukturell verbessert: Preset-Kopf als Card, Empfehlungs-Banner (Winner), profil-spezifische Vergleichs-Matrix mit Mini-Bars, und Stunden-Verlauf für die Top-3 Orte.

## Ausgangslage: Was schon existiert

### Bestehende Compare-Seite
- **Datei:** `frontend/src/routes/compare/+page.svelte` (688 Zeilen)
- **Aktueller API-Aufruf:** `GET /api/compare` (alter Python-Endpoint, veraltet)
- **Vorhandene Struktur:**
  - `LocationsRail` (Sidebar, Issue #249 — bereits implementiert)
  - `NewLocationWizard` (Dialog)
  - Preset-Card mit Datum/Zeit/Stunden/Profil-Controls
  - Einfacher Winner-Banner (grüne Card, Name + Score)
  - Vergleichs-Tabelle: Metriken als Zeilen, Locations als Spalten (bestColor-Logik)
  - Wetter Drill-Down (stündliche Detailtabelle per Location)
  - Auto-Reports (Subscriptions-Liste, wenn kein Ergebnis)
  - "Als Auto-Report speichern" Button + SubscriptionForm Dialog

### Backend: POST /api/compare/run (Issue #250)
- **Route:** `POST /api/compare/run` (bereits registriert in `cmd/server/main.go:110`)
- **Handler:** `internal/handler/compare_run.go`
- **Engine:** `internal/compare/engine.go`

#### Request-Payload:
```json
{
  "location_ids": ["kebab-case-id"],
  "date": "YYYY-MM-DD",
  "profile": "WINTERSPORT|ALPINE_TOURING|SUMMER_TREKKING|ALLGEMEIN"
}
```

#### Response-Typ (CompareResult):
```go
type CompareResult struct {
    Rows   []CompareRow                         `json:"rows"`
    Winner *CompareWinner                       `json:"winner,omitempty"`
    Hourly map[string][]model.ForecastDataPoint `json:"hourly"`
}

type CompareRow struct {
    LocationID string                      `json:"location_id"`
    Score      int                         `json:"score"`       // 0–100
    Rank       int                         `json:"rank"`        // 1 = bester
    Metrics    model.SegmentWeatherSummary `json:"metrics"`
}

type CompareWinner struct {
    LocationID string   `json:"location_id"`
    Tags       []string `json:"tags"`  // z.B. ["Wenig Wind", "Viel Sonne"]
}
```

#### SegmentWeatherSummary (Metriken-Felder):
```
temp_min_c, temp_max_c, temp_avg_c
wind_max_kmh, gust_max_kmh, wind_direction_avg_deg
precip_sum_mm, precip_type_dominant
cloud_avg_pct, humidity_avg_pct
thunder_level_max, visibility_min_m, freezing_level_m
wind_chill_min_c, pop_max_pct, cape_max_jkg
pressure_avg_hpa, dewpoint_avg_c
uv_index_max, dni_avg_wm2
snow_depth_cm, snow_new_sum_cm
dominant_wmo_code
```

### Profil-Mismatch (KRITISCH!)
Frontend-Typen (`types.ts`) nutzen Kleinschreibung: `'wintersport' | 'wandern' | 'allgemein' | 'summer_trekking'`
Backend erwartet Großschreibung: `'WINTERSPORT' | 'ALPINE_TOURING' | 'SUMMER_TREKKING' | 'ALLGEMEIN'`

Außerdem: Frontend hat `'wandern'` — Backend hat `'ALPINE_TOURING'`.

→ **Frontend-Typen müssen angepasst werden**, ODER das Backend muss Kleinschreibung tolerieren (besser: Frontend anpassen, Backend ist schon deployed).

### Profil-spezifische Metriken (aus scoring.go)

| Profil | Metriken (sortiert nach Gewicht) |
|--------|----------------------------------|
| WINTERSPORT | snow_depth_cm (30%), snow_new_sum_cm (25%), dni_avg_wm2 (20%), wind_max_kmh (15%), cloud_avg_pct (10%) |
| ALPINE_TOURING | Lawinenstufe (35%, Placeholder=0), snow_new_sum_cm (25%), visibility_min_m (20%), wind_max_kmh (20%) |
| SUMMER_TREKKING | precip_sum_mm (30%), thunder_level_max (25%), wind_max_kmh (20%), uv_index_max (15%), visibility_min_m (10%) |
| ALLGEMEIN | temp_max_c (25%), wind_max_kmh (25%), precip_sum_mm (25%), visibility_min_m (25%) |

### Wichtige Einschränkung
Die Engine gibt **nur LocationIDs** zurück (keine Namen). Location-Namen müssen via `locations`-Array (aus page.server.ts) aufgelöst werden.

Die Engine gibt kein `time_window` zurück — Zeitfenster sind nur für den Request relevant, nicht Teil des Response.

## Relevante Dateien

| Datei | Relevanz |
|-------|----------|
| `frontend/src/routes/compare/+page.svelte` | **Hauptdatei** — wird umgebaut |
| `frontend/src/routes/compare/+page.server.ts` | Lädt `locations` und `subscriptions` für SSR |
| `frontend/src/lib/types.ts` | ActivityProfile + ForecastDataPoint Types — Profile-Enum muss angepasst werden |
| `frontend/src/lib/components/compare/LocationsRail.svelte` | Sidebar (unverändert) |
| `frontend/src/lib/components/compare/NewLocationWizard.svelte` | Dialog (unverändert) |
| `frontend/src/lib/components/SubscriptionForm.svelte` | Für "Als Auto-Report speichern" (unverändert) |
| `internal/compare/types.go` | Backend-DTOs |
| `internal/compare/scoring.go` | Profil-Metriken + WinnerTags |
| `internal/handler/compare_run.go` | HTTP-Handler |
| `cmd/server/main.go:110` | Route `POST /api/compare/run` |

## Neue UI-Komponenten (aus Issue #251)

Alle als neue Svelte-Dateien unter `frontend/src/lib/components/compare/`:

1. **`PresetHeader.svelte`** — Datum, Von/Bis, Forecast-Horizont, Aktivitätsprofil, Actions (Preset laden, Als Auto-Briefing speichern, Vergleich starten), Kurzinfo (N Locations · Zeitfenster · Horizont)

2. **`RecommendationBanner.svelte`** — Winner-Card: Score-Badge (groß), Location-Name, Begründungs-Tags (Chips, ok/warn/info-Farben), aus `CompareWinner.tags`

3. **`CompareMatrix.svelte`** — Locations als Spalten, Metriken als Zeilen (profil-spezifisch), Best-Value grün markiert, Mini-Bar pro Zelle

4. **`HourlyMatrix.svelte`** — Top-3 Locations als Tabs/Sections, stündliche Spalten: Uhrzeit, Temp, Wind, Böen, Niederschlag, Risiko-Pill

## Bestehende Patterns (für Konsistenz)

- **Card/Table-Komponenten:** `$lib/components/ui/card`, `$lib/components/ui/table`
- **Btn-Komponente:** `$lib/components/ui/btn`
- **Badge/Pill:** `$lib/components/ui/badge`, `$lib/components/ui/pill`
- **Design-System:** `docs/reference/design_system.md` — g-accent, g-success, g-warning etc.
- **API-Call-Pattern:** `api.post<T>('/api/...', body)` via `$lib/api.ts`
- **Svelte 5 Runes:** `$state`, `$derived`, `$props` (kein Options API)

## Risiken & Offene Fragen

1. **ActivityProfile-Mismatch:** Frontend-Werte (`wintersport`, `wandern`, `summer_trekking`, `allgemein`) passen nicht zu Backend-Werten (`WINTERSPORT`, `ALPINE_TOURING`, `SUMMER_TREKKING`, `ALLGEMEIN`). Mapping nötig + `wandern` → `ALPINE_TOURING` semantisch prüfen.

2. **LocationID-zu-Name-Mapping:** Engine gibt nur IDs zurück. Das `locations`-Array aus SSR enthält Namen → clientseitig auflösen.

3. **Zeitfenster im Request:** Die Engine-Spec (Issue #250) zeigt keinen `time_window_start/end` im `CompareRequest`. Aktuell werden nur `date` + `profile` + `location_ids` gesendet. Das Zeitfenster ist Frontend-only (UI-Kontrolle vorhanden, aber kein Backend-Effekt). → In Spec klären ob Zeitfenster ignoriert werden oder ob `CompareRequest` erweitert werden muss.

4. **Alte API aufrechterhalten:** `GET /api/compare` (Python-Proxy) bleibt unverändert. Frontend wechselt auf `POST /api/compare/run`.

5. **Mini-Bar-Logik:** Relative Verhältnisse innerhalb einer Spalte — benötigt Min/Max über alle Locations pro Metrik.

## Nächste Schritte

→ `/2-analyse` für detaillierte Analyse und Entscheidungen
