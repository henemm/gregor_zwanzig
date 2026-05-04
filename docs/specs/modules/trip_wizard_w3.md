---
entity_id: trip_wizard_w3
type: module
created: 2026-04-19
updated: 2026-04-19
status: draft
version: "1.0"
tags: [sveltekit, frontend, trips, wizard, report-config, scheduling, alerts]
---

# Trip Wizard W3: Report Configuration (SvelteKit)

## Approval

- [ ] Approved

## Purpose

Ersetzt den Step-4-Platzhalter ("Kommt in W3") im Trip Wizard durch eine vollstaendige Report-Konfigurationsoberflaeche: Der User stellt Zeitplan, Channels, Alert-Schwellwerte und erweiterte Optionen ein, und das Ergebnis wird als `report_config` im Trip gespeichert. Diese Komponente ist der letzte Schritt vor dem Speichern und ermoeglicht es Wanderern, genau zu steuern, wann, wie und unter welchen Bedingungen sie Wetter-Reports erhalten — ohne neue API-Endpoints zu benoetigen.

## Scope

### In Scope (W3)

- `WizardStep4ReportConfig.svelte`: Neue Komponente mit 4 konfigurierbaren Sektionen
- Zeitplan-Sektion: Master-Toggle "Reports aktiviert" + Morgen/Abend-Zeitauswahl
- Channel-Sektion: E-Mail, Signal, Telegram (kein SMS)
- Alert-Sektion: Toggle "Bei Aenderungen benachrichtigen" + 3 numerische Schwellwerte
- Erweitert-Sektion: collapsed by default, toggle via showAdvanced State
- Time-Normalisierung: Python `"HH:MM:SS"` → HTML `"HH:MM"` beim Laden
- `TripWizard.svelte`: `reportConfig` State ergaenzt, `WizardStep4ReportConfig` eingebunden, `save()` erweitert
- `frontend/e2e/trip-wizard.spec.ts`: 5 neue W3-Tests

### Out of Scope (W3)

- Backend-seitige Validierung von `report_config`
- Neue API-Endpoints
- SMS-Channel
- TypeScript `TripReportConfig` Interface (bleibt `Record<string, unknown>`)
- Vorschau der konfigurierten Report-Ausgabe

## Architecture

```
TripWizard.svelte
  ├── let reportConfig = $state(existingTrip?.report_config)
  └── WizardStep4ReportConfig (step === 4, bind:reportConfig)
        ├── Zeitplan-Sektion
        │     [ ] Reports aktiviert (master toggle)
        │     Morgen:  input[type=time] (default "07:00")
        │     Abend:   input[type=time] (default "18:00")
        ├── Channel-Sektion
        │     [x] E-Mail
        │     [ ] Signal
        │     [ ] Telegram
        ├── Alert-Sektion
        │     [x] Bei Aenderungen benachrichtigen
        │     Temperatur-Schwellwert: input[type=number] (default 5.0)
        │     Wind-Schwellwert:       input[type=number] (default 20.0)
        │     Niederschlag-Schwellwert: input[type=number] (default 10.0)
        └── Erweitert (collapsed by default, toggle via showAdvanced)
              [x] Kompakte Zusammenfassung
              [x] Tageslicht anzeigen
              Wind-Exposition Mindesthoehe: input[type=number] (leer = null)
              Mehrtages-Trend: [x] Morning [ ] Evening → ["morning"]

TripWizard.save()
  → includes report_config: reportConfig in trip payload (unconditional)
  → POST /api/trips (create) or PUT /api/trips/{id} (edit)
```

## Source

### Neue Dateien (werden bei Implementierung erstellt)

| Datei | Zweck | ~LOC |
|-------|-------|------|
| `frontend/src/lib/components/wizard/WizardStep4ReportConfig.svelte` | Zeitplan + Channels + Alerts + Erweitert | ~130 |

### Geaenderte Dateien

| Datei | Aenderung |
|-------|-----------|
| `frontend/src/lib/components/wizard/TripWizard.svelte` | `reportConfig` State, `WizardStep4ReportConfig` Import + Einbindung, `save()` erweitert | ~18 LOC |
| `frontend/e2e/trip-wizard.spec.ts` | 5 neue W3-Tests ergaenzt | ~40 LOC |

### Gesamt: 1 neue + 2 geaenderte Dateien, ~188 LOC

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| Go API `PUT /api/trips/{id}` | API (existiert) | `report_config` speichern im Edit-Mode |
| Go API `POST /api/trips` | API (existiert) | `report_config` speichern im Create-Mode |
| `lib/components/wizard/TripWizard.svelte` | Komponente (existiert) | Container: gibt `reportConfig` via `bind:` weiter, ruft `save()` auf |
| `lib/types.ts` `Trip` | Types (existieren) | `report_config: Record<string, unknown> \| undefined` Feld |
| `shadcn-svelte` Checkbox, Label, Card, Switch | Library (existiert) | UI-Grundbausteine fuer Checkboxen, Toggles, Sektions-Karten |
| Svelte 5 `$state`, `$props`, `$effect` | Framework | Reaktiver State, Sync lokaler State → reportConfig |

## Implementation Details

### WizardStep4ReportConfig.svelte — Interner State und Props

```typescript
interface Props {
  reportConfig: Record<string, unknown> | undefined;
  mode?: 'create' | 'edit';
}
let { reportConfig = $bindable(), mode = 'create' }: Props = $props();

// Zeitplan
let enabled = $state(true);
let morning_time = $state('07:00');
let evening_time = $state('18:00');

// Channels
let send_email = $state(true);
let send_signal = $state(false);
let send_telegram = $state(false);

// Alerts
let alert_on_changes = $state(true);
let change_threshold_temp_c = $state(5.0);
let change_threshold_wind_kmh = $state(20.0);
let change_threshold_precip_mm = $state(10.0);

// Erweitert
let showAdvanced = $state(false);
let show_compact_summary = $state(true);
let show_daylight = $state(true);
let wind_exposition_min_elevation_m: number | null = $state(null);
let trend_morning = $state(false);
let trend_evening = $state(true);
```

### onMount: Edit-Mode laden und Zeit normalisieren

```typescript
onMount(() => {
  if (!reportConfig) return; // Create-Mode: Defaults behalten

  const c = reportConfig as Record<string, unknown>;

  if (typeof c.enabled === 'boolean') enabled = c.enabled;
  // Time normalisierung: Python "07:00:00" → HTML "07:00"
  if (typeof c.morning_time === 'string') morning_time = c.morning_time.slice(0, 5);
  if (typeof c.evening_time === 'string') evening_time = c.evening_time.slice(0, 5);

  if (typeof c.send_email === 'boolean') send_email = c.send_email;
  if (typeof c.send_signal === 'boolean') send_signal = c.send_signal;
  if (typeof c.send_telegram === 'boolean') send_telegram = c.send_telegram;

  if (typeof c.alert_on_changes === 'boolean') alert_on_changes = c.alert_on_changes;
  if (typeof c.change_threshold_temp_c === 'number') change_threshold_temp_c = c.change_threshold_temp_c;
  if (typeof c.change_threshold_wind_kmh === 'number') change_threshold_wind_kmh = c.change_threshold_wind_kmh;
  if (typeof c.change_threshold_precip_mm === 'number') change_threshold_precip_mm = c.change_threshold_precip_mm;

  if (typeof c.show_compact_summary === 'boolean') show_compact_summary = c.show_compact_summary;
  if (typeof c.show_daylight === 'boolean') show_daylight = c.show_daylight;
  // null-safe: leeres Feld bleibt null
  wind_exposition_min_elevation_m = typeof c.wind_exposition_min_elevation_m === 'number'
    ? c.wind_exposition_min_elevation_m
    : null;

  // multi_day_trend_reports: string[] → trend_morning/trend_evening flags
  if (Array.isArray(c.multi_day_trend_reports)) {
    const arr = c.multi_day_trend_reports as string[];
    trend_morning = arr.includes('morning');
    trend_evening = arr.includes('evening');
  }
});
```

### $effect: lokaler State → reportConfig sync

```typescript
$effect(() => {
  const multi_day_trend_reports: string[] = [];
  if (trend_morning) multi_day_trend_reports.push('morning');
  if (trend_evening) multi_day_trend_reports.push('evening');

  reportConfig = {
    enabled,
    morning_time,
    evening_time,
    send_email,
    send_signal,
    send_telegram,
    alert_on_changes,
    change_threshold_temp_c,
    change_threshold_wind_kmh,
    change_threshold_precip_mm,
    show_compact_summary,
    show_daylight,
    wind_exposition_min_elevation_m,
    multi_day_trend_reports,
  };
});
```

### wind_exposition_min_elevation_m: leeres Feld → null

```svelte
<input
  type="number"
  value={wind_exposition_min_elevation_m ?? ''}
  oninput={(e) => {
    const v = (e.target as HTMLInputElement).value;
    wind_exposition_min_elevation_m = v === '' ? null : Number(v);
  }}
/>
```

### TripWizard.svelte — Aenderungen

```svelte
<!-- Ergaenzte Imports -->
import WizardStep4ReportConfig from './WizardStep4ReportConfig.svelte';

<!-- Ergaenzter State -->
let reportConfig = $state(existingTrip?.report_config);

<!-- Step 4 Einbindung (ersetzt Platzhalter) -->
{#if currentStep === 4}
  <WizardStep4ReportConfig bind:reportConfig />
{/if}

<!-- In save(): report_config unconditional einbinden.
     W2 hat display_config bereits unconditional gemacht.
     W3 macht dasselbe fuer report_config — die existingTrip-Guard
     fuer report_config wird entfernt, da der Wizard jetzt immer
     ein vollstaendiges report_config-Objekt mit Defaults liefert.
     Im Create-Mode enthaelt reportConfig die Defaults aus onMount/$effect. -->
const trip: Trip = {
  id: tripId || crypto.randomUUID().slice(0, 8),
  name: tripName,
  stages,
  display_config: displayConfig,
  report_config: reportConfig,
  ...(existingTrip && {
    avalanche_regions: existingTrip.avalanche_regions,
    aggregation: existingTrip.aggregation,
    weather_config: existingTrip.weather_config,
  }),
};
```

### Data-testids fuer E2E-Tests

| Attribut | Element | Zweck |
|----------|---------|-------|
| `data-testid="wizard-step4-report"` | Container-Div | Schritt-Erkennung in Tests |
| `data-testid="report-enabled"` | Master-Toggle | Reports-Aktivierung pruefen |
| `data-testid="report-morning-time"` | input[type=time] | Morgen-Zeit pruefen |
| `data-testid="report-evening-time"` | input[type=time] | Abend-Zeit pruefen |
| `data-testid="report-send-email"` | Checkbox | E-Mail-Channel pruefen |
| `data-testid="report-send-signal"` | Checkbox | Signal-Channel pruefen |
| `data-testid="report-send-telegram"` | Checkbox | Telegram-Channel pruefen |
| `data-testid="report-alert-changes"` | Checkbox | Alert-Toggle pruefen |
| `data-testid="report-show-advanced"` | Toggle-Button | Erweitert-Sektion aufklappen |
| `data-testid="report-compact-summary"` | Checkbox | Kompakte Zusammenfassung (Erweitert) |
| `data-testid="report-show-daylight"` | Checkbox | Tageslicht anzeigen (Erweitert) |
| `data-testid="report-wind-exposition"` | input[type=number] | Wind-Exposition Mindesthoehe (Erweitert) |
| `data-testid="report-trend-morning"` | Checkbox | Mehrtages-Trend Morning (Erweitert) |
| `data-testid="report-trend-evening"` | Checkbox | Mehrtages-Trend Evening (Erweitert) |

### E2E Tests (5 Tests in trip-wizard.spec.ts)

| Nr | Test | Prueft |
|----|------|--------|
| 1 | Step 4 shows report config container | `wizard-step4-report` sichtbar nach Navigation zu Step 4 |
| 2 | Schedule section has time inputs with defaults | `report-morning-time` hat value "07:00", `report-evening-time` hat value "18:00" |
| 3 | Channel checkboxes: email checked by default | `report-send-email` ist checked, `report-send-signal` unchecked, `report-send-telegram` unchecked |
| 4 | Alert section has threshold inputs visible | `report-alert-changes` ist checked, drei Zahlen-Inputs sichtbar |
| 5 | Advanced section expandable via toggle | Klick auf `report-show-advanced` zeigt versteckte Felder |

## Expected Behavior

### Create-Mode (neuer Trip)

- **Input:** `reportConfig` ist `undefined`, kein existingTrip
- **Output:** `$effect` laeuft sofort, `reportConfig` wird mit Default-Werten behuellt: `{ enabled: true, morning_time: "07:00", evening_time: "18:00", send_email: true, send_signal: false, send_telegram: false, alert_on_changes: true, change_threshold_temp_c: 5.0, change_threshold_wind_kmh: 20.0, change_threshold_precip_mm: 10.0, show_compact_summary: true, show_daylight: true, wind_exposition_min_elevation_m: null, multi_day_trend_reports: ["evening"] }`
- **Side effects:** Beim Speichern enthaelt Trip immer ein vollstaendiges `report_config` Objekt

### Edit-Mode (Trip hat bestehende report_config)

- **Input:** `reportConfig = { morning_time: "07:00:00", send_signal: true, ... }` (Python-Format mit Sekunden)
- **Output:** `morning_time` wird zu `"07:00"` normalisiert, `send_signal` Checkbox erscheint gecheckt, alle anderen Felder aus gespeichertem Wert rekonstruiert
- **Side effects:** `$effect` aktualisiert `reportConfig` erst nach erster User-Interaktion oder Mount

### wind_exposition_min_elevation_m leer lassen

- **Input:** User loescht den Inhalt des Hoehen-Inputs
- **Output:** `wind_exposition_min_elevation_m` wird `null`, nicht `""` oder `0`
- **Side effects:** Backend erhaelt `null` im JSON (Feld nicht gesetzt)

### multi_day_trend_reports Array-Mapping

- **Input:** User waehlt "Morning" Checkbox ab, "Evening" Checkbox bleibt aktiv
- **Output:** `multi_day_trend_reports` wird `["evening"]`
- **Side effects:** Kein — Array wird bei jedem $effect-Lauf neu aufgebaut

### Erweitert-Sektion eingeklappt

- **Input:** Komponente wird gemountet
- **Output:** `showAdvanced` ist `false`, Erweitert-Sektion nicht sichtbar
- **Side effects:** Klick auf Toggle-Button setzt `showAdvanced = true`, Sektion wird sichtbar

## Known Limitations

- Time-Wert wird als String gespeichert — keine Validierung ob "HH:MM" wohlgeformt ist
- `wind_exposition_min_elevation_m: null` wird als JSON `null` gesendet — Backend muss null von fehlendem Feld unterscheiden koennen
- Keine Validierung ob `morning_time < evening_time`
- Step-4-Platzhalter ist ein Inline-Div in TripWizard.svelte (Zeile 100-102), kein separates File — wird direkt ersetzt
- SMS-Channel absichtlich ausgelassen (nicht implementiert) — spaeteres Feature-Flag noetig bei Aktivierung

## Changelog

- 2026-04-19: Initial spec created. Baut auf W2 (7428854) auf — W2 hat display_config unconditional gemacht, W3 tut dasselbe fuer report_config. Data-testids fuer Erweitert-Sektion ergaenzt.
