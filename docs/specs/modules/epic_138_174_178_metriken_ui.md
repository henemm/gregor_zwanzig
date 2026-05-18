---
entity_id: epic_138_174_178_metriken_ui
type: module
created: 2026-05-18
updated: 2026-05-18
status: draft
version: "1.0"
tags: [frontend, sveltekit, go, weather-config, trip-detail, metrics, epic-138]
---

# Epic #138 Phase 2 — Metriken-Editor UI-Komponenten (Issues #174–178)

## Approval

- [ ] Approved

## Purpose

Baut auf dem funktionsfähigen `WeatherMetricsTab.svelte` (Phase 1, VERIFIED) auf und ergänzt fünf Features: strukturierte Gruppen-Komponenten (#174), einen Roh/Indikator-Pill-Toggle mit erweiterter INDICATOR_MAP (#175), eine Live-Tabellen-Vorschau (#176), einen Server-seitigen "Als Preset speichern"-Dialog (#177) und dirty-State-Warnung (#178).

## Source

**Frontend — neu:**
- `frontend/src/lib/components/trip-detail/MetricGroup.svelte`
- `frontend/src/lib/components/trip-detail/MetricCheckbox.svelte`
- `frontend/src/lib/components/trip-detail/TablePreview.svelte`
- `frontend/src/lib/components/trip-detail/SavePresetDialog.svelte`

**Frontend — geändert:**
- `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte`
- `frontend/src/lib/components/trip-detail/index.ts`
- `frontend/src/lib/types.ts`

**Backend — neu:**
- `internal/model/metric_preset.go`
- `internal/handler/metric_preset.go`

**Backend — geändert:**
- `internal/store/store.go`
- `cmd/server/main.go`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `WeatherMetricsTab.svelte` (Phase 1) | Svelte | Basis-Komponente — wird refaktoriert |
| `GET /api/metrics` | API | Katalog mit 25 Metriken + `has_friendly_format` |
| `GET /api/templates` | API | 7 Standard-Presets |
| `GET /api/metric-presets` | API (neu) | User-definierte Presets laden |
| `POST /api/metric-presets` | API (neu) | Neues Preset speichern |
| `DELETE /api/metric-presets/{id}` | API (neu) | Preset löschen |
| `<Eyebrow>`, `<Pill>`, `<Dialog.*>`, `<Table.*>` | UI-Komponenten | Aus bestehender UI-Bibliothek |

## Implementation Details

### §1 dirty-State (#178)

**Ziel:** Pill „Ungespeicherte Änderungen" + Verwerfen/Speichern-Buttons sichtbar, wenn `enabledMap` oder `friendlyMap` sich gegenüber dem letzten gespeicherten Stand geändert haben.

**Umsetzung in `WeatherMetricsTab.svelte`:**

```typescript
let savedSnapshot = $state('');   // JSON.stringify({enabledMap, friendlyMap}) beim letzten Save
const isDirty = $derived(
  JSON.stringify({ enabledMap, friendlyMap }) !== savedSnapshot
);
```

- `savedSnapshot` wird gesetzt: (a) nach erfolgreichem `handleSave()`, (b) nach `initMaps()` (initialer Load)
- Template: `{#if isDirty}` → Pill `tone="warning"` mit Text „Ungespeicherte Änderungen" + Button „Verwerfen" + Button „Speichern"
- „Verwerfen" → `resetToSnapshot()`: parst `savedSnapshot` zurück und setzt `enabledMap`/`friendlyMap`
- Der bestehende Save-Button in der save-row bleibt als sekundärer Speicherpfad erhalten (`disabled` wenn `!isDirty && !saving`)

**data-testid:**
| TestID | Element | Zweck |
|--------|---------|-------|
| `weather-metrics-dirty-pill` | `<Pill>` | Warnung bei ungespeicherten Änderungen |
| `weather-metrics-discard` | `<button>` | Änderungen verwerfen |

### §2 `MetricGroup.svelte` (#174)

**Props:**
```typescript
interface Props {
  label: string;         // Kategorie-Label (z.B. "Wind")
  activeCount: number;   // Anzahl aktivierter Metriken in dieser Gruppe
  totalCount: number;    // Gesamtanzahl Metriken in dieser Gruppe
  children: Snippet;
}
```

**Template:**
```html
<section class="metric-group">
  <div class="metric-group-header">
    <Eyebrow>{label}</Eyebrow>
    <span class="metric-group-counter">{activeCount} / {totalCount}</span>
  </div>
  <ul class="metric-group-list">
    {@render children()}
  </ul>
</section>
```

Counter wird accent-farbig wenn `activeCount > 0`, faint wenn `activeCount === 0`.

**data-testid:** `metric-group-{kategorie-slug}` auf `<section>`, z.B. `metric-group-wind`.

### §3 `MetricCheckbox.svelte` (#174 + #175)

**Props:**
```typescript
interface Props {
  metric: MetricEntry;          // aus /api/metrics
  enabled: boolean;
  useIndicator: boolean;        // true = Indikator, false = Roh
  indicatorCapable: boolean;    // aus INDICATOR_MAP
  onToggle: (enabled: boolean) => void;
  onModeChange: (useIndicator: boolean) => void;
}
```

**Template-Struktur:**
```
[Custom-Checkbox] [Label]  [Unit]  [Short]
                            [Roh-Pill | Indikator-Pill]  ← nur wenn indicatorCapable
```

- Custom-Checkbox: `<button type="button">` mit Checkmark-SVG (kein `<input type="checkbox">`) für einheitliches Styling
- Roh-Pill / Indikator-Pill: `<Pill tone={useIndicator ? 'default' : 'accent'}>Roh</Pill>` + `<Pill tone={useIndicator ? 'accent' : 'default'}>Indikator</Pill>`
- Nur wenn `indicatorCapable === true` werden die Pills gerendert

**data-testid:**
| TestID | Element |
|--------|---------|
| `weather-metrics-tab-checkbox-{id}` | Custom-Checkbox-Button |
| `weather-metrics-tab-format-raw-{id}` | Roh-Pill |
| `weather-metrics-tab-format-indicator-{id}` | Indikator-Pill |

### §4 INDICATOR_MAP in `WeatherMetricsTab.svelte` (#175)

Konstante im Script-Block (ersetzt `metric.has_friendly_format` als alleinige Trigger-Bedingung):

```typescript
const INDICATOR_MAP: Record<string, string> = {
  // 9 backend-eligible (has_friendly_format=True)
  wind_direction:  'N / O / S / W',
  thunder:         'keins / mittel / hoch / extrem',
  cape:            'niedrig / mittel / hoch / extrem',
  cloud_total:     'klar / teilw. / bewölkt / bedeckt',
  cloud_low:       'klar / teilw. / bewölkt / bedeckt',
  cloud_mid:       'klar / teilw. / bewölkt / bedeckt',
  cloud_high:      'klar / teilw. / bewölkt / bedeckt',
  visibility:      'gut / eingeschränkt / schlecht / sehr schlecht',
  sunshine:        'hell / wechselhaft / bedeckt',
  // 3 frontend-erweitert (has_friendly_format=False im Backend)
  wind:            'ruhig / mäßig / stark / sturm',
  gust:            'harmlos / mäßig / stark / orkan',
  rain_probability:'niedrig / mittel / hoch / sehr hoch',
};
```

`indicatorCapable(id: string): boolean` → `id in INDICATOR_MAP`.

Wird an `<MetricCheckbox indicatorCapable={indicatorCapable(metric.id)}>` übergeben.

**Hinweis:** `wind`, `gust`, `rain_probability` haben `has_friendly_format=False` im Backend. Der Python-Formatter ignoriert `use_friendly_format=true` für diese IDs stillschweigend und gibt Rohwerte aus. Das ist dokumentiertes Verhalten — der INDICATOR_MAP steuert nur die Frontend-UI, nicht den Formatter.

### §5 `TablePreview.svelte` (#176)

**Props:**
```typescript
interface Props {
  catalog: MetricCatalog;
  enabledMap: Record<string, boolean>;
  friendlyMap: Record<string, boolean>;
}
```

**Aufbau:**
- Zeigt nur Metriken mit `enabledMap[id] === true` als Spalten
- Spaltenreihenfolge: CATEGORY_ORDER aus WeatherMetricsTab (`sortedCategories()`)
- 4 statische Beispieldatenzeilen (hardcodiert, repräsentativ für einen Tagesverlauf)
- Spalten-Header: `{metric.label}` + wenn `friendlyMap[id] === true` und `indicatorCapable(id)`: kleiner `·skala`-Suffix kursiv
- Zellwerte: Rohdatenwert für `friendlyMap[id] === false` (oder nicht indicator-capable); Indikator-Label (aus `INDICATOR_SAMPLE_VALUES`) kursiv + accent-farbig für `friendlyMap[id] === true` und `indicatorCapable(id)`

**Statische Beispieldaten (4 Zeilen):**
```typescript
const SAMPLE_ROWS = [
  { label: 'Mo 09:00', temperature: '14°C', wind: '23 km/h', gust: '38 km/h', wind_direction: 'SW', precipitation: '0,2 mm', thunder: 'keins', ... },
  { label: 'Mo 12:00', temperature: '18°C', wind: '31 km/h', gust: '52 km/h', wind_direction: 'W',  precipitation: '0,0 mm', thunder: 'keins', ... },
  { label: 'Mo 15:00', temperature: '16°C', wind: '45 km/h', gust: '68 km/h', wind_direction: 'W',  precipitation: '1,8 mm', thunder: 'mittel', ... },
  { label: 'Mo 18:00', temperature: '12°C', wind: '28 km/h', gust: '44 km/h', wind_direction: 'NW', precipitation: '4,2 mm', thunder: 'hoch', ... },
];
```

Komponente wird in `WeatherMetricsTab.svelte` unterhalb der Kategorie-Gruppen, oberhalb der save-row eingebaut.

**data-testid:** `weather-metrics-table-preview` auf dem Root-Element.

### §6 `SavePresetDialog.svelte` (#177) + Go-Backend

**Dialog-Trigger:** Neuer Button „Als Preset speichern" in der save-row von `WeatherMetricsTab.svelte` (nur sichtbar wenn `!isDirty` — also nach erfolgreichem Speichern der Trip-Konfiguration).

**Props:**
```typescript
interface Props {
  open: boolean;
  enabledMap: Record<string, boolean>;
  friendlyMap: Record<string, boolean>;
  catalog: MetricCatalog;
  onClose: () => void;
  onSaved: (preset: MetricPreset) => void;
}
```

**Dialog-Inhalt:**
- Input: Name (required, max 40 Zeichen)
- Textarea: Beschreibung (optional, max 120 Zeichen)
- Zusammenfassung (read-only, derived):
  - `{activeCount} Metriken aktiv · {rawCount} Rohwert · {indicatorCount} Indikator`
- Checkbox: „Als Standard für neue Trips" (`isDefault`)
- Buttons: „Abbrechen" + „Speichern"

**Save-Flow:** `POST /api/metric-presets` mit `{name, description, is_default, metrics: string[], friendly_ids: string[]}` → 201 Created → `onSaved(preset)` → Dialog schließt.

**data-testid:** `save-preset-dialog`, `save-preset-name`, `save-preset-description`, `save-preset-is-default`, `save-preset-submit`.

---

### §7 Go-Backend: User-Presets-Endpoint

**Neues Modell `internal/model/metric_preset.go`:**

```go
package model

import "time"

type MetricPreset struct {
    ID          string    `json:"id"`
    Name        string    `json:"name"`
    Description string    `json:"description,omitempty"`
    IsDefault   bool      `json:"is_default"`
    Metrics     []string  `json:"metrics"`      // enabled metric IDs
    FriendlyIDs []string  `json:"friendly_ids"` // IDs mit use_friendly_format=true
    CreatedAt   time.Time `json:"created_at"`
}
```

**Storage:** `data/users/{user_id}/metric_presets.json` (JSON-Array). Eine Datei pro User.

**Neue Store-Methoden in `internal/store/store.go`:**

```go
func (s *Store) PresetsFile() string {
    return filepath.Join(s.DataDir, "users", s.UserID, "metric_presets.json")
}

func (s *Store) LoadMetricPresets() ([]model.MetricPreset, error)
func (s *Store) SaveMetricPresets(presets []model.MetricPreset) error
```

`LoadMetricPresets` gibt `[]` (leerer Slice, kein Fehler) zurück wenn Datei nicht existiert.

**Neuer Handler `internal/handler/metric_preset.go`:**

```go
// GET  /api/metric-presets     → ListMetricPresetsHandler
// POST /api/metric-presets     → CreateMetricPresetHandler
// DELETE /api/metric-presets/{id} → DeleteMetricPresetHandler
```

- `ListMetricPresetsHandler`: lädt alle Presets für den aktuellen User
- `CreateMetricPresetHandler`: generiert UUID, setzt `CreatedAt`, wenn `IsDefault=true` → setzt alle anderen `IsDefault=false`, speichert
- `DeleteMetricPresetHandler`: filtert Preset mit `id` heraus, speichert Rest

**Neue Routen in `cmd/server/main.go`:**

```go
r.Get("/api/metric-presets",         handler.ListMetricPresetsHandler(store))
r.Post("/api/metric-presets",        handler.CreateMetricPresetHandler(store))
r.Delete("/api/metric-presets/{id}", handler.DeleteMetricPresetHandler(store))
```

**TypeScript-Interface in `frontend/src/lib/types.ts`:**

```typescript
export interface MetricPreset {
    id: string;
    name: string;
    description?: string;
    is_default: boolean;
    metrics: string[];
    friendly_ids: string[];
    created_at: string;
}
```

### §8 `WeatherMetricsTab.svelte` — Umbau-Übersicht

Nach der Refaktorierung:
- Importiert `MetricGroup`, `MetricCheckbox`, `TablePreview`, `SavePresetDialog`
- `sortedCategories()` + `catalog[cat]` → Map zu `<MetricGroup>` + `<MetricCheckbox>`
- INDICATOR_MAP-Konstante definiert (12 Einträge)
- `isDirty` + `savedSnapshot` für dirty-State
- `showSavePresetDialog` Boolean-State für Dialog-Trigger
- User-Presets laden via `GET /api/metric-presets` → werden in Preset-Liste vor Standard-Templates angezeigt

### §9 LoC-Budget

| Datei | Aktion | Est. LoC |
|-------|--------|----------|
| `WeatherMetricsTab.svelte` | Refaktor + dirty-State + Dialog-Trigger | +80 / -60 |
| `MetricGroup.svelte` | NEU | +45 |
| `MetricCheckbox.svelte` | NEU | +85 |
| `TablePreview.svelte` | NEU | +95 |
| `SavePresetDialog.svelte` | NEU | +105 |
| `internal/model/metric_preset.go` | NEU | +20 |
| `internal/store/store.go` | +Preset-Methoden | +40 |
| `internal/handler/metric_preset.go` | NEU | +80 |
| `cmd/server/main.go` | +3 Routen | +6 |
| `frontend/src/lib/types.ts` | +MetricPreset Interface | +10 |
| `index.ts` | +Exports | +4 |
| **Gesamt netto** | | **~510 LoC** |

LoC-Override vor Implementierung: `workflow.py set-field loc_limit_override 550`.

## Expected Behavior

- **Input:** User öffnet Wetter-Metriken-Tab, ändert Checkboxen.
- **Output:** Pill „Ungespeicherte Änderungen" erscheint; TablePreview aktualisiert sich sofort; Verwerfen setzt auf letzten gespeicherten Stand zurück.
- **Input:** User wählt eine Metrik mit INDICATOR_MAP und klickt Indikator-Pill.
- **Output:** ModeBtn wechselt auf Indikator (accent-farbig), Tabellen-Vorschau zeigt kursiven Indikator-Wert.
- **Input:** User klickt „Als Preset speichern", gibt Namen ein, klickt „Speichern".
- **Output:** `POST /api/metric-presets` → 201; Preset erscheint in der Preset-Liste oberhalb der Standard-Templates.

## Acceptance Criteria

**AC-1:** Given der Metriken-Tab ist geöffnet und eine Checkbox wird verändert / When die Checkbox umschaltet / Then erscheint `data-testid="weather-metrics-dirty-pill"` mit Text „Ungespeicherte Änderungen" sichtbar im DOM.

**AC-2:** Given der dirty-State ist aktiv / When der Button `data-testid="weather-metrics-discard"` geklickt wird / Then werden alle Checkboxen auf den Stand des letzten erfolgreichen Speicherns zurückgesetzt und `weather-metrics-dirty-pill` verschwindet.

**AC-3:** Given der Metriken-Tab ist geladen / When die Kategorie-Liste gerendert ist / Then gibt es für jede der 5 Kategorien ein `data-testid="metric-group-{slug}"` Element, das eine `<Eyebrow>` als Header und einen Zähler `aktiv / gesamt` enthält.

**AC-4:** Given eine Metrik mit `id in INDICATOR_MAP` (12 Metriken) ist im Tab sichtbar / When die Metrik-Zeile gerendert ist / Then sind `data-testid="weather-metrics-tab-format-raw-{id}"` und `data-testid="weather-metrics-tab-format-indicator-{id}"` als Pill-Elemente im DOM — bei einer Metrik ohne INDICATOR_MAP-Eintrag sind diese Elemente NICHT im DOM.

**AC-5:** Given mindestens eine Metrik ist aktiviert / When `data-testid="weather-metrics-table-preview"` gerendert ist / Then hat die Tabelle genau so viele Spalten wie aktivierte Metriken, und für Metriken im Indikator-Modus sind Zellwerte kursiv + accent-farbig dargestellt.

**AC-6:** Given der User klickt „Als Preset speichern", gibt Namen ein und bestätigt / When der Submit geklickt wird / Then sendet der Client `POST /api/metric-presets` mit `{name, metrics, friendly_ids, is_default}`; bei HTTP 201 erscheint das neue Preset in der Preset-Liste oberhalb der Standard-Templates.

**AC-7:** Given ein User-Preset wurde gespeichert mit `is_default=true` / When `GET /api/metric-presets` aufgerufen wird / Then hat genau ein Preset `is_default: true` — alle anderen haben `is_default: false`.

**AC-8:** Given der Tab rendert Kategorie-Gruppen / When die Gruppen sichtbar sind / Then zeigt der Zähler im `MetricGroup`-Header die korrekte Anzahl aktiver Metriken in dieser Gruppe — der Zähler reagiert ohne Seiten-Reload auf Checkbox-Änderungen.

## Known Limitations

- **INDICATOR_MAP ist frontend-only:** `wind`, `gust`, `rain_probability` zeigen Indikator-Pill im UI, aber der Python-Formatter ignoriert `use_friendly_format=true` für diese IDs und gibt Rohwerte aus.
- **TablePreview mit Mockdaten:** Die 4 Beispielzeilen sind statisch hardcodiert — sie zeigen keine echten Wetterdaten des Trips.
- **Preset-Löschung nur über API:** Kein Delete-Button im Dialog (#177 Scope) — das gehört in ein Preset-Management-Feature.
- **Tab-Wechsel ohne Warnung:** Wenn `isDirty === true` und der User auf einen anderen Tab wechselt, gibt es keinen `beforeunload`-Guard — Änderungen gehen stillschweigend verloren (analog zu Phase 1).

## Changelog

- 2026-05-18: Initial spec — Issues #174–178 (Phase 2 Epic #138). 4 neue Frontend-Komponenten, Go-Backend für User-Presets (3 Endpoints), ~510 LoC netto, 11 Dateien. 8 Acceptance Criteria im AC-N-Format.
