---
entity_id: sveltekit_weather_table
type: module
created: 2026-04-13
updated: 2026-04-13
status: draft
version: "1.0"
tags: [migration, sveltekit, frontend, weather, forecast]
---

# M3c: Weather Table (SvelteKit)

## Approval

- [ ] Approved

## Purpose

Stuendliche Wetter-Tabelle als SvelteKit-Page. User waehlt eine Location, Stunden-Anzahl und sieht eine Forecast-Tabelle mit Emoji-Symbolen, Temperatur, Niederschlag, Wind und Wolken. Nutzt den bestehenden Go Forecast-Endpoint. Fundament fuer spaetere Compare-Page (M3e).

## Scope

### In Scope

- `/weather` Route mit Location-Selector und Stunden-Auswahl
- Client-side Forecast-Fetch nach Button-Click
- 8-spaltige stuendliche Tabelle (Zeit, Symbol, Temp, Precip, Wind, Boeen, Windrichtung, Wolken)
- Weather-Emoji-Logik als TypeScript-Utility (Port der Python-Funktion)
- Forecast TypeScript Types (ForecastDataPoint, ForecastMeta, ForecastResponse)
- Provider/Modell-Info Anzeige
- Navigation-Eintrag "Wetter" in Sidebar

### Out of Scope

- Trip-basierte Multi-Waypoint-Forecasts (M3e Compare)
- Aggregation/Scoring (M3e)
- Risk Assessment Anzeige (spaeter)
- Weather Config (Metrik-Auswahl pro Trip/Location)
- Wintersport-spezifische Felder (Schneehoehe, Neuschnee)

## Architecture

```
/weather
  +page.server.ts: load locations[] (fuer Selector)
  +page.svelte:
    [Location Selector] [Stunden: 24/48/72] [Laden Button]
    Provider: OPENMETEO · icon_d2 · Europe/Vienna
    +------------------------------------------+
    | Zeit  | ☀️ | Temp | Precip | Wind | ...  |
    | 08:00 | ☀️ | 12°  | 0.0    | 15   | ...  |
    | 09:00 | 🌤️ | 14°  | 0.0    | 18   | ...  |
    +------------------------------------------+
```

### Datenfluss

```
1. SSR: +page.server.ts laedt locations[] (fuer Dropdown)
2. User waehlt Location + Stunden
3. Client: api.get('/api/forecast?lat=X&lon=X&hours=N')
4. Go API -> OpenMeteo -> ForecastResponse
5. Svelte rendert Tabelle mit weatherEmoji() pro Zeile
```

## Source

- **File:** `frontend/src/lib/utils/weatherEmoji.ts` (neu, ~40 LOC)
  **Identifier:** `weatherEmoji()`, `degToCardinal()`
- **File:** `frontend/src/routes/weather/+page.server.ts` (neu, ~20 LOC)
  **Identifier:** `load()` PageServerLoad
- **File:** `frontend/src/routes/weather/+page.svelte` (neu, ~120 LOC)
  **Identifier:** Weather Route Component
- **File:** `frontend/src/lib/types.ts` (geaendert, +30 LOC)
  **Identifier:** `ForecastDataPoint`, `ForecastMeta`, `ForecastResponse`
- **File:** `frontend/src/routes/+layout.svelte` (geaendert, +1 LOC)
  **Identifier:** `nav` Array

**Gesamt: 5 Dateien, ~211 LOC**

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| Go Forecast Endpoint | API | GET /api/forecast?lat=X&lon=X&hours=N |
| Go Location CRUD | API | GET /api/locations (fuer Selector) |
| SvelteKit Setup (M2) | Foundation | Auth, Layout, API Client |
| M3b Locations | Data | Location-Liste fuer Dropdown |
| shadcn-svelte | Library | Button, Table (bereits installiert) |

## Implementation Details

### TypeScript Types (types.ts)

```typescript
export type ThunderLevel = 'NONE' | 'MED' | 'HIGH';

export interface ForecastDataPoint {
  ts: string;
  t2m_c?: number | null;
  wind10m_kmh?: number | null;
  wind_direction_deg?: number | null;
  gust_kmh?: number | null;
  precip_1h_mm?: number | null;
  cloud_total_pct?: number | null;
  wmo_code?: number | null;
  thunder_level?: ThunderLevel | null;
  visibility_m?: number | null;
  wind_chill_c?: number | null;
  humidity_pct?: number | null;
  pop_pct?: number | null;
  is_day?: number | null;
  dni_wm2?: number | null;
  uv_index?: number | null;
}

export interface ForecastMeta {
  provider: string;
  model: string;
  grid_res_km: number;
}

export interface ForecastResponse {
  timezone: string;
  meta: ForecastMeta;
  data: ForecastDataPoint[];
}
```

### Weather Emoji Logik (weatherEmoji.ts)

4-Stufen-Prioritaet (Port der Python-Funktion):
1. WMO-Code -> Niederschlags-Emoji (Regen, Schnee, Gewitter, Nebel)
2. Nacht (is_day=0) -> Mond-Emoji
3. DNI-basiert (Sonneneinstrahlung W/m2)
4. Fallback: Cloud-Prozent -> Wolken-Emoji

Plus `degToCardinal(deg)`: Grad -> Himmelsrichtung (N, NE, E, SE, S, SW, W, NW)

### Tabellen-Spalten

| Spalte | Feld | Format |
|--------|------|--------|
| Zeit | ts | HH:MM (toLocaleTimeString) |
| Symbol | wmo_code + is_day + dni + cloud | Emoji via weatherEmoji() |
| Temp | t2m_c | X.X° |
| Precip | precip_1h_mm | X.X mm |
| Wind | wind10m_kmh | X km/h |
| Boeen | gust_kmh | X km/h |
| Winddir | wind_direction_deg | Kardinal (N, SW, etc.) |
| Wolken | cloud_total_pct | X% |

### Location Selector

Native `<select>` (gleicher Stil wie LocationForm):
- Alle Locations aus API
- Default: keine Auswahl
- Nach Auswahl + Klick "Laden" -> Forecast fetch

### Stunden-Auswahl

Native `<select>` mit Optionen: 24h, 48h (default), 72h, 120h, 240h

## Expected Behavior

- **Input:** Location-Auswahl via Dropdown + Stunden-Anzahl (24/48/72/120/240) + Klick auf "Laden"
- **Output:** HTML-Tabelle mit 8 Spalten (Zeit, Weather-Emoji, Temperatur, Niederschlag, Wind, Boeen, Windrichtung, Wolken). Meta-Zeile mit Provider, Modell, Zeitzone.
- **Side effects:** Client-side Fetch von Go `/api/forecast` Endpoint bei Button-Click. Kein Server-side Forecast-Fetch.

### Zustaende

- **Initial:** Location-Selector + Stunden-Auswahl sichtbar, keine Tabelle
- **Laden:** Loading-Text waehrend API-Call
- **Ergebnis:** Meta-Info + Forecast-Tabelle
- **Fehler:** "Bitte Location waehlen" oder API-Fehlermeldung
- **Viele Stunden:** Tabelle scrollt vertikal (max 240 Zeilen)

## Known Limitations

- Nur Location-basiert, kein Trip-Waypoint-Support
- Keine Aggregation (nur Rohdaten pro Stunde)
- Keine Metrik-Auswahl (feste 8 Spalten)
- Kein Auto-Refresh (manueller Laden-Button)
- Wind-Chill, UV-Index, Humidity nicht in der Tabelle (spaeter erweiterbar)

## Testbarkeit

### Playwright E2E Tests

1. **Seite laedt:** Location-Selector und Laden-Button sichtbar
2. **Ohne Auswahl:** Fehlermeldung bei Klick auf Laden
3. **Forecast laden:** Location waehlen, Laden klicken, Tabelle erscheint
4. **Tabelle hat 8 Spalten:** Header pruefen
5. **Meta-Info:** Provider/Modell sichtbar nach Laden
6. **Navigation:** "Wetter" Link in Sidebar

## Changelog

- 2026-04-13: Initial spec created
