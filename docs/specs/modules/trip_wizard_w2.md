---
entity_id: trip_wizard_w2
type: module
created: 2026-04-18
updated: 2026-04-18
status: draft
version: "1.0"
tags: [sveltekit, frontend, trips, wizard, weather, display-config, metrics]
---

# Trip Wizard W2: Weather Templates (SvelteKit)

## Approval

- [ ] Approved

## Purpose

Ersetzt den Step-3-Platzhalter im Trip Wizard durch eine vollstaendige Wetter-Konfigurationsoberflaeche: Der User waehlt ein vordefiniertes Profil (Wintersport, Wandern, Allgemein) oder konfiguriert Metriken manuell, und das Ergebnis wird als `display_config` im Trip gespeichert. Diese Komponente ermoeglicht es Wanderern, die angezeigten Wetter-Metriken gezielt auf ihr Aktivitaets-Profil zuzuschneiden, ohne Backend-Aenderungen zu erfordern.

## Scope

### In Scope (W2)

- `WizardStep3Weather.svelte`: Neue Komponente mit Template-Dropdown und Metrik-Checkbox-Grid
- 7 Template-Definitionen hardcoded im Frontend (erweitert Python `PROFILE_METRIC_IDS` von 3 auf 7)
- Metrik-Katalog geladen aus bestehendem `GET /api/metrics` Endpoint
- Kategorie-Gruppierung der Checkboxen (Temperatur, Wind, Niederschlag, Atmosphaere, Winter/Schnee)
- Automatische Template-Erkennung bei Edit-Mode (Abgleich enabledMap mit Template-Definition)
- `TripWizard.svelte`: `displayConfig` State ergaenzt, `WizardStep3Weather` eingebunden, `save()` erweitert
- `trip-wizard.spec.ts`: Step-3-Platzhalter-Test ersetzt durch W2-Tests

### Out of Scope (W2)

- Step 4: Report-Konfiguration (W3)
- Backend-seitige Validierung von `display_config`
- Neue API-Endpoints
- Persistierung von Benutzer-definierten Templates
- Anzeige-Vorschau der konfigurierten Metriken

## Architecture

```
TripWizard.svelte
  ├── let displayConfig = $state(existingTrip?.display_config)
  └── WizardStep3Weather (step === 3, bind:displayConfig)
        ├── Template-Dropdown (Kein Profil / Wintersport / Wandern / Allgemein / Benutzerdefiniert)
        ├── onMount: GET /api/metrics → catalog laden → enabledMap aufbauen
        ├── applyTemplate(): enabledMap mit Template-Metrik-IDs ueberschreiben
        ├── Checkbox-Grid (nach Kategorie gruppiert)
        │     Temperatur: [ ] temperature  ...
        │     Wind:       [ ] wind  [ ] gust  [ ] wind_chill  ...
        │     Niederschlag: [ ] precipitation  [ ] thunder  ...
        │     Atmosphaere: [ ] visibility  [ ] rain_probability  ...
        │     Winter/Schnee: [ ] snow_depth  [ ] fresh_snow  ...
        └── $effect: enabledMap → displayConfig = { metrics: [{metric_id, enabled}, ...] }

TripWizard.save()
  → includes display_config: displayConfig in trip payload
  → POST /api/trips (create) or PUT /api/trips/{id} (edit)
```

## Source

### Neue Dateien (werden bei Implementierung erstellt)

| Datei | Zweck | ~LOC |
|-------|-------|------|
| `frontend/src/lib/components/wizard/WizardStep3Weather.svelte` | Template-Selector + Metrik-Checkbox-Grid | ~150 |

### Geaenderte Dateien

| Datei | Aenderung |
|-------|-----------|
| `frontend/src/lib/components/wizard/TripWizard.svelte` | `displayConfig` State, `WizardStep3Weather` Import + Einbindung, `save()` erweitert | ~15 LOC |
| `frontend/src/routes/trips/[id]/edit/trip-wizard.spec.ts` | Step-3-Platzhalter-Test entfernt, W2-Tests ergaenzt | ~25 LOC |

### Gesamt: 1 neue + 2 geaenderte Dateien, ~190 LOC

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| Go API `GET /api/metrics` | API (existiert) | Metrik-Katalog laden (metric_id, label, category) |
| Go API `PUT /api/trips/{id}` | API (existiert) | `display_config` speichern im Edit-Mode |
| Go API `POST /api/trips` | API (existiert) | `display_config` speichern im Create-Mode |
| `lib/components/WeatherConfigDialog.svelte` | Komponente (existiert) | Referenz-Pattern: `buildEnabledMap`, Kategorie-Gruppierung, Checkbox-Grid |
| `lib/components/wizard/TripWizard.svelte` | Komponente (existiert) | Container: gibt `displayConfig` via `bind:` weiter, ruft `save()` auf |
| `lib/types.ts` `Trip` | Types (existieren) | `display_config: Record<string, unknown> \| undefined` Feld |
| `shadcn-svelte` Select, Checkbox, Label, Card | Library (existiert) | UI-Grundbausteine fuer Dropdown und Checkbox-Grid |
| Svelte 5 `$state`, `$props`, `$effect`, `$derived` | Framework | Reaktiver State, Sync enabledMap → displayConfig |

## Implementation Details

### WizardStep3Weather.svelte — Interner State und Props

```typescript
interface Props {
  displayConfig: Record<string, unknown> | undefined;
}
let { displayConfig = $bindable() }: Props = $props();

// Aus /api/metrics geladen
let catalog: { metric_id: string; label: string; category: string }[] = $state([]);
let catalogLoaded = $state(false);
let loadError: string | null = $state(null);

// Welche Metriken sind aktiv
let enabledMap: Record<string, boolean> = $state({});

// Aktuell ausgewaehltes Template ('', 'alpen-trekking', 'wandern', 'skitouren', 'wintersport', 'radtour', 'wassersport', 'allgemein')
let selectedTemplate: string = $state('');

// true wenn enabledMap von selectedTemplate abweicht
let isCustom: boolean = $derived(
  selectedTemplate !== '' && !matchesTemplate(enabledMap, selectedTemplate)
);
```

### Template-Definitionen (hardcoded, erweitert gegenueber Python PROFILE_METRIC_IDS)

```typescript
const TEMPLATES: Record<string, { label: string; metrics: string[] }> = {
  'alpen-trekking': {
    label: 'Alpen-Trekking',
    metrics: [
      'temperature', 'wind_chill', 'wind', 'gust',
      'precipitation', 'thunder', 'cape', 'rain_probability',
      'snowfall_limit', 'freezing_level',
      'cloud_total', 'cloud_low', 'visibility', 'uv_index'
    ]
  },
  'wandern': {
    label: 'Wandern',
    metrics: [
      'temperature', 'humidity',
      'wind', 'gust',
      'precipitation', 'rain_probability',
      'cloud_total', 'sunshine', 'uv_index'
    ]
  },
  'skitouren': {
    label: 'Skitouren',
    metrics: [
      'temperature', 'wind_chill', 'wind', 'gust',
      'precipitation', 'fresh_snow', 'snow_depth', 'snowfall_limit',
      'freezing_level',
      'cloud_total', 'cloud_low', 'visibility'
    ]
  },
  'wintersport': {
    label: 'Wintersport (Piste)',
    metrics: [
      'temperature', 'wind_chill', 'wind', 'gust',
      'precipitation', 'fresh_snow', 'snow_depth',
      'cloud_total', 'sunshine', 'visibility'
    ]
  },
  'radtour': {
    label: 'Radtour / Bikepacking',
    metrics: [
      'temperature', 'wind', 'wind_direction', 'gust',
      'precipitation', 'rain_probability', 'thunder', 'cape',
      'cloud_total', 'sunshine', 'uv_index'
    ]
  },
  'wassersport': {
    label: 'Wassersport',
    metrics: [
      'temperature', 'wind', 'gust', 'wind_direction',
      'precipitation', 'rain_probability', 'thunder', 'cape',
      'cloud_total', 'visibility'
    ]
  },
  'allgemein': {
    label: 'Allgemein',
    metrics: [
      'temperature', 'wind', 'gust',
      'precipitation', 'rain_probability',
      'cloud_total', 'sunshine'
    ]
  },
};
```

Begruendung der Template-Zuordnungen:
- **Alpen-Trekking:** `cape` ergaenzt `thunder` als quantitativer Gewitter-Fruehindikator. `cloud_low` zeigt ob Gletscher/Grat ueber der Wolkendecke liegt (via `calculate_cloud_status()`). `freezing_level` fuer Vereisung in der Hoehe.
- **Wandern:** `humidity` statt `wind_chill` — Hitze+Feuchtigkeit ist das Risiko an der Kueste.
- **Skitouren:** `cloud_low` wie Alpen-Trekking (Gipfel ueber Nebel). `freezing_level` fuer Nassschneelawinen.
- **Radtour/Wassersport:** `cape` weil auf offener Strasse/Wasser exponiert. `wind_direction` ist fuer beide Aktivitaeten kritisch.

### Kategorie-Gruppierung (aus WeatherConfigDialog-Pattern)

```typescript
const CATEGORY_LABELS: Record<string, string> = {
  temperature: 'Temperatur',
  wind: 'Wind',
  precipitation: 'Niederschlag',
  atmosphere: 'Atmosphaere',
  winter: 'Winter / Schnee',
};
const CATEGORY_ORDER = ['temperature', 'wind', 'precipitation', 'atmosphere', 'winter'];
```

### onMount: Katalog laden und enabledMap aufbauen

```typescript
onMount(async () => {
  try {
    const res = await fetch('/api/metrics');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    catalog = await res.json();

    // Edit-Mode: bestehende display_config rekonstruieren
    if (displayConfig?.metrics) {
      const metrics = displayConfig.metrics as { metric_id: string; enabled: boolean }[];
      for (const m of metrics) {
        enabledMap[m.metric_id] = m.enabled;
      }
      // Fehlendes aus Katalog mit false auffuellen
      for (const m of catalog) {
        if (!(m.metric_id in enabledMap)) enabledMap[m.metric_id] = false;
      }
      // Template-Erkennung: passt enabledMap zu einem Template?
      for (const [key] of Object.entries(TEMPLATES)) {
        if (matchesTemplate(enabledMap, key)) {
          selectedTemplate = key;
          break;
        }
      }
    } else {
      // Create-Mode: alle Metriken deaktiviert als Standard
      for (const m of catalog) {
        enabledMap[m.metric_id] = false;
      }
    }
    catalogLoaded = true;
  } catch (e) {
    loadError = e instanceof Error ? e.message : 'Katalog nicht ladbar';
  }
});
```

### applyTemplate(): enabledMap ueberschreiben

```typescript
function applyTemplate(templateKey: string) {
  selectedTemplate = templateKey;
  if (templateKey === '') return; // "Kein Profil" — enabledMap unveraendert lassen
  const ids = TEMPLATES[templateKey] ?? [];
  for (const m of catalog) {
    enabledMap[m.metric_id] = ids.includes(m.metric_id);
  }
}
```

### matchesTemplate(): Template-Erkennung

```typescript
function matchesTemplate(map: Record<string, boolean>, key: string): boolean {
  const ids = TEMPLATES[key] ?? [];
  return catalog.every(m =>
    map[m.metric_id] === ids.includes(m.metric_id)
  );
}
```

### $effect: enabledMap → displayConfig sync

```typescript
$effect(() => {
  if (!catalogLoaded) return; // Guard: erst nach erfolgreichem Katalog-Load
  const metrics = Object.entries(enabledMap).map(([metric_id, enabled]) => ({
    metric_id,
    enabled,
  }));
  displayConfig = { metrics };
});
```

### TripWizard.svelte — Aenderungen

```svelte
<!-- Ergaenzte Imports -->
import WizardStep3Weather from './WizardStep3Weather.svelte';

<!-- Ergaenzter State -->
let displayConfig = $state(existingTrip?.display_config);

<!-- Step 3 Einbindung (ersetzt WizardStep3Placeholder) -->
{#if currentStep === 3}
  <WizardStep3Weather bind:displayConfig />
{/if}

<!-- In save(): display_config einbeziehen -->
const trip: Trip = {
  id: tripId || crypto.randomUUID().slice(0, 8),
  name: tripName,
  stages,
  display_config: displayConfig,
  ...(existingTrip && {
    avalanche_regions: existingTrip.avalanche_regions,
    aggregation: existingTrip.aggregation,
    weather_config: existingTrip.weather_config,
    report_config: existingTrip.report_config,
  }),
};
```

### Data-testids fuer E2E-Tests

| Attribut | Element | Zweck |
|----------|---------|-------|
| `data-testid="wizard-step3-weather"` | Container-Div | Schritt-Erkennung in Tests |
| `data-testid="weather-template-select"` | Template-Dropdown | Template-Auswahl testen |
| `data-testid="metric-checkbox-{metric_id}"` | Pro-Metrik-Checkbox | Einzelne Metrik-Toggles pruefen |

## Expected Behavior

### Create-Mode (User hat kein Template gewaehlt)

- **Input:** `displayConfig` ist `undefined`, kein existingTrip
- **Output:** `displayConfig` bleibt `undefined` wenn User Step 3 ueberspringt (kein $effect-Trigger vor Katalog-Load)
- **Side effects:** Backend verwendet Python-Defaults wenn `display_config` fehlt

### Create-Mode (User waehlt Template "Wandern")

- **Input:** User oeffnet Dropdown, waehlt "Wandern"
- **Output:** `enabledMap` wird mit `wandern`-Metriken ueberschrieben, `displayConfig` wird zu `{ metrics: [{metric_id: "temperature", enabled: true}, ...] }`
- **Side effects:** Checkbox-Grid zeigt entsprechende Haekchen gesetzt

### Edit-Mode (Trip hat bestehende display_config)

- **Input:** `displayConfig = { metrics: [{metric_id: "temperature", enabled: true}, ...] }`
- **Output:** `enabledMap` wird aus `display_config.metrics` rekonstruiert, passendes Template wird automatisch erkannt und im Dropdown vorgewaehlt
- **Side effects:** Keine — `displayConfig` wird erst nach User-Interaktion ueberschrieben

### Checkbox-Toggle divergiert vom Template

- **Input:** User waehlt Template "Allgemein", deaktiviert dann "wind"
- **Output:** `isCustom` wird `true`, Dropdown wechselt zu "Benutzerdefiniert", `enabledMap["wind"]` ist `false`
- **Side effects:** `displayConfig` wird mit angepassten Werten aktualisiert

### API-Fehler beim Katalog-Laden

- **Input:** `GET /api/metrics` liefert HTTP-Fehler
- **Output:** `loadError` wird gesetzt, Fehlermeldung im Step angezeigt
- **Side effects:** `catalogLoaded` bleibt `false`, `$effect`-Guard verhindert `displayConfig`-Ueberschreibung, Wizard kann weiterhin zu Step 4 navigieren

## Known Limitations

- Template-Definitionen sind dupliziert (Frontend + Python Backend) — Aenderungen muessen an beiden Stellen gemacht werden
- "Kein Profil" Option setzt keine Metriken (enabledMap bleibt wie vor Template-Auswahl) — kein dediziertes "Alle deaktivieren"
- Template-Erkennung im Edit-Mode schlaegt fehl wenn display_config zusaetzliche Felder neben `metrics` enthaelt (erweiterbar bei W3)
- Keine Lade-Animation waehrend Katalog-Fetch (nur Text-Fehlermeldung bei Fehler)
- `WizardStep3Placeholder.svelte` wird nicht geloescht (kann nach W2-Deployment entfernt werden)

## Changelog

- 2026-04-18: Initial spec created
