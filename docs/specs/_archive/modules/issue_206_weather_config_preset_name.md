---
entity_id: issue_206_weather_config_preset_name
type: module
created: 2026-05-18
updated: 2026-05-18
status: draft
version: "1.0"
issue: 206
tags: [weather-config, display-config, preset, frontend, python, trip-detail, issue-206]
---

# Issue 206 — `preset_name` in `display_config` persistieren

## Approval

- [ ] Approved

## Purpose

`WeatherMetricsPreviewCard` leitet den angezeigten Preset-Namen derzeit aus
`trip.aggregation.profile` ab — ein Workaround, der zu falschen Labels führt, sobald
das Profil und die tatsächlich gewählte Metriken-Vorlage auseinanderlaufen. Ziel dieses
Workflows ist es, `preset_name` als persistiertes Feld in `Trip.display_config` einzuführen:
beim Speichern im `WeatherMetricsTab` wird der Template-Key (z. B. `"wandern"`) nach
`display_config.preset_name` geschrieben und von der Card direkt gelesen. Damit ist
die Anzeige unabhängig vom Aktivitätsprofil und bleibt bei Änderungen stabil.

**Befund: `display_config`, nicht `weather_config`**

Der `PUT /api/trips/{id}/weather-config`-Handler (`weather_config.go:60`) schreibt
ausschließlich in `trip.DisplayConfig` — nicht in `trip.WeatherConfig`. `WeatherMetricsTab`
liest beim Init aus `trip.display_config` und schreibt nach `display_config`. Die
Hilfsfunktion `getActiveMetrics()` (`rightColumn.ts:41`) liest fälschlich aus
`trip.weather_config?.metrics` und wird in diesem Issue mitbehoben.

## Source

- **MODIFY:** `src/app/models.py`
  — `UnifiedWeatherDisplayConfig` erhält `preset_name: Optional[str] = None`
- **MODIFY:** `src/app/loader.py`
  — `_parse_display_config()` liest `preset_name`; `_trip_to_dict()` serialisiert es
- **MODIFY:** `frontend/src/lib/types.ts`
  — neues Interface `DisplayConfig { preset_name?: string; metrics?: WeatherConfigMetric[] }`;
  `Trip.display_config` wird von `Record<string, unknown>` auf `DisplayConfig` umgestellt
- **MODIFY:** `frontend/src/lib/utils/rightColumn.ts`
  — `getPresetLabel()` bevorzugt `trip.display_config?.preset_name` vor Profile-Ableitung;
  `getActiveMetrics()` liest aus `trip.display_config?.metrics` (Bug-Fix: las bisher aus `trip.weather_config?.metrics`)
- **MODIFY:** `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte`
  — `handleSave()` schickt `preset_name` mit; `initMaps()` stellt Template-Auswahl aus `preset_name` wieder her
- **MODIFY:** `frontend/src/lib/utils/rightColumn.test.ts`
  — Test-Fixtures von `weather_config` auf `display_config` umbauen

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `UnifiedWeatherDisplayConfig` | Python-Dataclass | DTO für persistierte Display-Konfiguration (`src/app/models.py`) |
| `_parse_display_config()` | Python-Funktion | Deseralisiert `display_config` aus Trip-JSON (`src/app/loader.py`) |
| `_trip_to_dict()` | Python-Funktion | Serialisiert Trip inkl. `display_config` nach JSON (`src/app/loader.py`) |
| `DisplayConfig` | TS-Interface | Frontend-Typ für `trip.display_config` (`frontend/src/lib/types.ts`) |
| `WeatherMetricsTab.svelte` | Svelte-Komponente | Schreibt `preset_name` beim Speichern (`frontend/src/lib/components/trip-detail/`) |
| `WeatherMetricsPreviewCard` | Svelte-Komponente | Liest `preset_name` für Label-Anzeige (Konsument; keine Änderung) |
| `getPresetLabel()` | TS-Funktion | Gibt lesbares Template-Label zurück (`frontend/src/lib/utils/rightColumn.ts`) |
| `getActiveMetrics()` | TS-Funktion | Gibt aktive Metriken zurück — Bug-Fix: Quelle von `weather_config` auf `display_config` (`frontend/src/lib/utils/rightColumn.ts`) |
| `PUT /api/trips/{id}/weather-config` | Go-API-Endpunkt | Schreibt in `trip.DisplayConfig` (`map[string]interface{}`); keine Änderung nötig |

## Implementation Details

### 1. `src/app/models.py` — Feld hinzufügen

```python
@dataclass
class UnifiedWeatherDisplayConfig:
    trip_id: str
    metrics: list[MetricConfig]
    preset_name: Optional[str] = None   # NEU: Template-Key, z.B. "wandern"
    show_night_block: bool = True
    # … restliche Felder unverändert
```

`preset_name` enthält den Template-**Key** (stabile ID), nicht das Label. Bei eigener
Auswahl (`"__custom__"` oder leer) bleibt das Feld `None`.

### 2. `src/app/loader.py` — Serialisierung und Deserialisierung

`_parse_display_config()` liest den neuen Key:

```python
def _parse_display_config(data: dict) -> UnifiedWeatherDisplayConfig:
    return UnifiedWeatherDisplayConfig(
        trip_id=data.get("trip_id", ""),
        metrics=...,
        preset_name=data.get("preset_name"),   # NEU — None wenn nicht vorhanden
        show_night_block=data.get("show_night_block", True),
        # …
    )
```

`_trip_to_dict()` serialisiert `preset_name` nur, wenn vorhanden:

```python
if config.preset_name is not None:
    display_cfg["preset_name"] = config.preset_name
```

**Migration:** Lazy — Bestands-Trips ohne `preset_name` erhalten beim Laden `None`.
Frontend fällt auf Profile-Fallback zurück. Kein aktiver Migrations-Pass nötig.

### 3. `frontend/src/lib/types.ts` — Interface einführen

```typescript
export interface DisplayConfig {
  preset_name?: string;                // Template-Key, z.B. "wandern"; fehlt bei eigener Auswahl
  metrics?: WeatherConfigMetric[];     // Aktive Metriken
  // weitere display_config-Felder bleiben als unknown-Schicht, bis sie typisiert werden
}

export interface Trip {
  // …
  display_config?: DisplayConfig;      // war: Record<string, unknown>
  // …
}
```

### 4. `frontend/src/lib/utils/rightColumn.ts` — Zwei Korrekturen

**`getPresetLabel()` — bevorzugt `display_config.preset_name`:**

```typescript
export function getPresetLabel(trip: Trip): string {
  const savedKey = trip.display_config?.preset_name;
  if (savedKey) {
    const template = METRIC_TEMPLATES.find(t => t.id === savedKey);
    if (template) return template.label;
  }
  // Fallback: Ableitung aus aggregation.profile (bisheriges Verhalten)
  return derivePresetLabelFromProfile(trip.aggregation?.profile);
}
```

**`getActiveMetrics()` — Bug-Fix, liest aus `display_config`:**

```typescript
export function getActiveMetrics(trip: Trip): WeatherConfigMetric[] {
  // VORHER (Bug): trip.weather_config?.metrics
  return trip.display_config?.metrics ?? DEFAULT_METRICS;
}
```

### 5. `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte`

**`initMaps()` — Template-Auswahl wiederherstellen:**

```typescript
function initMaps() {
  const savedKey = trip.display_config?.preset_name;
  selectedTemplate = savedKey && METRIC_TEMPLATES.some(t => t.id === savedKey)
    ? savedKey
    : '';   // '' = eigene Auswahl, falls Key unbekannt oder nicht vorhanden
  // … restliche Init-Logik
}
```

**`handleSave()` — `preset_name` mitschicken:**

```typescript
async function handleSave() {
  const payload: DisplayConfig = {
    ...currentDisplayConfig,           // ALLE bestehenden display_config-Felder (Merge-Sicherheit)
    metrics: selectedMetrics,
    preset_name: selectedTemplate || undefined,  // '' → undefined (nicht speichern)
  };
  await fetch(`/api/trips/${trip.id}/weather-config`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}
```

**Wichtig — Merge-Sicherheit:** Der Handler (`weather_config.go`) ersetzt `trip.DisplayConfig`
vollständig. Der Tab muss beim Save daher den **gesamten** bisherigen `display_config`-Inhalt
mitsenden (Spread `...currentDisplayConfig`), nicht nur die geänderten Felder.

**Restore-Validierung:** `initMaps()` prüft, ob der gespeicherte `preset_name` in
`METRIC_TEMPLATES` bekannt ist, bevor `selectedTemplate` gesetzt wird. Unbekannte Keys
(gelöschte Templates o.ä.) werden als `''` (eigene Auswahl) behandelt.

### 6. `frontend/src/lib/utils/rightColumn.test.ts` — Fixtures umbauen

Bestehende Tests, die `trip.weather_config.metrics` als Quelle voraussetzen, werden auf
`trip.display_config.metrics` umgestellt. Neue Tests prüfen:

- `getPresetLabel()` gibt `preset_name`-basiertes Label zurück, wenn `display_config.preset_name` gesetzt
- `getPresetLabel()` fällt auf Profile-Ableitung zurück, wenn `preset_name` fehlt oder unbekannt ist
- `getActiveMetrics()` liest aus `display_config.metrics`, nicht aus `weather_config.metrics`

## Expected Behavior

- **Input:** `WeatherMetricsTab` speichert Metriken + Template-Auswahl `"wandern"`.
- **Output:** `trip.display_config.preset_name === "wandern"` ist nach dem Speichern
  persistent; `WeatherMetricsPreviewCard` zeigt das korrekte Label ohne Profile-Ableitung.
- **Side effects:**
  - Bestands-Trips ohne `preset_name` verhalten sich unverändert (Fallback aktiv).
  - `getActiveMetrics()` liest fortan aus `display_config` — Tests, die `weather_config.metrics`
    nutzen, müssen angepasst werden.
  - Das Go-Backend bleibt unverändert: `DisplayConfig` ist `map[string]interface{}` und
    speichert `preset_name` transparent.

## Acceptance Criteria

- **AC-1:** Given ein Trip hat in `display_config` kein `preset_name`-Feld (Bestandsdaten)
  When `WeatherMetricsPreviewCard` das Label abruft via `getPresetLabel(trip)`
  Then wird das Label aus `trip.aggregation.profile` abgeleitet (bisheriger Fallback) und kein Fehler geworfen.
  - Test: (populated after /tdd-red)

- **AC-2:** Given User wählt im `WeatherMetricsTab` das Template `"wandern"` und klickt Speichern
  When `PUT /api/trips/{id}/weather-config` abgesetzt wird
  Then enthält der Request-Body `display_config.preset_name === "wandern"`.
  - Test: (populated after /tdd-red)

- **AC-3:** Given ein Trip hat `display_config.preset_name = "wandern"` persistent gespeichert
  When `getPresetLabel(trip)` aufgerufen wird
  Then gibt die Funktion das Label des Templates mit `id === "wandern"` zurück, nicht das aus `aggregation.profile` abgeleitete Label.
  - Test: (populated after /tdd-red)

- **AC-4:** Given User öffnet den `WeatherMetricsTab` eines Trips mit gespeichertem `preset_name = "wandern"`
  When `initMaps()` ausgeführt wird
  Then ist `selectedTemplate === "wandern"` und die passende Template-Zeile ist vorausgewählt.
  - Test: (populated after /tdd-red)

- **AC-5:** Given User wählt im `WeatherMetricsTab` "— Eigene Auswahl —" (`selectedTemplate === ''`) und klickt Speichern
  When der Payload gebaut wird
  Then fehlt `preset_name` im Request-Body (oder ist `undefined`/`null`) — das Feld wird nicht als leerer String persistiert.
  - Test: (populated after /tdd-red)

- **AC-6:** Given `WeatherMetricsTab` speichert neue Metriken
  When `handleSave()` den Payload zusammenbaut
  Then enthält der Payload alle bisherigen `display_config`-Felder (Merge via Spread) — kein bestehendes Feld geht beim Save verloren.
  - Test: (populated after /tdd-red)

- **AC-7:** Given `getActiveMetrics(trip)` wird auf einem Trip aufgerufen, der nur `display_config.metrics` (kein `weather_config.metrics`) hat
  When die Funktion ausgeführt wird
  Then werden die Metriken aus `display_config.metrics` zurückgegeben (kein leeres Ergebnis wegen des bisherigen `weather_config`-Bug).
  - Test: (populated after /tdd-red)

- **AC-8:** Given `initMaps()` liest einen `preset_name`, der in keinem bekannten Template enthalten ist (z. B. gelöschtes oder umbenanntes Template)
  When die Restore-Validierung prüft, ob der Key in `METRIC_TEMPLATES` existiert
  Then wird `selectedTemplate` auf `''` (eigene Auswahl) gesetzt — keine Exception, kein ungültiger Zustand.
  - Test: (populated after /tdd-red)

- **AC-9:** Given TypeScript-Compiler prüft `types.ts` nach dem Umbau
  When `tsc --noEmit` oder `npm run check` ausgeführt wird
  Then hat `Trip.display_config` den Typ `DisplayConfig` (nicht `Record<string, unknown>`) und Zugriffe auf `.preset_name` und `.metrics` kompilieren ohne Fehler.
  - Test: (populated after /tdd-red)

## Out of Scope

- **`preset_id` als separates Datenbankfeld** — ein `string`-Feld in `display_config` ist ausreichend; kein separates Feld auf Modell-Ebene.
- **Preset-Verwaltungs-UI** (CRUD für Templates, Rename, Delete) — Templates sind codebasiert; keine Admin-Oberfläche.
- **Go-Backend-Änderungen** — `DisplayConfig` ist `map[string]interface{}`; neues Feld wird transparent gespeichert ohne Code-Anpassung.
- **Python-Formatter-Integration** — `preset_name` ist rein ein Anzeige-Hinweis; der Formatter nutzt die `metrics`-Liste direkt.
- **Migration bestehender Trips** — Lazy-Migration reicht; kein Script, kein aktiver Pass.

## Risiken & Implementierungshinweise

| Risiko | Auswirkung | Gegenmaßnahme |
|--------|------------|---------------|
| Tab-Save überschreibt `display_config` vollständig | Felder außerhalb von `metrics` + `preset_name` (z. B. `show_night_block`) gehen verloren | `handleSave()` muss via Spread (`...currentDisplayConfig`) alle bestehenden Felder mitschicken — nicht nur die geänderten |
| Restore-Validierung fehlt | Ungültiger `preset_name` aus einem umbenannten Template setzt `selectedTemplate` auf einen unbekannten Wert, UI wirkt inkonsistent | `initMaps()` prüft via `METRIC_TEMPLATES.some(t => t.id === savedKey)` vor dem Setzen |
| `getActiveMetrics()` Bug bleibt unbemerkt | `WeatherMetricsPreviewCard` zeigt falsche oder leere Metriken für Trips, die nur `display_config.metrics` haben | Bug-Fix ist Teil dieses Issues — `rightColumn.test.ts`-Fixtures müssen auf `display_config` umgestellt werden |

## Known Limitations

- `DisplayConfig`-Interface im Frontend typisiert vorerst nur `preset_name` und `metrics` vollständig; weitere Felder (`show_night_block`, `night_interval_hours`, etc.) bleiben bis zu einer späteren Typisierungsrunde implizit via Spread erhalten.
- Der Fallback von `getPresetLabel()` auf `aggregation.profile` bleibt erhalten, um Bestands-Trips ohne `preset_name` korrekt anzuzeigen.

## Files to Change

| # | Datei | Schicht | Aktion | LoC (netto) |
|---|-------|---------|--------|-------------|
| 1 | `src/app/models.py` | Python | MODIFY — `preset_name: Optional[str] = None` auf `UnifiedWeatherDisplayConfig` | ~2 |
| 2 | `src/app/loader.py` | Python | MODIFY — `_parse_display_config()` + `_trip_to_dict()` | ~6 |
| 3 | `frontend/src/lib/types.ts` | Frontend | MODIFY — Interface `DisplayConfig`, `Trip.display_config` umstellen | ~8 |
| 4 | `frontend/src/lib/utils/rightColumn.ts` | Frontend | MODIFY — `getPresetLabel()` + `getActiveMetrics()` Bug-Fix | ~12 |
| 5 | `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte` | Frontend | MODIFY — `initMaps()` + `handleSave()` | ~10 |
| 6 | `frontend/src/lib/utils/rightColumn.test.ts` | Frontend/Test | MODIFY — Fixtures + neue Tests | ~15 |

**Gesamt:** ~53 LoC netto, 6 Dateien

## Changelog

- 2026-05-18: Initial spec für Issue #206 (`preset_name` in `display_config`). Befund `display_config` vs. `weather_config` dokumentiert, Merge-Risiko und Restore-Validierung als explizite Implementierungshinweise, Bug-Fix `getActiveMetrics()` im Scope, 9 Acceptance Criteria (AC-N-Format), Out-of-Scope klar abgegrenzt.
