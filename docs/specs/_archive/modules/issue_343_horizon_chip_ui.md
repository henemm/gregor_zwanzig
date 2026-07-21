---
entity_id: issue_343_horizon_chip_ui
type: module
created: 2026-05-23
updated: 2026-05-23
status: draft
version: "1.0"
tags: [frontend, weather, ui, svelte, horizon-chip]
parent_epic: 304
predecessor: 342
---

<!-- Issue #343 — HorizonChip-UI im Wetter-Editor (Sub-Issue 2 von Klammer-Epic #304) -->

# Issue #343 — HorizonChip-UI im Wetter-Editor

## Approval

- [ ] Approved

## Purpose

Ergänzt den `WeatherMetricsTab.svelte` im Trip-Detail-Wetter-Tab um eine neue Toggle-Komponente `HorizonChip`: pro Metrik-Zeile drei togglebare Tag-Pills (`heute / morgen / übermorgen`), die unabhängig von Aus-Schalter und Roh/Indikator-Modus funktionieren. Lädt und speichert die `horizons`-Felder aus `Trip.display_config.metrics[]` (Backend live aus #342), erweitert `TablePreview` auf drei nebeneinanderliegende Mini-Tabellen pro Horizont und `SavePresetDialog` um eine ZEITHORIZONTE-Box mit dynamischer Wording-Zusammenfassung. Ohne diese UI bleibt die in #342 gebaute Backend-Filterung pro Etappe für den User unsichtbar.

## Scope

### In Scope

- Neue Brand-Komponente `HorizonChip.svelte` (`[data-slot="horizon-chip"]` mit `[data-active]`-Attribut, Vorbild: Pill/Segmented)
- `MetricCheckbox.svelte`: drei `HorizonChip`-Instanzen nach den Roh/Indikator-Pills einfügen; Mobile-Breakpoint < 600 px stellt Chips in Zeile 2 unter den Metrik-Namen, eingerückt auf Namens-Höhe
- `WeatherMetricsTab.svelte`: neuer State `horizonsMap: Record<string, Horizons>` parallel zu `enabledMap`/`friendlyMap`; in `initMaps()` aus Trip-Load befüllen, in `isDirty`-Snapshot aufnehmen, in Save-Payload mitsenden
- `TablePreview.svelte`: Umbau von einer Tabelle auf drei separate Mini-Tabellen `HEUTE / MORGEN / ÜBERMORGEN`, jeweils nur Spalten für die im `horizonsMap` aktivierten Metriken; Layout-Header mit Eyebrow + Zähler (`HEUTE — N METRIKEN`)
- `SavePresetDialog.svelte`: neue Box „WIRD GESPEICHERT" mit ZEITHORIZONTE-Eyebrow, Wording-Heuristik-Zusammenfassung, Metrik-Liste mit `●●●` / `●●○` / `●○○`-Indikatoren pro Metrik; Save-Payload sendet `metrics[].horizons` mit
- `frontend/src/lib/types.ts`: TypeScript-Type `Horizons` einführen, `WeatherConfigMetric` und `MetricPreset.metrics[]` um optionales `horizons` erweitern
- TypeScript-Helper `computeHorizonSummary(metrics, horizonsMap)` (für Dialog-Wording)
- Svelte-Component-Tests (Vitest + @testing-library/svelte) für `HorizonChip` und `computeHorizonSummary`
- Playwright-E2E-Test `issue-343-horizon-chips.spec.ts`: Toggle-Roundtrip + Mobile-Layout + SavePresetDialog-ZEITHORIZONTE-Box

### Out of Scope

- Backend-Änderungen — sind in **#342** fertig und live (PATCH-Endpoint, Schema-Migration, Renderer-Filter)
- Account-Karte zur Preset-Verwaltung (Umbenennen, Löschen, Default-Setzen aus UI) → **#344**
- Konsolidierung des alten `EditWeatherSection`-Pfads mit `WeatherMetricsTab` → **#345**
- Wizard-Step-3-Wetter-Integration (das Mockup `soll-flow1D-wizard-step3-wetter.png` zeigt das Layout im Wizard, aber diese Spec adressiert den Trip-Detail-Tab; Wizard-Integration folgt in separatem Sub-Issue)
- Mobile-Layout der `TablePreview` unter 1100 px (CSS-Grid `auto-fit` als Pragmatik; eigenes Design-Mockup folgt)
- Server-seitige Persistenz-Migration der `metric_presets.json` auf Platte (lazy-Migration aus #342 reicht)

## Source

- **File:** `frontend/src/lib/components/ui/horizon-chip/HorizonChip.svelte` (NEU)
- **File:** `frontend/src/lib/components/trip-detail/MetricCheckbox.svelte` (modifiziert)
- **File:** `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte` (modifiziert)
- **File:** `frontend/src/lib/components/trip-detail/TablePreview.svelte` (modifiziert)
- **File:** `frontend/src/lib/components/trip-detail/SavePresetDialog.svelte` (modifiziert)
- **File:** `frontend/src/lib/types.ts` (erweitert)
- **File:** `frontend/src/lib/utils/horizonHelpers.ts` (NEU — `computeHorizonSummary()`)
- **Identifier:** `HorizonChip`, `MetricCheckbox`, `WeatherMetricsTab`, `TablePreview`, `SavePresetDialog`, `computeHorizonSummary`

> **Schicht-Hinweis:** Diese Spec betrifft **ausschließlich** die Frontend-Schicht (SvelteKit unter `frontend/src/`). Backend (Go-API + Python-Renderer) ist aus #342 live und wird nicht angefasst. PUT `/api/trips/{id}/weather-config` und POST `/api/metric-presets` akzeptieren das neue Schema bereits (Compat-Layer für alte Payloads ist vorhanden).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `issue_342_pro_metrik_horizon_backend` Spec | Vorgänger-Spec | Backend-Schema (`Horizons`, `DisplayMetric`, PATCH-Endpoint, Filter) — live |
| `epic_138_174_178_metriken_ui` Spec | Vorgänger-Spec | Definiert heutigen Stand von `WeatherMetricsTab`, `MetricCheckbox`, `TablePreview`, `SavePresetDialog`, `MetricPreset`-Type |
| `<Pill>` (`frontend/src/lib/components/ui/pill/Pill.svelte`) | Atom | Vorbild für `[data-slot]`-Pattern (Selector + Attribut-getriebenes Styling) |
| `<Segmented>` (`frontend/src/lib/components/ui/segmented/Segmented.svelte`) | Atom | Vorbild für `[data-active]`-Attribut + Click-Handler |
| `<Btn>` (`frontend/src/lib/components/ui/btn/Btn.svelte`) | Atom | Wird in `MetricCheckbox` für Roh/Indikator-Pills weiter genutzt; `HorizonChip` kommt visuell daneben |
| `<Card>`, `<Eyebrow>`, `<Dialog>` | Atoms | In `TablePreview` (Sektion-Header) + `SavePresetDialog` (ZEITHORIZONTE-Box) |
| `PUT /api/trips/{id}/weather-config` | Backend-API | Trip-Persistenz mit `display_config.metrics[].horizons` |
| `POST /api/metric-presets` | Backend-API | User-Preset-Speicherung mit `metrics[].horizons` |
| `--g-ink`, `--g-paper`, `--g-ink-faint`, `--g-accent`, `--g-s-*`, `--g-r-pill`, `--g-font-mono`, `--g-text-xs` | Design-Tokens | Visuelles Styling der HorizonChip-Komponente |

## Architecture

### State-Flow im `WeatherMetricsTab.svelte`

```
                  GET /api/trips/{id}
                         |
                         v
+------------------------+------------------------+
| trip.display_config.metrics: [                  |
|   {metric_id, enabled, use_friendly_format,     |
|    horizons:{today, tomorrow, day_after}}       |
| ]                                               |
+------------------------+------------------------+
                         |
                         v
                   initMaps()
                         |
       +-----------------+-----------------+--------------------+
       v                 v                 v                    v
  enabledMap        friendlyMap       horizonsMap         savedSnapshot
  (existing)        (existing)        (NEU)               (JSON v. allen drei)
       |                 |                 |                    |
       +-----------------+-----------------+--------------------+
                         |
                         v
              { Render Komponenten-Baum }
                  |          |          |
                  v          v          v
        MetricCheckbox  MetricCheckbox  ...   ← HorizonChip-Klicks
                  |                                   |
                  v                                   v
            onModeChange()                     onHorizonChange(day)
                  |                                   |
                  +-----------------+-----------------+
                                    v
                          isDirty = (JSON-Diff zu savedSnapshot)
                                    |
                          dirty-Pill + Speichern-Button
                                    |
                                    v
                            handleSave()
                                    |
                                    v
                PUT /api/trips/{id}/weather-config
                  Body: { metrics: [
                    {metric_id, enabled, use_friendly_format, horizons}
                  ] }
                                    |
                                    v
                       savedSnapshot ← aktualisiert
```

### Komponenten-Hierarchie

```
WeatherMetricsTab.svelte
├── MetricGroup (pro Kategorie)
│   └── MetricCheckbox (pro Metrik)
│       ├── Checkbox + Label + Unit
│       ├── Btn "Roh" / Btn "Indikator"  (existing, conditional)
│       └── HorizonChip × 3              (NEU: heute / morgen / übermorgen)
├── TablePreview                          (UMGEBAUT: 3 Mini-Tabellen)
│   ├── PageSection-Header
│   ├── Strip (Profil-Wahl + Zähler)
│   └── 3 × <table>                       (Grid, auto-fit minmax(280px,1fr))
│       ├── HEUTE — N METRIKEN
│       ├── MORGEN — N METRIKEN
│       └── ÜBERMORGEN — N METRIKEN
└── SavePresetDialog                      (ERWEITERT: ZEITHORIZONTE-Box)
    ├── Name / Beschreibung
    ├── Box "WIRD GESPEICHERT"
    │   ├── Status-Zeile (existing)
    │   ├── Hairline
    │   ├── Eyebrow "ZEITHORIZONTE"
    │   ├── Wording-Zeile (computeHorizonSummary)
    │   └── Zwei-Spalten-Liste mit ●●●/●●○/●○○-Pattern
    └── Default-Checkbox + Footer
```

## Data Model

### TypeScript-Erweiterungen in `frontend/src/lib/types.ts`

```typescript
// NEU
export type Horizons = {
  today: boolean;
  tomorrow: boolean;
  day_after: boolean;
};

export const HORIZONS_ALL: Horizons = {
  today: true,
  tomorrow: true,
  day_after: true,
};

// ERWEITERT — additiv, optional
export interface WeatherConfigMetric {
  metric_id: string;
  enabled: boolean;
  use_friendly_format: boolean;
  horizons?: Horizons;   // NEU — default {true,true,true} bei Load
}

// ERWEITERT — Backend hat Schema umgestellt (siehe #342)
export interface MetricPresetMetric {
  metric_id: string;
  enabled: boolean;
  use_friendly_format: boolean;
  horizons?: Horizons;
}

export interface MetricPreset {
  id: string;
  name: string;
  description?: string;
  is_default: boolean;
  metrics: MetricPresetMetric[];   // war []string + friendly_ids []string
  created_at: string;
}
```

### Default-Verhalten

- Beim Load eines Trips ohne `horizons` (Legacy): `initMaps()` setzt `horizonsMap[metric_id] = HORIZONS_ALL`
- Beim Aktivieren einer vorher deaktivierten Metrik (Checkbox-Toggle ON): `horizonsMap[metric_id]` wird auf `HORIZONS_ALL` initialisiert, falls noch nicht vorhanden
- `isDirty`-Snapshot enthält `horizonsMap` als Teil der JSON-Vergleichsbasis

### Save-Payload (PUT `/api/trips/{id}/weather-config`)

```json
{
  "metrics": [
    {
      "metric_id": "wind",
      "enabled": true,
      "use_friendly_format": false,
      "horizons": {"today": true, "tomorrow": true, "day_after": true}
    },
    {
      "metric_id": "thunder",
      "enabled": true,
      "use_friendly_format": true,
      "horizons": {"today": false, "tomorrow": true, "day_after": true}
    }
  ]
}
```

### Save-Payload (POST `/api/metric-presets`)

```json
{
  "name": "Mein Skitouren-Set",
  "description": "Frühjahr, Lawinenfokus, kurze Tage",
  "is_default": false,
  "metrics": [
    {"metric_id":"wind", "enabled":true, "use_friendly_format":false,
     "horizons":{"today":true,"tomorrow":true,"day_after":true}},
    {"metric_id":"thunder", "enabled":true, "use_friendly_format":true,
     "horizons":{"today":false,"tomorrow":true,"day_after":true}}
  ]
}
```

## Implementation Details

### §1 `HorizonChip.svelte` (NEU)

**Pfad:** `frontend/src/lib/components/ui/horizon-chip/HorizonChip.svelte`

**Props:**

```typescript
interface Props {
  day: 'today' | 'tomorrow' | 'day_after';
  active: boolean;
  onclick: () => void;
  disabled?: boolean;   // default false
}
```

**Template + Style (Svelte 5):**

```svelte
<script lang="ts">
  type Day = 'today' | 'tomorrow' | 'day_after';
  let { day, active, onclick, disabled = false }: {
    day: Day;
    active: boolean;
    onclick: () => void;
    disabled?: boolean;
  } = $props();

  const LABELS: Record<Day, string> = {
    today: 'HEUTE',
    tomorrow: 'MORGEN',
    day_after: 'ÜBERMORGEN',
  };
</script>

<button
  type="button"
  data-slot="horizon-chip"
  data-active={active}
  data-day={day}
  {disabled}
  aria-pressed={active}
  {onclick}
>{LABELS[day]}</button>

<style>
  [data-slot="horizon-chip"] {
    /* Größe: 32 px Höhe, padding hebt Touch-Target auf 44 × 44 */
    min-height: 32px;
    min-width: 44px;
    padding: var(--g-s-1) var(--g-s-3);
    border-radius: var(--g-r-pill);
    border: 1px solid var(--g-ink-faint);
    background: transparent;
    color: var(--g-ink-faint);
    font-family: var(--g-font-mono);
    font-size: var(--g-text-xs);
    letter-spacing: var(--g-track-caps);
    text-transform: uppercase;
    cursor: pointer;
    transition: background 120ms, color 120ms, border-color 120ms;
  }
  [data-slot="horizon-chip"][data-active="true"] {
    background: var(--g-ink);
    color: var(--g-paper);
    border-color: var(--g-ink);
  }
  [data-slot="horizon-chip"]:disabled {
    cursor: not-allowed;
    opacity: 0.5;
  }
  [data-slot="horizon-chip"]:focus-visible {
    outline: 2px solid var(--g-accent);
    outline-offset: 2px;
  }
</style>
```

**Verhalten:**

- `aria-pressed` reflektiert `active`
- `data-active="true"` ist der einzige Style-Hebel (kein `class:active` — Vorbild Segmented/Pill)
- Touch-Target ≥ 44 × 44 px (Charter §7), Mono-Caps-Schrift (Charter §5)
- KEIN Border-Radius-Hex-Fallback, KEINE Inline-Farben — nur Tokens

### §2 `MetricCheckbox.svelte` — Erweiterung

**Neue Props:**

```typescript
interface Props {
  // ... existing props ...
  horizons: Horizons;
  onHorizonChange: (day: 'today' | 'tomorrow' | 'day_after') => void;
}
```

**Template-Ergänzung (Desktop):**

Nach dem existierenden Roh/Indikator-Pill-Block, vor dem Kebab-`…`, drei `HorizonChip`-Instanzen in einem Flex-Container:

```svelte
<div class="horizon-chips" data-slot="horizon-chip-group">
  <HorizonChip day="today" active={horizons.today}
               onclick={() => onHorizonChange('today')} />
  <HorizonChip day="tomorrow" active={horizons.tomorrow}
               onclick={() => onHorizonChange('tomorrow')} />
  <HorizonChip day="day_after" active={horizons.day_after}
               onclick={() => onHorizonChange('day_after')} />
</div>
```

**Mobile (< 600 px) — Chip-Umbruch in Zeile 2:**

```svelte
<style>
  .metric-row {
    display: grid;
    grid-template-columns: auto 1fr auto auto;
    grid-template-areas: "check name pills menu";
    gap: var(--g-s-3);
    align-items: center;
  }
  .horizon-chips {
    grid-area: pills;
    display: flex;
    gap: var(--g-s-2);
  }
  @media (max-width: 599px) {
    .metric-row {
      grid-template-columns: auto 1fr auto;
      grid-template-areas:
        "check name menu"
        ".     chips menu";
      row-gap: var(--g-s-2);
    }
    .horizon-chips {
      grid-area: chips;
      flex-wrap: wrap;
    }
  }
</style>
```

Die Mobile-Variante stellt die Chips in Zeile 2 unter den Namen, eingerückt auf die Höhe des Metrik-Namens (Checkbox-Spalte bleibt leer als `.` im Grid-Area-Map). Die Roh/Indikator-Pills bleiben in Zeile 1 — kein Bottom-Sheet, kein Umbruch des Modus-Toggles.

**Verhalten bei deaktivierter Metrik:**

`HorizonChip` ist togglebar AUCH wenn `enabled === false` — AC-2. Visuell wird die Zeile via `opacity: 0.6` gedämpft, die Chips sind aber funktional. Das spiegelt das im Mockup gezeigte „Luftfeuchtigkeit"-Beispiel (deaktivierte Metrik mit blassen, aber klickbaren Chips).

### §3 `WeatherMetricsTab.svelte` — State + Save

**Neuer State:**

```typescript
let horizonsMap = $state<Record<string, Horizons>>({});
```

**`initMaps()` (existing) wird erweitert:**

```typescript
function initMaps() {
  const dc = trip?.display_config?.metrics ?? [];
  enabledMap = Object.fromEntries(dc.map(m => [m.metric_id, m.enabled]));
  friendlyMap = Object.fromEntries(dc.map(m => [m.metric_id, m.use_friendly_format]));
  horizonsMap = Object.fromEntries(
    dc.map(m => [m.metric_id, m.horizons ?? { ...HORIZONS_ALL }])
  );
  savedSnapshot = JSON.stringify({ enabledMap, friendlyMap, horizonsMap });
}
```

**Neuer Handler:**

```typescript
function onHorizonChange(metricId: string, day: keyof Horizons) {
  const current = horizonsMap[metricId] ?? { ...HORIZONS_ALL };
  horizonsMap = {
    ...horizonsMap,
    [metricId]: { ...current, [day]: !current[day] },
  };
}
```

**`isDirty` — JSON-Snapshot erweitert:**

```typescript
const isDirty = $derived(
  JSON.stringify({ enabledMap, friendlyMap, horizonsMap }) !== savedSnapshot
);
```

**`handleSave()` — Payload mit horizons:**

```typescript
async function handleSave() {
  const payload = {
    metrics: Object.keys(enabledMap).map(id => ({
      metric_id: id,
      enabled: enabledMap[id],
      use_friendly_format: friendlyMap[id] ?? false,
      horizons: horizonsMap[id] ?? { ...HORIZONS_ALL },
    })),
  };
  await fetch(`/api/trips/${tripId}/weather-config`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  savedSnapshot = JSON.stringify({ enabledMap, friendlyMap, horizonsMap });
}
```

**„Verwerfen"-Handler:**

```typescript
function resetToSnapshot() {
  const snap = JSON.parse(savedSnapshot);
  enabledMap = snap.enabledMap;
  friendlyMap = snap.friendlyMap;
  horizonsMap = snap.horizonsMap;
}
```

### §4 `TablePreview.svelte` — Drei Mini-Tabellen

**Neue Props:**

```typescript
interface Props {
  catalog: MetricCatalog;
  enabledMap: Record<string, boolean>;
  friendlyMap: Record<string, boolean>;
  horizonsMap: Record<string, Horizons>;   // NEU
}
```

**Aufbau:**

```svelte
<section data-slot="table-preview">
  <header>
    <Eyebrow>SCHRITT 3 VON 4 · NEUE TOUR · VORSCHAU</Eyebrow>
    <h2>Vorschau — so kommt das Briefing pro Tag an</h2>
    <p class="sub">
      Pro Tag erscheinen nur die Metriken, die du oben für diesen Horizont
      aktiviert hast. Sample-Stunden 09/12/15/18 für die Vorschau — im echten
      Briefing entscheidet das pro-Etappe-Profil.
    </p>
  </header>

  <div class="profile-strip">
    <Eyebrow>AKTIVITÄTSPROFIL</Eyebrow>
    <Pill>Alpen-Trekking (Sommer)</Pill>
    <span class="counter">
      {totalActive} METRIKEN · {horizonConfigCount} HORIZONT-KONFIGS
    </span>
  </div>

  <div class="grid-three">
    {#each (['today', 'tomorrow', 'day_after'] as const) as day}
      <table data-day={day}>
        <caption>
          <Eyebrow>{DAY_LABEL[day]} — {colCount(day)} METRIKEN</Eyebrow>
        </caption>
        <thead>
          <tr>
            <th>zeit</th>
            {#each visibleCols(day) as col}
              <th>
                <div class="col-name">{col.label}</div>
                <div class="col-unit">{col.unit}</div>
              </th>
            {/each}
          </tr>
        </thead>
        <tbody>
          {#each SAMPLE_ROWS as row}
            <tr>
              <td class="time">{row.time}</td>
              {#each visibleCols(day) as col}
                <td>{row.values[col.metric_id]}</td>
              {/each}
            </tr>
          {/each}
        </tbody>
      </table>
    {/each}
  </div>
</section>
```

**Layout — CSS Grid:**

```css
.grid-three {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: var(--g-s-6);
}
```

Bei < 1100 px Editor-Breite stapeln die drei Tabellen über `auto-fit` automatisch vertikal. Das ist die Pragmatik bis ein eigenes Mobile-Mockup folgt (siehe Out of Scope).

**Empty-State pro Tag-Tabelle:** Wenn `colCount(day) === 0`:

```svelte
<div class="empty-day">
  <Eyebrow>{DAY_LABEL[day]}</Eyebrow>
  <p>Keine Metriken für diesen Horizont aktiviert.</p>
</div>
```

**Helper:**

```typescript
const DAY_LABEL = {
  today: 'HEUTE',
  tomorrow: 'MORGEN',
  day_after: 'ÜBERMORGEN',
} as const;

function visibleCols(day: 'today' | 'tomorrow' | 'day_after'): MetricCol[] {
  return Object.keys(enabledMap)
    .filter(id => enabledMap[id])
    .filter(id => (horizonsMap[id] ?? HORIZONS_ALL)[day])
    .map(id => ({ metric_id: id, ...catalog.metricsById[id] }));
}

function colCount(day: 'today' | 'tomorrow' | 'day_after'): number {
  return visibleCols(day).length;
}
```

### §5 `SavePresetDialog.svelte` — ZEITHORIZONTE-Box

**Neue Props:**

```typescript
interface Props {
  // ... existing ...
  horizonsMap: Record<string, Horizons>;   // NEU
}
```

**Box „WIRD GESPEICHERT" zwischen Beschreibung und Default-Checkbox:**

```svelte
<Card padding={20}>
  <Eyebrow>WIRD GESPEICHERT</Eyebrow>

  <!-- Existing Statuszeile -->
  <div class="status">
    <strong>{activeCount}</strong> Metriken aktiv ·
    <strong>{rawCount}</strong> Rohwert ·
    <strong>{indicatorCount}</strong> Indikator
  </div>

  <hr />

  <!-- NEU: Horizon-Zusammenfassung -->
  <Eyebrow>ZEITHORIZONTE</Eyebrow>
  <div class="horizon-summary">{horizonSummary}</div>

  <!-- NEU: Metrik-Liste mit ●●●/●●○/●○○-Pattern -->
  <div class="metric-dot-grid">
    {#each activeMetrics as m}
      <div class="metric-dot-row">
        <span class="metric-name">{m.label}</span>
        <span class="dots">{dotsFor(horizonsMap[m.id])}</span>
      </div>
    {/each}
  </div>
</Card>
```

**Save-Payload-Erweiterung:**

```typescript
async function handleSubmit() {
  const body = {
    name,
    description,
    is_default: isDefault,
    metrics: Object.keys(enabledMap)
      .filter(id => enabledMap[id])
      .map(id => ({
        metric_id: id,
        enabled: true,
        use_friendly_format: friendlyMap[id] ?? false,
        horizons: horizonsMap[id] ?? { ...HORIZONS_ALL },
      })),
  };
  const res = await fetch('/api/metric-presets', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const preset = await res.json();
  onSaved(preset);
}
```

### §6 `computeHorizonSummary()` (NEU) — Wording-Heuristik

**Pfad:** `frontend/src/lib/utils/horizonHelpers.ts`

```typescript
import type { Horizons } from '$lib/types';

type HorizonSummaryInput = {
  metric_id: string;
  horizons: Horizons;
};

/**
 * Wording-Heuristik aus Issue #343 Context-Dok.
 * Gruppiert Metriken nach Horizont-Pattern und gibt
 * eine condensed Zusammenfassungs-Zeile zurück.
 *
 * Beispiel-Output:
 *   "5 alle drei Tage · 2 nur heute + morgen · 1 nur heute"
 *
 * Einträge mit n=0 werden weggelassen.
 */
export function computeHorizonSummary(metrics: HorizonSummaryInput[]): string {
  const buckets = {
    allThree: 0,           // (t, t, t)
    todayTomorrow: 0,      // (t, t, f)
    onlyToday: 0,          // (t, f, f)
    tomorrowDayAfter: 0,   // (f, t, t)
    other: 0,              // alles andere
  };

  for (const m of metrics) {
    const { today, tomorrow, day_after } = m.horizons;
    if (today && tomorrow && day_after) buckets.allThree++;
    else if (today && tomorrow && !day_after) buckets.todayTomorrow++;
    else if (today && !tomorrow && !day_after) buckets.onlyToday++;
    else if (!today && tomorrow && day_after) buckets.tomorrowDayAfter++;
    else buckets.other++;
  }

  const parts: string[] = [];
  if (buckets.allThree > 0)         parts.push(`${buckets.allThree} alle drei Tage`);
  if (buckets.todayTomorrow > 0)    parts.push(`${buckets.todayTomorrow} nur heute + morgen`);
  if (buckets.onlyToday > 0)        parts.push(`${buckets.onlyToday} nur heute`);
  if (buckets.tomorrowDayAfter > 0) parts.push(`${buckets.tomorrowDayAfter} nur morgen + übermorgen`);
  if (buckets.other > 0)            parts.push(`${buckets.other} sonstige Kombinationen`);
  return parts.join(' · ');
}

/**
 * Liefert die ●●●/●●○/●○○-Darstellung für eine Horizons-Konfig.
 * Reihenfolge: heute / morgen / übermorgen.
 */
export function dotsForHorizons(h: Horizons): string {
  return [h.today, h.tomorrow, h.day_after]
    .map(b => (b ? '●' : '○'))
    .join('');
}
```

### §7 LoC-Budget

| Block | Datei | Δ LoC |
|---|---|---|
| HorizonChip-Komponente | `HorizonChip.svelte` (NEU) | +80 |
| MetricCheckbox-Erweiterung | `MetricCheckbox.svelte` | +35 |
| WeatherMetricsTab State+Save | `WeatherMetricsTab.svelte` | +45 |
| TablePreview Drei-Tabellen | `TablePreview.svelte` | +120 |
| SavePresetDialog ZEITHORIZONTE | `SavePresetDialog.svelte` | +80 |
| TypeScript-Types | `types.ts` | +15 |
| Wording-Helper | `horizonHelpers.ts` (NEU) | +40 |
| Vitest Component-Tests | `HorizonChip.test.ts`, `horizonHelpers.test.ts` | +80 |
| Playwright-E2E | `issue-343-horizon-chips.spec.ts` (NEU) | +120 |
| **Gesamt netto** | | **~615 LoC** |

Über 250-LoC-Limit. Override vor Implementierung mit Begründung „5 Frontend-Komponenten + neue HorizonChip-Atom-Komponente + Wording-Helper + Component- und E2E-Tests in einer Iteration":

```bash
python3 .claude/hooks/workflow.py set-field loc_limit_override 700
```

## Expected Behavior

- **Input:** User öffnet Trip-Detail-Wetter-Tab eines Trips. Trip-JSON hat in `display_config.metrics[]` für `thunder` ein `horizons: {today:false, tomorrow:true, day_after:true}`.
- **Output:** Die HorizonChip-Reihe in der `thunder`-Zeile zeigt `HEUTE` als outline (inaktiv), `MORGEN` und `ÜBERMORGEN` als filled (aktiv). `TablePreview` zeigt drei Mini-Tabellen, in der `HEUTE`-Tabelle fehlt die `thunder`-Spalte, in `MORGEN` und `ÜBERMORGEN` ist sie sichtbar.

- **Input:** User klickt auf den `HEUTE`-Chip von `thunder`.
- **Output:** Chip wechselt auf filled (aktiv). „Ungespeicherte Änderungen"-Pill erscheint im Tab-Header. `TablePreview.HEUTE` zeigt jetzt die `thunder`-Spalte.

- **Input:** User klickt „Speichern". Nach erfolgreichem PUT lädt der User die Seite neu.
- **Output:** Die HorizonChip-States sind unverändert (`thunder` HEUTE = aktiv, MORGEN = aktiv, ÜBERMORGEN = aktiv). „Ungespeicherte Änderungen"-Pill ist nicht sichtbar.

- **Input:** User klickt „Als Preset speichern", gibt Namen `"Mein Skitouren-Set"` ein, sieht im Dialog die ZEITHORIZONTE-Zusammenfassung.
- **Output:** POST `/api/metric-presets` enthält `metrics[].horizons`. Preset erscheint danach in der Preset-Liste mit den gespeicherten Horizonten.

- **Side effects:**
  - `data/users/{user_id}/trips/{trip_id}.json` wird via Read-Modify-Write aktualisiert (nur `display_config.metrics[]` ändert sich)
  - `data/users/{user_id}/metric_presets.json` wird beim Preset-Save erweitert
  - Bei Mobile-Viewport < 600 px brechen die HorizonChips automatisch in Zeile 2 unter den Metrik-Namen

## Acceptance Criteria

- **AC-1:** Given der Trip-Detail-Wetter-Tab ist geöffnet und mindestens eine Metrik ist sichtbar / When der User einen `HorizonChip` (`data-slot="horizon-chip"` mit z.B. `data-day="today"`) klickt / Then togglet das `data-active`-Attribut des Chips (`"true"` ↔ `"false"`), `aria-pressed` reflektiert den neuen Stand, und im Tab-Header erscheint `data-testid="weather-metrics-dirty-pill"` mit Text „Ungespeicherte Änderungen"
  - Test: (populated after /4-tdd-red)

- **AC-2:** Given eine Metrik-Zeile, deren Checkbox auf `enabled=false` steht (Metrik deaktiviert) / When der User auf einen `HorizonChip` in dieser Zeile klickt / Then ist der Klick wirksam (Chip togglet, `horizonsMap[metric_id][day]` ändert sich, dirty-State wird true) — die Chips sind also AUCH bei deaktivierter Metrik bedienbar, nicht nur visuell sichtbar
  - Test: (populated after /4-tdd-red)

- **AC-3:** Given der User hat einen `HorizonChip` getoggelt und auf „Speichern" geklickt (Response 200) / When der User die Seite neu lädt (`location.reload()` oder erneuter `GET /api/trips/{id}`) / Then sind die `horizonsMap`-Werte unverändert (z.B. `thunder.horizons.today = false` bleibt `false`), kein dirty-Pill ist sichtbar, und der `savedSnapshot` enthält den gespeicherten Zustand
  - Test: (populated after /4-tdd-red)

- **AC-4:** Given der User klickt „Als Preset speichern" und sendet den Dialog mit Namen `"Mein Preset"` ab / When der POST `/api/metric-presets`-Request abgesendet wird / Then enthält der Request-Body `metrics[]` als Liste von Objekten mit `metric_id`, `enabled`, `use_friendly_format` und `horizons: {today, tomorrow, day_after}` — und der Response (das gespeicherte Preset) enthält die `horizons`-Felder byte-identisch zurück
  - Test: (populated after /4-tdd-red)

- **AC-5:** Given mindestens eine Metrik ist aktiv und ihre `horizonsMap` ist `{today:true, tomorrow:false, day_after:true}` / When `TablePreview` gerendert wird / Then sind im DOM drei separate `<table data-day="today|tomorrow|day_after">`-Elemente vorhanden; die `today`- und `day_after`-Tabelle enthält eine Spalte mit dieser Metrik, die `tomorrow`-Tabelle nicht; jede Tabelle hat einen `<caption>` mit Eyebrow im Format `HEUTE — N METRIKEN`
  - Test: (populated after /4-tdd-red)

- **AC-6:** Given der Viewport hat eine Breite < 600 px (Mobile) / When eine `MetricCheckbox` gerendert wird / Then steht der `HorizonChip`-Block in Zeile 2 unter dem Metrik-Namen (über `grid-template-areas` mit `"check name menu"` in Zeile 1 und `". chips menu"` in Zeile 2); die Chips sind eingerückt auf Namens-Höhe (Spalte `name`) — und die Roh/Indikator-Pills bleiben in Zeile 1 in der `pills`/`menu`-Spalte
  - Test: (populated after /4-tdd-red)

- **AC-7:** Given der Dialog `SavePresetDialog` ist geöffnet mit z.B. 5 Metriken `(t,t,t)`, 2 Metriken `(t,t,f)` und 1 Metrik `(t,f,f)` / When der Dialog gerendert wird / Then enthält der Dialog im DOM einen Block `data-slot="horizon-summary"` (oder vergleichbarem Testid) mit dem exakten Text `"5 alle drei Tage · 2 nur heute + morgen · 1 nur heute"` (Buckets mit n=0 sind weggelassen), und unterhalb folgt die Metrik-Liste mit `●●●` / `●●○` / `●○○`-Indikatoren in der Reihenfolge heute/morgen/übermorgen
  - Test: (populated after /4-tdd-red)

## Component Specs (Mockup-Mapping)

### `HorizonChip.svelte` (Mockup: `soll-flow1D-wizard-step3-wetter.png`)

| Aspekt | Wert |
|---|---|
| Pfad | `frontend/src/lib/components/ui/horizon-chip/HorizonChip.svelte` |
| Höhe | 32 px (`min-height: 32px`) |
| Touch-Target | ≥ 44 × 44 px (per Padding) |
| Form | Pill (`--g-r-pill`) |
| Inaktiv | Border `--g-ink-faint`, transparent BG, Text `--g-ink-faint` |
| Aktiv | BG `--g-ink`, Text `--g-paper`, Border `--g-ink` |
| Schrift | `--g-font-mono`, `--g-text-xs` (11 px), uppercase, `--g-track-caps` |
| Labels | `HEUTE` / `MORGEN` / `ÜBERMORGEN` (deutsch, COPY.md-konform) |
| `data-slot` | `"horizon-chip"` |
| `data-active` | `"true"` \| `"false"` |
| `data-day` | `"today"` \| `"tomorrow"` \| `"day_after"` |
| Aria | `aria-pressed={active}` |

### `MetricCheckbox.svelte` (Mockup: `soll-issue343-mobile-metric-row.png`)

| Aspekt | Wert |
|---|---|
| Desktop-Layout | Grid `auto 1fr auto auto` (check / name / pills / menu) |
| Mobile-Layout (< 600 px) | Zwei Zeilen: Zeile 1 `check / name / menu`, Zeile 2 `. / chips / menu` |
| Chip-Gap (Desktop) | `--g-s-2` (8 px) |
| Chip-Gap (Mobile, Zeile 2 Indent) | Indent = Checkbox-Spaltenbreite + `--g-s-3` |
| Roh/Indikator-Pills | Bleiben in Zeile 1 — kein Umbruch, kein Bottom-Sheet |
| Deaktivierte Metrik | `.metric-row[data-enabled="false"]` → `opacity: 0.6` für Name+Pills, aber Chips bleiben voll funktional (AC-2) |

### `WeatherMetricsTab.svelte` (Mockup: bestehender Tab + neue Chip-Reihe)

| Aspekt | Wert |
|---|---|
| Neuer State | `horizonsMap: Record<string, Horizons>` |
| `initMaps()` | Liest `display_config.metrics[].horizons`, defaultet `HORIZONS_ALL` |
| `isDirty` | `JSON.stringify({enabledMap, friendlyMap, horizonsMap}) !== savedSnapshot` |
| `handleSave()` | PUT-Payload enthält `horizons` pro Metrik |
| `resetToSnapshot()` | Stellt `horizonsMap` aus Snapshot wieder her |
| Neuer Prop für `MetricCheckbox` | `horizons={horizonsMap[id]} onHorizonChange={(day) => onHorizonChange(id, day)}` |
| Neuer Prop für `TablePreview` | `horizonsMap={horizonsMap}` |
| Neuer Prop für `SavePresetDialog` | `horizonsMap={horizonsMap}` |

### `TablePreview.svelte` (Mockup: `soll-issue343-table-preview.png`)

| Aspekt | Wert |
|---|---|
| Sektion-Header | Eyebrow `SCHRITT 3 VON 4 · NEUE TOUR · VORSCHAU` + H2 „Vorschau — so kommt das Briefing pro Tag an" + Sub-Text |
| Profil-Strip | Eyebrow `AKTIVITÄTSPROFIL` + Pill `Alpen-Trekking (Sommer)` + Counter `{totalActive} METRIKEN · {horizonConfigCount} HORIZONT-KONFIGS` |
| Layout | CSS-Grid `grid-template-columns: repeat(auto-fit, minmax(280px, 1fr))` mit Gap `--g-s-6` |
| Tabellen-Caption | `<caption>` mit `<Eyebrow>` im Format `HEUTE — N METRIKEN` (deutsch) |
| Spalten-Header | `zeit` + pro Metrik `{label}` + `{unit}` (zwei-Zeilen-Stack) |
| Sample-Zeilen | 4 Zeilen `09:00 / 12:00 / 15:00 / 18:00`, hardcodiert (analog zu existierendem `SAMPLE_ROWS`) |
| Spalten-Filter | `enabledMap[id] && horizonsMap[id][day]` |
| Empty-State pro Tag | Bei `colCount(day) === 0`: Eyebrow + Text „Keine Metriken für diesen Horizont aktiviert." |
| Responsive | < 1100 px Editor-Breite → Tabellen stapeln vertikal über `auto-fit` (Pragmatik) |

### `SavePresetDialog.svelte` (Mockup: `soll-issue343-save-preset-dialog.png`)

| Aspekt | Wert |
|---|---|
| Header | Eyebrow `EIGENES PRESET` + H2 „Auswahl als Preset speichern" + Close-X |
| Name-Input | Required, max 40 Zeichen (existing) |
| Beschreibung-Textarea | Optional, max 120 Zeichen (existing) |
| Box „WIRD GESPEICHERT" | Card zwischen Beschreibung und Default-Checkbox |
| Statuszeile (Zeile 1 der Box) | `{n} Metriken aktiv · {n} Rohwert · {n} Indikator` (existing) |
| Hairline | `<hr />` zwischen Statuszeile und ZEITHORIZONTE-Block |
| ZEITHORIZONTE-Eyebrow | `<Eyebrow>ZEITHORIZONTE</Eyebrow>` |
| Wording-Zeile | `computeHorizonSummary(activeMetrics)` — z.B. `5 alle drei Tage · 2 nur heute + morgen · 1 nur heute` |
| Metrik-Dot-Liste | Zwei-Spalten-Grid, pro Metrik: `{label}    {●●●/●●○/●○○}`. Reihenfolge der Dots: heute / morgen / übermorgen. Helper: `dotsForHorizons(h)` |
| Default-Checkbox | „Als Standard für neue Trips verwenden" (existing) |
| Footer | „Abbrechen" + „Preset speichern" (Primary, existing) |
| Save-Payload | POST `/api/metric-presets` mit `metrics[].horizons` |
| `data-testid` | `save-preset-horizon-summary` auf der Wording-Zeile (für AC-7) |

## Wording-Heuristik für SavePresetDialog

Aus Context-Dok übernommen und algorithmisch in `computeHorizonSummary()` umgesetzt:

| Pattern (today, tomorrow, day_after) | Bucket-Label |
|---|---|
| `(true, true, true)` | `{n} alle drei Tage` |
| `(true, true, false)` | `{n} nur heute + morgen` |
| `(true, false, false)` | `{n} nur heute` |
| `(false, true, true)` | `{n} nur morgen + übermorgen` |
| **alles andere** | `{n} sonstige Kombinationen` |

Reihenfolge der Buckets in der Zusammenfassungs-Zeile: alle-drei → heute+morgen → nur-heute → morgen+übermorgen → sonstige. Buckets mit `n=0` werden **weggelassen**. Trenner zwischen Buckets: ` · ` (Mittelpunkt mit Leerzeichen, COPY.md §8).

**Beispiel-Outputs:**

- 5 Metriken alle drei Tage, 2 nur heute+morgen, 1 nur heute → `5 alle drei Tage · 2 nur heute + morgen · 1 nur heute`
- 8 Metriken alle drei Tage → `8 alle drei Tage`
- 3 Metriken alle drei Tage, 1 nur morgen+übermorgen, 1 mit Pattern `(false, true, false)` → `3 alle drei Tage · 1 nur morgen + übermorgen · 1 sonstige Kombinationen`

## Affected Files

| Pfad | Änderung | Schicht |
|------|----------|---------|
| `frontend/src/lib/components/ui/horizon-chip/HorizonChip.svelte` | **NEU** — Brand-Atom mit `[data-slot]`-Pattern | Frontend |
| `frontend/src/lib/components/trip-detail/MetricCheckbox.svelte` | Drei `HorizonChip` einfügen + Mobile-Grid-Layout (< 600 px) | Frontend |
| `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte` | `horizonsMap`-State + initMaps-Erweiterung + Save-Payload + Snapshot | Frontend |
| `frontend/src/lib/components/trip-detail/TablePreview.svelte` | Umbau auf drei Mini-Tabellen + Grid-Layout + Empty-State | Frontend |
| `frontend/src/lib/components/trip-detail/SavePresetDialog.svelte` | „WIRD GESPEICHERT"-Box mit ZEITHORIZONTE-Zusammenfassung + Dot-Grid | Frontend |
| `frontend/src/lib/types.ts` | `Horizons`-Type + `HORIZONS_ALL`-Const + `WeatherConfigMetric.horizons?` + `MetricPreset.metrics[]`-Schema | Frontend |
| `frontend/src/lib/utils/horizonHelpers.ts` | **NEU** — `computeHorizonSummary()` + `dotsForHorizons()` | Frontend |
| `frontend/src/lib/components/ui/horizon-chip/HorizonChip.test.ts` | **NEU** — Component-Tests (Vitest + @testing-library/svelte) | Frontend-Tests |
| `frontend/src/lib/utils/horizonHelpers.test.ts` | **NEU** — Wording-Heuristik-Tests | Frontend-Tests |
| `frontend/e2e/issue-343-horizon-chips.spec.ts` | **NEU** — Playwright-E2E (Toggle-Roundtrip, Mobile-Viewport, SavePresetDialog) | Frontend-E2E |

## Tests

Alle Tests laufen **ohne Mocks** (CLAUDE.md-Pflicht: „KEINE MOCKED TESTS!"). Component-Tests rendern echte Svelte-Komponenten, E2E-Tests laufen gegen ein echtes Test-Backend mit `GZ_TEST_FIXTURE_DIR`.

### Vitest Component-Tests (`HorizonChip.test.ts`)

- **`test_horizon_chip_renders_inactive_state`**: Render mit `active={false}`, prüft `data-active="false"`, `aria-pressed="false"`, Text `HEUTE` für `day="today"`.
- **`test_horizon_chip_renders_active_state`**: Render mit `active={true}`, prüft `data-active="true"`, `aria-pressed="true"`.
- **`test_horizon_chip_click_invokes_callback`**: Render mit `onclick`-Spy, klickt, prüft dass Spy einmal aufgerufen wurde.
- **`test_horizon_chip_disabled_state`**: Render mit `disabled={true}`, prüft dass Button `disabled` ist und Klick nicht durchgeht.
- **`test_horizon_chip_labels_per_day`**: Drei Render-Durchläufe für `today`/`tomorrow`/`day_after`, prüft Text `HEUTE`/`MORGEN`/`ÜBERMORGEN`.

### Vitest Helper-Tests (`horizonHelpers.test.ts`)

- **`test_compute_summary_all_three`**: Eine Metrik `(t,t,t)` → `"1 alle drei Tage"`.
- **`test_compute_summary_mixed_buckets`** (AC-7-Vorlauf): 5×`(t,t,t)`, 2×`(t,t,f)`, 1×`(t,f,f)` → `"5 alle drei Tage · 2 nur heute + morgen · 1 nur heute"`.
- **`test_compute_summary_zero_buckets_omitted`**: 3×`(t,t,t)` → nur `"3 alle drei Tage"`, keine leeren Buckets.
- **`test_compute_summary_other_pattern`**: 1×`(f,t,f)` → `"1 sonstige Kombinationen"`.
- **`test_compute_summary_empty_list`**: `[]` → `""`.
- **`test_dots_for_horizons`**: `(t,t,t)` → `"●●●"`, `(t,t,f)` → `"●●○"`, `(t,f,f)` → `"●○○"`, `(f,f,f)` → `"○○○"`.

### Playwright-E2E (`frontend/e2e/issue-343-horizon-chips.spec.ts`)

Setup: `GZ_TEST_FIXTURE_DIR=...` env aktiviert FixtureProvider (siehe `issue_263_openmeteo_fixture_provider`). Test-Trip mit drei Etappen (heute/morgen/übermorgen) wird gesichert. Login via Test-Account.

- **`test_horizon_toggle_save_reload_roundtrip`** (AC-1, AC-3): Öffne Trip-Detail, navigiere zu Wetter-Tab. Klicke HorizonChip `today` von `thunder` (initial aktiv). Prüfe dirty-Pill erscheint. Klicke „Speichern". Reload Seite. Prüfe Chip ist immer noch inaktiv, dirty-Pill ist weg. Prüfe `TablePreview.HEUTE` enthält keine `thunder`-Spalte.
- **`test_horizon_chip_clickable_when_metric_disabled`** (AC-2): Deaktiviere Metrik via Checkbox. Klicke HorizonChip in derselben Zeile. Prüfe dass Chip togglet und dirty-Pill erscheint.
- **`test_table_preview_three_separate_tables`** (AC-5): Setze `thunder.horizons` auf `{t,f,t}`. Prüfe DOM enthält `<table data-day="today">`, `<table data-day="tomorrow">`, `<table data-day="day_after">`. Prüfe `today`-Tabelle hat `thunder`-Spalte, `tomorrow` nicht, `day_after` ja.
- **`test_mobile_chip_wraps_to_second_row`** (AC-6): `page.setViewportSize({width: 400, height: 800})`. Render Metric-Row. Prüfe via `getBoundingClientRect()`, dass die HorizonChips eine Y-Position haben, die größer ist als die Y-Position des Metrik-Namens (also in Zeile 2 stehen).
- **`test_save_preset_dialog_horizon_summary`** (AC-4, AC-7): Konfiguriere 5 Metriken mit `(t,t,t)`, 2 mit `(t,t,f)`, 1 mit `(t,f,f)`. Klicke „Als Preset speichern". Prüfe Dialog enthält `data-testid="save-preset-horizon-summary"` mit Text `"5 alle drei Tage · 2 nur heute + morgen · 1 nur heute"`. Sende Dialog ab. Intercept POST-Request, prüfe Body enthält `metrics[].horizons` pro Eintrag. Prüfe Response 201 und Preset taucht in der Preset-Liste auf.

## Risks

1. **Doppelte Pflege während #345 noch offen ist:** Der alte Pfad `EditWeatherSection.svelte` existiert parallel und wird in **#345** konsolidiert. Diese Spec berührt `EditWeatherSection` NICHT — User, die noch über den alten Pfad gehen, sehen keine HorizonChips. Mitigation: #345 als Folge-Issue dokumentiert, kein paralleler Fix.

2. **Backend-API-Kompatibilität bei alten Trips:** PUT `/api/trips/{id}/weather-config` muss alte Payloads (ohne `horizons`) und neue Payloads (mit `horizons`) gleichermaßen akzeptieren. Backend hat den Compat-Layer aus #342 — wenn jedoch ein Frontend-Roll-out vor dem Backend-Deploy passiert, sendet das Frontend `horizons` und ein altes Backend würde es ignorieren oder ablehnen. Mitigation: Backend ist seit Commit X live; Frontend-Deploy hängt deterministisch davon ab. Pre-Deploy-Check: `curl https://staging.gregor20.henemm.com/api/health` und Schema-Probe.

3. **`TablePreview`-Mockup zeigt nur Desktop ≥ 1100 px:** Unterhalb dieser Breite (z.B. Tablet 800 px Editor-Breite) gibt es kein finales Mockup. Pragmatik in dieser Iteration: CSS-Grid `auto-fit minmax(280px, 1fr)` stapelt automatisch vertikal. Mitigation: explizit in Out of Scope dokumentiert; eigenes Mobile-Tabletten-Mockup folgt in Folge-Iteration.

4. **Wording-Heuristik kann bei „exotischen" Kombinationen unübersichtlich werden:** Wenn ein User 5 verschiedene Horizont-Pattern kombiniert, sieht er nur `"5 sonstige Kombinationen"`. Mitigation: das ist beabsichtigte Pragmatik (sonst würde die Zeile unleserlich lang) — die `●●●`/`●●○`/`●○○`-Liste darunter zeigt die exakten Werte. Wenn das im User-Feedback als Problem auftaucht: Folge-Issue für detailliertere Bucket-Liste.

5. **Touch-Target auf Mobile bei drei Chips dicht beieinander:** `min-width: 44px` + `min-height: 32px` mit Padding ergibt nominal 44×44, aber der Abstand zwischen den Chips (Gap `--g-s-2` = 8 px) ist im Worst-Case knapp. Mitigation: Playwright-Test misst tatsächliche `boundingClientRect`-Werte; bei Regression Gap auf `--g-s-3` (12 px) erhöhen.

6. **LoC-Limit 250 wird überschritten (~615 LoC):** Override `loc_limit_override 700` mit dokumentierter Begründung „5 Frontend-Komponenten + neue HorizonChip-Atom-Komponente + Wording-Helper + Component- und E2E-Tests in einer Iteration" vor Phase 6.

## Out of Scope

- **Backend-Änderungen** — Schema, PATCH-Endpoint, Renderer-Filter sind aus **#342** fertig und live deployed
- **Account-Karte zur Preset-Verwaltung** (Umbenennen, Löschen, Default-Setzen aus UI) → **#344**
- **Konsolidierung `EditWeatherSection` ↔ `WeatherMetricsTab`** → **#345**
- **Wizard-Step-3-Wetter-Integration**: Das Mockup `soll-flow1D-wizard-step3-wetter.png` zeigt das Layout im Wizard-Kontext, aber diese Spec adressiert ausschließlich den Trip-Detail-Wetter-Tab. Wizard-Integration folgt in separatem Sub-Issue, sobald der Trip-Detail-Pfad stabil läuft.
- **Mobile-/Tablet-Layout der `TablePreview` < 1100 px**: CSS-Grid `auto-fit minmax(280px, 1fr)` wird als Pragmatik implementiert; eigenes Mockup folgt in eigener Iteration.
- **SMS-Renderer-Integration der Horizonte**: SMS nutzt `display_config.metrics` heute nicht direkt — wäre separate Aufgabe.
- **Visual-Indikator für Horizont-Status im `WeatherMetricsTab`-Header** (z.B. „2 Metriken haben nicht alle Tage aktiv"): nicht im Issue gefordert.
- **Drag-and-Drop für Spalten-Reihenfolge in `TablePreview`**: nicht gefordert.

## Known Limitations

- **`MetricPreset`-Type-Migration im Frontend:** Backend hat das Schema von `{metrics: string[], friendly_ids: string[]}` auf `{metrics: DisplayMetric[]}` umgestellt (#342). Das Frontend hatte vorher `MetricPreset.metrics: string[]` — diese Spec stellt den Type um. Wenn andere Stellen im Frontend `MetricPreset.metrics` als Array von Strings lesen, müssen diese Stellen mit-angepasst werden. Eine Suche `MetricPreset.metrics` in Phase 6 ist Pflicht.
- **Empty-State pro Tag-Tabelle**: Wenn ein User für einen Tag 0 Metriken aktiviert, zeigt die `TablePreview` einen dezenten Hinweis-Text. Das könnte irritieren, wenn der User die Vorschau sucht, aber alles deaktiviert hat — das ist beabsichtigtes Verhalten (kein Spalten-Header ohne Daten).
- **Keine Bulk-Toggle-Aktion** (z.B. „Alle Metriken auf nur heute"): nicht im Scope. Wäre ein Folge-Feature, falls User-Feedback es verlangt.
- **`computeHorizonSummary()` ist nicht i18n-fähig**: Strings sind hart deutsch. Bei zukünftiger Übersetzung in andere Sprachen muss der Helper auf eine i18n-Lib umgestellt werden.

## Changelog

- 2026-05-23: Initial spec erstellt. Sub-Issue 2 von Klammer-Epic #304 (Predecessor: #342). Frontend-Erweiterung des `WeatherMetricsTab.svelte` mit neuer `HorizonChip`-Atom-Komponente, Mobile-Chip-Umbruch in `MetricCheckbox`, Umbau von `TablePreview` auf drei Mini-Tabellen, ZEITHORIZONTE-Box in `SavePresetDialog`, Wording-Helper `computeHorizonSummary()`. ~615 LoC netto, 10 Dateien (7 Komponenten/Helper + 3 Test-Dateien). 7 Acceptance Criteria im AC-N-Format. Out-of-Scope: Backend (#342 fertig), Account-Karte (#344), EditWeatherSection-Konsolidierung (#345), Wizard-Integration (Folge-Sub-Issue).
